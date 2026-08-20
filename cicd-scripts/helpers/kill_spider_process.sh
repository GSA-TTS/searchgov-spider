#!/bin/bash
# Check if a filename argument is provided
if [ -z "$1" ]; then
    echo "Usage: kill_spider_process.sh <filename>"
    return 1
fi

filename="$1"

# Find all process PIDs matching filenam. Should only be one, but just in case
pids=$(pgrep -f $filename)

if [ -z "$pids" ]; then
    echo "No '${filename}' processes found"
else
    for pid in $pids; do
        echo "Sending SIGTERM to process $pid"
        # Send SIGTERM for graceful termination
        kill $pid
        sleep 5
        if kill -0 $pid 2>/dev/null; then
            echo "Process $pid still running, sending SIGKILL"
            # Force kill with SIGKILL if still running
            kill -9 $pid
            if kill -0 $pid 2>/dev/null; then
                echo "Failed to kill process $pid even with SIGKILL"
            else
                echo "Process $pid killed with SIGKILL"
            fi
        else
            echo "Process $pid terminated gracefully"
        fi
    done
fi
