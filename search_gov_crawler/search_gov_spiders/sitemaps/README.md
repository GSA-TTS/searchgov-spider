# Spider Sitemap Monitoring

## Generate a CSV list of sitemaps for **ALL** production URLs in `CRAWL_SITES_FILE`
```bash
# Prep
python -m venv venv
. venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r ./search_gov_crawler/requirements.txt

# Create the all_production_sitemaps.csv file
python search_gov_crawler/search_gov_spiders/sitemaps/sitemap_finder.py
```
