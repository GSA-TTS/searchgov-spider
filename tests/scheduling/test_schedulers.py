import re

import pytest
from apscheduler.events import JobExecutionEvent, JobSubmissionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.job import Job
from apscheduler.jobstores.base import ConflictingIdError, JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore

from search_gov_crawler.scheduling.schedulers import SpiderBackgroundScheduler


@pytest.fixture(name="spider_scheduler")
def fixture_spider_scheduler(mock_redis_jobstore) -> SpiderBackgroundScheduler:
    return SpiderBackgroundScheduler(
        jobstores={"redis": mock_redis_jobstore},
        executors={"default": ThreadPoolExecutor()},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": None},
        timezone="UTC",
    )


def test_spider_scheduler(spider_scheduler):
    assert isinstance(spider_scheduler, SpiderBackgroundScheduler)


def test_spider_scheduler_unsupported_jobstore():
    scheduler = SpiderBackgroundScheduler(jobstores={"redis": MemoryJobStore()})
    with pytest.raises(ValueError, match="Unsupported jobstore"):
        scheduler._get_pending_jobstore()


@pytest.fixture(name="job_submission_event")
def fixture_job_submission_event() -> JobSubmissionEvent:
    return JobSubmissionEvent(job_id="test_job_id", code=1, jobstore="redis", scheduled_run_times=None)


@pytest.fixture(name="job_execution_event")
def fixture_job_execution_event() -> JobExecutionEvent:
    return JobExecutionEvent(job_id="test_job_id", code=1, jobstore="redis", scheduled_run_time=None)


def test_add_pending_job(caplog, spider_scheduler, job_submission_event):
    with caplog.at_level("DEBUG"):
        spider_scheduler.add_pending_job(job_submission_event)

    log_messages = ("Added test_job_id to pending jobs key test_pending_jobs", "Jobs in pending queue: 0")
    assert all(log_message in caplog.messages for log_message in log_messages)


def test_remove_pending_job(caplog, spider_scheduler, job_execution_event):
    with caplog.at_level("DEBUG"):
        spider_scheduler.remove_pending_job(job_execution_event)

    log_messages = ("Removed test_job_id from pending jobs key test_pending_jobs", "Jobs in pending queue: 0")
    assert all(log_message in caplog.messages for log_message in log_messages)


def test_remove_pending_job_by_id(caplog, spider_scheduler):
    with caplog.at_level("DEBUG"):
        spider_scheduler.remove_pending_job_by_id("test_job_id")

    log_messages = ("Removed test_job_id from pending jobs key test_pending_jobs", "Jobs in pending queue: 0")
    assert all(log_message in caplog.messages for log_message in log_messages)


def test_remove_all_pending_jobs(caplog, spider_scheduler):
    with caplog.at_level("DEBUG"):
        spider_scheduler.remove_all_pending_jobs()

    log_messages = ("Removed all pending jobs from key test_pending_jobs", "Jobs in pending queue: 0")
    assert all(log_message in caplog.messages for log_message in log_messages)


@pytest.mark.parametrize("include_pending_jobs", [True, False])
def test_remove_all_jobs(caplog, spider_scheduler, include_pending_jobs):
    with caplog.at_level("DEBUG"):
        spider_scheduler.remove_all_jobs(include_pending_jobs=include_pending_jobs)

    message = "Removed all pending jobs from key test_pending_jobs"
    if include_pending_jobs:
        assert message in caplog.messages
    else:
        assert message not in caplog.messages


def test_trigger_pending_jobs(caplog, monkeypatch, spider_scheduler, mock_redis_jobstore) -> None:
    def mock_lookup_job(*_args, **_kwargs):
        return Job(
            scheduler=spider_scheduler,
            id="job1",
            name="test",
            func=print,
            args=[],
            kwargs={},
        )

    monkeypatch.setattr(spider_scheduler, "modify_job", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(mock_redis_jobstore, "lookup_job", mock_lookup_job)
    monkeypatch.setattr(mock_redis_jobstore.redis, "zrange", lambda *_args, **_kwargs: [b"test::job1", b"test::job2"])

    with caplog.at_level("DEBUG"):
        spider_scheduler.trigger_pending_jobs()

    assert "Found and retrieved 2 pending jobs from key test_pending_jobs" in caplog.messages


@pytest.fixture(name="test_jobs")
def fixture_test_jobs() -> list[dict]:
    return [
        {"func": print, "id": "job1", "name": "Job 1", "args": [], "kwargs": {}, "trigger": "test"},
        {"func": print, "id": "job2", "name": "Job 2", "args": [], "kwargs": {}, "trigger": "test"},
    ]


def test_add_jobs(mocker, spider_scheduler, test_jobs):
    mock_add_job = mocker.patch.object(spider_scheduler, "add_job")

    spider_scheduler.add_jobs(jobs=test_jobs, jobstore="redis")
    assert mock_add_job.call_count == len(test_jobs)


def test_add_jobs_conflicting_ids(mocker, spider_scheduler, test_jobs):
    mock_add_job = mocker.patch.object(spider_scheduler, "add_job")
    mock_add_job.side_effect = ConflictingIdError("job1")

    with pytest.raises(ConflictingIdError, match=re.escape("Job identifier (job1) conflicts with an existing job")):
        spider_scheduler.add_jobs(jobs=test_jobs, jobstore="redis")


def test_add_jobs_conflicting_ids_update_existing(mocker, spider_scheduler, test_jobs):
    mock_add_job = mocker.patch.object(spider_scheduler, "add_job")
    mock_add_job.side_effect = ConflictingIdError("job1")
    mock_modify_job = mocker.patch.object(spider_scheduler, "modify_job")
    mock_reschedule_job = mocker.patch.object(spider_scheduler, "reschedule_job")

    spider_scheduler.add_jobs(jobs=test_jobs, jobstore="redis", update_existing=True)
    assert mock_add_job.call_count == len(test_jobs)
    assert mock_modify_job.call_count == len(test_jobs)
    assert mock_reschedule_job.call_count == len(test_jobs)


def test_add_jobs_other_exception(mocker, spider_scheduler, test_jobs):
    mock_add_job = mocker.patch.object(spider_scheduler, "add_job")
    mock_add_job.side_effect = Exception("Some other error")

    with pytest.raises(Exception, match="Some other error"):
        spider_scheduler.add_jobs(jobs=test_jobs, jobstore="redis")


def test_remove_jobs(mocker, spider_scheduler, test_jobs):
    mock_remove_jobs = mocker.patch.object(spider_scheduler, "remove_job")

    spider_scheduler.remove_jobs(jobs_ids=[job["id"] for job in test_jobs], jobstore="redis")
    assert mock_remove_jobs.call_count == len(test_jobs)


def test_remove_jobs_job_lookup_error(mocker, spider_scheduler, test_jobs):
    mock_remove_jobs = mocker.patch.object(spider_scheduler, "remove_job")
    mock_remove_jobs.side_effect = JobLookupError("job1")

    with pytest.raises(JobLookupError, match="job1"):
        spider_scheduler.remove_jobs(jobs_ids=[job["id"] for job in test_jobs], jobstore="redis")
