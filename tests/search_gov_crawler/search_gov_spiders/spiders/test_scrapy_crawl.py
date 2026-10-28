import os
import subprocess
import sys
from pathlib import Path

import pytest

ERROR_LOGGING_TEST_CASES = [
    ("domain_spider", ["-a", "allowed_domains=example.gov"], "missing 2 required keyword-only arguments"),
]


@pytest.mark.parametrize(("spider_name", "spider_args", "error_msg"), ERROR_LOGGING_TEST_CASES)
def test_scrapy_crawl_error_logging(spider_name, spider_args, error_msg):
    args = [sys.executable, "-m", "scrapy", "crawl", spider_name, *spider_args]
    scrapy_env = os.environ.copy()
    project_root = Path(__file__).parent.parent.parent.parent.parent
    scrapy_env["PYTHONPATH"] = str(project_root)

    result = subprocess.run(  # noqa: S603
        args, check=False, cwd=Path(project_root, "search_gov_crawler"), env=scrapy_env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert error_msg in result.stderr
