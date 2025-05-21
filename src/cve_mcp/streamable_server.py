#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamable HTTP MCP server for CVE Search.

This implementation follows the standard MCP server pattern with StreamableHTTP transport.
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
        MCP_SERVER_TRANSPORT,
        MCP_REQUEST_TIMEOUT,
        MCP_LIST_TIMEOUT,
        MCP_CONNECT_TIMEOUT,
        MCP_RETRY_COUNT,
    )
except (ImportError, AttributeError) as e:
    logger.warning(f"Error importing constants: {e}, using defaults")
    # Default values
    MCP_SERVER_HOST = "0.0.0.0"
    MCP_SERVER_PORT = 8080
    MCP_SERVER_TRANSPORT = "streamable-http"
    MCP_REQUEST_TIMEOUT = 180
    MCP_LIST_TIMEOUT = 90
    MCP_CONNECT_TIMEOUT = 30
    MCP_RETRY_COUNT = 3

# Base URL for CVE search
BASE_URL = "https://cve.circl.lu/api/"

# Function to get data from the CVE API
async def get_requests(uri: str, retry_count: int = MCP_RETRY_COUNT, timeout: int = MCP_REQUEST_TIMEOUT) -> Dict[str, Any]:
    """Get data from the CVE API with retries and error handling.
    
    Args:
        uri: The API endpoint URI
        retry_count: Number of retries on failure
        timeout: Request timeout in seconds
        
    Returns:
        JSON response or error dictionary
    """
    session = requests.Session()
    url = f"{BASE_URL}{uri}"
    
    # Backoff parameters
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
                # Calculate backoff with jitter
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
                # Use the same backoff strategy
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
            
    # This should not be reached
    return {"error": "Maximum retry attempts reached"}

# PID file management
def create_pid_file(pid_file):
    """Create a PID file"""
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"Created PID file: {pid_file}")

def remove_pid_file(pid_file):
    """Remove the PID file if it exists"""
    if os.path.exists(pid_file):
        os.remove(pid_file)
        logger.info(f"Removed PID file: {pid_file}")

