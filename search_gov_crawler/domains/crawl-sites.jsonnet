// This file is used to generate json files.  The -m option must be used to generated multiple files.

local csv_domains = import 'config/domains_csv.libsonnet';
local elasticsearch_domains = import 'config/domains_elasticsearch.libsonnet';
local endpoint_domains = import 'config/domains_endpoint.libsonnet';

local CrawlSite(domain) = {
  name: domain.name,
  allow_query_string: domain.config.allow_query_string,
  allowed_domains: domain.config.allowed_domains,
  handle_javascript: domain.config.handle_javascript,
  schedule: domain.config.schedule,
  output_target: domain.config.output_target,
  starting_urls: domain.config.starting_urls,
  depth_limit: domain.config.depth_limit,
  deny_paths: domain.config.deny_paths,
};

// define output file names and their contents below
{
  'crawl-sites-production.json': [CrawlSite(domain) for domain in csv_domains + endpoint_domains + elasticsearch_domains],
  'crawl-sites-staging.json': [CrawlSite(domain) for domain in csv_domains + endpoint_domains + elasticsearch_domains],
  'crawl-sites-development.json': [CrawlSite(domain) for domain in csv_domains + endpoint_domains + elasticsearch_domains],
}
