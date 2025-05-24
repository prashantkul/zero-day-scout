#!/bin/bash

# Start the CVE MCP server in SSE mode
echo "Starting CVE MCP Server..."
python src/cve_mcp/agent_mcp_server.py --transport sse --port 8000