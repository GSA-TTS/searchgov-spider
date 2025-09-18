import pytest
from apscheduler.events import JobExecutionEvent, JobSubmissionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.job import Job
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
