import pytest

from search_gov_crawler.scheduling.jobstores import SpiderRedisJobStore


class MockRedisClient:
    @staticmethod
    def zadd(*_args, **_kwargs):
        return True

    @staticmethod
    def zrem(*_args, **_kwargs):
        return True

    @staticmethod
    def delete(*_args, **_kwargs):
        return True

    @staticmethod
    def zrange(*_args, jobs_to_output, **_kwargs): ...

    @staticmethod
    def lookup_job(*_args, **_kwargs):
        return True

    @staticmethod
    def zcard(*_args, **_kwargs):
        return 0

    @staticmethod
    def scan_iter(*_args, **_kwargs):
        return ["test-key"]

    @staticmethod
    def object(*_args, **_kwargs):
        return True

    @staticmethod
    def ping():
        return True

    @staticmethod
    def llen(*_args, **_kwargs):
        return 0


@pytest.fixture(name="mock_redis_jobstore")
def fixture_mock_redis_jobstore() -> SpiderRedisJobStore:
    jobstore = SpiderRedisJobStore(pending_jobs_key="test_pending_jobs")
    jobstore._alias = "redis"
    jobstore.redis = MockRedisClient()
    return jobstore
