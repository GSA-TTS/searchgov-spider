#!/bin/bash

# CD into the current script directory (which != $pwd)
cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && cd ../

LOG_FILE=/var/log/scrapy_scheduler.log
START_SCRIPT=search_gov_crawler/scrapy_scheduler.py

source ~/.profile
sudo touch $LOG_FILE
sudo chown -R $(whoami) $LOG_FILE

# Start sitemap monitor
SITEMAP_SCRIPT=search_gov_crawler/search_gov_spiders/sitemaps/sitemap_monitor.py
SITEMAP_LOG_FILE=/var/log/scrapy_sitemap_monitor.log
SITEMAP_DIR=/var/tmp/spider_sitemaps

sudo touch $SITEMAP_LOG_FILE
sudo chown -R $(whoami) $SITEMAP_LOG_FILE

# Remove existing sitemap directory (if it exists)
if [ -d "$SITEMAP_DIR" ]; then
    sudo rm -rf "$SITEMAP_DIR"
fi

# Recreate directory and set ownership
sudo mkdir -p "$SITEMAP_DIR"
sudo chown -R "$(whoami)" "$SITEMAP_DIR"
nohup bash -c "source ./venv/bin/activate && ./venv/bin/python ./$SITEMAP_SCRIPT" >> $SITEMAP_LOG_FILE 2>&1 &

# Start scheduler
nohup bash -c "source ./venv/bin/activate && ./venv/bin/python ./$START_SCRIPT" >> $LOG_FILE 2>&1 &

# check that scheduler is running before exit, it not raise error
if [[ -n $(pgrep -f "scrapy_scheduler.py") ]]; then
    echo "App start completed successfully."
else
    echo "ERROR: Could not start scrapy_scheduler.py. See log file for details."
    exit 1
fi
