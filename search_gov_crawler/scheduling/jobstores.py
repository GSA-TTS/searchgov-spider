import logging
from datetime import UTC, datetime

from apscheduler.jobstores.redis import RedisJobStore

log = logging.getLogger(__name__)


class SpiderRedisJobStore(RedisJobStore):
    """An extension to the APScheduler RedisJobStore that adds functionality to manage pending jobs."""

    def __init__(self, pending_jobs_key: str, *args, **kwargs):
        self.pending_jobs_key = pending_jobs_key
        super().__init__(*args, **kwargs)

    @property
    def alias(self) -> str:
        """Return the alias of the job store."""

        if self._alias is None:
            msg = "Job store alias is not set. Please set the alias before using it."
            raise ValueError(msg)

        return self._alias

    def count_pending_jobs(self) -> int:
        """Count the number of pending jobs in the job store"""

        count = self.redis.zcard(self.pending_jobs_key)
        log.debug("Counted %s pending jobs in key %s", count, self.pending_jobs_key)
        return count

    def add_pending_job(self, job_id) -> None:
        """Add a job to the pending jobs set"""

        self.redis.zadd(
            self.pending_jobs_key,
            {job_id: datetime.now(tz=UTC).timestamp()},
        )
        log.debug("Added %s to pending jobs key %s", job_id, self.pending_jobs_key)

    def get_all_pending_jobs(self) -> list:
        """Get all pending jobs with their states from the jobstore"""

        pending_job_ids = [job_id.decode("utf8") for job_id in self.redis.zrange(self.pending_jobs_key, 0, -1)]
        pending_jobs = []
        for pending_job_id in pending_job_ids:
            job = self.lookup_job(job_id=pending_job_id)
            if not job:
                log.warning("Job %s not found in job store", pending_job_id)
                continue
            pending_jobs.append(job)

        log.debug("Found and retrieved %s pending jobs from key %s", len(pending_jobs), self.pending_jobs_key)
        return pending_jobs

    def remove_pending_job(self, job_id) -> None:
        """Remove a job from the pending jobs set"""

        self.redis.zrem(self.pending_jobs_key, job_id)
        log.debug("Removed %s from pending jobs key %s", job_id, self.pending_jobs_key)

    def remove_all_pending_jobs(self) -> None:
        """Remove all pending jobs from the pending jobs set"""

        self.redis.delete(self.pending_jobs_key)
        log.debug("Removed all pending jobs from key %s", self.pending_jobs_key)
