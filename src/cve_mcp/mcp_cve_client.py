"""
MCP CVE Client - Client for interacting with the CVE MCP Server.

This client provides a high-level interface for communicating with the CVE MCP Server
using the StreamableHTTP transport.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class McpCveClient:
    """
    High-level client for CVE MCP Server communication.
    
    This client provides convenient methods for all CVE operations supported
    by the MCP server.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        """
        Initialize the CVE MCP client.
        
        Args:
            host: MCP server host
            port: MCP server port
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.mcp_endpoint = urljoin(self.base_url, "/mcp/")
        
    async def _call_tool_with_session(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Call a tool on the MCP server with a new session each time.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Parsed tool response
        """
        try:
            # Create a new connection for each call
            async with streamablehttp_client(self.mcp_endpoint) as streams:
                # Unpack the 3-tuple: read_stream, write_stream, session_id_callback
                read_stream, write_stream, session_id_callback = streams
                
                # Create client session using async context manager
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Call the tool
                    result = await session.call_tool(tool_name, arguments or {})
                    
                    # Parse the response
                    if hasattr(result, 'content') and result.content:
                        # Extract text content
                        for content in result.content:
                            if hasattr(content, 'text'):
                                try:
                                    # Try to parse as JSON
                                    return json.loads(content.text)
                                except json.JSONDecodeError:
                                    # Return as string if not JSON
                                    return {"result": content.text}
                                    
                    return {"error": "No content in response"}
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def search_cve(self, cve_id: str) -> Dict[str, Any]:
        """
        Search for a specific CVE by ID.
        
        Args:
            cve_id: CVE ID (e.g., "CVE-2021-44228")
            
        Returns:
            CVE details or error
        """
        return await self._call_tool_with_session("vul_cve_search", {"cve_id": cve_id})
    
    async def get_latest_cves(self) -> List[Dict[str, Any]]:
        """
        Get the latest 30 CVEs.
        
        Returns:
            List of latest CVEs or error
        """
        result = await self._call_tool_with_session("vul_last_cves")
        
        # Handle the response format
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "error" not in result:
            # If it's wrapped in an object, try to extract the list
            if "cves" in result:
                return result["cves"]
            elif "data" in result:
                return result["data"]
            elif "result" in result and isinstance(result["result"], list):
                return result["result"]
        
        return result
    
    async def search_vendor_product_cves(self, vendor: str, product: str) -> List[Dict[str, Any]]:
        """
        Search for CVEs by vendor and product.
        
        Args:
            vendor: Vendor name
            product: Product name
            
        Returns:
            List of CVEs or error
        """
        result = await self._call_tool_with_session("vul_vendor_product_cve", {
            "vendor": vendor,
            "product": product
        })
        
        # Handle the response format
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "error" not in result:
            # Try to extract list from various possible formats
            for key in ["cves", "data", "result", "vulnerabilities"]:
                if key in result and isinstance(result[key], list):
                    return result[key]
        
        return result
    
    async def get_vendors(self) -> Dict[str, Any]:
        """
        Get list of all vendors.
        
        Returns:
            Dict with vendor list or error
        """
        result = await self._call_tool_with_session("vul_vendors")
        
        # Normalize the response - if it's a list, wrap it in a dict
        if isinstance(result, list):
            return {"vendor": result}
        elif isinstance(result, dict) and "error" not in result:
            # If it already has a vendor key, return as-is
            if "vendor" in result:
                return result
            # Otherwise check if the dict contains vendor data
            return result
        
        return result
    
    async def get_vendor_products(self, vendor: str) -> Dict[str, Any]:
        """
        Get products for a specific vendor.
        
        Args:
            vendor: Vendor name
            
        Returns:
            Dict with product list or error
        """
        result = await self._call_tool_with_session("vul_vendor_products", {"vendor": vendor})
        
        # Normalize the response - if it's a list, wrap it in a dict
        if isinstance(result, list):
            return {"product": result}
        elif isinstance(result, dict) and "error" not in result:
            # If it already has a product key, return as-is
            if "product" in result:
                return result
            # Otherwise wrap the whole dict
            return {"product": result}
        
        return result
    
    async def get_db_update_status(self) -> Dict[str, Any]:
        """
        Get CVE database update status.
        
        Returns:
            Database status information
        """
        return await self._call_tool_with_session("vul_db_update_status")
    
    async def ping(self) -> Dict[str, Any]:
        """
        Ping the MCP server to test connectivity.
        
        Returns:
            Server response with timing information
        """
        return await self._call_tool_with_session("ping")


class CVESearchClient:
    """
    Lower-level client for direct MCP communication with persistent connection.
    
    This client maintains a connection throughout its lifetime and must be used
    within an async context manager.
    """
    
    def __init__(self, endpoint: str = None):
        """
        Initialize the CVE search client.
        
        Args:
            endpoint: Full MCP endpoint URL (e.g., "http://localhost:8080/mcp/")
        """
        if endpoint:
            self.endpoint = endpoint
        else:
            self.endpoint = "http://localhost:8080/mcp/"
        
        self._session = None
        self._streams = None
        self._context = None
    
    async def __aenter__(self):
        """Enter the async context manager."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        await self.close()
    
    async def connect(self):
        """Connect to the MCP server."""
        if self._session is not None:
            return
            
        try:
            # Create StreamableHTTP connection
            self._context = streamablehttp_client(self.endpoint)
            self._streams = await self._context.__aenter__()
            # Unpack the 3-tuple: read_stream, write_stream, session_id_callback
            read_stream, write_stream, session_id_callback = self._streams
            
            # Create client session (will be used with async context manager later)
            self._session = ClientSession(read_stream, write_stream)
            await self._session.initialize()
            
            logger.info(f"Connected to MCP server at {self.endpoint}")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    async def close(self):
        """Close the connection."""
        if self._context:
            await self._context.__aexit__(None, None, None)
            self._context = None
            self._session = None
            self._streams = None
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the MCP server."""
        if not self._session:
            raise RuntimeError("Not connected. Use 'async with' or call connect() first.")
        
        try:
            result = await self._session.list_tools()
            
            # Convert tool objects to dicts
            tools = []
            if hasattr(result, 'tools'):
                for tool in result.tools:
                    tools.append({
                        "name": getattr(tool, 'name', 'unknown'),
                        "description": getattr(tool, 'description', ''),
                        "inputSchema": getattr(tool, 'inputSchema', {})
                    })
            
            return tools
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Raw tool response
        """
        if not self._session:
            raise RuntimeError("Not connected. Use 'async with' or call connect() first.")
        
        try:
            return await self._session.call_tool(tool_name, arguments or {})
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise