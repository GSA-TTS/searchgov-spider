#!/bin/bash

# Function to check if CodeDeploy agent is running
check_codedeploy() {
    if ! pgrep -f codedeploy-agent > /dev/null; then
        echo "AWS CodeDeploy agent is not running. Starting it now..."
        sudo service codedeploy-agent start
        if [ $? -eq 0 ]; then
            echo "AWS CodeDeploy agent started successfully."
        else
            echo "Failed to start AWS CodeDeploy agent."
        fi
    else
        echo "AWS CodeDeploy agent is running."
    fi
}

# Setup CodeDeploy monitoring cron jobs for reboot and hourly
setup_codedeploy_cron() {
    echo "Setting up CodeDeploy monitoring cron jobs..."
    
    # Define the script path
    local CODEDEPLOY_SCRIPT_PATH="$(pwd)/cicd-scripts/helpers/check_codedeploy.sh"
    
    # Verify the script exists
    if [ ! -f "$CODEDEPLOY_SCRIPT_PATH" ]; then
        echo "Error: check_codedeploy.sh not found at $CODEDEPLOY_SCRIPT_PATH"
        return 1
    fi
    
    # Make the script executable
    # NOTE: This might be redundant since app_install.sh already does this (with a relative path)
    echo "Making check_codedeploy.sh executable..."
    chmod +x "$CODEDEPLOY_SCRIPT_PATH"
    
    # Define cron entries
    local REBOOT_CRON_ENTRY="@reboot $CODEDEPLOY_SCRIPT_PATH"
    local HOURLY_CRON_ENTRY="0 * * * * $CODEDEPLOY_SCRIPT_PATH"
    
    echo "Removing any existing crontab entries for check_codedeploy.sh..."
    # Remove all existing crontab entries that contain "check_codedeploy.sh"
    (crontab -l 2>/dev/null | grep -v -F "check_codedeploy.sh") | crontab -
    
    echo "Adding new CodeDeploy monitoring cron jobs..."
    # Add both new cron entries
    (crontab -l 2>/dev/null; echo "$REBOOT_CRON_ENTRY"; echo "$HOURLY_CRON_ENTRY") | crontab -
    
    if [ $? -eq 0 ]; then
        echo "CodeDeploy cron jobs added successfully:"
        echo "  - Reboot execution: $REBOOT_CRON_ENTRY"
        echo "  - Hourly execution: $HOURLY_CRON_ENTRY"
        
        echo "Current CodeDeploy crontab entries:"
        crontab -l | grep "check_codedeploy.sh" | sed 's/^/  /'
        return 0
    else
        echo "Failed to add the following CodeDeploy cron jobs:"
        echo "  - Reboot: $REBOOT_CRON_ENTRY"
        echo "  - Hourly: $HOURLY_CRON_ENTRY"
        return 1
    fi
}

# Execute the function
check_codedeploy
