// This file is used to generate the full production crawl list.

local csv_domains = import 'domains_csv.libsonnet';
local elasticsearch_domains = import 'domains_elasticsearch.libsonnet';
local endpoint_domains = import 'domains_endpoint.libsonnet';

// generate the crawl list
[
  {
    name: domain.name,
    allow_query_string: domain.config.allow_query_string,
    allowed_domains: domain.config.allowed_domains,
    handle_javascript: domain.config.handle_javascript,
    schedule: domain.config.schedule,
    output_target: domain.config.output_target,
    starting_urls: domain.config.starting_urls,
  }
  for domain in csv_domains + endpoint_domains + elasticsearch_domains
]
