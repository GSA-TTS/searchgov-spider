#!/bin/bash

# Setup high-level variables
# run_sitemap_monitor.py needs to be started from search_gov_crawler because that's where the scrapy.cfg is
LOG_FILE=/var/log/scrapy_scheduler.log
SCHEDULER_SCRIPT=search_gov_crawler/scrapy_scheduler.py
SITEMAP_SCRIPT=run_sitemap_monitor.py
SITEMAP_DIR=/var/tmp/spider_sitemaps
DAP_SCRIPT=search_gov_crawler/dap_extractor.py

# ensure profile vars and log file are configured
source ~/.profile
sudo touch $LOG_FILE
sudo chown -R $(whoami) $LOG_FILE

# Remove existing sitemap directory (if it exists)
if [ -d "$SITEMAP_DIR" ]; then
    sudo rm -rf "$SITEMAP_DIR"
fi

# Recreate directory and set ownership
sudo mkdir -p "$SITEMAP_DIR"
sudo chown -R "$(whoami)" "$SITEMAP_DIR"

# CD into the current script directory (which != $pwd)
cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && cd ../

# start sitemap monitor
nohup bash -c "source ./venv/bin/activate && cd ./search_gov_crawler && python $SITEMAP_SCRIPT" >> $LOG_FILE 2>&1 &

# start dap extractor
nohup bash -c "source ./venv/bin/activate && ./venv/bin/python ./$DAP_SCRIPT" >> $LOG_FILE 2>&1 &

# Start scheduler
nohup bash -c "source ./venv/bin/activate && ./venv/bin/python ./$SCHEDULER_SCRIPT" >> $LOG_FILE 2>&1 &

# check that scheduler is running before exit, it not raise error
if [[ -n $(pgrep -f "scrapy_scheduler.py") ]]; then
    echo "App start completed successfully."
else
    echo "ERROR: Could not start scrapy_scheduler.py. See log file for details."
    exit 1
fi
