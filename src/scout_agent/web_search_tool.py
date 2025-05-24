"""
Web Search Tool for the Zero-Day Scout Agentic RAG system.

This module implements a web search tool using the Tavily API:
- WebSearchTool: Tool for searching the web for security information
"""

from typing import Dict, List, Any, Optional
import json
import logging
import os
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

from google.adk.tools import FunctionTool

# Load environment variables (including Tavily API key)
load_dotenv()

logger = logging.getLogger(__name__)


class WebSearchTool(FunctionTool):
    """
    Tool for searching the internet for up-to-date security information.
    
    This tool uses the Tavily search API to retrieve information from the internet,
    allowing agents to access current and accurate security information beyond
    what might be available in the RAG corpus or CVE database.
    """
    
    def __init__(self):
        """Initialize the web search tool."""
        # API key for Tavily - load from environment variable
        self.api_key = os.environ.get("TAVILY_API_KEY")
        self.search_endpoint = "https://api.tavily.com/search"
        
        # Define the function that will be called by the tool
        def web_search(
            query: str,
            include_answer: bool = True,
            max_results: int = 5,
            include_domains: Optional[List[str]] = None,
            exclude_domains: Optional[List[str]] = None,
            search_type: str = "security"
        ) -> str:
            """
            Search the web for security-related information using Tavily.
            
            Args:
                query: The search query (e.g., "latest zero-day vulnerabilities")
                include_answer: Whether to include an AI-generated answer summary
                max_results: Maximum number of results to return (1-10)
                include_domains: Only include results from these domains
                exclude_domains: Exclude results from these domains
                search_type: Type of search ('security' or 'general')
                
            Returns:
                Search results formatted as text
            """
            return self._search_web(
                query, include_answer, max_results, include_domains, exclude_domains, search_type
            )
        
        # Initialize the FunctionTool with our function
        super().__init__(func=web_search)
    
    def _search_web(
        self,
        query: str,
        include_answer: bool = True,
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        search_type: str = "security"
    ) -> str:
        """
        Execute a web search query using Tavily API.
        
        Args:
            query: The search query to use
            include_answer: Whether to include an AI-generated answer summary
            max_results: Maximum number of results to return (1-10)
            include_domains: Only include results from these domains
            exclude_domains: Exclude results from these domains
            search_type: Type of search ('security' or 'general')
            
        Returns:
            Search results formatted as text
        """
        if not query:
            return "Error: No search query provided"
        
        if not self.api_key:
            logger.warning("Tavily API key not found in environment variables")
            return (
                "Web Search Results (Fallback Mode):\n\n"
                "Web search capability is currently unavailable due to missing API key. "
                "Please try using the RAG query tool or CVE lookup tool instead."
            )
        
        # Validate parameters
        max_results = min(max(1, max_results), 10)  # Between 1 and 10
        
        # Construct search context for security-focused queries
        if search_type.lower() == "security":
            # Enhance query with security focus
            security_context = "cybersecurity vulnerabilities CVE"
            enhanced_query = f"{query} {security_context}"
        else:
            enhanced_query = query
            
        try:
            logger.info(f"Executing web search: {query}")
            
            # Prepare the request payload
            payload = {
                "api_key": self.api_key,
                "query": enhanced_query,
                "search_depth": "advanced",
                "max_results": max_results,
                "include_answer": include_answer,
            }
            
            # Add optional domain filters if provided
            if include_domains:
                payload["include_domains"] = include_domains
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains
            
            # Execute the search request
            response = requests.post(self.search_endpoint, json=payload)
            
            # Check if the request was successful
            if response.status_code != 200:
                logger.error(f"Tavily API error: {response.status_code} - {response.text}")
                return f"Error executing web search: API returned status code {response.status_code}"
            
            # Extract results from the response
            search_results = response.json()
            
            # Format the results for display
            return self._format_search_results(search_results, query)
            
        except Exception as e:
            logger.error(f"Error in web search: {e}")
            return f"Error searching the web: {str(e)}"
    
    def _format_search_results(self, search_results: Dict[str, Any], query: str) -> str:
        """
        Format search results into a readable text format.
        
        Args:
            search_results: The search results from Tavily API
            query: The original search query
            
        Returns:
            Formatted text with search results
        """
        try:
            # Extract the result list and answer if available
            results = search_results.get("results", [])
            answer = search_results.get("answer", "")
            
            # Format as markdown for better readability
            lines = []
            
            # Add the answer if available
            if answer:
                lines.append(f"# Web Search Results for: {query}\n")
                lines.append(f"{answer}\n")
            else:
                lines.append(f"The following information was found via web search for: '{query}'\n")
            
            # Add results
            if results:
                lines.append("## Research Sources\n")
                lines.append("### Web Search Sources\n")
                
                for i, result in enumerate(results, 1):
                    title = result.get("title", "Untitled")
                    url = result.get("url", "")
                    content = result.get("content", "")
                    
                    # Extract domain for display
                    domain = urlparse(url).netloc
                    
                    # Format the source nicely - using same format as RAG and CVE sources
                    lines.append(f"**{i}. {title}**")
                    lines.append(f"*Source:* [{domain}]({url})")
                    
                    # Add a snippet of content (truncated for readability)
                    if content:
                        snippet = content[:200] + "..." if len(content) > 200 else content
                        lines.append(f"*Excerpt:* \"{snippet}\"\n")
            else:
                lines.append("No results found.")
                
            return "\n".join(lines)
        
        except Exception as e:
            logger.error(f"Error formatting search results: {e}")
            return f"Error formatting search results: {str(e)}"