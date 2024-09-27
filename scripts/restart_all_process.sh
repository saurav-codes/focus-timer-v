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
        local focus_timer_dir=$(find "$search_dir" -type d -name "focus-timer" -print -quit)
        if [ -z "$focus_timer_dir" ]; then
            echo "Error: Could not find focus-timer directory." >&2
            exit 1
        fi
        echo "$focus_timer_dir"
    fi
}

# Function to activate virtual environment
activate_venv() {
    local focus_timer_dir="$1"
    local venv_activate="$focus_timer_dir/venv/bin/activate"
    if [ ! -f "$venv_activate" ]; then
        echo "Error: Virtual environment not found at $venv_activate" >&2
        exit 1
    fi
    source "$venv_activate"
}

# Function to gracefully stop a process
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

# Function to run Django management commands
run_django_command() {
    local command="$1"
    echo "Running $command..."
    python manage.py "$command"
}

# Main script execution
main() {
    echo "Finding focus-timer directory..."
    local focus_timer_dir=$(find_focus_timer_dir)
    echo "Found focus-timer directory: $focus_timer_dir"
    cd "$focus_timer_dir" || exit 1

    echo "working directory: $focus_timer_dir"
    echo "Stopping all processes..."
    echo "-------------------------------------------------"
    echo ""
    echo "Stopping runserver..."
    stop_process "runserver"
    echo "Stopping redis_scheduler..."
    stop_process "redis_scheduler"
    echo "Stopping uvicorn..."
    stop_process "uvicorn"

    echo "Activating virtual environment..."
    activate_venv "$focus_timer_dir"

    # New: Ask user if they want to run collectstatic
    run_django_command "collectstatic --no-input"

    # New: Ask user if they want to run migrations
    read -p "Do you want to run migrations? (y/n): " run_migrations
    if [[ $run_migrations =~ ^[Yy]$ ]]; then
        run_django_command "migrate"
    fi

    run_django_command "reset_all_redis_lock"

    echo "Starting all processes..."

    echo "Starting uvicorn server..."
    nohup "$focus_timer_dir/venv/bin/uvicorn" src.asgi:application --workers 4 &

    echo "Starting Redis scheduler..."
    nohup "$focus_timer_dir/venv/bin/python" manage.py redis_scheduler &

    echo "All processes started."
}

# Set locale to UTF-8
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

# Run the main function
main
