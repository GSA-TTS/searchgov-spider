// elasticsearch domain config for export
local DomainConfig = import 'domain_config.libsonnet';
local output_target = 'elasticsearch';
[
  // start long running domains first
  {
    name: 'NIH Research Festival (nih-oir-research_festival)',
    config: DomainConfig(allowed_domains='researchfestival.nih.gov',
                         starting_urls='https://researchfestival.nih.gov/',
                         schedule='00 06 * * TUE',
                         output_target=output_target),

  },

  // run the rest a few minutes later
  {
    name: 'Search.gov (usasearch)',
    config: DomainConfig(allowed_domains='search.gov',
                         starting_urls='https://www.search.gov/',
                         schedule='15 06 * * TUE',
                         output_target=output_target),
  },
  {
    name: 'Bureau of Engraving and Printing (bep)',
    config: DomainConfig(allowed_domains='bep.gov',
                         starting_urls='https://www.bep.gov/',
                         schedule='15 06 * * TUE',
                         output_target=output_target),
  },
  {
    name: 'Department of Energy - Hydrogen (doe-h2)',
    config: DomainConfig(allowed_domains='hydrogen.energy.gov',
                         starting_urls='https://www.hydrogen.energy.gov/',
                         schedule='15 06 * * TUE',
                         output_target=output_target),
  },
  {
    name: 'Eisenhower Presidential Library (eisenhower)',
    config: DomainConfig(allowed_domains='eisenhowerlibrary.gov',
                         starting_urls='https://www.eisenhowerlibrary.gov/',
                         schedule='15 06 * * TUE',
                         output_target=output_target),
  },
  {
    name: 'CDFI Fund (cdfifund)',
    config: DomainConfig(allowed_domains='cdfifund.gov',
                         starting_urls='https://www.cdfifund.gov/',
                         schedule='15 06 * * TUE',
                         output_target=output_target),
  },
]
