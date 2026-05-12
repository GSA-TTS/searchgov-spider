#!/bin/bash

set -euo pipefail

SSM_SERVICE_NAME="amazon-ssm-agent"
SSM_SNAP_SERVICE_NAME="snap.amazon-ssm-agent.amazon-ssm-agent.service"

is_ssm_active() {
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl is-active --quiet "${SSM_SERVICE_NAME}"; then
            return 0
        fi

        if systemctl is-active --quiet "${SSM_SNAP_SERVICE_NAME}"; then
            return 0
        fi
    fi

    pgrep -f "amazon-ssm-agent" >/dev/null 2>&1
}

# Function to start the service using systemctl or service
_start_ssm() {
    if command -v systemctl >/dev/null 2>&1; then
        echo "Attempting to start ${SSM_SERVICE_NAME} with systemctl..."
        if sudo systemctl start "${SSM_SERVICE_NAME}" 2>/dev/null; then
            return 0
        fi

        echo "Falling back to snap-managed SSM service..."
        if sudo systemctl start "${SSM_SNAP_SERVICE_NAME}" 2>/dev/null; then
            return 0
        fi

        # Both systemctl attempts failed — check if agent is already running via snap/pgrep
        if pgrep -f "amazon-ssm-agent" >/dev/null 2>&1; then
            echo "SSM agent is already running (snap-managed). No action needed."
            return 0
        fi

        echo "SSM agent not found after all start attempts."
        return 1
    else
        echo "systemctl not available; attempting to start ${SSM_SERVICE_NAME} with service..."
        sudo service "${SSM_SERVICE_NAME}" start
        return $?
    fi
}

# Function to check if SSM agent is running
check_ssm() {
    # Prefer systemctl check if available
    if command -v systemctl >/dev/null 2>&1; then
        if ! is_ssm_active; then
            echo "AWS SSM Agent (${SSM_SERVICE_NAME}) is not active. Starting it now..."
            if _start_ssm; then
                echo "AWS SSM Agent started successfully (systemctl)."
            else
                echo "Failed to start AWS SSM Agent via systemctl."
                return 1
            fi
        else
            echo "AWS SSM Agent (${SSM_SERVICE_NAME}) is active."
        fi
    else
        # Fallback to pgrep check if systemctl is not present
        if ! is_ssm_active; then
            echo "AWS SSM Agent process not found. Starting it now..."
            if _start_ssm; then
                echo "AWS SSM Agent started successfully (service)."
            else
                echo "Failed to start AWS SSM Agent via service."
                return 1
            fi
        else
            echo "AWS SSM Agent process is running."
        fi
    fi

    return 0
}

# Setup SSM monitoring cron jobs for reboot and hourly
setup_ssm_cron() {
    echo "Setting up SSM monitoring cron jobs..."

    local SSM_SCRIPT_PATH="$(pwd)/cicd-scripts/helpers/check_ssm.sh"

    # Verify the script exists
    if [ ! -f "$SSM_SCRIPT_PATH" ]; then
        echo "Error: check_ssm.sh not found at $SSM_SCRIPT_PATH"
        return 1
    fi

    echo "Making $SSM_SCRIPT_PATH executable..."
    chmod +x "$SSM_SCRIPT_PATH"

    # Define cron entries
    local REBOOT_CRON_ENTRY="@reboot $SSM_SCRIPT_PATH"
    local HOURLY_CRON_ENTRY="0 * * * * $SSM_SCRIPT_PATH"

    echo "Removing any existing crontab entries for check_ssm.sh..."
    # Remove all existing crontab entries that contain "check_ssm.sh"
    (crontab -l 2>/dev/null | grep -v -F "check_ssm.sh") | crontab - || true

    echo "Adding new SSM monitoring cron jobs..."
    # Add both new cron entries
    (crontab -l 2>/dev/null; echo "$REBOOT_CRON_ENTRY"; echo "$HOURLY_CRON_ENTRY") | crontab -

    if [ $? -eq 0 ]; then
        echo "SSM cron jobs added successfully:"
        echo "  - Reboot execution: $REBOOT_CRON_ENTRY"
        echo "  - Hourly execution: $HOURLY_CRON_ENTRY"

        echo "Current SSM crontab entries:"
        crontab -l | grep "check_ssm.sh" | sed 's/^/  /' || echo "  (none listed)"
        return 0
    else
        echo "Failed to add the following SSM cron jobs:"
        echo "  - Reboot: $REBOOT_CRON_ENTRY"
        echo "  - Hourly: $HOURLY_CRON_ENTRY"
        return 1
    fi
}

# Execute the function
check_ssm
