#!/bin/bash

# Define a function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  start       Start the server in the foreground"
    echo "  start-bg    Start the server in the background"
    echo "  stop        Stop a running server"
    echo "  status      Check if the server is running"
    echo "  restart     Restart the server (stop if running, then start)"
    echo "  test        Run the test client against the server"
    echo "  --debug     Enable debug logging (with start, start-bg, or test)"
    echo "  --help      Show this help message"
}

# Parse arguments
ACTION="start"
DEBUG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        start|start-bg|stop|status|restart|test)
            ACTION="$1"
            shift
            ;;
        --debug)
            DEBUG="--debug"
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Get the script directory (should be project root)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the project root directory
cd "$SCRIPT_DIR"

# Path to the Python script
SERVER_SCRIPT="src/cve_mcp/streamable_server.py"

# Function to start the server
start_server() {
    local mode="$1"
    
    if [ "$mode" = "background" ]; then
        echo "Starting CVE MCP Server in the background..."
        python "$SERVER_SCRIPT" --background $DEBUG
    else
        echo "Starting CVE MCP Server in the foreground..."
        python "$SERVER_SCRIPT" $DEBUG
    fi
}

# Function to stop the server
stop_server() {
    echo "Stopping CVE MCP Server..."
    python "$SERVER_SCRIPT" --stop
}

# Function to check server status
check_status() {
    python "$SERVER_SCRIPT" --status
}

# Function to run the test client
run_test_client() {
    echo "Running test client against CVE MCP Server..."
    DEBUG_FLAG=""
    if [ -n "$DEBUG" ]; then
        DEBUG_FLAG="--debug"
    fi
    python test_streamable_mcp_client.py $DEBUG_FLAG
}

# Main logic based on action
case $ACTION in
    start)
        start_server "foreground"
        ;;
    start-bg)
        start_server "background"
        ;;
    stop)
        stop_server
        ;;
    status)
        check_status
        ;;
    restart)
        stop_server
        sleep 2
        start_server "background"
        ;;
    test)
        run_test_client
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

exit 0

# Usage

# # Start in foreground
# ./start_cve_mcp_server.sh start

# # Start in background
# ./start_cve_mcp_server.sh start-bg

# # Start in background with debug logging
# ./start_cve_mcp_server.sh start-bg --debug

# # Check status
# ./start_cve_mcp_server.sh status

# # Stop the server
# ./start_cve_mcp_server.sh stop

# # Restart the server
# ./start_cve_mcp_server.sh restart

# # Run test client
# ./start_cve_mcp_server.sh test

# # Run test client with debug output
# ./start_cve_mcp_server.sh test --debug

# # Show help
# ./start_cve_mcp_server.sh --help


