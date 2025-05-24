# MCP Integration for Zero-Day Scout

This document describes the MCP (Message Communication Protocol) integration in the Zero-Day Scout system, which enables the Scout Agent to communicate with the CVE Search server using Google's Agent Development Kit (ADK).

## Overview

The integration connects Zero-Day Scout's agent system to a local CVE-Search MCP server, providing real-time access to comprehensive vulnerability databases. This allows the agent to look up specific CVEs, search for vendor/product vulnerabilities, and retrieve the latest security information directly from authoritative sources.

## Architecture

The MCP integration consists of the following components:

```
┌───────────────┐                         ┌────────────────┐
│ Orchestrator  │                         │ MCP-enabled    │
│ Agent         │────┐                    │ Research Agent │
└───────────────┘    │                    └────────────────┘
                     │                            │
                     ▼                            ▼
┌────────────────┐  ┌──────────────┐      ┌────────────────┐
│ Planner Agent  │  │ Analysis     │      │ ADK MCPToolset │
└────────────────┘  │ Agent        │      └────────────────┘
                     └──────────────┘              │
                                                   ▼
                                          ┌─────────────────┐
                                          │ MCP Server (SSE)│
                                          └─────────────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │ CVE Database    │
                                          └─────────────────┘
```

## Key Components

### 1. CVE MCP Server

A StreamableHTTP-based MCP server providing CVE database access:

- Located in `src/cve_mcp/streamable_server.py`
- Provides tools for CVE search, vendor/product queries, and database status
- Supports both StreamableHTTP and SSE transports
- Implements retry logic and health monitoring

### 2. CVE Lookup Agent

A specialized agent that connects to the MCP server for vulnerability lookups:

- Located in `src/scout_agent/cve_agent.py`
- Creates ADK-compatible tools from MCP endpoints
- Handles query parsing and response formatting
- Provides AgentTool wrapper for integration

### 3. OrchestratorAgent

Coordinates the agent workflow and integrates CVE tools:

- Located in `src/scout_agent/agent.py`
- Dynamically adds CVE tools to Research Agent when MCP is available
- Manages asynchronous initialization and resource cleanup
- Dynamically creates and initializes the MCP research agent during query processing
- Handles agent recreation to avoid parent conflicts
- Maintains backward compatibility with non-MCP operation

### 3. MCP Server

A FastAPI server with SSE transport that provides CVE search functionality:

- Located in `src/cve_mcp/agent_mcp_server.py`
- Exposes CVE search tools via the MCP protocol
- Provides `/health` and `/ping` endpoints for monitoring
- Includes a ping tool for connection health checking and latency measurement
- Implemented using the FastAPI framework

## Using the MCP Integration

To use the MCP integration:

1. Start the MCP server:
   ```bash
   ./start_cve_mcp_server.sh start
   ```

2. Run the Scout CLI:
   ```bash
   python src/apps/scout_cli.py
   ```

3. Issue a query about a specific CVE or security vulnerability.

The Scout Agent will automatically connect to the MCP server to retrieve relevant CVE information.

## Testing the MCP Integration

To test the MCP integration:

1. Run the integration test:
   ```bash
   ./run_cve_mcp_sse.sh
   ```

2. For a lightweight test that only checks connectivity:
   ```bash
   ./test_init_mcp.py
   ```

## Implementation Details

### MCP Client Initialization

The MCP client is initialized in the `AdkMcpResearchAgent` class using ADK's native `MCPToolset.from_server` method:

```python
# Create connection parameters
mcp_params = SseServerParams(url=mcp_uri)

# Use the from_server method that works
result = await MCPToolset.from_server(connection_params=mcp_params)

# Extract tools from the tuple result
self.mcp_tools = result[0]
```

### OrchestratorAgent Integration

The `OrchestratorAgent` integrates the MCP research agent in its workflow:

1. Creates the base research agent (non-MCP version) during initialization.
2. Asynchronously creates and initializes the MCP research agent during `process_query`.
3. If MCP initialization succeeds, replaces the research agent with the MCP-enabled version.
4. Recreates the sequential agent workflow to avoid parent conflicts.

### Available MCP Tools

The CVE Search MCP server provides the following tools:

- `vul_vendors`: Get a list of vendors
- `vul_vendor_products`: Get products for a vendor
- `vul_vendor_product_cve`: Get CVEs for a vendor and product
- `vul_cve_search`: Search for a specific CVE by ID
- `vul_last_cves`: Get the latest CVEs
- `vul_db_update_status`: Get database update status
- `ping`: Check server connectivity and measure response time

### Fallback Mechanism

If the MCP server is unavailable or initialization fails, the system falls back to the local CVE lookup tool:

```python
def _setup_fallback_agent(self):
    """Set up fallback agent with local CVE tool."""
    self.cve_lookup_tool = CveLookupTool()
    self.agent = LlmAgent(
        name="security_researcher",
        description="Security researcher specialized in finding vulnerability information",
        model=self.model_name,
        instruction=RESEARCH_TASK_PROMPT,
        tools=[self.rag_tool, self.cve_lookup_tool, self.web_search_tool],
        output_key="research_findings",
    )
    self.connected = False
```

## Troubleshooting

If you encounter issues with the MCP integration:

1. Check if the MCP server is running:
   ```bash
   curl http://localhost:8080/health
   curl http://localhost:8080/ping
   ```
   
   Or use the dedicated ping test tool:
   ```bash
   python test_ping.py
   ```

2. Run the initialization test to verify connectivity:
   ```bash
   ./test_init_mcp.py
   ```

3. Check the server logs:
   ```bash
   ./start_cve_mcp_server.sh logs
   ```

4. Restart the MCP server:
   ```bash
   ./start_cve_mcp_server.sh restart
   ```

## Monitoring Server Health

The MCP server includes built-in health monitoring features:

### HTTP Health Endpoints

1. `/health` - Basic server status check
   ```bash
   curl http://localhost:8080/health
   ```

2. `/ping` - Response time measurement and server status
   ```bash
   curl http://localhost:8080/ping
   ```

### Ping Tool

The server exposes a `ping` tool via MCP that can be used by clients to check connectivity:

```python
client = McpCveClient()
client.connect()
result = client.ping()
print(f"Server response time: {result['response_time_ms']}ms")
```

### CVE CLI Tool

A beautiful command-line interface is provided for interacting with the MCP server:

```bash
# Interactive mode
python src/cve_mcp/cve_cli.py

# Search for specific CVE
python src/cve_mcp/cve_cli.py --cve CVE-2021-44228

# Get latest CVEs
python src/cve_mcp/cve_cli.py --latest

# Search by vendor/product
python src/cve_mcp/cve_cli.py --vendor microsoft --product windows_10
```

Features:
- Beautiful colored terminal UI
- Interactive and single-command modes
- CVE search, vendor/product queries, and database status
- CVSS score color coding
- Formatted output for easy reading

See `src/cve_mcp/README_CVE_CLI.md` for detailed usage.

### Ping Test Tool

A comprehensive ping test tool is provided in `test_ping.py`:

```bash
# Basic usage
python test_ping.py

# Test with 10 pings
python test_ping.py --count 10

# Test only HTTP ping
python test_ping.py --mode http

# Test only MCP ping
python test_ping.py --mode mcp

# Custom server location
python test_ping.py --host otherserver --port 8080
```

The ping test measures:
- Round-trip time (RTT) from client perspective
- Server processing time
- Estimated network latency
- Response reliability (packet loss)