#!/bin/bash

# Script to manage the streamable HTTP MCP server

# Default settings
HOST="0.0.0.0"
PORT="8080"
LOG_LEVEL="INFO"
JSON_RESPONSE=""

# Function to show usage
show_usage() {
    echo "Usage: $0 [options] {start|stop|status|restart|foreground}"
    echo ""
    echo "Commands:"
    echo "  start       Start the server in background mode"
    echo "  stop        Stop the running server"
    echo "  status      Check if the server is running"
    echo "  restart     Restart the server"
    echo "  foreground  Start the server in foreground mode"
    echo ""
    echo "Options:"
    echo "  --host          Host to bind to (default: $HOST)"
    echo "  --port          Port to bind to (default: $PORT)"
    echo "  --log-level     Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: $LOG_LEVEL)"
    echo "  --json-response Enable JSON responses instead of SSE streams"
    echo "  --debug         Enable debug mode (shorthand for --log-level DEBUG)"
    echo ""
    echo "Example:"
    echo "  $0 start --port 8080 --debug"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --json-response)
            JSON_RESPONSE="--json-response"
            shift
            ;;
        --debug)
            LOG_LEVEL="DEBUG"
            shift
            ;;
        start|stop|status|restart|foreground)
            COMMAND="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Check if command was provided
if [ -z "$COMMAND" ]; then
    echo "Error: No command specified"
    show_usage
fi

# Function to start the server
start_server() {
    echo "Starting streamable HTTP MCP server at $HOST:$PORT..."
    
    # Start the server with the specified options
    if [ "$1" = "background" ]; then
        # Run in background mode
        nohup python src/cve_mcp/streamable_server.py \
            --host "$HOST" \
            --port "$PORT" \
            --log-level "$LOG_LEVEL" \
            $JSON_RESPONSE \
            --daemon \
            > /dev/null 2>&1 &
            
        # Wait for server to start
        sleep 2
        
        # Check if server is running
        python src/cve_mcp/streamable_server.py --status
        if [ $? -eq 0 ]; then
            echo "Server started successfully"
        else
            echo "Failed to start server"
            exit 1
        fi
    else
        # Run in foreground mode
        python src/cve_mcp/streamable_server.py \
            --host "$HOST" \
            --port "$PORT" \
            --log-level "$LOG_LEVEL" \
            $JSON_RESPONSE
    fi
}

# Function to stop the server
stop_server() {
    echo "Stopping streamable HTTP MCP server..."
    python src/cve_mcp/streamable_server.py --stop
}

# Function to check server status
check_status() {
    python src/cve_mcp/streamable_server.py --status
    return $?
}

# Execute the command
case $COMMAND in
    start)
        # Check if server is already running
        if check_status > /dev/null; then
            echo "Server is already running"
        else
            start_server "background"
        fi
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
    foreground)
        start_server "foreground"
        ;;
    *)
        show_usage
        ;;
esac

exit 0