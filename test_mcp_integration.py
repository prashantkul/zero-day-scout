#!/usr/bin/env python
"""
Test script for the MCP server integration with Zero-Day Scout.

This script tests the connection to the MCP server and the functionality
of the CVE lookup tools using the MCP client.

To use this script:
1. First start the MCP server: ./start_cve_mcp_server.sh
2. Then run this test script: python test_mcp_integration.py
"""

import os
import sys
import logging
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import our modules
from src.scout_agent.mcp_cve_client import McpCveClient
from src.scout_agent.tools import CveLookupTool

# Set up logging
logging.basicConfig(level=logging.INFO)
console = Console()

def test_mcp_connection():
    """Test the connection to the MCP server."""
    console.print("[bold]Testing MCP Server Connection[/bold]\n")
    
    try:
        # Initialize client with default settings
        client = McpCveClient()
        
        # Try a simple API call to test the connection
        console.print("[yellow]Attempting to connect to MCP server...[/yellow]")
        _ = client._make_request("vul_vendors")
        
        console.print("[green]✓ Successfully connected to MCP server![/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to MCP server: {str(e)}[/red]")
        console.print("\n[yellow]Make sure the MCP server is running with:[/yellow]")
        console.print("    ./start_cve_mcp_server.sh")
        return False

def test_basic_operations():
    """Test basic operations of the MCP client."""
    console.print("\n[bold]Testing Basic MCP Client Operations[/bold]\n")
    
    client = McpCveClient()
    
    try:
        # Test getting a specific CVE
        console.print("[yellow]Testing CVE lookup...[/yellow]")
        cve_id = "CVE-2021-44228"  # Log4j vulnerability
        cve_data = client.get_cve(cve_id)
        
        if cve_data and not (isinstance(cve_data, dict) and "error" in cve_data):
            console.print(f"[green]✓ Successfully retrieved CVE: {cve_id}[/green]")
            formatted = client.format_cve_output(cve_data)
            console.print(Panel(Markdown(formatted), title=f"CVE Details", width=100))
        else:
            console.print(f"[red]✗ Failed to retrieve CVE data for {cve_id}[/red]")
            if isinstance(cve_data, dict) and "error" in cve_data:
                console.print(f"   Error: {cve_data['error']}")
        
        # Test getting the latest CVEs
        console.print("\n[yellow]Testing latest CVEs lookup...[/yellow]")
        latest_data = client.get_latest_cves(limit=3)
        
        if latest_data and len(latest_data) > 0:
            console.print(f"[green]✓ Successfully retrieved latest CVEs[/green]")
            formatted = client.format_cve_output(latest_data[:3])  # Limit to 3 for display
            console.print(Panel(Markdown(formatted), title="Latest CVEs", width=100))
        else:
            console.print("[red]✗ Failed to retrieve latest CVEs[/red]")
        
        return True
    except Exception as e:
        console.print(f"[red]✗ Error during MCP operations: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False

def test_cve_lookup_tool():
    """Test the CveLookupTool integration."""
    console.print("\n[bold]Testing CVE Lookup Tool[/bold]\n")
    
    try:
        # Initialize tool
        tool = CveLookupTool()
        
        # Test looking up a specific CVE
        console.print("[yellow]Testing CVE lookup with tool...[/yellow]")
        result = tool._lookup_cve(cve_id="CVE-2021-44228")
        console.print(Panel(Markdown(result), title="CVE Lookup Result", width=100))
        
        # Test getting latest CVEs
        console.print("\n[yellow]Testing latest CVEs with tool...[/yellow]")
        result = tool._lookup_cve(get_latest=True, max_results=3)
        console.print(Panel(Markdown(result), title="Latest CVEs Result", width=100))
        
        return True
    except Exception as e:
        console.print(f"[red]✗ Error testing CVE lookup tool: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False

def main():
    """Run the MCP integration tests."""
    console.print("\n[bold green]===== MCP Server Integration Test =====\n[/bold green]")
    
    # Test MCP connection first
    connection_ok = test_mcp_connection()
    if not connection_ok:
        console.print("\n[bold red]Aborting tests: Cannot connect to MCP server.[/bold red]")
        return 1
    
    # Test basic operations
    operations_ok = test_basic_operations()
    
    # Test CVE lookup tool
    tool_ok = test_cve_lookup_tool()
    
    # Print summary
    console.print("\n[bold]===== Test Summary =====\n[/bold]")
    console.print(f"MCP Connection: {'[green]PASSED[/green]' if connection_ok else '[red]FAILED[/red]'}")
    console.print(f"Basic Operations: {'[green]PASSED[/green]' if operations_ok else '[red]FAILED[/red]'}")
    console.print(f"CVE Lookup Tool: {'[green]PASSED[/green]' if tool_ok else '[red]FAILED[/red]'}")
    
    # Exit with appropriate code
    if connection_ok and operations_ok and tool_ok:
        console.print("\n[bold green]All tests passed successfully![/bold green]")
        return 0
    else:
        console.print("\n[bold red]Some tests failed, see details above.[/bold red]")
        return 1

if __name__ == "__main__":
    sys.exit(main())