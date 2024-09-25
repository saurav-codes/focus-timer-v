#!/bin/bash

stop_process() {
    local process_name="$1"
    echo "Stopping $process_name..."
    ps aux | awk -v pname="$process_name" '$0 ~ pname && !/awk/ {print $2}' | xargs kill -TERM 2>/dev/null || true
    sleep 2
    if ps aux | awk -v pname="$process_name" '$0 ~ pname && !/awk/ {exit 1}'; then
        echo "Force stopping $process_name..."
        ps aux | awk -v pname="$process_name" '$0 ~ pname && !/awk/ {print $2}' | xargs kill -KILL 2>/dev/null || true
    fi
}

echo "Stopping all processes..."
echo "-------------------------------------------------"
echo ""
echo "Stopping runserver..."
stop_process "runserver"
echo "Stopping redis_scheduler..."
stop_process "redis_scheduler"
echo "Stopping uvicorn..."
stop_process "uvicorn"
echo "-------------------------------------------------"
