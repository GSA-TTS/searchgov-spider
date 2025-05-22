# Architecture

## High Level Diagram
A basic representation of our architecture is below.  Here you can see a JSON configuration file feeding into a scheduler process which, in turn, launces multiple scrapy processes, each capable of writing to its own target system. The number of concurrent jobs is configurable within the system.
```mermaid
flowchart LR
    J[json config file] --> S[Scheduler]
    S --> P0[Scrapy Process 0] --> T0[Output Target 0]
    S --> P1[Scrapy Process 1] --> T1[Output Target 1]
    S --> P2[Scrapy Process 2] --> T2[Output Target 2]
    S -.-> PN[Scrapy Process N] -.-> TN[Output Target N]
    style PN stroke-dasharray: 5 5
    style TN stroke-dasharray: 5 5
```

The [Scrapy documentation](https://docs.scrapy.org/en/latest/topics/architecture.html) does a good job of explaning the internals of Scrapy, which for us, is encapsulated in each of the "Scrapy Process" blocks above.

## Scheduler State
The state of the scheduler is stored in Redis so that it can persist between restarts and deployments.  The spider scheduler uses three keys: one to hold information about the job (Job State), one to hold information about the next time the job will run (Next Run Time), and a third that keeps tracks of jobs that have been sent to the executor but have not yet finished (Pending Jobs).  The Job State and Next Run Time keys are native to APScheduler.  The Pending Jobs key is a custom Spider APSchedule extension that allows us to keep our often significantly large queue of jobs in place between restarts or deployments.

```mermaid
flowchart LR
    subgraph Spider
    S[Scheduler]
    end
    subgraph Redis
    direction TB
    J[Job State Key]
    P[Pending Jobs Key]
    N[Next Run Time Key]
    end
    S <--> Redis
```

### Job State
Each scrapy process stores its current state in redis so that it can be restarted at the point it stoped during a deployment or if there is some other need to stop a job.  For each running spider job there is a key that tracks the pending requests (requests) for the job and another key that tracks URLs that the spider job has already seen (dupefilter) so that they are not scraped again.  As the job finsihed, the requests key gets smaller and smaller until it is empty.  When the spider job finishes, both keys are removed.  If the spider job is stopped prior to being finished the keys remain so that when the spider starts again it can use them to pick up where it left off.
```mermaid
flowchart TB
    subgraph Spider
    direction LR
    S0[Scrapy Process 0]
    S1[Scrapy Process 1]
    S2[Scrapy Process 2]
    SN[Scrapy Process N]
    end
    subgraph Redis
    direction TB
    D0[Dupefilter Key 0]
    R0[Requests Key 0]
    D1[Dupefilter Key 1]
    R1[Requests Key 1]
    D2[Dupefilter Key 2]
    R2[Requests Key 2]
    DN[Dupefilter Key N]
    RN[Requests Key N]
    end
    S0 <--> D0
    S0 <--> R0
    S1 <--> D1
    S1 <--> R1
    S2 <--> D2
    S2 <--> R2
    SN <--> DN
    SN <--> RN
```

## Output Targets
We support three output targets for our scrapy jobs.  These are specified in a `crawl-sites.json` file or as a command line argument to a scrapy or benchmark job.  The options are:

1. `csv` - This is the default and if selected will output all scraped URLs to csv files in the [output folder](../search_gov_crawler/output/)

2. `endpoint` - This is used to send links to a indexing service, such as searchgov.  All URLs will be posted to the endpoint contained in the `SPIDER_URLS_API` environment variables.

3. `elasticsearch` - This option is used to post content to an Elasticsearch host and index based on environment variable configurations.  Here, it is not just the links being captured but also the content.
