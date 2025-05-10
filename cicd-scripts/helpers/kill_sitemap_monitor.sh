#!/bin/bash

# Find all process PIDs matching sitemap_monitor.py. Should only be one, but just in case
pids=$(pgrep -f "sitemap_monitor.py")

if [ -z "$pids" ]; then
    echo "No 'sitemap_monitor.py' processes found"
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
