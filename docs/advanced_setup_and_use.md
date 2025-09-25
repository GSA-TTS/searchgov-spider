# Setup and Use
This page gives a more detailed description and further instructions on running the spider in various ways.

#### Table of contents
* [Environment Variables](#environment-variables)
* [Output Targets](#output-targets)
* [Search Engines](#search-engines)
* [Starting Spider Jobs](#starting-spider-jobs)
  * [Option 1: command-line](#option-1-scrapy-crawl-with-different-output)
  * [Option 2: benchmark](#option-2-benchmark-command-line)
  * [Option 3: running-scrapy-scheduler](#option-3-running-scrapy-scheduler)
* [Running For All Domains](#running-against-all-listed-searchgov-domains)
* [Adding New Spiders](#adding-new-spiders)
* [Running Sitemap Monitor](#running-sitemap-monitor)
* [Running DAP Extractor](#running-dap-extractor)

## Environment Variables
If running a scheduler or benchmark, we support the use of a `.env` file in the project root to read keys and values.  Othewise these must be exported through other means.   We also provide a `.env.development` for use with dock as well as a example for some of these values.

```bash
# Optional variables for process control and info
SCRAPY_LOG_LEVEL="INFO"
SPIDER_SCRAPY_MAX_WORKERS="5"
SPIDER_CRAWL_SITES_FILE_NAME="crawl-sites-sample.json"

# Needed for elasticsearch Output target
SEARCHELASTIC_INDEX="development-i14y-documents-searchgov"
ES_HOSTS="http://localhost:9200"
ES_USER="username"
ES_PASSWORD="password"

# Needed for endpoint Output Target
SPIDER_URLS_API="https://jsonplaceholder.typicode.com/posts"

# Needed for deployment
SPIDER_PYTHON_VERSION="3.12"

# Needed for DAP Extractor
DAP_API_BASE_URL="https://api.gsa.gov/analytics/dap/v2.0.0"
DAP_EXTRACTOR_SCHEDULE="*/5 * * * *"
DAP_VISITS_DAYS_BACK=7
DAP_VISITS_MAX_AGE=14
DATA_GOV_API_KEY="NOT-A-REAL-API-KEY"
```

## Search Engines
Before setting the output target to `elastcisearch` for any domains:
1. Install required nltk modules (only required for output target of elasticsearch):
```bash
# make sure the virtual environment is activate
python ./search_gov_crawler/search_engines/install_nltk.py
```

2. Ensure elasticsearch/opensearch is running by using the docker compose file at the project root:
```bash
# ensure current working directory is the project root
docker compose up
```

3. Create index in elasticsearch/opensearch using a template.  Documents will still load without this
step but it is necessary to enable full searchgov functionality.
```bash
/bin/bash docker_create_index.sh
```

## Starting Spider Jobs

Make sure to follow [Quick Start](../README.md#quick-start) steps, before running any spiders.

### Option 1: Scrapy Crawl With Different Output

1. Navigate to the [search_gov_crawler](../search_gov_crawler) directory
2. Run a scrapy crawl command

```bash
# write URLs to a CSV
scrapy crawl domain_spider -a allowed_domains=quotes.toscrape.com -a start_urls=https://quotes.toscrape.com -a output_target=csv

# post URLs to an endpoint
scrapy crawl domain_spider -a allowed_domains=quotes.toscrape.com -a start_urls=https://quotes.toscrape.com -a output_target=endpoint

# post documents to elasticsearch
scrapy crawl domain_spider_js -a allowed_domains=quotes.toscrape.com -a start_urls=https://quotes.toscrape.com/js -a output_target=elasticsearch
```

### Option 2: Benchmark Command Line

The benchmark script is primarily intended for use in timing and testing scrapy runs.  There are two ways to run.  In either case if
you want to redirect your ouput to a log file and not have the terminal session tied up the whole time you should wrap your command using something like `nohup <benchmark command> >> scrapy.log 2>&1 &`
1. To run a single domain (specifying starting URL `-u`, allowed domain `-d`, and `-o` for output target):
```bash
python search_gov_spiders/benchmark.py -u https://www.example.com -d example.com -o csv
```

2. To run multiple spiders simultaneously, provide a json file in the format of the [*crawl-sites-development.json file*](../search_gov_crawler/domains/crawl-sites-development.json) as an argument:
```bash
python search_gov_spiders/benchmark.py -f /path/to/crawl-sites-like-file.json
```

There are other options available.  Run `python search_gov_spiders/benchmark.py -h` for more info.

### Option 3: Running scrapy scheduler

This process allows for scrapy to be run directly using an in-memory scheduler.  The schedule is based on the initial schedule setup in the [crawl-sites-sample.json file](../search_gov_crawler/search_gov_spiders/utility_files/crawl-sites-sample.json).  The process will run until killed.

The json input file must be in a format similar what is below.  There are validations in place when the file is read and in tests that should help
prevent this file from getting into an invalid state.

```json
[
    {
        "name": "Example",
        "allowed_domains": "example.com",
        "allow_query_string": false,
        "handle_javascript": false,
        "schedule": "30 08 * * MON",
        "starting_urls": "https://www.example.com"
    }
]
```

0. Source virtual environment and update dependencies.

1. Start scheduler

        $ python search_gov_crawler/scrapy_scheduler.py


## Running Against All Listed Search.gov Domains

This method is *not recommended*.  If you want to run a large amount of domains you should [setup a schedule](#option-3-custom-scheduler).

Navigate down to `search_gov_crawler/search_gov_spiders`, then enter the command below:
```commandline
scrapy crawl domain_spider
```
to run for all urls / domains that do not require javacript handling.  To run for all sites that require
javascript run:
```commandline
scrapy crawl domain_spider_js
```
^^^ These will take a _long_ time

## Adding new spiders

1.  Navigate to anywhere within the [Scrapy project root](../search_gov_crawler) directory and run this command:

        $ scrapy genspider -t crawl <spider_name> "<spider_starting_domain>"

2. Using the [domain spider](../search_gov_crawler/search_gov_spiders/spiders/domain_spider.py) as an example, copy code to the new spider file.

3. Modify the `rules` in the new spider as needed. Here's the [Scrapy rules documentation](https://docs.scrapy.org/en/latest/topics/spiders.html#crawling-rules) for the specifics.


## Running Sitemap Monitor
To start the Sitemap monitor run:
```bash
# make sure the virtual environment is activate
cd search_gov_crawler
python run_sitemap_monitor.py
```

The process will start by checking all sitemaps that are identified in the schedule or have domain attributes that meet the defined criteria for inclusion.  The URLs from those sitemaps are stored on disk and used to determine if a new URL appears.  If new URLs are found, the sitemap monitor starts a spider process to capture the content at those URLs but does not crawl links found at those URLs.  The process then sleeps for a defined interval.  If no new URLs are found the processes simply sleeps until it is time to check again.

The logic related to discovering sitemaps can be found in the [SitemapFinder class](../search_gov_crawler/search_gov_spiders/sitemaps/sitemap_finder.py) and can also be run idependently to create a list of sitemap locations for all domains.  See the [README](../search_gov_crawler/search_gov_spiders/sitemaps/README.md) in the Sitemaps module for instructions.

## Running DAP Extractor
Starting the DAP extractor is simple:
```bash
# make sure the virtual environment is activate
python search_gov_crawler/dap_extractor.py
```

The process schedules itself using APScheduler.  The schedule is controlled by the `DAP_EXTRACTOR_SCHEDULE` environment variable.  It will not run if this value is not set.  The environment variables `DAP_API_BASE_URL` and `DATA_GOV_API_KEY` allow for access to the DAP API by the process and are also required.  The extractor process will by default pull a certain number of days of data and retain data for a certain number of days.  If you want to change these defaults you can add options to the command:
```bash
# to see help message
python search_gov_crawler/dap_extractor.py --help

# Increase the retrival and retention periods
python search_gov_crawler/dap_extractor.py --days-back 30 --max-age 365
```
These retrieval and retention periods are also configurable by environment variables: `DAP_VISITS_DAYS_BACK`and `DAP_VISITS_MAX_AGE` respectively. These essentially serve as default values. Passing values on the command line will override the values in the environment variables.
