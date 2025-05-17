#!/usr/bin/env python
"""
Test script for the MCP CVE integration in Zero-Day Scout.

This script tests the MCP CVE client and the updated CveLookupTool.
"""

import os
import sys
import logging
import json
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import MCP modules
from src.scout_agent.mcp_cve_client import McpCveClient
from src.scout_agent.tools import CveLookupTool

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

def test_mcp_client():
    """Test the MCP CVE client directly."""
    console.print("[bold]Testing MCP CVE Client[/bold]")
    
    try:
        # Initialize client
        client = McpCveClient()
        console.print("[green]✓ Client initialized[/green]")
        
        # Test getting vendors
        console.print("\n[bold]Testing vendor lookup...[/bold]")
        vendors = client.get_vendors()
        if vendors:
            console.print(f"[green]✓ Found {len(vendors)} vendors[/green]")
            console.print(f"Sample vendors: {', '.join(vendors[:5])}...")
        else:
            console.print("[yellow]No vendors found[/yellow]")
        
        # Test getting products for a vendor
        console.print("\n[bold]Testing product lookup...[/bold]")
        test_vendor = "apache"
        products = client.get_products(test_vendor)
        if products:
            console.print(f"[green]✓ Found {len(products)} products for {test_vendor}[/green]")
            console.print(f"Sample products: {', '.join(products[:5])}...")
        else:
            console.print(f"[yellow]No products found for {test_vendor}[/yellow]")
        
        # Test getting a specific CVE
        console.print("\n[bold]Testing CVE lookup...[/bold]")
        test_cve = "CVE-2021-44228"  # Log4Shell vulnerability
        cve_data = client.get_cve(test_cve)
        if isinstance(cve_data, dict) and cve_data.get("id") == test_cve:
            console.print(f"[green]✓ Successfully retrieved {test_cve}[/green]")
            # Show formatted output
            formatted = client.format_cve_output(cve_data)
            console.print(Panel(Markdown(formatted), title=f"[cyan]{test_cve} Details[/cyan]", width=100))
        else:
            console.print(f"[yellow]Failed to retrieve {test_cve} or unexpected format[/yellow]")
            console.print(cve_data)
        
        # Test getting latest CVEs
        console.print("\n[bold]Testing latest CVEs...[/bold]")
        latest_cves = client.get_latest_cves(limit=5)
        if latest_cves and len(latest_cves) > 0:
            console.print(f"[green]✓ Retrieved {len(latest_cves)} latest CVEs[/green]")
            # Show formatted output
            formatted = client.format_cve_output(latest_cves)
            console.print(Panel(Markdown(formatted), title="[cyan]Latest CVEs[/cyan]", width=100))
        else:
            console.print("[yellow]Failed to retrieve latest CVEs or none available[/yellow]")
        
        # Test searching for CVEs
        console.print("\n[bold]Testing CVE search...[/bold]")
        search_keyword = "log4j"
        search_results = client.search_cves(keyword=search_keyword, limit=5)
        if search_results and len(search_results) > 0:
            console.print(f"[green]✓ Found {len(search_results)} CVEs matching '{search_keyword}'[/green]")
            # Show formatted output
            formatted = client.format_cve_output(search_results)
            console.print(Panel(Markdown(formatted), title=f"[cyan]Search Results for '{search_keyword}'[/cyan]", width=100))
        else:
            console.print(f"[yellow]No CVEs found matching '{search_keyword}'[/yellow]")
        
        return True
    
    except Exception as e:
        console.print(f"[bold red]Error testing MCP client: {e}[/bold red]")
        import traceback
        console.print(traceback.format_exc())
        return False

def test_cve_lookup_tool():
    """Test the CveLookupTool."""
    console.print("[bold]\nTesting CVE Lookup Tool[/bold]")
    
    try:
        # Initialize tool
        tool = CveLookupTool()
        console.print("[green]✓ Tool initialized[/green]")
        
        # Test specific CVE lookup
        console.print("\n[bold]Testing specific CVE lookup...[/bold]")
        cve_result = tool._lookup_cve(cve_id="CVE-2021-44228")
        console.print(Panel(Markdown(cve_result), title="[cyan]CVE Lookup Result[/cyan]", width=100))
        
        # Test vendor lookup
        console.print("\n[bold]Testing vendor lookup...[/bold]")
        vendor_result = tool._lookup_cve(vendor="apache", max_results=5)
        console.print(Panel(Markdown(vendor_result), title="[cyan]Vendor Lookup Result[/cyan]", width=100))
        
        # Test keyword search
        console.print("\n[bold]Testing keyword search...[/bold]")
        keyword_result = tool._lookup_cve(keywords="spring4shell", max_results=5)
        console.print(Panel(Markdown(keyword_result), title="[cyan]Keyword Search Result[/cyan]", width=100))
        
        # Test latest CVEs
        console.print("\n[bold]Testing latest CVEs...[/bold]")
        latest_result = tool._lookup_cve(get_latest=True, max_results=5)
        console.print(Panel(Markdown(latest_result), title="[cyan]Latest CVEs Result[/cyan]", width=100))
        
        return True
    
    except Exception as e:
        console.print(f"[bold red]Error testing CVE lookup tool: {e}[/bold red]")
        import traceback
        console.print(traceback.format_exc())
        return False

def main():
    """Run the MCP CVE tests."""
    console.print("\n[bold green]===== MCP CVE Integration Test =====\n[/bold green]")
    
    # Test MCP client
    client_success = test_mcp_client()
    
    # Test CVE lookup tool
    tool_success = test_cve_lookup_tool()
    
    # Print summary
    console.print("\n[bold]===== Test Summary =====\n[/bold]")
    console.print(f"MCP Client: {'[green]PASSED[/green]' if client_success else '[red]FAILED[/red]'}")
    console.print(f"CVE Lookup Tool: {'[green]PASSED[/green]' if tool_success else '[red]FAILED[/red]'}")
    
    # Exit with appropriate code
    if client_success and tool_success:
        console.print("\n[bold green]All tests passed successfully![/bold green]")
        return 0
    else:
        console.print("\n[bold red]Some tests failed, see details above.[/bold red]")
        return 1

if __name__ == "__main__":
    sys.exit(main())