#!/bin/bash

# Function to check if CloudWatch agent is running
check_cloudwatch() {
    if ! pgrep -f amazon-cloudwatch-agent > /dev/null; then
        echo "AWS CloudWatch agent is not running. Starting it now..."
        sudo service amazon-cloudwatch-agent start
        if [ $? -eq 0 ]; then
            echo "AWS CloudWatch agent started successfully."
        else
            echo "Failed to start AWS CloudWatch agent."
        fi
    else
        echo "AWS CloudWatch agent is running."
    fi
}

# Setup CloudWatch monitoring cron jobs for reboot and hourly
setup_cloudwatch_cron() {
    echo "Setting up CloudWatch monitoring cron jobs..."
    
    # Define the script path
    local CLOUDWATCH_SCRIPT_PATH="$(pwd)/cicd-scripts/helpers/check_cloudwatch.sh"
    
    # Verify the script exists
    if [ ! -f "$CLOUDWATCH_SCRIPT_PATH" ]; then
        echo "Error: check_cloudwatch.sh not found at $CLOUDWATCH_SCRIPT_PATH"
        return 1
    fi
    
    # Make the script executable
    # NOTE: This might be redundant since app_install.sh already does this (with a relative path)
    echo "Making check_cloudwatch.sh executable..."
    chmod +x "$CLOUDWATCH_SCRIPT_PATH"
    
    # Define cron entries
    local REBOOT_CRON_ENTRY="@reboot $CLOUDWATCH_SCRIPT_PATH"
    local HOURLY_CRON_ENTRY="0 * * * * $CLOUDWATCH_SCRIPT_PATH"
    
    echo "Removing any existing crontab entries for check_cloudwatch.sh..."
    # Remove all existing crontab entries that contain "check_cloudwatch.sh"
    (crontab -l 2>/dev/null | grep -v -F "check_cloudwatch.sh") | crontab - || true
    
    echo "Adding new CloudWatch monitoring cron jobs..."
    # Add both new cron entries
    (crontab -l 2>/dev/null; echo "$REBOOT_CRON_ENTRY"; echo "$HOURLY_CRON_ENTRY") | crontab -
    
    if [ $? -eq 0 ]; then
        echo "CloudWatch cron jobs added successfully:"
        echo "  - Reboot execution: $REBOOT_CRON_ENTRY"
        echo "  - Hourly execution: $HOURLY_CRON_ENTRY"
        
        echo "Current CloudWatch crontab entries:"
        crontab -l | grep "check_cloudwatch.sh" | sed 's/^/  /'
        return 0
    else
        echo "Failed to add the following CloudWatch cron jobs:"
        echo "  - Reboot: $REBOOT_CRON_ENTRY"
        echo "  - Hourly: $HOURLY_CRON_ENTRY"
        return 1
    fi
}

# Execute the function
check_cloudwatch
