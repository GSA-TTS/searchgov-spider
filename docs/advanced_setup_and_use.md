# Setup and Use
This page gives a more detailed description and further instructions on running the spider in various ways.

#### Table of contents
* [Environment Variables](#environment-variables)
* [Output Targets](#output-targets)
* [Elasticsearch](#elasticsearch)
* [Starting Spider Jobs](#starting-spider-jobs)
  * [Option 1: command-line](#option-1-scrapy-crawl-with-different-output)
  * [Option 2: benchmark](#option-2-benchmark-command-line)
  * [Option 3: running-scrapy-scheduler](#option-3-running-scrapy-scheduler)
* [Running For All Domains](#running-against-all-listed-searchgov-domains)
* [Adding New Spiders](#adding-new-spiders)

## Environment Variables
If running a scheduler or benchmark, we support the use of a `.env` file in the project root to read keys and values.  Othewise these must be exported through other means.

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
```

## Elasticsearch
Before setting the output target to `elastcisearch` for any domains:
1. Install required nltk modules (only required for output target of elasticsearch):
```bash
# make sure the virtual environment is activate
python ./search_gov_crawler/elasticsearch/install_nltk.py
```

2. Start elasticsearch using the docker compose file at the project root:
```bash
# ensure current working directory is the project root
docker compose up
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
