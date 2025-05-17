"""
MCP Client for CVE-Search integration with Zero-Day Scout.

This module provides a client interface to communicate with the CVE-Search MCP server,
allowing the agent system to query vulnerability information from CVE databases.
"""

import logging
import json
import httpx
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class McpCveClient:
    """
    Client for interacting with the CVE-Search MCP server.
    
    This class handles the communication with the MCP server, making requests
    and formatting responses for use by the agent tools.
    """
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        """
        Initialize the MCP CVE client.
        
        Args:
            base_url: The base URL of the MCP server (default: http://localhost:3000)
        """
        self.base_url = base_url
        self.timeout = 10.0  # Default timeout in seconds
        self.session = httpx.Client(timeout=self.timeout)
        logger.info(f"Initialized MCP CVE client with base URL: {base_url}")
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the MCP server.
        
        Args:
            endpoint: The API endpoint to call
            params: Optional query parameters
            
        Returns:
            The JSON response from the server
            
        Raises:
            Exception: If the request fails or returns an error
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            logger.debug(f"Making request to MCP server: {url} with params: {params}")
            response = self.session.get(url, params=params)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            # Try to parse JSON response
            data = response.json()
            return data
        except httpx.RequestError as e:
            logger.error(f"Error connecting to MCP server: {e}")
            raise Exception(f"Failed to connect to MCP server: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from MCP server: {e}")
            raise Exception(f"MCP server returned an error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise Exception(f"Invalid response from MCP server: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in MCP request: {e}")
            raise
    
    def get_vendors(self) -> List[str]:
        """
        Get a list of all vendors in the CVE database.
        
        Returns:
            List of vendor names
        """
        try:
            data = self._make_request("api/browse/vendors")
            if isinstance(data, list):
                return data
            else:
                logger.warning(f"Unexpected vendor data format: {type(data)}")
                return []
        except Exception as e:
            logger.error(f"Failed to get vendors: {e}")
            return []
    
    def get_products(self, vendor: str) -> List[str]:
        """
        Get a list of products for a specific vendor.
        
        Args:
            vendor: The vendor name to look up products for
            
        Returns:
            List of product names
        """
        try:
            data = self._make_request(f"api/browse/products/{vendor}")
            if isinstance(data, list):
                return data
            else:
                logger.warning(f"Unexpected product data format: {type(data)}")
                return []
        except Exception as e:
            logger.error(f"Failed to get products for vendor '{vendor}': {e}")
            return []
    
    def get_cve(self, cve_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific CVE.
        
        Args:
            cve_id: The CVE ID to look up (e.g., CVE-2021-34434)
            
        Returns:
            Dictionary with CVE details
        """
        try:
            # Ensure CVE ID is properly formatted
            if not cve_id.startswith("CVE-"):
                cve_id = f"CVE-{cve_id}"
            
            data = self._make_request(f"api/cve/{cve_id}")
            return data
        except Exception as e:
            logger.error(f"Failed to get CVE '{cve_id}': {e}")
            return {"error": str(e)}
    
    def search_cves(self, 
                   keyword: Optional[str] = None,
                   vendor: Optional[str] = None,
                   product: Optional[str] = None,
                   cwe: Optional[str] = None,
                   limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for CVEs based on various criteria.
        
        Args:
            keyword: Keyword to search in CVE descriptions
            vendor: Vendor name to filter by
            product: Product name to filter by
            cwe: CWE ID to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of matching CVE entries
        """
        try:
            # Build query parameters based on provided filters
            params = {}
            if keyword:
                params["keyword"] = keyword
            if limit:
                params["limit"] = str(limit)
            
            # Determine the endpoint based on search criteria
            if vendor and product:
                endpoint = f"api/search/vendor_product/{vendor}/{product}"
            elif vendor:
                endpoint = f"api/search/vendor/{vendor}"
            elif cwe:
                endpoint = f"api/search/cwe/{cwe}"
            else:
                endpoint = "api/search"
            
            data = self._make_request(endpoint, params)
            
            # Handle different response formats
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            elif isinstance(data, list):
                return data
            else:
                return [data] if data else []
                
        except Exception as e:
            logger.error(f"Failed to search CVEs: {e}")
            return []
    
    def get_latest_cves(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Get the latest CVEs from the database.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of recent CVE entries
        """
        try:
            data = self._make_request("api/recent", {"limit": str(limit)})
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "results" in data:
                return data["results"]
            else:
                logger.warning(f"Unexpected latest CVE data format: {type(data)}")
                return []
        except Exception as e:
            logger.error(f"Failed to get latest CVEs: {e}")
            return []
    
    def format_cve_output(self, cve_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """
        Format CVE data into a readable string for the agent.
        
        Args:
            cve_data: CVE data to format (single entry or list)
            
        Returns:
            Formatted string with CVE information
        """
        # Handle empty results
        if not cve_data:
            return "No CVE information found."
        
        # Handle list of CVEs
        if isinstance(cve_data, list):
            result = f"Found {len(cve_data)} CVE entries:\n\n"
            
            for cve in cve_data[:10]:  # Limit to 10 entries in output
                try:
                    # Extract key information
                    cve_id = cve.get("id") or cve.get("cve_id") or "Unknown CVE"
                    summary = cve.get("summary", "No description available")
                    
                    # Format CVSS information
                    cvss = cve.get("cvss", None)
                    cvss_str = f" (CVSS: {cvss})" if cvss else ""
                    
                    # Format published date
                    published = cve.get("Published", None) or cve.get("published", None)
                    if published:
                        try:
                            if isinstance(published, str):
                                date_obj = datetime.strptime(published.split('T')[0], "%Y-%m-%d")
                                date_str = date_obj.strftime("%b %d, %Y")
                            else:
                                date_str = "Unknown date"
                        except Exception:
                            date_str = published
                    else:
                        date_str = "Unknown date"
                    
                    # Add to result
                    result += f"### {cve_id}{cvss_str}\n"
                    result += f"**Published:** {date_str}\n"
                    result += f"**Summary:** {summary}\n\n"
                except Exception as e:
                    logger.error(f"Error formatting CVE entry: {e}")
                    result += f"Error formatting entry: {str(e)}\n\n"
            
            # Add note if results were limited
            if len(cve_data) > 10:
                result += f"_Showing 10 of {len(cve_data)} results_"
            
            return result
            
        # Handle single CVE entry
        elif isinstance(cve_data, dict):
            try:
                if "error" in cve_data:
                    return f"Error retrieving CVE information: {cve_data['error']}"
                
                cve_id = cve_data.get("id") or cve_data.get("cve_id") or "Unknown CVE"
                result = f"## {cve_id}\n\n"
                
                # Add summary
                summary = cve_data.get("summary", "No description available")
                result += f"**Summary:** {summary}\n\n"
                
                # Add CVSS information
                cvss = cve_data.get("cvss", None)
                if cvss:
                    result += f"**CVSS Score:** {cvss}\n"
                
                # Add published date
                published = cve_data.get("Published", None) or cve_data.get("published", None)
                if published:
                    try:
                        if isinstance(published, str):
                            date_obj = datetime.strptime(published.split('T')[0], "%Y-%m-%d")
                            date_str = date_obj.strftime("%b %d, %Y")
                        else:
                            date_str = "Unknown date"
                    except Exception:
                        date_str = published
                    result += f"**Published:** {date_str}\n"
                
                # Add CWE information
                cwe = cve_data.get("cwe", None)
                if cwe:
                    if isinstance(cwe, str):
                        result += f"**CWE:** {cwe}\n"
                    elif isinstance(cwe, list) and cwe:
                        result += f"**CWE:** {', '.join(cwe)}\n"
                
                # Add reference information
                references = cve_data.get("references", [])
                if references:
                    result += "\n**References:**\n"
                    for ref in references[:5]:  # Limit references
                        result += f"- {ref}\n"
                    if len(references) > 5:
                        result += f"_...and {len(references) - 5} more references_\n"
                
                # Add affected products
                affected = cve_data.get("vulnerable_product", []) or cve_data.get("vulnerable_products", [])
                if affected:
                    result += "\n**Affected Products:**\n"
                    for product in affected[:10]:  # Limit products
                        # Clean up product string
                        product_clean = product.replace("cpe:/", "").replace("cpe:2.3:", "")
                        result += f"- {product_clean}\n"
                    if len(affected) > 10:
                        result += f"_...and {len(affected) - 10} more affected products_\n"
                
                return result
            except Exception as e:
                logger.error(f"Error formatting CVE data: {e}")
                return f"Error formatting CVE information: {str(e)}"
        else:
            return "Invalid CVE data format."