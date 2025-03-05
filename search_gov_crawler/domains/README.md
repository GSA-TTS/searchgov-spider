## Using Jsonnet to generate crawl files
So as to have better control and readabilty of these configuration files, we use [Jsonnet](https://jsonnet.org/) to generate json files that control our jobs.

### Domain Files
There is one file for each of the different output targets we support (csv, endpoint, and elasticsearc) as well as a common file imported by the other domain files that contains code used by all others.

- domains_csv.libsonnet: contains configuration for domains with an output target of `csv`.
- domains_endpoint.libsonnet: contains configuration for domains with an output target of `endpoint`.
- domains_elasticsearch.libsonnet: contains configuration for domains with an output target of `elasticsearch`.
- domain_config.libsonnet: contains source for `DomainConfig` fuction used to generate domain configurations for all output targets.

### Check Formatting
Use the `jsonnetfmt` command to check formatting prior to commiting and changes, for example:
```bash
jsonnetfmt -i *.jsonnet *.libsonnet
```

### Generate JSON files
Use the `jsonnet` command to create new json files after adjusting domain configurations, for example:
```bash
# To create/recreate the full production file
jsonnet crawl-sites-production.jsonnet > crawl-sites-production.json

# To create/recreate the production scrutiny-only file
jsonnet crawl-sites-production-scrutiny.jsonnet > crawl-sites-production-scrutiny.json

# To create/recreate the sample file
jsonnet crawl-sites-sample.jsonnet > crawl-sites-sample.json
```
