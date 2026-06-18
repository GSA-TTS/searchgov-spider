#!/bin/bash

# Ensures a file exists, is executable, then sources it into the current shell.
# Use for scripts that set environment variables or define functions needed in the caller.
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

# Ensures a file exists, is executable, then runs it in a subprocess.
# Use for standalone scripts that do not need to share the current shell environment.
run_executable() {
  local script="$1"

  if [ -f "$script" ]; then
    sudo chmod +x "$script"
    sudo chown -R "$(whoami)" "$script"
    echo "$script is now executable."
    bash "$script"
  else
    echo "Error: $script not found!"
    return 1
  fi
}
