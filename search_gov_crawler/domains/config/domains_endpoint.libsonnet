// endpoint domain config for export
local DomainConfig = import 'domain_config.libsonnet';
local output_target = 'endpoint';
[
  // long running domains, start these early
  {
    name: 'NOAA CoastWatch East Coast Node',
    config: DomainConfig(allowed_domains='eastcoast.coastwatch.noaa.gov',
                         starting_urls='https://eastcoast.coastwatch.noaa.gov/',
                         schedule='30 08 * * MON',
                         output_target=output_target,
                         depth_limit=3),
  },
  {
    name: 'VA Benefits.va.gov',
    config: DomainConfig(allowed_domains='benefits.va.gov',
                         starting_urls='https://benefits.va.gov/benefits/',
                         schedule='30 08 * * MON',
                         output_target=output_target,
                         depth_limit=3),
  },
  // everything else starts at 0930
  {
    name: 'DOS AIS USVISA INFO',
    config: DomainConfig(allowed_domains='ais.usvisa-info.com',
                         starting_urls='https://ais.usvisa-info.com/',
                         schedule='30 09 * * MON',
                         output_target=output_target,
                         depth_limit=3),
  },
  {
    name: 'toolkit.climate.gov - endpoint',
    config: DomainConfig(allowed_domains='toolkit.climate.gov',
                         starting_urls='https://toolkit.climate.gov',
                         schedule='30 09 * * MON',
                         output_target=output_target,
                         depth_limit=3),
  },
  {
    name: 'ED Office of Hearings and Appeals OHA',
    config: DomainConfig(allowed_domains='oha.ed.gov',
                         starting_urls='https://oha.ed.gov',
                         schedule='30 09 * * MON',
                         output_target=output_target,
                         depth_limit=3),
  },
  {
    name: 'FDA Import Alerts',
    config: DomainConfig(allowed_domains='www.accessdata.fda.gov',
                         starting_urls='https://www.accessdata.fda.gov/CMS_IA/default.html',
                         schedule='30 09 * * MON',
                         output_target=output_target,
                         depth_limit=8),
  },
  {
    name: 'NOAA CoastWatch West Coast',
    config: DomainConfig(allowed_domains='coastwatch.pfeg.noaa.gov',
                         starting_urls='https://coastwatch.pfeg.noaa.gov/',
                         schedule='30 09 * * MON',
                         output_target=output_target,
                         depth_limit=3),
  },
]
