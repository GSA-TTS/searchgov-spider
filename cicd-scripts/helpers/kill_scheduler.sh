#!/bin/bash

# Find the process ID of the running scrapy_scheduler.py script
echo "Searching for scrapy_scheduler.py process..."
PROCESS_ID=$(pgrep -f "scrapy_scheduler.py")

# Check if the process ID was found
if [ -n "$PROCESS_ID" ]; then
  echo "Found scrapy_scheduler.py process with PID: $PROCESS_ID"

  # Kill the process
  echo "Killing process with PID: $PROCESS_ID"
  kill "$PROCESS_ID" 2>/dev/null

  # Pause to allow the process to terminate
  sleep 3

  # Verify if the process was killed
  if ! kill -0 "$PROCESS_ID" 2>/dev/null; then
    echo "Process scrapy_scheduler.py (PID: $PROCESS_ID) has been terminated."
  else
    echo "Failed to terminate the process or process no longer exists."
  fi
fi
