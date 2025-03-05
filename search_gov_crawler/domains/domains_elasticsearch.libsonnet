// elasticsearch domain config for export
local DomainConfig = import 'domain_config.libsonnet';
local output_target = 'elasticsearch';
[
  {
    name: 'Federal Audit Clearinghouse',
    config: DomainConfig(allowed_domains='fac.gov',
                         starting_urls='https://www.fac.gov/',
                         schedule='00 06 * * TUE',
                         output_target=output_target),
  },
]
