# searchgov-spider
The home for the spider that supports [Search.gov](https://www.search.gov).

#### Table of contents
* [About](#about)
* [Quick Start (Docker)](#quick-start---docker)
* [Quick Start (Local)](#quick-start---local-development)
* [Entry Points](#entrypoints)
* [Signed Commits](#signed-commits)
* [Helpful Links](#helpful-links)

## About
The SearchGov Spider application is the main source of search results for [SearchGov](https://github.com/GSA/search-gov).  This app is used to automatically crawl and capture content from domains that SearchGov serves as well as providing means for maintaining these documents in our indices.   The documentation here represents the most current state of the application and our design.

### Technologies
We currently run python 3.12.  The spider is based on the open source [scrapy](https://scrapy.org/) framework.  On top of that we use several other open source libraries and scrapy plugins.  See our [requirements file](search_gov_crawler/requirements.txt) for more details.

### Core Scrapy File Structure
*Note: Other files and directories are within the repository but the folders and files below relate to those needed for the scrapy framework.

```bash
├── search_gov_crawler              # scrapy root
|   ├── config                      # contains configuration and settings
│   ├── dap                         # code for handling data from DAP
│   ├── domains                     # json files with domains to scrape
│   ├── indexing                    # code related to indexing content in opensearch
|   ├── run                         # code used to help run and schedule jobs
│   ├── scheduling                  # code for job scheduling and storing schedules in redis
|   ├── search_gov_app              # code for communicating with the searchgov app
│   ├── search_gov_spider           # scrapy project dir
│   │   ├── extensions              # custom scrapy extensions
│   │   ├── helpers                 # common functions
│   │   ├── job_state               # code related to storing job state in redis
│   │   ├── sitemaps                # code related to indexing based on sitemap data
│   │   ├── spiders                 # all search_gov_spider spiders
│   │   │   ├── domain_spider.py    # for html pages
│   │   │   ├── domain_spider_js.py # for js pages
│   │   ├── items.py                # defines individual output of scrapes
│   │   ├── middlewares.py          # custom middleware code
│   │   ├── monitors.py             # custom spidermon monitors
│   │   ├── pipelines.py            # custom item pipelines
│   │   ├── settings.py             # settings that control all scrapy jobs
│   ├── scrapy.cfg
```

## Quick Start - Docker
Docker can be used to run spider from this repo. Make commands have been added for convenience.

0. Start [search-services](https://www.github.com/GSA/search-services).
After cloning and changing directories to this projects root, run:
```
docker compose up
```

1. Build spider image
After search services is running, build

```bash
make docker-build
```

2. Run the scrapy scheduler process.
This will start the spider-scheduler container and run domains based on the development schedule.  Watch logs and check output.  It may be that no jobs are scheduled for a while so nothing will run. If a crawl does start watch the logs for information about records loaded to Opensearch.  Then, visit [Opensearch Dashboards](http://localhost:5602) to view indexed documents.

```
make docker-run-scrapy-scheduler
```

3. Run an on-demand crawl
To direct documents from a specific domain, use the helper make command to trigger an on-demand crawl.  The `docker-scrapy-crawl` command as a shortcut to running any `scrapy crawl` command. Use `ARGS` to pass in all other arguments.  For instance, starting at `https://www.gsa.gov` and limited to pages in the `www.gsa.gov` domain, you might run:

```bash
make docker-scrapy-crawl ARGS="domain_spider -a allowed_domains='www.gsa.gov' -a start_urls='https://www.gsa.gov' -a output_target='opensearch' -a depth_limit=3"
```


## Quick Start - Local Development
If you want to get started quickly running a scrape follow these instructions:

0. Ensure python can be installed locally using pyenv
```
brew install pyenv
pyenv install 3.12.1
```

1. Install and activate virtual environment:
```bash
pyenv exec python -m venv venv
source venv/bin/activate
```

2. Ensure latest pip and add required python modules:
```bash
pip install --upgrade pip
pip install -r requirements.txt

# required for domains that need javascript
playwright install --with-deps
playwright install chrome --force
```

3. Ensure `PYTHONPATH` is set
A `PYTHONPATH` environment variable is likely required to be inplace prior to running spider code.  This can be set in your shell's profile or rc file or in your IDE's terminal config.  The values should be pointed to the project root, e.g. `export PYTHONPATH=/local/path/to/searchgov-spider`

4. Run A Spider:
```bash
cd search_gov_crawler
scrapy crawl domain_spider -a allowed_domains=www.gsa.gov -a start_urls=https://www.gsa.gov -a output_target=csv
```

5. Check Output:

The output of this scrape is one or more csv files containing URLs in the [output directory](search_gov_crawler/output).

6. Learn More:

For more advanced usage, see the [Advanced Setup and Use Page](docs/advanced_setup_and_use.md)

## Entrypoints
* [Scrapy Scheduler](search_gov_crawler/scrapy_scheduler.py) - Process that manages and runs spider crawls based on a schedule.

* [Sitemap Monitor](search_gov_crawler/run_sitemap_monitor.py) - Process that monitors domains for changes in their sitemaps and triggers spider runs to capture changes.

* [DAP Extractor](search_gov_crawler/dap_extractor.py) - Stand-alone job that handles extracting and loading DAP visits data for use in spider crawls.

* [Document Lifecycle Manager](search_gov_crawler/dap_extractor.py) - Stand-alone job that deletes documents from the search index when they are no longer needed.

* [Benchmark](search_gov_crawler/benchmark.py) - Allows for manual testing and benchmarking using similar mechanisms as scheduled runs.

## Signed Commits
The GSA-TTS organization requires **all commits in pull requests to be cryptographically signed**. Unsigned commits will be blocked from merging.  Follow instructions at https://handbook.18f.org/tools/git-signing/ or https://docs.github.com/en/authentication/managing-commit-signature-verification to set this up.

## Helpful Links
* [Architecture](docs/architecture.md)

* [Advanced Setup and Use](docs/advanced_setup_and_use.md)

* [Deployments](docs/deployments.md)

* [Operations](docs/operations.md)

* [Spider Schedules and Domain Configs README](search_gov_crawler/domains/README.md)
  * [Current Production Domain List - JSON](search_gov_crawler/domains/crawl-sites-production.json)
  * [Current Production Domain List - Markdown](search_gov_crawler/domains/crawl-sites-production.md)
