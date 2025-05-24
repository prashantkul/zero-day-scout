
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamable HTTP MCP server for CVE Search.

This implementation follows the standard MCP server pattern with StreamableHTTP transport
and provides a backward-compatible SSE endpoint.
"""

import os
import sys
import time
import json
import signal
import logging
import argparse
import requests
import asyncio
import contextlib
import traceback
from collections.abc import AsyncIterator
from typing import Dict, Any, List, Union, Optional

import anyio
import uvicorn
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
# from mcp.server.sse import SseServerTransport # For backward compatibility - not needed
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send
from starlette.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("cve-search-mcp")

# Add project root to the path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import constants
try:
    from config.constants import (
        MCP_SERVER_HOST,
        MCP_SERVER_PORT,
        MCP_SERVER_TRANSPORT, # This might be less relevant if supporting multiple
        MCP_REQUEST_TIMEOUT,
        MCP_LIST_TIMEOUT,
        MCP_CONNECT_TIMEOUT,
        MCP_RETRY_COUNT,
    )
except (ImportError, AttributeError) as e:
    logger.warning(f"Error importing constants: {e}, using defaults")
    MCP_SERVER_HOST = "0.0.0.0"
    MCP_SERVER_PORT = 8080
    MCP_REQUEST_TIMEOUT = 180
    MCP_RETRY_COUNT = 3

# Base URL for CVE search
BASE_URL = "https://cve.circl.lu/api/"

# Function to get data from the CVE API (remains the same)
async def get_requests(uri: str, retry_count: int = MCP_RETRY_COUNT, timeout: int = MCP_REQUEST_TIMEOUT) -> Dict[str, Any]:
    session = requests.Session()
    url = f"{BASE_URL}{uri}"
    max_backoff = 10
    base_backoff = 1
    for attempt in range(retry_count):
        try:
            logger.debug(f"Request attempt {attempt+1}/{retry_count} for {url}")
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            logger.warning(f"Request timeout ({timeout}s) for {url} on attempt {attempt+1}: {str(e)}")
            if attempt < retry_count - 1:
                import random
                backoff = min(max_backoff, base_backoff * (2 ** attempt))
                jitter = random.uniform(0.8, 1.2)
                sleep_time = backoff * jitter
                logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time)
            else:
                return {"error": f"Request timed out after {retry_count} attempts: {str(e)}"}
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error for {url} on attempt {attempt+1}: {str(e)}")
            if attempt < retry_count - 1:
                import random
                backoff = min(max_backoff, base_backoff * (2 ** attempt))
                jitter = random.uniform(0.8, 1.2)
                sleep_time = backoff * jitter
                logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time)
            else:
                return {"error": f"Connection failed after {retry_count} attempts: {str(e)}"}
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') else "unknown"
            logger.error(f"HTTP error {status_code} for {url}: {str(e)}")
            return {"error": f"HTTP error {status_code}: {str(e)}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {url}: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}
        except ValueError as e:
            logger.error(f"JSON parsing error for {url}: {str(e)}")
            return {"error": f"Invalid JSON response: {str(e)}"}
    return {"error": "Maximum retry attempts reached"}

# PID file management (remains the same)
def create_pid_file(pid_file):
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"Created PID file: {pid_file}")

def remove_pid_file(pid_file):
    if os.path.exists(pid_file):
        os.remove(pid_file)
        logger.info(f"Removed PID file: {pid_file}")

# Run the MCP server
def run_server(host: str, port: int, log_level: str, json_response_for_streamable: bool):
    try:
        logging.getLogger().setLevel(getattr(logging, log_level.upper()))
        logging.getLogger("mcp").setLevel(getattr(logging, log_level.upper()))
        
        app = Server("cve-search-mcp") # Core MCP application logic

        # Tool definitions (remain the same)
        @app.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[Union[types.TextContent, types.ImageContent]]:
            logger.info(f"Tool call: {name}, arguments: {arguments}")
            ctx = app.request_context
            if name == "vul_vendors":
                result = await get_requests("browse")
                return [types.TextContent(type="text", text=json.dumps(result))]
            elif name == "vul_vendor_products":
                vendor = arguments.get("vendor", "")
                if not vendor: return [types.TextContent(type="text", text=json.dumps({"error": "Missing vendor parameter"}))]
                result = await get_requests(f"browse/{vendor}")
                return [types.TextContent(type="text", text=json.dumps(result))]
            elif name == "vul_vendor_product_cve":
                vendor = arguments.get("vendor", "")
                product = arguments.get("product", "")
                if not vendor or not product: return [types.TextContent(type="text", text=json.dumps({"error": "Missing vendor or product parameter"}))]
                result = await get_requests(f"search/{vendor}/{product}")
                return [types.TextContent(type="text", text=json.dumps(result))]
            elif name == "vul_cve_search":
                cve_id = arguments.get("cve_id", "")
                if not cve_id: return [types.TextContent(type="text", text=json.dumps({"error": "Missing cve_id parameter"}))]
                result = await get_requests(f"cve/{cve_id}")
                return [types.TextContent(type="text", text=json.dumps(result))]
            elif name == "vul_last_cves":
                result = await get_requests("last")
                return [types.TextContent(type="text", text=json.dumps(result))]
            elif name == "vul_db_update_status":
                result = await get_requests("dbInfo")
                return [types.TextContent(type="text", text=json.dumps(result))]
            elif name == "ping":
                start_time = time.time()
                # Log message without accessing non-existent attributes
                logger.info("Ping received from client")
                response_time = (time.time() - start_time) * 1000
                result = {"status": "ok", "server": "CVE Search MCP Server", "version": "1.0.0", "timestamp": time.time(), "response_time_ms": round(response_time, 2)}
                return [types.TextContent(type="text", text=json.dumps(result))]
            else:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        @app.list_tools()
        async def list_tools() -> List[types.Tool]:
            return [
                types.Tool(name="vul_vendors", description="Get a list of all vendors", inputSchema={"type": "object", "properties": {}}),
                types.Tool(name="vul_vendor_products", description="Get products for a specific vendor", inputSchema={"type": "object", "required": ["vendor"], "properties": {"vendor": {"type": "string", "description": "Vendor name"}}}),
                types.Tool(name="vul_vendor_product_cve", description="Get CVEs for a vendor and product", inputSchema={"type": "object", "required": ["vendor", "product"], "properties": {"vendor": {"type": "string"}, "product": {"type": "string"}}}),
                types.Tool(name="vul_cve_search", description="Search for a CVE by ID", inputSchema={"type": "object", "required": ["cve_id"], "properties": {"cve_id": {"type": "string"}}}),
                types.Tool(name="vul_last_cves", description="Get latest 30 CVEs", inputSchema={"type": "object", "properties": {}}),
                types.Tool(name="vul_db_update_status", description="Get CVE DB update status", inputSchema={"type": "object", "properties": {}}),
                types.Tool(name="ping", description="Check server connectivity", inputSchema={"type": "object", "properties": {}})
            ]

        # Manager for StreamableHTTP transport (primary)
        streamable_manager = StreamableHTTPSessionManager(
            app=app,
            event_store=None,
            json_response=json_response_for_streamable, # Use the specific arg here
            stateless=True,
        )


        # SSE transport not implemented - use StreamableHTTP instead

        # Handler for StreamableHTTP requests

        async def handle_streamable_mcp_request(scope: Scope, receive: Receive, send: Send) -> None:
            await streamable_manager.handle_request(scope, receive, send)

        # Handler for SSE requests - redirect to StreamableHTTP
        async def handle_sse_mcp_request(scope: Scope, receive: Receive, send: Send) -> None:
            # For now, redirect SSE requests to use StreamableHTTP
            await streamable_manager.handle_request(scope, receive, send)

        # Lifespan context manager to run both managers
        @contextlib.asynccontextmanager
        async def lifespan(starlette_app_instance: Starlette) -> AsyncIterator[None]:
            async with streamable_manager.run():
                logger.info("MCP server started with StreamableHTTPSessionManager and SSE transport")
                try:
                    yield
                finally:
                    logger.info("MCP server shutting down session managers")
        
        # Starlette app with both MCP handlers mounted
        starlette_app = Starlette(
            debug=(log_level.upper() == "DEBUG"),
            routes=[
                Mount("/mcp/", app=handle_streamable_mcp_request),      # Primary StreamableHTTP
                Mount("/mcp/sse", app=handle_streamable_mcp_request),   # SSE requests redirected to StreamableHTTP
            ],
            lifespan=lifespan,
        )
        
        # HTTP ping endpoint (remains the same)
        @starlette_app.route("/ping")
        async def ping(request):
            start_time = time.time()
            response_time = (time.time() - start_time) * 1000
            return JSONResponse({"status": "ok", "server": "CVE Search MCP Server", "version": "1.0.0", "timestamp": time.time(), "response_time_ms": round(response_time, 2)})
        
        logger.info(f"Starting MCP server at http://{host}:{port}")
        logger.info(f"  - StreamableHTTP MCP: http://{host}:{port}/mcp/")
        logger.info(f"  - SSE MCP (Legacy): http://{host}:{port}/mcp/sse")
        logger.info(f"  - HTTP Ping: http://{host}:{port}/ping")
        logger.info(f"  - JSON response mode for StreamableHTTP: {'enabled' if json_response_for_streamable else 'disabled'}")
        
        uvicorn.run(starlette_app, host=host, port=port, log_level=log_level.lower())
        return True
    except Exception as e:
        logger.error(f"Error running MCP server: {e}", exc_info=True)
        return False

def main():
    parser = argparse.ArgumentParser(description="MCP server for CVE Search with StreamableHTTP and SSE")
    parser.add_argument("--host", default=MCP_SERVER_HOST, help=f"Host (default: {MCP_SERVER_HOST})")
    parser.add_argument("--port", type=int, default=MCP_SERVER_PORT, help=f"Port (default: {MCP_SERVER_PORT})")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    # Renamed --json-response to be specific to streamable manager
    parser.add_argument("--streamable-json-response", action="store_true", help="Enable JSON responses for StreamableHTTP manager")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop server")
    parser.add_argument("--status", action="store_true", help="Check server status")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    if args.debug: args.log_level = "DEBUG"
    
    pid_dir = os.path.join(project_root, "var", "run")
    os.makedirs(pid_dir, exist_ok=True)
    pid_file = os.path.join(pid_dir, "streamable_server.pid")

    if args.status:
        # ... (status logic remains the same)
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f: pid = f.read().strip()
            print(f"Server is running with PID {pid}")
            try:
                os.kill(int(pid), 0)
                print("Process is active")
                return 0
            except (OSError, ProcessLookupError): # Changed from just OSError
                print("Process not found. PID file might be stale.")
                remove_pid_file(pid_file)
                return 1
        else:
            print("Server is not running (no PID file found)")
            return 1
        return 0 # Added to ensure it returns if not exiting above

    if args.stop:
        # ... (stop logic remains the same)
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f: pid = f.read().strip()
            print(f"Stopping server with PID {pid}...")
            try:
                os.kill(int(pid), signal.SIGTERM)
                time.sleep(2) # Give it a moment
                try:
                    os.kill(int(pid), 0) # Check if still alive
                    print("Server did not stop gracefully. Sending SIGKILL...")
                    os.kill(int(pid), signal.SIGKILL)
                except (OSError, ProcessLookupError): # Changed from just OSError
                    print("Server stopped successfully.")
            except (OSError, ProcessLookupError): # Changed from just OSError
                print("Process not found. PID file might be stale.")
            finally:
                remove_pid_file(pid_file) # Ensure PID removed
            return 0
        else:
            print("Server is not running (no PID file found)")
            return 1
        return 0 # Added

    if args.daemon: create_pid_file(pid_file)

    def signal_handler(sig, frame):
        signal_name = signal.Signals(sig).name
        logger.info(f"Received {signal_name}. Shutting down...")
        if args.daemon and os.path.exists(pid_file): remove_pid_file(pid_file)
        # sys.exit(0) # Consider a cleaner shutdown via asyncio events if uvicorn supports it well
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Pass the renamed json_response argument
        success = run_server(args.host, args.port, args.log_level, args.streamable_json_response)
        if args.daemon and os.path.exists(pid_file): remove_pid_file(pid_file)
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down...")
        if args.daemon and os.path.exists(pid_file): remove_pid_file(pid_file)
        return 0

if __name__ == "__main__":
    sys.exit(main())
