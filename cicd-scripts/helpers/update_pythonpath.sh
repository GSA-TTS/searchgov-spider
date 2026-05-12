#!/bin/bash

# Define the current directory
CURRENT_DIR=$(pwd)

# Define the .profile file location.  The .profile is used here because it is sourced
# for non-interactive shells, which is what the codedeploy agent uses to run things.
PROFILE=$HOME/.profile

# Ensure the profile exists before grepping or sourcing it.
touch "$PROFILE"

# Check if .profile contains an export PYTHONPATH line
if grep -q "^export PYTHONPATH=" "$PROFILE"; then
    # Extract the existing PYTHONPATH line
    PYTHONPATH_LINE=$(grep "^export PYTHONPATH=" "$PROFILE")

    # Construct the updated PYTHONPATH line
    UPDATED_LINE="export PYTHONPATH=${CURRENT_DIR}"

    # Update the .profile file
    sed -i "s|^export PYTHONPATH=.*|$UPDATED_LINE|" "$PROFILE"
    echo "Updated PYTHONPATH to include the current directory: $CURRENT_DIR"
else
    # Add a new export PYTHONPATH line to .profile
    echo "export PYTHONPATH=${CURRENT_DIR}" >> "$PROFILE"
    echo "Added new PYTHONPATH to .profile including the current directory: $CURRENT_DIR"
fi

# Apply changes for the current session
source "$PROFILE"

# Check that PYTHONPATH has been applied
if [ -n "${PYTHONPATH:-}" ]; then
    echo "PYTHONPATH changes applied: ${PYTHONPATH}"
else
    echo "ERROR: Could not apply PYTHONPATH changes"
    exit 2
fi
