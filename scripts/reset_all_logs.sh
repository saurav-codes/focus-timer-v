#!/bin/bash

set -e

# Function to find the focus-timer directory
find_focus_timer_dir() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS-specific path
        # since mac is my local machine, i know the path
        echo "/Users/sauravsharma/Developer/personal/startups/focus_timer"
    else
        # Linux path finding logic
        local search_dir="$HOME"
        local focus_timer_dir=$(find "$search_dir" -type d -name "focus-timer-v" -print -quit)
        if [ -z "$focus_timer_dir" ]; then
            echo "Error: Could not find focus-timer-v directory." >&2
            exit 1
        fi
        echo "$focus_timer_dir"
    fi
}

focus_timer_dir=$(find_focus_timer_dir)

# reset all the logs in logs/

echo "Resetting all the logs in logs/"
echo "" > $focus_timer_dir/logs/django.log
echo "" > $focus_timer_dir/logs/nginx-access.log
echo "" > $focus_timer_dir/logs/nginx-error.log
echo "" > $focus_timer_dir/logs/redis_scheduler.log
echo "✨ All logs have been successfully cleared! ✨"
