#!/bin/bash

# CD into the current script directory (which != $pwd)
cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && cd ../

source ./cicd-scripts/helpers/ensure_executable.sh

### FUNCTIONS ###

# stop dap extractor
stop_dap_extractor() {
    echo "Stopping dap_extractor.py (if running)..."
    run_executable "./cicd-scripts/helpers/kill_dap_extractor.sh"
}

# Stop sitemap monitor
stop_sitemap_monitor() {
    echo "Stopping run_sitemap_monitor.py (if running)..."
    run_executable "./cicd-scripts/helpers/kill_sitemap_monitor.sh"
}

# Stop freshness checker
#stop_freshness_checker() {
#    echo "Stopping check_freshness.py (if running)..."
#    ensure_executable "./cicd-scripts/helpers/kill_freshness_checker.sh"
#}

# Remove virtual environment if it exists
remove_venv() {
    echo "Removing Python virtual environment..."

    # Check if a virtual environment is active and deactivate it
    if [[ -n "${VIRTUAL_ENV:-}" ]] && type deactivate >/dev/null 2>&1; then
        deactivate
    fi

    if [ -n "${VIRTUAL_ENV:-}" ] && [ -d "$VIRTUAL_ENV" ]; then
        rm -rf "$VIRTUAL_ENV"
    fi

    if [ -d "venv" ]; then
        rm -rf "venv"
    fi
}

# Purge pip cache
purge_pip_cache() {
    echo "Purging pip cache..."
    rm -rf ~/.cache/pip
}

# Stop freshness checker
stop_freshness_checker() {
    echo "Stopping check_freshness.py (if running)..."
    run_executable "./cicd-scripts/helpers/kill_freshness_checker.sh"
}

# Stop scrapy scheduler if running
stop_scrapy_scheduler() {
    echo "Stopping scrapy_scheduler.py (if running)..."
    run_executable "./cicd-scripts/helpers/kill_scheduler.sh"
}

# Display remaining scrapy processes
display_remaining_scrapy_processes() {
    echo -e "\nRemaining scrapy processes (if any):"
    ps -ef | grep scrapy | grep -v grep || echo "No scrapy processes running."
}

# Force kill any remaining scrapy background jobs
kill_remaining_scrapy_jobs() {
    echo "Force killing remaining scrapy background jobs..."

    local SCRAPY_PIDS=$(ps aux | grep -ie [s]crapy | awk '{print $2}')
    if [ -n "$SCRAPY_PIDS" ]; then
        echo "Sending SIGINT to scrapy PIDs: $SCRAPY_PIDS"
        echo $SCRAPY_PIDS | xargs kill -SIGINT
        sleep 5
        # Force kill any that survived SIGINT
        local REMAINING=$(ps aux | grep -ie [s]crapy | awk '{print $2}')
        if [ -n "$REMAINING" ]; then
            echo "Force killing with SIGKILL (PIDs survived SIGINT): $REMAINING"
            echo $REMAINING | xargs kill -9
        else
            echo "All scrapy jobs terminated after SIGINT."
        fi
    else
        echo "No remaining scrapy jobs to kill."
    fi
}

# Remove nohup jobs (python scripts)
remove_nohup_jobs() {
    echo "Removing nohup jobs (python)..."
    local nohup_pids
    local scheduler_pids

    nohup_pids=$(pgrep -f "nohup.*python" || true)
    if [ -n "$nohup_pids" ]; then
        echo "$nohup_pids" | xargs --no-run-if-empty kill -SIGINT
    else
        echo "No nohup python jobs found."
    fi

    scheduler_pids=$(pgrep -f "scrapy_scheduler" || true)
    if [ -n "$scheduler_pids" ]; then
        echo "$scheduler_pids" | xargs --no-run-if-empty kill -SIGINT
    else
        echo "No scrapy_scheduler jobs found."
    fi
}

# Remove cron job entries referencing the given string
remove_cron_entry() {
    if [ -z "$1" ]; then
        echo "Error: No cron entry provided."
        return
    fi

    local CRON_ENTRY="$1"
    local CRON_USER=$(whoami)

    echo "Removing cron job entries referencing: $CRON_ENTRY"

    # Remove cron job for the current user (including the full path if needed)
    local current_crontab
    current_crontab=$(sudo crontab -l -u "$CRON_USER" 2>/dev/null || true)

    if [ -z "$current_crontab" ]; then
        echo "No cron jobs found for '$CRON_USER'."
        return 0
    fi

    printf '%s\n' "$current_crontab" | grep -v -F "$CRON_ENTRY" | sudo crontab -u "$CRON_USER" - || true

    echo "Cron job entries for '$CRON_ENTRY' removed."
}

### SCRIPT EXECUTION ###

# Stop DAP Extractor
stop_dap_extractor

# Stop sitemap monitoring
stop_sitemap_monitor

# Remove virtual environment
remove_venv

# Purge pip cache
purge_pip_cache

# Stop freshness checker
stop_freshness_checker

# Stop scrapy scheduler if running
stop_scrapy_scheduler

# Display remaining scrapy processes (if any)
display_remaining_scrapy_processes

# Force kill any remaining scrapy background jobs
kill_remaining_scrapy_jobs

# Remove nohup jobs (python)
remove_nohup_jobs

# Remove specific cron jobs
remove_cron_entry "check_cloudwatch.sh"
remove_cron_entry "check_codedeploy.sh"
remove_cron_entry "check_ssm.sh"
remove_cron_entry "app_start.sh"

echo "App stop completed successfully."
