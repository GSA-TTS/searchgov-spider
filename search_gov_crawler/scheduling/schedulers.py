import logging
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from apscheduler.events import JobExecutionEvent, JobSubmissionEvent
from apscheduler.jobstores.base import ConflictingIdError, JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler

from search_gov_crawler.scheduling.jobstores import SpiderRedisJobStore

log = logging.getLogger(__name__)


class SpiderBackgroundScheduler(BackgroundScheduler):
    """Extends the BackgroundScheduler to add methods for managing pending jobs."""

    supported_jobstore_classes: ClassVar[tuple] = (SpiderRedisJobStore,)

    def _get_pending_jobstore(self, alias: str | None = "redis") -> SpiderRedisJobStore:
        """
        Get the pending job store by alias. If no alias is provided, defaults to "redis".  Raises a value
        error if the jobstore is not supported.
        """

        pending_jobstore = self._jobstores[alias]

        if not any(pending_jobstore.__class__ is cls for cls in self.supported_jobstore_classes):
            msg = f"Unsupported jobstore: {type(pending_jobstore)}, please use one of {self.supported_jobstore_classes}"
            raise ValueError(msg)

        return pending_jobstore

    def add_pending_job(self, event: JobSubmissionEvent) -> None:
        """Add a job to the pending jobs list when sent to the executor. Assume we mean redis."""

        jobstore = self._get_pending_jobstore()
        if jobstore:
            jobstore.add_pending_job(event.job_id)

        log.info("Jobs in pending queue: %s", jobstore.count_pending_jobs())

    def remove_pending_job(self, event: JobExecutionEvent) -> None:
        """Remove a job from the pending jobs list in the case of success or error. Assume we mean redis."""

        jobstore = self._get_pending_jobstore()
        if jobstore:
            jobstore.remove_pending_job(event.job_id)

        log.info("Jobs in pending queue: %s", jobstore.count_pending_jobs())

    def remove_pending_job_by_id(self, job_id: str) -> None:
        """Remove a job from the pending jobs list by job_id. Assume we mean redis."""

        jobstore = self._get_pending_jobstore()
        if jobstore:
            jobstore.remove_pending_job(job_id)

        log.info("Jobs in pending queue: %s", jobstore.count_pending_jobs())

    def remove_all_pending_jobs(self) -> None:
        """Remove all pending jobs from the job store.  Assume we mean redis."""

        jobstore = self._get_pending_jobstore()
        if jobstore:
            jobstore.remove_all_pending_jobs()

        log.info("Jobs in pending queue: %s", jobstore.count_pending_jobs())

    def remove_all_jobs(self, jobstore: str | None = None, include_pending_jobs: bool = True) -> None:
        """Remove all jobs from the job store with an option to include pending jobs."""

        if include_pending_jobs:
            self.remove_all_pending_jobs()
        return super().remove_all_jobs(jobstore)

    def trigger_pending_jobs(self, offset_seconds: int = 5) -> None:
        """
        Get all pending jobs, add them as immediate jobs to the scheduler, and remove them from the pending
        job store.
        """

        jobstore = self._get_pending_jobstore()
        if jobstore:
            jobs = jobstore.get_all_pending_jobs()

            for job in jobs:
                self.modify_job(job.id, next_run_time=datetime.now(tz=UTC) + timedelta(seconds=offset_seconds))
                self.remove_pending_job_by_id(job.id)

    def add_jobs(self, jobs: list[dict], jobstore: str, *, update_existing: bool = False) -> None:
        """
        Add multiple jobs to the scheduler. If job already exists, update and reschedule.
        Log any other errors encountered.
        """

        for job in jobs:
            try:
                self.add_job(**job, jobstore=jobstore)
            except ConflictingIdError:
                if update_existing:
                    job_id = job.pop("id")
                    self.modify_job(job_id=job_id, **job)
                    job_trigger = job.pop("trigger")
                    self.reschedule_job(job_id, trigger=job_trigger)
                else:
                    log.exception("Error adding job %s", job.get("id"))
                    raise
            except Exception:
                log.exception("Error adding job %s", job.get("id"))
                raise

    def remove_jobs(self, jobs_ids: list[str], jobstore: str) -> None:
        """Remove multiple jobs from the scheduler."""

        for job_id in jobs_ids:
            try:
                self.remove_job(job_id, jobstore=jobstore)
            except JobLookupError:
                log.exception("Job %s not found in scheduler, cannot remove", job_id)
                raise
