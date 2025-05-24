"""
CVE Lookup Agent for Zero-Day Scout.

This module implements a specialized agent for CVE (Common Vulnerabilities and Exposures) lookups
using direct MCP tools from the CVE Search MCP Server.
"""

import asyncio
import logging
import sys
import os
import time
import json
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools import agent_tool
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Part, UserContent

# Add the project root to the Python path if needed
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import constants from config
try:
    from config.constants import MCP_SERVER_CLIENT_HOST, MCP_SERVER_PORT, MCP_SERVER_TRANSPORT
except ImportError:
    # Default values if import fails
    MCP_SERVER_CLIENT_HOST = "localhost"
    MCP_SERVER_PORT = 8080
    MCP_SERVER_TRANSPORT = "streamable-http"

logger = logging.getLogger(__name__)


class MCPStreamableHTTPClient:
    """Direct MCP StreamableHTTP client for CVE tools."""
    
    def __init__(self, endpoint: str):
        """Initialize the MCP StreamableHTTP client.
        
        Args:
            endpoint: The StreamableHTTP endpoint URL
        """
        if urlparse(endpoint).scheme not in ("http", "https"):
            raise ValueError(f"Endpoint {endpoint} is not a valid HTTP(S) URL")
        self.endpoint = endpoint
        self._tools = []
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the MCP server."""
        try:
            async with streamablehttp_client(self.endpoint) as streams:
                # Unpack the 3-tuple: read_stream, write_stream, session_id_callback
                read_stream, write_stream, session_id_callback = streams
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    self._tools = tools_result.tools if hasattr(tools_result, 'tools') else []
                    return self._tools
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with the given arguments."""
        try:
            async with streamablehttp_client(self.endpoint) as streams:
                # Unpack the 3-tuple: read_stream, write_stream, session_id_callback
                read_stream, write_stream, session_id_callback = streams
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise


# CVE agent prompt with instructions on using MCP tools
CVE_AGENT_PROMPT = """
You are a specialized CVE Lookup tool that provides authoritative information about security vulnerabilities.

You have access to CVE database tools for vulnerability information:
- search_cve: Search for detailed information about a specific CVE by ID
- get_latest_cves: Get the latest vulnerabilities from the database
- search_vendor_product_cves: Search for CVEs affecting a specific vendor and product

When you receive a query about vulnerabilities:
1. For specific CVE IDs (e.g., "CVE-2021-44228"), use search_cve with the exact ID
2. For vendor/product vulnerabilities, use search_vendor_product_cves
3. For latest vulnerability information, use get_latest_cves
4. For well-known vulnerability names like "Log4Shell", map them to the correct CVE ID (CVE-2021-44228)

Always provide comprehensive information including:
- Technical description of the vulnerability
- CVSS severity scores
- Affected software versions
- Exploitation methods and attack vectors
- Recommended mitigations and patches
- Publication and disclosure dates

Format your responses clearly with proper structure and headers. Focus on providing accurate, 
authoritative information from official vulnerability databases.

IMPORTANT: Always use the available tools to fetch real vulnerability data - never fabricate or guess information.
"""


