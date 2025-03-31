#!/bin/bash

# CD into the current script directory (which != $pwd)
cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && cd ../

LOG_FILE=/var/log/scrapy_scheduler.log
START_SCRIPT=search_gov_crawler/scrapy_scheduler.py

source ~/.profile

# Run the script in the background using the virtual environment
sudo chmod +x ./$START_SCRIPT

sudo touch $LOG_FILE
sudo chown -R $(whoami) $LOG_FILE

echo PYTHONPATH is $PYTHONPATH

nohup bash -c "source ./venv/bin/activate && ./venv/bin/python ./$START_SCRIPT" >> $LOG_FILE 2>&1 &

# check that scheduler is running before exit, it not raise error
if [[ -n $(pgrep -f "scrapy_scheduler.py") ]]; then
    echo "App start completed successfully."
else
    echo "ERROR: Could not start scrapy_scheduler.py. See log file for details."
    exit 1
fi
