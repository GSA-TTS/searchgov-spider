# searchgov-spider
The home for the spider that supports [Search.gov](https://www.search.gov).

#### Table of contents
* [About](#about)
* [Quick Start (Docker)](#quick-start---docker)
* [Quick Start (Local)](#quick-start---local-development)
* [Entry Points](#entrypoints)
* [Signed Commits](#signed-commits)
* [Helpful Links](#helpful-links)

## About
With the move away from using Bing to provide search results for some domains, we need a solution that can index sites that were previously indexed by Bing and/or that do not have standard sitemaps.  Additionally, the Scrutiny desktop application is being run manually to provide coverage for a few dozen domains that cannot be otherwise indexed.  The spider application is our solution to both the Bing problem and the removal of manual steps.  The documentation here represents the most current state of the application and our design.

### Technologies
We currently run python 3.12.  The spider is based on the open source [scrapy](https://scrapy.org/) framework.  On top of that we use several other open source libraries and scrapy plugins.  See our [requirements file](search_gov_crawler/requirements.txt) for more details.

### Core Scrapy File Structure
*Note: Other files and directories are within the repository but the folders and files below relate to those needed for the scrapy framework.

```bash
├── search_gov_crawler              # scrapy root
│   ├── dap                         # code for handling data from DAP
│   ├── domains                     # json files with domains to scrape
│   ├── indexing                    # code related to indexing content in opensearch
│   ├── scheduling                  # code for job scheduling and storing schedules in redis
|   ├── search_gov_app              # code for communicating with the searchgov app
│   ├── search_gov_spider           # scrapy project dir
│   │   ├── extensions              # custom scrapy extensions
│   │   ├── helpers                 # common functions
│   │   ├── job_state               # code related to storing job state in redis
│   │   ├── sitemaps                # code related to indexing based on sitemap data
│   │   ├── spiders                 # all search_gov_spider spiders
│   │   │   ├── domain_spider.py    # for html pages
│   │   │   ├── domain_spider_js.py # for js pages
│   │   ├── items.py                # defines individual output of scrapes
│   │   ├── middlewares.py          # custom middleware code
│   │   ├── monitors.py             # custom spidermon monitors
│   │   ├── pipelines.py            # custom item pipelines
│   │   ├── settings.py             # settings that control all scrapy jobs
│   ├── scrapy.cfg
```

## Quick Start - Docker
Docker can be used to run spider from this repo or from [search-services](https://www.github.com/GSA/search-services).  If you want to run other SearchGov services besides spider and its dependencies, you should use the search services repo.

1. Start docker:

The spider profile must be used to start the spider and its dependencies.
```bash
docker compose --profile spider up
```

2. Watch Logs and Check Output:

The default behavior is that the `spider-scheduler` and `spider-sitemap` containers start running based on our development schedule.  It may be that no jobs are scheduled for a while so nothing will run.  Likewise, the sitemap process may not detect changes and index any documents.

If a crawl does start watch the logs for information about records loaded to Opensearch.  Then, visit [Opensearch Dashboards](http://localhost:5602) to view indexed documents.

3. Run an on-demand crawl
To direct documents from a specific domain, use the helper script to trigger an on-demand crawl.  Here the `spider crawl` command can be used as a shortcut to trigger a non-js crawl starting at `https://www.gsa.gov` and limited to pages in the `www.gsa.gov` domain.

```bash
docker compose run spider /bin/bash -c "spider crawl www.gsa.gov https://www.gsa.gov"
```


## Quick Start - Local Development

1. Install and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Add required python modules:
```bash
pip install -r requirements.txt

# required for domains that need javascript
playwright install --with-deps
playwright install chrome --force
```

3. Start Redis locally:
```bash
redis-server
```

4. Run A Spider:
```bash
cd search_gov_crawler

# to run for a non-js domain:
scrapy crawl domain_spider -a allowed_domains=quotes.toscrape.com -a start_urls=https://quotes.toscrape.com -a output_target=csv

# or to run for a js domain
scrapy crawl domain_spider_js -a allowed_domains=quotes.toscrape.com -a start_urls=https://quotes.toscrape.com/js -a output_target=csv
```

5. Check Output:

The output of this scrape is one or more csv files containing URLs in the [output directory](search_gov_crawler/output).

6. Learn More:

For more advanced usage, see the [Advanced Setup and Use Page](docs/advanced_setup_and_use.md)

## Entrypoints
* [Scrapy Scheduler](search_gov_crawler/scrapy_scheduler.py) - Process that manages and runs spider crawls based on a schedule.

* [Sitemap Monitor](search_gov_crawler/run_sitemap_monitor.py) - Process that monitors domains for changes in their sitemaps and triggers spider runs to capture changes.

* [DAP Extractor](search_gov_crawler/dap_extractor.py) - Stand-alone job that handles extracting and loading DAP visits data for use in spider crawls.

* [Benchmark](search_gov_crawler/benchmark.py) - Allows for manual testing and benchmarking using similar mechanisms as scheduled runs.

## Signed Commits

The GSA-TTS organization requires **all commits in pull requests to be cryptographically signed**. Unsigned commits will be blocked from merging.

### Option A — SSH signing (recommended)

#### 1. Generate an SSH key (skip if you already have one)

```bash
ssh-keygen -t ed25519 -C "you@example.com" -f ~/.ssh/github_signing_key
```

#### 2. Register the key as a **Signing Key** on GitHub

> ⚠️ This must be added as a *Signing Key*, not just an *Authentication Key*.

1. Go to **https://github.com/settings/ssh/new**
2. Set **Key type** to **Signing Key**
3. Paste the contents of `~/.ssh/github_signing_key.pub`

#### 3. Create the allowed signers file

```bash
echo "you@example.com $(cat ~/.ssh/github_signing_key.pub)" > ~/.ssh/allowed_signers
```

#### 4. Configure git for this repo

```bash
git config --local gpg.format ssh
git config --local user.signingkey ~/.ssh/github_signing_key
git config --local commit.gpgsign true
git config --local gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
```

Replace `--local` with `--global` to apply to all repos.

#### 5. Verify

```bash
echo "test" | ssh-keygen -Y sign -n git -f ~/.ssh/github_signing_key
```

You should see a `-----BEGIN SSH SIGNATURE-----` block.

---

### Option B — GPG signing

#### 1. Install GPG

```bash
brew install gnupg
```

#### 2. Generate a GPG key

```bash
gpg --full-generate-key
```

Choose **RSA and RSA**, key size **4096**, and enter your GitHub-verified email.

#### 3. Get your key ID

```bash
gpg --list-secret-keys --keyid-format=long
```

Copy the long key ID from the `sec` line (after `rsa4096/`).

#### 4. Export and add the key to GitHub

```bash
gpg --armor --export YOUR_KEY_ID
```

Go to **https://github.com/settings/gpg/new**, paste it, and save.

#### 5. Configure git for this repo

```bash
git config --local user.signingkey YOUR_KEY_ID
git config --local commit.gpgsign true
```

---

### IntelliJ IDEA

IntelliJ reads git's signing config automatically — no additional IDE settings needed. Commits via **Git > Commit** will be signed as long as the steps above are complete.

If IntelliJ uses a bundled git, verify it points to your system git under **Settings → Version Control → Git → Path to Git executable**.

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| `error: gpg failed to sign the data` | Run `export GPG_TTY=$(tty)` and add to your shell profile |
| Commit shows **Unverified** on GitHub | Signing key not registered on your GitHub account — see step 2/4 above |
| Commits signed locally but blocked by org | Key must be added as a **Signing Key** (not just Authentication Key) on GitHub |

## Helpful Links
* [Architecture](docs/architecture.md)

* [Advanced Setup and Use](docs/advanced_setup_and_use.md)

* [Deployments](docs/deployments.md)

* [Operations](docs/operations.md)

* [Spider Schedules and Domain Configs README](search_gov_crawler/domains/README.md)
  * [Current Production Domain List - JSON](search_gov_crawler/domains/crawl-sites-production.json)
  * [Current Production Domain List - Markdown](search_gov_crawler/domains/crawl-sites-production.md)
