## Using Jsonnet to generate crawl files
So as to have better control and readabilty of these configuration files, we use [Jsonnet](https://jsonnet.org/) to generate json files that control our jobs.

### Domain Configuration Files
In the config directory, there is one file for each of the different output targets we support (csv, endpoint, and elasticsearc) as well as a common file imported by the other domain files that contains code used by all others.

- domains_csv.libsonnet: contains configuration for domains with an output target of `csv`.
- domains_endpoint.libsonnet: contains configuration for domains with an output target of `endpoint`.
- domains_elasticsearch.libsonnet: contains configuration for domains with an output target of `elasticsearch`.
- domain_config.libsonnet: contains source for `DomainConfig` fuction used to generate domain configurations for all output targets.

### Check Formatting
Use the `jsonnetfmt` command to check formatting prior to commiting and changes:
```bash
jsonnetfmt -i *.jsonnet config/*.libsonnet
```

### Jsonnet File
We use a single jsonnet file to generate all the files we need.  The file is setup to use [multi-file output](https://jsonnet.org/learning/getting_started.html#multi) with both the names and the contents of the output files defined in the jsonnet file.

### Generate JSON files
To create or recreate the json files after changes, use the `jsonnet` command:
```bash
jsonnet -m . crawl-sites.jsonnet
```