# Run the MCP server
def run_server(host: str, port: int, log_level: str, json_response: bool):
    """Run the MCP server."""
    try:
        # Set the log level
        logging.getLogger().setLevel(getattr(logging, log_level.upper()))
        logging.getLogger("mcp").setLevel(getattr(logging, log_level.upper()))
        
        # Create the MCP server
        app = Server("cve-search-mcp")
        
        # Define tools
        @app.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[Union[types.TextContent, types.ImageContent]]:
            """Handle tool calls."""
            logger.info(f"Tool call: {name}, arguments: {arguments}")
            ctx = app.request_context
            
            if name == "vul_vendors":
                result = await get_requests("browse")
                return [types.TextContent(type="text", text=json.dumps(result))]
                
            elif name == "vul_vendor_products":
                vendor = arguments.get("vendor", "")
                if not vendor:
                    return [types.TextContent(type="text", text=json.dumps({"error": "Missing vendor parameter"}))]
                    
                result = await get_requests(f"browse/{vendor}")
                return [types.TextContent(type="text", text=json.dumps(result))]
                
            elif name == "vul_vendor_product_cve":
                vendor = arguments.get("vendor", "")
                product = arguments.get("product", "")
                if not vendor or not product:
                    return [types.TextContent(type="text", text=json.dumps({"error": "Missing vendor or product parameter"}))]
                    
                result = await get_requests(f"search/{vendor}/{product}")
                return [types.TextContent(type="text", text=json.dumps(result))]
                
            elif name == "vul_cve_search":
                cve_id = arguments.get("cve_id", "")
                if not cve_id:
                    return [types.TextContent(type="text", text=json.dumps({"error": "Missing cve_id parameter"}))]
                    
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
                
                # Send a log message with the ping info
                await ctx.session.send_log_message(
                    level="info",
                    data=f"Ping received from {ctx.client_name or 'unknown client'}",
                    logger="ping",
                    related_request_id=ctx.request_id,
                )
                
                # Calculate response time
                response_time = (time.time() - start_time) * 1000
                
                result = {
                    "status": "ok",
                    "server": "CVE Search MCP Server",
                    "version": "1.0.0",
                    "timestamp": time.time(),
                    "response_time_ms": round(response_time, 2)
                }
                
                return [types.TextContent(type="text", text=json.dumps(result))]
                
            else:
                return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        @app.list_tools()
        async def list_tools() -> List[types.Tool]:
            """List available tools."""
            return [
                types.Tool(
                    name="vul_vendors",
                    description="Get a list of all vendors in the vulnerability database",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="vul_vendor_products",
                    description="Get products for a specific vendor",
                    inputSchema={
                        "type": "object",
                        "required": ["vendor"],
                        "properties": {
                            "vendor": {
                                "type": "string",
                                "description": "Vendor name to look up"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="vul_vendor_product_cve",
                    description="Get CVEs for a specific vendor and product",
                    inputSchema={
                        "type": "object",
                        "required": ["vendor", "product"],
                        "properties": {
                            "vendor": {
                                "type": "string",
                                "description": "Vendor name to look up"
                            },
                            "product": {
                                "type": "string",
                                "description": "Product name to look up"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="vul_cve_search",
                    description="Search for a specific CVE by ID",
                    inputSchema={
                        "type": "object",
                        "required": ["cve_id"],
                        "properties": {
                            "cve_id": {
                                "type": "string",
                                "description": "CVE ID to look up (e.g., CVE-2021-44228)"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="vul_last_cves",
                    description="Get the latest 30 CVEs",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="vul_db_update_status",
                    description="Get information about the CVE database update status",
                    inputSchema={"type": "object", "properties": {}}
                ),
                types.Tool(
                    name="ping",
                    description="Check server connectivity and measure response time",
                    inputSchema={"type": "object", "properties": {}}
                )
            ]

        # Create the session manager with stateless mode for better reliability
        session_manager = StreamableHTTPSessionManager(
            app=app,
            event_store=None,
            json_response=json_response,
            stateless=True,
        )

        # Handler for streamable HTTP requests
        async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
            """Handle streamable HTTP requests."""
            await session_manager.handle_request(scope, receive, send)

        # Lifespan context manager
        @contextlib.asynccontextmanager
        async def lifespan(app: Starlette) -> AsyncIterator[None]:
            """Lifespan context manager for the session manager."""
            async with session_manager.run():
                logger.info("MCP server started with StreamableHTTP session manager")
                try:
                    yield
                finally:
                    logger.info("MCP server shutting down")

        # Add a plain HTTP ping endpoint for basic health checks
        async def http_ping(scope: Scope, receive: Receive, send: Send) -> None:
            """Simple HTTP ping endpoint."""
            if scope["type"] != "http":
                return
                
            if scope["method"] != "GET":
                await send({
                    "type": "http.response.start",
                    "status": 405,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({
                    "type": "http.response.body",
                    "body": json.dumps({"error": "Method not allowed"}).encode(),
                })
                return
                
            # Process the request
            start_time = time.time()
            response_time = (time.time() - start_time) * 1000
            
            response = {
                "status": "ok",
                "server": "CVE Search MCP Server",
                "version": "1.0.0",
                "timestamp": time.time(),
                "response_time_ms": round(response_time, 2)
            }
            
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": json.dumps(response).encode(),
            })

        # Create a Starlette app with the MCP handler mounted at /mcp
        starlette_app = Starlette(
            debug=(log_level.upper() == "DEBUG"),
            routes=[
                Mount("/mcp", app=handle_streamable_http),
            ],
            lifespan=lifespan,
        )
        
        # Add the HTTP ping endpoint
        @starlette_app.route("/ping")
        async def ping(request):
            start_time = time.time()
            response_time = (time.time() - start_time) * 1000
            return JSONResponse({
                "status": "ok",
                "server": "CVE Search MCP Server",
                "version": "1.0.0",
                "timestamp": time.time(),
                "response_time_ms": round(response_time, 2)
            })
        
        # Log server status
        logger.info(f"Starting MCP server at http://{host}:{port}")
        logger.info(f"  - HTTP Ping: http://{host}:{port}/ping")
        logger.info(f"  - MCP endpoint: http://{host}:{port}/mcp")
        logger.info(f"  - JSON response mode: {'enabled' if json_response else 'disabled'}")
        logger.info(f"Available tools: vul_vendors, vul_vendor_products, vul_vendor_product_cve, vul_cve_search, vul_last_cves, vul_db_update_status, ping")
        logger.info("Press Ctrl+C to stop the server")
        
        # Run the server
        uvicorn.run(starlette_app, host=host, port=port, log_level=log_level.lower())
        
        return True
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        traceback.print_exc()
        return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Streamable HTTP MCP server for CVE Search")
    
    parser.add_argument("--host", default=MCP_SERVER_HOST, help=f"Host to bind to (default: {MCP_SERVER_HOST})")
    parser.add_argument("--port", type=int, default=MCP_SERVER_PORT, help=f"Port to listen on (default: {MCP_SERVER_PORT})")
    parser.add_argument("--log-level", default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    parser.add_argument("--json-response", action="store_true", help="Enable JSON responses instead of SSE streams")
    parser.add_argument("--daemon", action="store_true", help="Run as a daemon (internal use)")
    parser.add_argument("--stop", action="store_true", help="Stop the running server")
    parser.add_argument("--status", action="store_true", help="Check server status")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (same as --log-level DEBUG)")
    
    args = parser.parse_args()
    
    # Update log level if debug is specified
    if args.debug:
        args.log_level = "DEBUG"
    
    # PID file path
    pid_dir = os.path.join(project_root, "var", "run")
    os.makedirs(pid_dir, exist_ok=True)
    pid_file = os.path.join(pid_dir, "streamable_server.pid")
    
    # Handle status check
    if args.status:
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                pid = f.read().strip()
            print(f"Server is running with PID {pid}")
            try:
                os.kill(int(pid), 0)  # Check if process exists
                print("Process is active")
                return 0
            except (OSError, ProcessLookupError):
                print("Process not found. PID file might be stale.")
                remove_pid_file(pid_file)
                return 1
        else:
            print("Server is not running (no PID file found)")
            return 1
    
    # Handle stop request
    if args.stop:
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                pid = f.read().strip()
            print(f"Stopping server with PID {pid}...")
            try:
                os.kill(int(pid), signal.SIGTERM)
                # Wait for process to terminate
                for _ in range(10):  # wait up to 10 seconds
                    time.sleep(1)
                    try:
                        os.kill(int(pid), 0)  # Check if process exists
                    except (OSError, ProcessLookupError):
                        # Process is gone
                        print("Server stopped successfully")
                        remove_pid_file(pid_file)
                        return 0
                
                # Process didn't stop
                print("Server did not stop gracefully. Sending SIGKILL...")
                os.kill(int(pid), signal.SIGKILL)
                remove_pid_file(pid_file)
                return 0
            except (OSError, ProcessLookupError):
                print("Process not found. PID file might be stale.")
                remove_pid_file(pid_file)
                return 1
        else:
            print("Server is not running (no PID file found)")
            return 1
    
    # Create PID file if running as daemon
    if args.daemon:
        create_pid_file(pid_file)
    
    # Set up signal handling
    def signal_handler(sig, frame):
        """Handle signals for graceful shutdown."""
        signal_name = "SIGINT" if sig == signal.SIGINT else "SIGTERM"
        logger.info(f"Received {signal_name}. Shutting down...")
        if args.daemon and os.path.exists(pid_file):
            remove_pid_file(pid_file)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run the server
        success = run_server(args.host, args.port, args.log_level, args.json_response)
        
        # Clean up PID file on exit
        if args.daemon and os.path.exists(pid_file):
            remove_pid_file(pid_file)
            
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down...")
        if args.daemon and os.path.exists(pid_file):
            remove_pid_file(pid_file)
        return 0

if __name__ == "__main__":
    sys.exit(main())