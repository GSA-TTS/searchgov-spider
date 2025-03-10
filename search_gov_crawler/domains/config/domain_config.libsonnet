/*
Exports the domain config function used for all domain output targets. Expects the following input arguments:
  - allowed_domains (str) a single or comma-separated list of domains that the crawler is allowed to access
  - starting_urls (str): a single or comma-separated list of URLs to start crawling from
  - schedule (str): a cron schedule for when the crawler should run
  - output_target (str): the target output for the crawler - set in each output target's domain file
  - options (list): a list of options that can be passed to the domain config function.  Current options include:
    - allow_query_string: if set, the crawler will allow query strings in URLs
    - handle_javascript: if set, the crawler will handle javascript on the page
*/

function(allowed_domains, starting_urls, schedule, output_target, options=[]) {
  allowed_domains: allowed_domains,
  allow_query_string: if ['allow_query_string'] == [o for o in options if o == 'allow_query_string'] then true else false,
  starting_urls: starting_urls,
  schedule: schedule,
  output_target: output_target,
  handle_javascript: if ['handle_javascript'] == [o for o in options if o == 'handle_javascript'] then true else false,
}
