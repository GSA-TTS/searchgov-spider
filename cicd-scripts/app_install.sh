#!/bin/bash

set -euo pipefail

# CD into the current script directory (which != $pwd)
cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && cd ../

sudo chmod +x ./cicd-scripts/helpers/ensure_executable.sh
source ./cicd-scripts/helpers/ensure_executable.sh

### VARIABLES ###
_CURRENT_BUILD_DIR=${PWD}
VENV_DIR=./venv
VENV_PYTHON="${VENV_DIR}/bin/python"
CURRENT_STEP="initialization"

### LOGGING ###

log_step() {
    echo
    echo "==> $1"
}

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

on_error() {
    local exit_code=$?
    local line_number=$1
    local failed_command=${2:-unknown}
    log_error "Step '${CURRENT_STEP}' failed at line ${line_number}."
    log_error "Command: ${failed_command}"
    exit "${exit_code}"
}

trap 'on_error "${LINENO}" "${BASH_COMMAND}"' ERR

### FUNCTIONS ###

run_step() {
    local step_name="$1"
    shift

    CURRENT_STEP="${step_name}"
    log_step "${step_name}"
    "$@"
    log_info "Completed: ${step_name}"
}

# Stop spider services
stop_services() {
    log_info "Running app_stop.sh..."
    ensure_executable "./cicd-scripts/app_stop.sh"
}

# Verify Python 3.12 is available (installed by Ansible during host provisioning)
check_python() {
    log_info "Verifying Python 3.12..."
    if ! command -v python3.12 &>/dev/null; then
        log_error "Python 3.12 not found. Ensure the Ansible spider playbook has run on this host."
        exit 1
    fi
    log_info "Python version: $(python3.12 --version)"
}

# Fetch environment variables from parameter store
fetch_env_vars() {
    log_info "Fetching environment variables..."
    ensure_executable "./cicd-scripts/helpers/fetch_env_vars.sh"
}

# Set environment paths
update_pythonpath() {
    log_info "Updating PYTHONPATH..."
    ensure_executable "./cicd-scripts/helpers/update_pythonpath.sh"
}

# Setup virtual environment
setup_virtualenv() {
    log_info "Setting up virtual environment..."
    rm -rf "$VENV_DIR"

    log_info "Creating venv with python3.12..."
    python3.12 -m venv "$VENV_DIR"

    if [ ! -x "$VENV_PYTHON" ]; then
        log_error "Venv creation failed"
        exit 1
    fi

    "$VENV_PYTHON" -m pip install --upgrade pip
}

# Install dependencies
install_dependencies() {
    log_info "Installing Python dependencies..."
    "$VENV_PYTHON" -m pip install --upgrade -r ./search_gov_crawler/requirements.txt
    log_info "Installing Playwright browser dependencies..."
    "$VENV_PYTHON" -m playwright install --with-deps
    log_info "Installing Playwright Chrome..."
    "$VENV_PYTHON" -m playwright install chrome --force
}

# Install NLTK (for text)
install_nltk() {
    log_info "Installing NLTK assets..."
    "$VENV_PYTHON" ./search_gov_crawler/indexing/install_nltk.py
}

# Configure permissions
configure_permissions() {
    log_info "Configuring file permissions..."
    sudo chmod -R 777 .
    sudo chown -R "$(whoami)" .
    sudo setfacl -Rdm g:dgsearch:rwx .
}

# Manage cron jobs
add_start_script_cron_job() {
    log_info "Adding app_start.sh cron job..."
    local app_start_script="app_start.sh"
    local start_script_path="$(pwd)/cicd-scripts/$app_start_script"

    chmod +x "$start_script_path"
    sudo chown -R $(whoami) "$start_script_path"

    # Remove any existing app_start.sh cron jobs
    if ! (crontab -l 2>/dev/null | grep -v -F "$app_start_script") | crontab -; then
        log_info "Warning: Could not remove existing $app_start_script cron jobs"
    fi

    # Add the new app_start.sh cron job
    if (crontab -l 2>/dev/null; echo "@reboot $start_script_path") | crontab -; then
        log_info "Added $app_start_script cron job successfully:"
        crontab -l | grep "$app_start_script" | sed 's/^/  /'
    else
        log_error "Failed to add $app_start_script cron job for: $start_script_path"
    fi
}

# Start monitoring agents
start_agents() {
    log_info "Starting AWS CloudWatch agent..."
    ensure_executable "./cicd-scripts/helpers/check_cloudwatch.sh"
    setup_cloudwatch_cron

    log_info "Starting AWS CodeDeploy agent..."
    ensure_executable "./cicd-scripts/helpers/check_codedeploy.sh"
    setup_codedeploy_cron

    log_info "Starting AWS SSM agent..."
    ensure_executable "./cicd-scripts/helpers/check_ssm.sh"
    setup_ssm_cron
}

### SCRIPT EXECUTION ###

run_step "Stop running services" stop_services
run_step "Fetch and export environment variables" fetch_env_vars
run_step "Check Python prerequisites" check_python
run_step "Set environment paths" update_pythonpath
run_step "Configure file permissions" configure_permissions
run_step "Create virtual environment" setup_virtualenv
run_step "Install application dependencies" install_dependencies
run_step "Install NLTK data" install_nltk
run_step "Start AWS agents" start_agents
run_step "Configure startup cron job" add_start_script_cron_job

CURRENT_STEP="completed"
log_info "App installation completed successfully."
