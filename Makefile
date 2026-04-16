# this makefile assumes python is installed and a virtual environment
# is installed in either the .venv or venv directories
VENV := $(shell ls -1 -d .venv venv 2> /dev/null | head -1)
PYTHON = $(abspath $(VENV)/bin/python3)

.PHONY: project-requirements
project-requirements: $(VENV)
	$(PYTHON) -m pip install --upgrade pip && $(PYTHON) -m pip install -r requirements.txt

# tasks related to domain config and markdown schedule
.PHONY: schedule-format
schedule-format:
	cd search_gov_crawler/domains && jsonnetfmt -i *.jsonnet config/*.libsonnet

.PHONY: schedule-generate schedule-markdown schedule
schedule-generate:
	cd search_gov_crawler/domains && jsonnet -m . crawl-sites.jsonnet

.PHONY: schedule-markdown schedule
schedule-markdown: project-requirements
	cd search_gov_crawler/domains && $(PYTHON) readschedule.py

.PHONY: schedule
schedule: schedule-format schedule-generate schedule-markdown

# tasks related to testing and project maintenence
.PHONY: tests
tests: project-requirements
	$(PYTHON) -m pytest tests

.PHONY: coverage
coverage: project-requirements
	$(PYTHON) -m coverage run -m pytest tests && $(PYTHON) -m coverage html

.PHONY: ruff-format
ruff-format: project-requirements
	$(PYTHON) -m ruff format --check --config ./ruff.toml --diff .

.PHONY: ruff-check
ruff-check: project-requirements
	$(PYTHON) -m ruff check --config ./ruff.toml .

.PHONY: ruff-all
ruff-all: ruff-format ruff-check
