// This file is used to generate the crawl list for just endpoint (legacy scrutiny) domains.

local endpoint_domains = import 'domains_endpoint.libsonnet';

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
  for domain in endpoint_domains
]
