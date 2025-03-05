// domains config function used for all domain output targets
function(allowed_domains, starting_urls, schedule, output_target, options=[]) {
  allowed_domains: allowed_domains,
  allow_query_string: if ['allow_query_string'] == [o for o in options if o == 'allow_query_string'] then true else false,
  starting_urls: starting_urls,
  schedule: schedule,
  output_target: output_target,
  handle_javascript: if ['handle_javascript'] == [o for o in options if o == 'handle_javascript'] then true else false,
}
