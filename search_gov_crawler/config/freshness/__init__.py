import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

FRESHNESS_CHECKER_CONFIG_FILE = Path(__file__).parent / os.environ.get(
    "SPIDER_FRESHNESS_CHECKER_CONFIG_FILE_NAME", "freshness-checker-production.json"
)
