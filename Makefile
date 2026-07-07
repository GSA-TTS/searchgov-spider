# --- Configuration & Variables ---

# Python Environment
VENV := $(shell ls -1 -d .venv venv 2> /dev/null | head -1)
PYTHON := $(abspath $(VENV)/bin/python3)

# Docker Configuration
IMAGE_NAME := searchgov-spider
DOCKERFILE := DockerFile.dev
ENV_FILE := .env.development
VOLUME_PROJECT_ROOT := $(PWD):/usr/src/searchgov-spider
CRAWLER_DIR := /usr/src/searchgov-spider/search_gov_crawler

# Container Names
SCRAPY_SCHEDULER_CONTAINER := spider-scrapy-scheduler
SITEMAP_MONITOR_CONTAINER := spider-sitemap-monitor

# --- Setup & Maintenance ---

.PHONY: project-requirements
project-requirements:
	@if [ -z "$(VENV)" ]; then echo "Error: Virtual environment (.venv or venv) not found."; exit 1; fi
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# --- Schedule Management ---

.PHONY: schedule-format
schedule-format:
	cd search_gov_crawler/domains && jsonnetfmt -i *.jsonnet config/*.libsonnet

.PHONY: schedule-generate
schedule-generate:
	cd search_gov_crawler/domains && jsonnet -m . crawl-sites.jsonnet

.PHONY: schedule-markdown
schedule-markdown: project-requirements
	cd search_gov_crawler/domains && $(PYTHON) readschedule.py

.PHONY: schedule
schedule: schedule-format schedule-generate schedule-markdown

# --- Testing & Quality Assurance ---

.PHONY: tests
tests: project-requirements
	$(PYTHON) -m pytest tests

.PHONY: coverage
coverage: project-requirements
	$(PYTHON) -m coverage run -m pytest tests
	$(PYTHON) -m coverage html

.PHONY: ruff-format
ruff-format: project-requirements
	$(PYTHON) -m ruff format --check --config ./ruff.toml --diff .

.PHONY: ruff-check
ruff-check: project-requirements
	$(PYTHON) -m ruff check --config ./ruff.toml .

.PHONY: ruff-all
ruff-all: ruff-format ruff-check

# --- Docker Operations ---

.PHONY: docker-build
docker-build: docker-remove-containers
	docker build -f $(DOCKERFILE) -t $(IMAGE_NAME) .

.PHONY: docker-remove-containers
docker-remove-containers:
	docker rm -f $(SCRAPY_SCHEDULER_CONTAINER) $(SITEMAP_MONITOR_CONTAINER) 2>/dev/null || true

.PHONY: docker-run-bash
docker-run-bash:
	@if [ "$(name)" ]; then \
        echo "Entering named container: $(name)"; \
		docker exec -it $(name) /bin/bash; \
	else \
	    echo "Entering a temporary container..."; \
		docker run -it --rm --env-file $(ENV_FILE) --network host --volume $(VOLUME_PROJECT_ROOT) $(IMAGE_NAME) /bin/bash; \
	fi

.PHONY: docker-run-scrapy-scheduler
docker-run-scrapy-scheduler:
	@if [ $$(docker ps -aq -f name=$(SCRAPY_SCHEDULER_CONTAINER)) ]; then \
		echo "Starting existing container: $(SCRAPY_SCHEDULER_CONTAINER)"; \
		docker start -ai $(SCRAPY_SCHEDULER_CONTAINER); \
	else \
		echo "Running new container: $(SCRAPY_SCHEDULER_CONTAINER)"; \
		docker run -it --name $(SCRAPY_SCHEDULER_CONTAINER) --env-file $(ENV_FILE) --network host \
			--volume $(VOLUME_PROJECT_ROOT) $(IMAGE_NAME) python $(CRAWLER_DIR)/scrapy_scheduler.py; \
	fi

.PHONY: docker-run-sitemap-monitor
docker-run-sitemap-monitor:
	@if [ $$(docker ps -aq -f name=$(SITEMAP_MONITOR_CONTAINER)) ]; then \
		echo "Starting existing container: $(SITEMAP_MONITOR_CONTAINER)"; \
		docker start -ai $(SITEMAP_MONITOR_CONTAINER); \
	else \
		echo "Running new container: $(SITEMAP_MONITOR_CONTAINER)"; \
		docker run -it --name $(SITEMAP_MONITOR_CONTAINER) --env-file $(ENV_FILE) --network host \
			--volume $(VOLUME_PROJECT_ROOT) -w $(CRAWLER_DIR) $(IMAGE_NAME) python run_sitemap_monitor.py; \
	fi

.PHONY: docker-scrapy-crawl
docker-scrapy-crawl:
	docker run -it --rm --env-file $(ENV_FILE) --network host --volume $(VOLUME_PROJECT_ROOT) \
	    -w $(CRAWLER_DIR) $(IMAGE_NAME) scrapy crawl $(ARGS)
