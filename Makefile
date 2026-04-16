.PHONY: venv install schedule-format schedule-generate schedule-markdown schedule

# python setup
venv:
	. .venv/bin/activate

install:venv
	python -m pip install -r requirements.txt

# tasks related to domain config and markdown schedule
schedule-format:
	cd /Users/dself/Projects/searchgov-spider/search_gov_crawler/domains && jsonnetfmt -i *.jsonnet config/*.libsonnet

schedule-generate:
	cd /Users/dself/Projects/searchgov-spider/search_gov_crawler/domains && jsonnet -m . crawl-sites.jsonnet

schedule-markdown:install
	cd /Users/dself/Projects/searchgov-spider/search_gov_crawler/domains && python readschedule.py

schedule: schedule-format schedule-generate schedule-markdown
