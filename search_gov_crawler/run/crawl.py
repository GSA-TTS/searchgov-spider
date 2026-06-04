import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def run_scrapy_crawl(spider: str, **kwargs) -> None:
    """
    Runs `scrapy crawl` command as a subprocess given the provided arguments. All kwargs
    will be passed in the form of `-a key=value` to the scrapy crawl command.
    """

    args = [sys.executable, "-m", "scrapy", "crawl", spider]
    for kwarg_name, kwarg_value in kwargs.items():
        args.append("-a")
        if isinstance(kwarg_value, list):
            args.append(f"{kwarg_name}={','.join(kwarg_value)}")
        else:
            args.append(f"{kwarg_name}={kwarg_value}")

    scrapy_env = os.environ.copy()
    scrapy_env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent)

    subprocess.run(args, check=True, cwd=Path(__file__).parent, env=scrapy_env)  # noqa: S603
    msg = "Successfully completed scrapy crawl with args spider=%s and kwargs %s"
    log.info(msg, spider, kwargs)
