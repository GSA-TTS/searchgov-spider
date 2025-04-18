# Spider Domain Schedule and Configuration

## Using Jsonnet to generate crawl files
So as to have better control and readabilty of these configuration files, we use [Jsonnet](https://jsonnet.org/) to generate json files that control our jobs.

### Legacy Files
We are maintaining a few files that spider used to use to create crawl sites files in the case that we need to reference them.  They are not used to generate any crawl site data.  You can access the files in the [legacy_files](legacy_files) folder.

### Domain Configuration Files
In the config directory, there is one file for each of the different output targets we support (csv, endpoint, and elasticsearc) as well as a common file imported by the other domain files that contains code used by all others.  These files contain all attributes necessary to have the spider run a domain.

- domains_csv.libsonnet: contains configuration for domains with an output target of `csv`.
- domains_endpoint.libsonnet: contains configuration for domains with an output target of `endpoint`.
- domains_elasticsearch.libsonnet: contains configuration for domains with an output target of `elasticsearch`.
- domain_config.libsonnet: contains source for `DomainConfig` fuction used to generate domain configurations for all output targets.

### Domain Configuration
A shared DomainConfig function is used to generate crawl site records in a specific format. When creating a new domain, choose the file that matches the output target and add a record to the file similar to the example below.  See the [DomainConfig](config/domain_config.libsonnet) function for more details.
```bash
  {
    name: 'New Domain To Crawl',
    config: DomainConfig(allowed_domains='new-domain.gov',
                         starting_urls='https://www.new-domain.gov/',
                         schedule='00 12 * * WED',
                         output_target=output_target),
  }
```

### Check Formatting
Use the `jsonnetfmt` command to check formatting prior to commiting and changes:
```bash
cd search_gov_crawler/domains
jsonnetfmt -i *.jsonnet config/*.libsonnet
```

### Jsonnet File
We use a single jsonnet file to generate all the files we need.  The file is setup to use [multi-file output](https://jsonnet.org/learning/getting_started.html#multi) with both the names and the contents of the output files defined in the jsonnet file.

### Generate JSON files
To create or recreate the json files after changes, use the `jsonnet` command:
```bash
cd search_gov_crawler/domains
jsonnet -m . crawl-sites.jsonnet
```

### Generate Markdown Schedules 
To generate all human readable schedules run readschedule
```bash 
cd search_gov_crawler/domains
python readschedule.py
```

To generate individual human readable schedules run readschedule with the json file you would like to create/update: 

```bash
cd search_gov_crawler/domains
python readschedule.py crawl-sites-development.json
python readschedule.py crawl-sites-staging.json
python readschedule.py crawl-sites-production.json   
```