class CveLookupAgent:
    """
    Specialized agent for CVE lookups using direct MCP tools.
    
    This agent connects to the CVE Search MCP Server to access up-to-date
    vulnerability information from official CVE databases.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17"):
        """
        Initialize the CVE Lookup Agent.
        
        Args:
            model_name: The Vertex AI model to use
        """
        self.model_name = model_name
        self.mcp_client = None
        self._connected = False

        # Create the CVE agent that will receive transfers
        self.agent = LlmAgent(
            name="cve_lookup_specialist",
            description="CVE lookup specialist for vulnerability information",
            model=self.model_name,
            instruction=CVE_AGENT_PROMPT
        )

    async def connect(self) -> bool:
        """
        Connect to the MCP server and retrieve CVE tools.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            logger.info("=========== CVE Lookup Agent ===========")
            logger.info("Connecting to MCP server for CVE tools")
            # Connect to the MCP server using StreamableHTTP endpoint
            server_url = f"http://{MCP_SERVER_CLIENT_HOST}:{MCP_SERVER_PORT}/mcp/"
            logger.info(f"Connecting to MCP server at: {server_url}")

            # Create MCP StreamableHTTP client
            self.mcp_client = MCPStreamableHTTPClient(server_url)

            # List available tools
            tools = await self.mcp_client.list_tools()
            logger.info(f"Connected to MCP server with {len(tools)} tools")

            # Log available tools
            for tool in tools:
                tool_name = getattr(tool, 'name', 'unknown')
                tool_desc = getattr(tool, 'description', 'no description')
                logger.info(f"Tool: {tool_name} - {tool_desc}")

            # Filter to only keep CVE-related tools
            cve_tools = [
                tool for tool in tools 
                if getattr(tool, 'name', '').startswith('vul_')
            ]

            if cve_tools:
                logger.info(f"Found {len(cve_tools)} CVE tools from MCP server")

                # Create ADK-compatible tools from MCP tools
                adk_tools = self._create_adk_tools()

                # Recreate the agent with the ADK tools
                self.agent = LlmAgent(
                    name="cve_lookup_specialist",
                    description="CVE lookup specialist for vulnerability information",
                    model=self.model_name,
                    instruction=CVE_AGENT_PROMPT,
                    tools=adk_tools
                )

                self._connected = True
                return True
            else:
                logger.warning("No CVE tools found in MCP server")
                self._connected = False
                return False

        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            import traceback
            logger.error(f"Connection error traceback: {traceback.format_exc()}")
            self._connected = False
            return False

    def _create_adk_tools(self) -> List[FunctionTool]:
        """Create ADK-compatible FunctionTools from MCP tools."""
        adk_tools = []

        # CVE Search tool
        async def search_cve(cve_id: str) -> str:
            """Search for detailed information about a specific CVE by ID."""
            try:
                result = await self.mcp_client.call_tool("vul_cve_search", {"cve_id": cve_id})
                return self._format_mcp_result(result)
            except Exception as e:
                return f"Error searching for CVE {cve_id}: {str(e)}"

        adk_tools.append(FunctionTool(search_cve))

        # Latest CVEs tool
        async def get_latest_cves() -> str:
            """Get the latest 30 CVEs from the database."""
            try:
                result = await self.mcp_client.call_tool("vul_last_cves", {})
                return self._format_mcp_result(result)
            except Exception as e:
                return f"Error getting latest CVEs: {str(e)}"

        adk_tools.append(FunctionTool(get_latest_cves))

        # Vendor products tool
        async def search_vendor_product_cves(vendor: str, product: str) -> str:
            """Search for CVEs affecting a specific vendor and product."""
            try:
                result = await self.mcp_client.call_tool("vul_vendor_product_cve", {"vendor": vendor, "product": product})
                return self._format_mcp_result(result)
            except Exception as e:
                return f"Error searching CVEs for {vendor} {product}: {str(e)}"

        adk_tools.append(FunctionTool(search_vendor_product_cves))

        return adk_tools

    def get_agent_tool(self):
        """Create an AgentTool wrapper for this CVE agent."""

        class CveAgentTool(agent_tool.AgentTool):
            def __init__(self, cve_agent_instance):
                self.cve_agent_instance = cve_agent_instance
                super().__init__(agent=cve_agent_instance.agent)

            async def run_async(self, *, args, tool_context):
                """Run the CVE agent and capture its response."""
                logger.info("Running CVE agent tool")
                logger.info(f"Received args: {args}")
                logger.info(f"Tool context: {tool_context}")

                # Extract the query from the args - AgentTool typically passes 'query' or 'input'
                query = args.get('query') or args.get('input') or str(args)

                # Use the CVE agent's lookup method to process the query
                try:
                    result = await self.cve_agent_instance.lookup(query)
                    logger.info(f"Agent tool result: {result}")
                    return result
                except Exception as e:
                    return f"Error during CVE lookup: {str(e)}"

        return CveAgentTool(self)

    def _format_mcp_result(self, result) -> str:
        """Format MCP tool result for display."""
        if hasattr(result, 'content') and result.content:
            # Extract text content from the result
            text_parts = []
            for content in result.content:
                if hasattr(content, 'text'):
                    text_parts.append(content.text)

            if text_parts:
                # Parse JSON if possible for better formatting
                try:
                    json_data = json.loads(text_parts[0])
                    return json.dumps(json_data, indent=2)
                except json.JSONDecodeError:
                    # Return as plain text
                    return text_parts[0]
            else:
                return "No text content in response"
        else:
            return f"Tool result: {str(result)}"

    async def lookup(self, query: str, timeout: float = 60.0) -> str:
        logger.info(f"CVE_AGENT.lookup() called with query: \"{query}\"")
        logger.info(f"CVE_AGENT.lookup(): Initial state - self.mcp_client is {'set' if self.mcp_client else 'None'}, self._connected is {self._connected}")

        if not self._connected or not self.mcp_client:
            logger.warning("CVE_AGENT.lookup(): Not connected or mcp_client is None. Attempting to connect...")
            connected_in_lookup = await self.connect() # connect() also logs its progress
            logger.info(f"CVE_AGENT.lookup(): Connection attempt result: {connected_in_lookup}. New state - self.mcp_client is {'set' if self.mcp_client else 'None'}, self._connected is {self._connected}")
            if not self.mcp_client: # Strict check after attempting connection
                logger.error("CVE_AGENT.lookup(): CRITICAL - self.mcp_client is None after connection attempt. Cannot proceed.")
                return "Error: Could not connect to CVE database. MCP client is not available."

        try:
            tool_name = None
            tool_params = {}
            extracted_cve_id = None # To store the CVE ID if found for specific formatting

            query_lower = query.lower()
            logger.info(f"CVE_AGENT.lookup(): Parsing query: \"{query_lower}\"")

            import re
            cve_match = re.search(r'cve-\d{4}-\d{4,}', query_lower) # Search in lowercase query
            if cve_match:
                extracted_cve_id = cve_match.group(0).upper()
                tool_name = "vul_cve_search"
                tool_params = {"cve_id": extracted_cve_id}
                logger.info(f"CVE_AGENT.lookup(): Determined tool: '{tool_name}' with params: {tool_params} for CVE ID: {extracted_cve_id}")
            elif "latest" in query_lower or "recent" in query_lower:
                tool_name = "vul_last_cves"
                tool_params = {}
                logger.info(f"CVE_AGENT.lookup(): Determined tool: '{tool_name}' for latest CVEs.")
            elif "database" in query_lower and ("update" in query_lower or "status" in query_lower):
                tool_name = "vul_db_update_status"
                tool_params = {}
                logger.info(f"CVE_AGENT.lookup(): Determined tool: '{tool_name}' for DB status.")
            else:
                if 'cve-' in query_lower:
                     logger.warning(f"CVE_AGENT.lookup(): Query contains 'cve-' but no specific ID matched regex. Defaulting or erroring might be better.")
                     tool_name = "vul_last_cves"
                     tool_params = {}
                     logger.info(f"CVE_AGENT.lookup(): Defaulting to '{tool_name}' due to ambiguous CVE query.")
                else:
                    tool_name = "vul_last_cves" # Default for non-specific queries
                    tool_params = {}
                    logger.info(f"CVE_AGENT.lookup(): Defaulting to '{tool_name}' for general query.")

            if not tool_name:
                logger.error("CVE_AGENT.lookup(): Could not determine an MCP tool to call.")
                return "Error: Could not determine appropriate CVE lookup tool for this query."

            logger.info(f"CVE_AGENT.lookup(): Attempting to call MCP tool '{tool_name}' with params: {tool_params}")
            mcp_result = await self.mcp_client.call_tool(tool_name, tool_params)
            logger.info(f"CVE_AGENT.lookup(): Raw MCP result object: {type(mcp_result)}")

            if not (hasattr(mcp_result, 'content') and mcp_result.content):
                logger.warning(f"CVE_AGENT.lookup(): MCP result for '{tool_name}' has no .content or it's empty. Result: {mcp_result}")
                return f"No content received from CVE tool '{tool_name}'."

            text_parts = []
            for content_part in mcp_result.content:
                if hasattr(content_part, 'text') and content_part.text is not None:
                    text_parts.append(content_part.text)
            
            if not text_parts:
                logger.warning(f"CVE_AGENT.lookup(): No non-None text parts found in MCP result for '{tool_name}'. Full content: {mcp_result.content}")
                return f"No usable text content received from CVE tool '{tool_name}'."

            json_text_payload = text_parts[0]
            logger.info(f"CVE_AGENT.lookup(): Text payload from MCP tool '{tool_name}': {json_text_payload[:1000]}...") # Log more for debugging

            try:
                json_data = json.loads(json_text_payload)
                logger.info(f"CVE_AGENT.lookup(): Successfully parsed JSON from MCP tool '{tool_name}'.")
                # logger.debug(f"CVE_AGENT.lookup(): Parsed JSON data: {json.dumps(json_data, indent=2)}") # Uncomment for full JSON

                if tool_name == "vul_cve_search" and extracted_cve_id and isinstance(json_data, dict):
                    logger.info(f"CVE_AGENT.lookup(): Formatting details for CVE: {extracted_cve_id} using CVE JSON 5.1 structure")
                    formatted_output = f"## CVE Details for {extracted_cve_id}\n\n"

                    cna_container = json_data.get("containers", {}).get("cna", {})
                    cve_metadata = json_data.get("cveMetadata", {})

                    descriptions = cna_container.get("descriptions", [])
                    summary = "Not available"
                    for desc in descriptions:
                        if desc.get("lang") == "en" and desc.get("value"):
                            summary = desc["value"]
                            break
                    formatted_output += f"**Summary:** {summary}\n\n"

                    metrics_list = cna_container.get("metrics", [])
                    cvss_v3_score_str = "Not available"
                    cvss_v3_vector_str = ""
                    for metric_set in metrics_list:
                        if "cvssV3_1" in metric_set:
                            cvss_data = metric_set["cvssV3_1"]
                            cvss_v3_score_str = str(cvss_data.get("baseScore", "Not available"))
                            cvss_v3_vector_str = cvss_data.get("vectorString", "")
                            break
                        elif "cvssV3_0" in metric_set:
                            cvss_data = metric_set["cvssV3_0"]
                            cvss_v3_score_str = str(cvss_data.get("baseScore", "Not available"))
                            cvss_v3_vector_str = cvss_data.get("vectorString", "")
                    
                    if cvss_v3_score_str != "Not available":
                        formatted_output += f"**CVSSv3 Score:** {cvss_v3_score_str}"
                        if cvss_v3_vector_str:
                            formatted_output += f" (`{cvss_v3_vector_str}`)"
                        formatted_output += "\n\n"
                    else:
                        # Check for older top-level CVSS field as a fallback (less likely for JSON 5.1)
                        cvss_score_legacy = json_data.get('cvss')
                        if cvss_score_legacy is not None:
                             formatted_output += f"**CVSS Score (legacy):** {cvss_score_legacy}\n\n"
                        else:
                             formatted_output += f"**CVSS Score:** Not available\n\n"

                    published_date = cve_metadata.get("datePublished")
                    if published_date:
                        formatted_output += f"**Published:** {published_date}\n"
                    
                    date_updated = cve_metadata.get("dateUpdated")
                    if date_updated:
                        formatted_output += f"**Last Updated (Metadata):** {date_updated}\n"
                    formatted_output += "\n"

                    references_list = cna_container.get("references", [])
                    if references_list and isinstance(references_list, list) and len(references_list) > 0:
                        formatted_output += "**References:**\n"
                        for ref_item in references_list[:5]:
                            url = ref_item.get("url")
                            name = ref_item.get("name")
                            if url:
                                 formatted_output += f"- {url}\n"
                            elif name:
                                 formatted_output += f"- (Name: {name})\n" # Indicate if it's just a name
                        if len(references_list) > 5:
                            formatted_output += f"- ...and {len(references_list) - 5} more.\n"
                        formatted_output += "\n"
                    else:
                        formatted_output += "**References:** Not available\n\n"

                    affected_list = cna_container.get("affected", [])
                    if affected_list and isinstance(affected_list, list) and len(affected_list) > 0:
                        formatted_output += "**Affected Products (Sample):**\n"
                        for aff_item in affected_list[:2]:
                            vendor = aff_item.get("vendor", "N/A")
                            product = aff_item.get("product", "N/A")
                            versions_info = "Versions not specified"
                            versions_data = aff_item.get("versions", [])
                            if versions_data:
                                v_details_list = []
                                for v_entry in versions_data[:2]:
                                    status = v_entry.get("status")
                                    ver = v_entry.get("version")
                                    lte = v_entry.get("lessThanOrEqual")
                                    lt = v_entry.get("lessThan")
                                    v_str = ver or lte or lt or ""
                                    if status and v_str:
                                        v_details_list.append(f"{v_str} ({status})")
                                    elif v_str:
                                        v_details_list.append(v_str)
                                if v_details_list:
                                    versions_info = ", ".join(v_details_list)
                            formatted_output += f"- Vendor: {vendor}, Product: {product} ({versions_info})\n"
                        if len(affected_list) > 2:
                            formatted_output += "- ...and more affected products/versions.\n"
                        formatted_output += "\n"
                        
                    problem_types = cna_container.get("problemTypes", [])
                    if problem_types and isinstance(problem_types, list) and len(problem_types) > 0:
                        cwe_ids = []
                        for pt_entry in problem_types:
                            for desc_entry in pt_entry.get("description", []):
                                if desc_entry.get("lang") == "en" and desc_entry.get("cweId"):
                                    cwe_ids.append(desc_entry["cweId"])
                        if cwe_ids:
                            formatted_output += f"**CWE(s):** {', '.join(list(set(cwe_ids)))}\n\n" # Use set to avoid duplicates

                    logger.info(f"CVE_AGENT.lookup(): Successfully formatted output for {extracted_cve_id}.")
                    return formatted_output
                else:
                    logger.info(f"CVE_AGENT.lookup(): Formatting generic JSON output for tool '{tool_name}'.")
                    return f"Response from '{tool_name}':\n\n```json\n{json.dumps(json_data, indent=2)}\n```"

            except json.JSONDecodeError as je:
                logger.error(f"CVE_AGENT.lookup(): JSONDecodeError for '{tool_name}' output: {je}. Payload was: {json_text_payload[:1000]}...")
                return f"Error: Could not parse JSON response from CVE tool '{tool_name}'. Raw response snippet: {json_text_payload[:200]}"
            except Exception as fmt_e:
                logger.error(f"CVE_AGENT.lookup(): Error formatting result for '{tool_name}': {fmt_e}", exc_info=True)
                return f"Error formatting result from CVE tool '{tool_name}'. Raw JSON might be: {json.dumps(json_data, indent=2) if 'json_data' in locals() else 'not available'}"

        except Exception as e:
            logger.error(f"CVE_AGENT.lookup(): General error during lookup for query \"{query}\": {e}", exc_info=True)
            return f"Error during CVE lookup: {str(e)}"

    async def cleanup(self):
        """
        Clean up resources used by the agent.
        
        This should be called when the agent is no longer needed.
        """
        logger.info("Cleaning up CVE Lookup Agent resources")

        if self.mcp_client:
            self.mcp_client = None

        self._connected = False
        logger.info("CVE Lookup Agent resources cleaned up")


# # Simple usage example
# async def main():
#     """Test the CVE Lookup Agent with a sample query."""
#     agent = CveLookupAgent()
#     connected = await agent.connect()

#     if connected:
#         result = await agent.lookup("Tell me about CVE-2021-44228 (Log4Shell)")
#         print(result)
#     else:
#         print("Failed to connect to MCP server")

#     await agent.cleanup()


# if __name__ == "__main__":
#     # Run the test function if this file is executed directly
#     asyncio.run(main())
