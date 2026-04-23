#!/bin/bash

# Function to ensure a file exists, is executable, and then runs it
ensure_executable() {
  local script="$1"

  if [ -f "$script" ]; then
    sudo chmod +x "$script"
    sudo chown -R "$(whoami)" "$script"
    echo "$script is now executable."
    source "$script"
  else
    echo "Error: $script not found!"
    return 1
  fi
}
