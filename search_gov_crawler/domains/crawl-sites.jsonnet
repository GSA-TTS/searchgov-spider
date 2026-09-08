// This file is used to generate json files.  The -m option must be used to generated multiple files.

local csv_domains = import 'config/domains_csv.libsonnet';
local endpoint_domains = import 'config/domains_endpoint.libsonnet';
local opensearch_domains = import 'config/domains_opensearch.libsonnet';
local all_domains = csv_domains + endpoint_domains + opensearch_domains;

local CrawlSite(domain) = {
  name: domain.name,
  allow_query_string: domain.config.allow_query_string,
  allowed_domains: domain.config.allowed_domains,
  handle_javascript: domain.config.handle_javascript,
  schedule: domain.config.schedule,
  output_target: domain.config.output_target,
  starting_urls: domain.config.starting_urls,
  depth_limit: domain.config.depth_limit,
  allow_paths: domain.config.allow_paths,
  deny_paths: domain.config.deny_paths,
  sitemap_urls: domain.config.sitemap_urls,
  check_sitemap_hours: domain.config.check_sitemap_hours,
};

// Define output file names and their contents below.  Development and staging files are a subset of the production files.
{
  'crawl-sites-production.json': [CrawlSite(domain) for domain in all_domains],
  'crawl-sites-staging.json': [CrawlSite(domain) for domain in all_domains if std.member(domain.config.lower_environments, 'staging')],
  'crawl-sites-development.json': [CrawlSite(domain) for domain in all_domains if std.member(domain.config.lower_environments, 'development')],
}
