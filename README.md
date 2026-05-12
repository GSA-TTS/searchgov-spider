# searchgov-spider

Crawler and supporting runtime processes for [Search.gov](https://www.search.gov). This repository contains the Scrapy-based crawlers, the scheduler that launches them, sitemap monitoring, DAP ingestion, deployment scripts, and supporting utilities.

## Contents
- [Overview](#overview)
- [Repository Layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Running the App Locally](#running-the-app-locally)
- [Common Developer Commands](#common-developer-commands)
- [Configuration](#configuration)
- [Docker and Related Services](#docker-and-related-services)
- [Additional Documentation](#additional-documentation)

## Overview

This project crawls websites that Search.gov indexes directly rather than relying on third-party search providers. At a high level, it:

- Crawls HTML and JavaScript-heavy sites with Scrapy and Playwright.
- Writes crawl output to CSV, an HTTP endpoint, or OpenSearch.
- Schedules recurring crawls from domain configuration files.
- Monitors sitemaps for changes and triggers targeted recrawls.
- Ingests DAP visit data into Redis for use during indexing and ranking.

The codebase targets Python 3.12 and uses Redis for scheduler and crawl state.

## Repository Layout

```text
.
├── cicd-scripts/                Deployment and instance lifecycle scripts
├── docs/                        Architecture, deployment, operations, and advanced usage docs
├── scripts/                     One-off utility scripts for cache, configs, and query testing
├── search_gov_crawler/          Main application package and Scrapy project root
│   ├── dap/                     DAP retrieval, transformation, and storage logic
│   ├── domains/                 Crawl configuration inputs and generated domain lists
│   ├── indexing/                OpenSearch indexing and NLTK setup
│   ├── scheduling/              APScheduler and Redis job state integration
│   ├── search_gov_app/          Integration code for Search.gov app data/configs
│   ├── search_gov_spiders/      Spiders, pipelines, middleware, monitors, and job state
│   ├── benchmark.py             Manual benchmark and ad hoc crawl runner
│   ├── dap_extractor.py         DAP scheduler / on-demand ingestion entrypoint
│   ├── run_sitemap_monitor.py   Sitemap monitor entrypoint
│   ├── scrapy_scheduler.py      Scheduled crawl entrypoint
│   └── scrapy.cfg               Scrapy configuration root
├── tests/                       Test suite
├── Makefile                     Common setup, lint, test, and schedule tasks
├── pyproject.toml               Package metadata and pytest configuration
└── requirements.txt             Root requirements wrapper
```

## Prerequisites

- Python 3.12.x
- `venv`
- Redis
- Google Chrome / Playwright browser dependencies for JavaScript-enabled crawling
- Optional but recommended: `make`, `pre-commit`

The repo is configured for Python 3.12 in [runtime.txt](/Users/amian/Documents/projects/searchgov-spider/runtime.txt:1) and [pyproject.toml](/Users/amian/Documents/projects/searchgov-spider/pyproject.toml:9).

## Local Setup

1. Create and activate a virtual environment:

```bash
python3.12 -m venv venv
source venv/bin/activate
```

2. Install project dependencies:

```bash
make project-requirements
```

If you prefer not to use `make`:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. Install Playwright browser dependencies for JavaScript crawling:

```bash
playwright install --with-deps
playwright install chrome --force
```

4. Start Redis locally:

```bash
redis-server
```

If you run Redis another way, make sure `REDIS_HOST` and `REDIS_PORT` match your local instance.

5. Optional: install git hooks:

```bash
pre-commit install
```

6. Optional: create a local `.env` file if you want to run the scheduler, sitemap monitor, endpoint output, DAP extraction, or OpenSearch indexing. The runtime entrypoints call `load_dotenv()`, so a repo-root `.env` file will be picked up automatically.

## Running the App Locally

### Run a single crawl

From the Scrapy project root:

```bash
cd search_gov_crawler
```

Run a non-JavaScript crawl:

```bash
scrapy crawl domain_spider \
  -a allowed_domains=quotes.toscrape.com \
  -a start_urls=https://quotes.toscrape.com \
  -a output_target=csv
```

Run a JavaScript-enabled crawl:

```bash
scrapy crawl domain_spider_js \
  -a allowed_domains=quotes.toscrape.com \
  -a start_urls=https://quotes.toscrape.com/js \
  -a output_target=csv
```

CSV output is written under [search_gov_crawler/output](/Users/amian/Documents/projects/searchgov-spider/search_gov_crawler/output:1).

### Run the scheduler

The scheduler reads crawl config records from a JSON file in `search_gov_crawler/domains/` and stores job state in Redis.

```bash
python search_gov_crawler/scrapy_scheduler.py
```

Useful environment variables:

- `SPIDER_CRAWL_SITES_FILE_NAME`
- `SPIDER_SCRAPY_MAX_WORKERS`
- `SPIDER_CRAWL_CONFIGS_CHECK_INTERVAL`
- `REDIS_HOST`
- `REDIS_PORT`

### Run the sitemap monitor

```bash
python search_gov_crawler/run_sitemap_monitor.py
```

This process reads the crawl config file, monitors sitemap sources, and triggers targeted crawls when it detects new URLs.

### Run the DAP extractor

Run once immediately:

```bash
python search_gov_crawler/dap_extractor.py --run-now
```

Run on a schedule:

```bash
python search_gov_crawler/dap_extractor.py
```

Required configuration:

- `DAP_API_BASE_URL`
- `DATA_GOV_API_KEY`
- `DAP_EXTRACTOR_SCHEDULE`

Optional configuration:

- `DAP_VISITS_DAYS_BACK`
- `DAP_VISITS_MAX_AGE`
- `REDIS_HOST`
- `REDIS_PORT`

### Run benchmark tooling

```bash
python search_gov_crawler/benchmark.py --help
```

This is useful for manual timing, benchmarking, and ad hoc crawl execution outside the main scheduler.

## Common Developer Commands

Install dependencies:

```bash
make project-requirements
```

Run tests:

```bash
make tests
```

Run coverage:

```bash
make coverage
```

Run lint and formatting checks:

```bash
make ruff-all
```

Run only formatting check:

```bash
make ruff-format
```

Run only linting:

```bash
make ruff-check
```

Regenerate crawl-site artifacts from Jsonnet:

```bash
make schedule
```

## Configuration

Common environment variables used in local development:

```bash
SCRAPY_LOG_LEVEL=INFO
REDIS_HOST=localhost
REDIS_PORT=6379
SPIDER_CRAWL_SITES_FILE_NAME=crawl-sites-development.json
SPIDER_SCRAPY_MAX_WORKERS=5
SPIDER_CRAWL_CONFIGS_CHECK_INTERVAL=300
SPIDER_URLS_API=https://local.search.usa.gov/urls
SPIDER_SPIDERMON_ENABLED=False
```

Additional variables are required depending on the output target or runtime:

- `csv`: no extra external service configuration required.
- `endpoint`: requires `SPIDER_URLS_API`.
- `opensearch`: requires OpenSearch-related credentials and host settings, plus NLTK data installation.
- `dap_extractor.py`: requires the DAP variables listed above.

To install the NLTK data used for OpenSearch-related indexing:

```bash
python search_gov_crawler/indexing/install_nltk.py
```

For a more complete deployment-oriented variable list, see [docs/advanced_setup_and_use.md](/Users/amian/Documents/projects/searchgov-spider/docs/advanced_setup_and_use.md:1) and [cicd-scripts/helpers/fetch_env_vars.sh](/Users/amian/Documents/projects/searchgov-spider/cicd-scripts/helpers/fetch_env_vars.sh:1).

## Docker and Related Services

This repository does not include a `docker-compose.yml` file. If you want a full local stack with Search.gov-related services such as OpenSearch and supporting infrastructure, use the companion `search-services` repository referenced in the project docs.

This repo can still be developed locally without Docker if you have:

- Python 3.12
- Redis
- Playwright browser dependencies

## Additional Documentation

- [Architecture](/Users/amian/Documents/projects/searchgov-spider/docs/architecture.md:1)
- [Advanced Setup and Use](/Users/amian/Documents/projects/searchgov-spider/docs/advanced_setup_and_use.md:1)
- [Deployments](/Users/amian/Documents/projects/searchgov-spider/docs/deployments.md:1)
- [Operations](/Users/amian/Documents/projects/searchgov-spider/docs/operations.md:1)
- [Domain Config Documentation](/Users/amian/Documents/projects/searchgov-spider/search_gov_crawler/domains/README.md:1)
- [Utility Scripts](/Users/amian/Documents/projects/searchgov-spider/scripts/README.md:1)
