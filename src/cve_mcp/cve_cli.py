#!/usr/bin/env python3
"""
CVE MCP Client - Command-line interface for interacting with the CVE MCP Server.

This CLI provides an interactive interface to search and retrieve CVE vulnerability
information from the MCP server.
"""

import asyncio
import json
import sys
import os
import argparse
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from rich.console import Console
    from rich.theme import Theme
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.markdown import Markdown
    from rich import box
    from rich.syntax import Syntax
    from rich.status import Status
except ImportError:
    print("This utility requires the 'rich' library. Install with: pip install rich")
    sys.exit(1)

from src.cve_mcp.mcp_cve_client import McpCveClient

# Set up logger
logger = logging.getLogger(__name__)

# Custom theme for CVE data
custom_theme = Theme({
    "logo": "bright_red bold",
    "logo.shadow": "red",
    "cmd": "bright_cyan",
    "cmd.desc": "bright_white",
    "cve.id": "bright_yellow bold",
    "cve.score": "bright_magenta",
    "cve.critical": "bright_red bold",
    "cve.high": "red",
    "cve.medium": "yellow",
    "cve.low": "green",
    "cve.date": "blue",
    "error": "bold red",
    "info": "bright_blue",
    "success": "bright_green",
    "warning": "yellow",
    "vendor": "cyan",
    "product": "bright_cyan",
})

console = Console(theme=custom_theme)


def display_logo():
    """Display the CVE MCP Client logo."""
    logo = """[logo]
 ██████╗██╗   ██╗███████╗    ███╗   ███╗ ██████╗██████╗ 
██╔════╝██║   ██║██╔════╝    ████╗ ████║██╔════╝██╔══██╗
██║     ██║   ██║█████╗      ██╔████╔██║██║     ██████╔╝
██║     ╚██╗ ██╔╝██╔══╝      ██║╚██╔╝██║██║     ██╔═══╝ 
╚██████╗ ╚████╔╝ ███████╗    ██║ ╚═╝ ██║╚██████╗██║     
 ╚═════╝  ╚═══╝  ╚══════╝    ╚═╝     ╚═╝ ╚═════╝╚═╝     
[/logo]
[logo.shadow]         CVE Database Client Interface[/logo.shadow]"""
    console.print(logo)
    console.print()


def display_commands():
    """Display available commands."""
    commands = Table(box=box.SIMPLE, expand=False, show_header=False)
    commands.add_column("Command", style="cmd")
    commands.add_column("Description", style="cmd.desc")
    
    commands.add_row("1", "Search CVE by ID")
    commands.add_row("2", "Get latest CVEs")
    commands.add_row("3", "Search by vendor/product")
    commands.add_row("4", "List all vendors")
    commands.add_row("5", "List products for a vendor")
    commands.add_row("6", "Database update status")
    commands.add_row("7", "Test server connection")
    commands.add_row("q", "Quit")
    
    console.print(Panel(commands, title="Available Commands", border_style="blue"))


def format_severity(score: float) -> str:
    """Format CVSS score with appropriate color."""
    if score >= 9.0:
        return f"[cve.critical]{score} (Critical)[/cve.critical]"
    elif score >= 7.0:
        return f"[cve.high]{score} (High)[/cve.high]"
    elif score >= 4.0:
        return f"[cve.medium]{score} (Medium)[/cve.medium]"
    else:
        return f"[cve.low]{score} (Low)[/cve.low]"


def display_cve_details(cve_data: Dict[str, Any]):
    """Display detailed CVE information in a formatted way."""
    if isinstance(cve_data, dict):
        # Handle CVE JSON 5.1 format
        if 'cveMetadata' in cve_data:
            # Extract CVE ID
            cve_id = cve_data.get('cveMetadata', {}).get('cveId', 'Unknown')
            console.print(f"\n[cve.id]CVE Details: {cve_id}[/cve.id]")
            console.print("=" * 50)
            
            # Get CNA container
            cna = cve_data.get('containers', {}).get('cna', {})
            
            # Title
            if 'title' in cna:
                console.print(f"\n[bold]Title:[/bold] {cna['title']}")
            
            # Summary/Description
            descriptions = cna.get('descriptions', [])
            for desc in descriptions:
                if desc.get('lang') == 'en':
                    console.print(f"\n[bold]Summary:[/bold]\n{desc.get('value', 'N/A')}")
                    break
            
            # CVSS Score - check in metrics
            metrics = cna.get('metrics', [])
            cvss_found = False
            for metric in metrics:
                if 'cvssV3_1' in metric:
                    cvss_data = metric['cvssV3_1']
                    score = cvss_data.get('baseScore', 0)
                    severity = cvss_data.get('baseSeverity', 'UNKNOWN')
                    vector = cvss_data.get('vectorString', '')
                    console.print(f"\n[bold]CVSS v3.1 Score:[/bold] {format_severity(score)} ({severity})")
                    if vector:
                        console.print(f"[bold]Vector:[/bold] {vector}")
                    cvss_found = True
                    break
            
            # If no CVSS in CNA metrics, check ADP section in containers
            if not cvss_found:
                # Check containers.adp
                adp_list = cve_data.get('containers', {}).get('adp', [])
                if not adp_list and 'adp' in cve_data:
                    # Fallback to top-level adp if it exists
                    adp_list = cve_data['adp']
                
                for adp_entry in adp_list:
                    if 'metrics' in adp_entry:
                        for metric in adp_entry['metrics']:
                            if 'cvssV3_1' in metric:
                                cvss_data = metric['cvssV3_1']
                                score = cvss_data.get('baseScore', 0)
                                severity = cvss_data.get('baseSeverity', 'UNKNOWN')
                                vector = cvss_data.get('vectorString', '')
                                console.print(f"\n[bold]CVSS v3.1 Score:[/bold] {format_severity(score)} ({severity})")
                                if vector:
                                    console.print(f"[bold]Vector:[/bold] {vector}")
                                cvss_found = True
                                break
                    if cvss_found:
                        break
            
            # Dates
            cve_meta = cve_data.get('cveMetadata', {})
            if 'datePublished' in cve_meta:
                console.print(f"\n[bold]Published:[/bold] [cve.date]{cve_meta['datePublished']}[/cve.date]")
            if 'dateUpdated' in cve_meta:
                console.print(f"[bold]Updated:[/bold] [cve.date]{cve_meta['dateUpdated']}[/cve.date]")
            
            # Affected Products
            affected = cna.get('affected', [])
            if affected:
                console.print(f"\n[bold]Affected Products:[/bold]")
                for product in affected[:3]:  # Show first 3
                    vendor = product.get('vendor', 'Unknown')
                    prod_name = product.get('product', 'Unknown')
                    console.print(f"  • [vendor]{vendor}[/vendor] - [product]{prod_name}[/product]")
                    
                    # Show versions if available
                    versions = product.get('versions', [])
                    if versions:
                        version_info = []
                        for v in versions[:2]:  # First 2 versions
                            version = v.get('version', '')
                            status = v.get('status', '')
                            if version and status:
                                version_info.append(f"{version} ({status})")
                        if version_info:
                            console.print(f"    Versions: {', '.join(version_info)}")
                
                if len(affected) > 3:
                    console.print(f"  ... and {len(affected) - 3} more products")
            
            # References
            references = cna.get('references', [])
            if references:
                console.print(f"\n[bold]References:[/bold]")
                for ref in references[:5]:  # Show first 5 references
                    url = ref.get('url', '')
                    name = ref.get('name', '')
                    if url:
                        console.print(f"  • {url}")
                    elif name:
                        console.print(f"  • {name}")
                if len(references) > 5:
                    console.print(f"  ... and {len(references) - 5} more references")
            
            # Problem Types (CWEs)
            problem_types = cna.get('problemTypes', [])
            if problem_types:
                cwe_list = []
                for pt in problem_types:
                    for desc in pt.get('descriptions', []):
                        if desc.get('cweId'):
                            cwe_list.append(desc['cweId'])
                if cwe_list:
                    console.print(f"\n[bold]CWE(s):[/bold] {', '.join(cwe_list)}")
                    
        else:
            # Fallback to old format if not CVE JSON 5.1
            cve_id = cve_data.get('id', 'Unknown')
            console.print(f"\n[cve.id]CVE Details: {cve_id}[/cve.id]")
            console.print("=" * 50)
            
            if 'summary' in cve_data:
                console.print(f"\n[bold]Summary:[/bold]\n{cve_data['summary']}")
            
            if 'cvss' in cve_data:
                score = cve_data['cvss']
                console.print(f"\n[bold]CVSS Score:[/bold] {format_severity(score)}")
            
            if 'Published' in cve_data:
                console.print(f"\n[bold]Published:[/bold] [cve.date]{cve_data['Published']}[/cve.date]")
            if 'Modified' in cve_data:
                console.print(f"[bold]Modified:[/bold] [cve.date]{cve_data['Modified']}[/cve.date]")


def display_cve_list(cve_list: List[Dict[str, Any]], title: str = "CVE List"):
    """Display a list of CVEs in a table format."""
    if not cve_list:
        console.print("[warning]No CVEs found.[/warning]")
        return
    
    table = Table(title=title, box=box.ROUNDED, expand=False)
    table.add_column("CVE ID", style="cve.id", no_wrap=True)
    table.add_column("CVSS", justify="center")
    table.add_column("Published", style="cve.date")
    table.add_column("Summary", max_width=50)
    
    for cve in cve_list[:20]:  # Show first 20
        # Extract fields from different possible formats
        cve_id = cve.get('id', cve.get('cve_id', 'Unknown'))
        cvss = cve.get('cvss', cve.get('cvss_score', 0.0))
        published = cve.get('Published', cve.get('published', cve.get('created', 'Unknown')))
        summary = cve.get('summary', cve.get('description', 'No summary available'))
        
        # Truncate summary if too long
        if len(summary) > 50:
            summary = summary[:47] + "..."
        
        table.add_row(
            cve_id,
            format_severity(cvss) if cvss else "N/A",
            published[:10] if len(published) > 10 else published,  # Show just date part
            summary
        )
    
    console.print(table)
    
    if len(cve_list) > 20:
        console.print(f"\n[info]Showing first 20 of {len(cve_list)} CVEs[/info]")


def display_list_in_columns(items: List[str], title: str, item_style: str = ""):
    """Display a list of items in a 3-column table format."""
    if not items:
        console.print(f"[warning]No {title.lower()} found.[/warning]")
        return
    
    console.print(f"\n[bold]{title} ({len(items)} total):[/bold]")
    
    # Display in 3-column table format
    table = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 2))
    table.add_column(justify="left", no_wrap=True, min_width=25)
    table.add_column(justify="left", no_wrap=True, min_width=25)
    table.add_column(justify="left", no_wrap=True, min_width=25)
    
    # Fill table row by row
    for i in range(0, len(items), 3):
        row = []
        for j in range(3):
            if i + j < len(items):
                item = items[i + j]
                # Truncate if too long
                if len(item) > 30:
                    item = item[:27] + "..."
                if item_style:
                    row.append(f"[{item_style}]{item}[/{item_style}]")
                else:
                    row.append(item)
            else:
                row.append("")
        table.add_row(*row)
    
    console.print(table)


def display_cve_ids_in_columns(cve_list: List[Dict[str, Any]], title: str = "CVE List"):
    """Display CVE IDs in a 3-column format."""
    if not cve_list:
        console.print("[warning]No CVEs found.[/warning]")
        return
    
    # Extract CVE IDs - handle different response formats
    cve_ids = []
    for cve in cve_list:
        cve_id = None
        
        # Check for CVE JSON 5.1 format (e.g., CVE-2025-5124)
        if 'cveMetadata' in cve and isinstance(cve['cveMetadata'], dict):
            cve_id = cve['cveMetadata'].get('cveId')
        
        # Check if it's the vulnerabilities format (from Red Hat advisories)
        elif 'vulnerabilities' in cve and isinstance(cve['vulnerabilities'], list):
            # For items with vulnerabilities array, we might want to show multiple CVEs
            # For now, just take the first one
            for vuln in cve['vulnerabilities']:
                if 'cve' in vuln:
                    cve_id = vuln['cve']
                    break
        
        # Otherwise try standard field names
        if not cve_id:
            cve_id = (cve.get('id') or 
                      cve.get('cve_id') or 
                      cve.get('cveId') or 
                      cve.get('CVE_ID') or
                      cve.get('cve', {}).get('id') if isinstance(cve.get('cve'), dict) else cve.get('cve') or
                      'Unknown')
        
        cve_ids.append(cve_id)
    
    display_list_in_columns(cve_ids, title, "cve.id")


def display_vendor_list(vendors: List[str]):
    """Display a list of vendors in columns."""
    display_list_in_columns(vendors, "Available Vendors", "vendor")


def display_product_list(products: List[str], vendor: str):
    """Display a list of products in columns."""
    display_list_in_columns(products, f"Products for {vendor}", "product")


async def search_cve_by_id(client: McpCveClient):
    """Search for a specific CVE by ID."""
    cve_id = Prompt.ask("\n[bold]Enter CVE ID[/bold] (e.g., CVE-2021-44228)")
    
    with Status(f"[info]Searching for {cve_id}...[/info]", spinner="dots"):
        result = await client.search_cve(cve_id)
    
    if "error" in result:
        console.print(f"[error]Error: {result['error']}[/error]")
    else:
        display_cve_details(result)


async def get_latest_cves(client: McpCveClient):
    """Get the latest CVEs."""
    with Status("[info]Fetching latest CVEs...[/info]", spinner="dots"):
        result = await client.get_latest_cves()
    
    if "error" in result:
        console.print(f"[error]Error: {result['error']}[/error]")
    elif isinstance(result, list):
        display_cve_ids_in_columns(result, "Latest CVEs")
    else:
        console.print("[error]Unexpected response format[/error]")


async def search_by_vendor_product(client: McpCveClient):
    """Search CVEs by vendor and product."""
    vendor = Prompt.ask("\n[bold]Enter vendor name[/bold] (e.g., microsoft, apache)")
    
    # Get products for this vendor first
    with Status(f"[info]Fetching products for {vendor}...[/info]", spinner="dots"):
        products_result = await client.get_vendor_products(vendor)
    
    if "error" in products_result:
        console.print(f"[error]Error: {products_result['error']}[/error]")
        return
    
    if isinstance(products_result, dict) and 'product' in products_result:
        products = products_result['product']
        display_list_in_columns(products, f"Products for {vendor}", "product")
    
    product = Prompt.ask("\n[bold]Enter product name[/bold]")
    
    with Status(f"[info]Searching CVEs for {vendor}/{product}...[/info]", spinner="dots"):
        result = await client.search_vendor_product_cves(vendor, product)
    
    if "error" in result:
        console.print(f"[error]Error: {result['error']}[/error]")
    elif isinstance(result, list):
        display_cve_ids_in_columns(result, f"CVEs for {vendor}/{product}")
    else:
        console.print("[error]Unexpected response format[/error]")


async def list_all_vendors(client: McpCveClient):
    """List all available vendors."""
    with Status("[info]Fetching vendor list...[/info]", spinner="dots"):
        result = await client.get_vendors()
    
    if "error" in result:
        console.print(f"[error]Error: {result['error']}[/error]")
    elif isinstance(result, dict) and 'vendor' in result:
        display_vendor_list(result['vendor'])
    else:
        console.print("[error]Unexpected response format[/error]")


async def list_vendor_products(client: McpCveClient):
    """List products for a specific vendor."""
    vendor = Prompt.ask("\n[bold]Enter vendor name[/bold]")
    
    with Status(f"[info]Fetching products for {vendor}...[/info]", spinner="dots"):
        result = await client.get_vendor_products(vendor)
    
    if "error" in result:
        console.print(f"[error]Error: {result['error']}[/error]")
    elif isinstance(result, dict) and 'product' in result:
        products = result['product']
        display_list_in_columns(products, f"Products for {vendor}", "product")
    else:
        console.print("[error]Unexpected response format[/error]")


async def check_db_status(client: McpCveClient):
    """Check database update status."""
    with Status("[info]Checking database status...[/info]", spinner="dots"):
        result = await client.get_db_update_status()
    
    if "error" in result:
        console.print(f"[error]Error: {result['error']}[/error]")
    else:
        console.print("\n[bold]Database Status:[/bold]")
        console.print(Panel(Syntax(json.dumps(result, indent=2), "json"), 
                          title="CVE Database Information", 
                          border_style="green"))


async def test_connection(client: McpCveClient):
    """Test connection to the MCP server."""
    with Status("[info]Testing connection to MCP server...[/info]", spinner="dots"):
        result = await client.ping()
    
    if result.get("status") == "ok":
        console.print("\n[success]✓ Connection successful![/success]")
        console.print(f"Server: {result.get('server', 'Unknown')}")
        console.print(f"Version: {result.get('version', 'Unknown')}")
        console.print(f"Response time: {result.get('response_time_ms', 'Unknown')}ms")
    else:
        console.print(f"[error]✗ Connection failed: {result.get('error', 'Unknown error')}[/error]")


async def interactive_mode(host: str, port: int):
    """Run the client in interactive mode."""
    display_logo()
    
    # Initialize client
    client = McpCveClient(host=host, port=port)
    
    # Test connection first
    console.print("[info]Connecting to CVE MCP Server...[/info]")
    result = await client.ping()
    
    if result.get("status") != "ok":
        console.print(f"[error]Failed to connect to server at {host}:{port}[/error]")
        console.print("[info]Make sure the CVE MCP server is running.[/info]")
        return
    
    console.print(f"[success]✓ Connected to {result.get('server', 'CVE MCP Server')}[/success]\n")
    
    while True:
        display_commands()
        choice = Prompt.ask("\n[bold cyan]Select command[/bold cyan]").strip().lower()
        
        try:
            if choice == "1":
                await search_cve_by_id(client)
            elif choice == "2":
                await get_latest_cves(client)
            elif choice == "3":
                await search_by_vendor_product(client)
            elif choice == "4":
                await list_all_vendors(client)
            elif choice == "5":
                await list_vendor_products(client)
            elif choice == "6":
                await check_db_status(client)
            elif choice == "7":
                await test_connection(client)
            elif choice in ["q", "quit", "exit"]:
                console.print("\n[info]Goodbye![/info]")
                break
            else:
                console.print("[warning]Invalid choice. Please try again.[/warning]")
        
        except KeyboardInterrupt:
            console.print("\n[warning]Operation cancelled.[/warning]")
            continue
        except Exception as e:
            console.print(f"\n[error]Error: {str(e)}[/error]")
            continue
        
        # Add spacing before next command
        console.print()


async def single_command_mode(args):
    """Execute a single command and exit."""
    client = McpCveClient(host=args.host, port=args.port)
    
    try:
        if args.cve:
            # Search for specific CVE
            result = await client.search_cve(args.cve)
            if "error" in result:
                console.print(f"[error]Error: {result['error']}[/error]")
            else:
                display_cve_details(result)
        
        elif args.latest:
            # Get latest CVEs
            result = await client.get_latest_cves()
            if "error" in result:
                console.print(f"[error]Error: {result['error']}[/error]")
            elif isinstance(result, list):
                display_cve_ids_in_columns(result, "Latest CVEs")
        
        elif args.vendor and args.product:
            # Search by vendor and product
            result = await client.search_vendor_product_cves(args.vendor, args.product)
            if "error" in result:
                console.print(f"[error]Error: {result['error']}[/error]")
            elif isinstance(result, list):
                display_cve_ids_in_columns(result, f"CVEs for {args.vendor}/{args.product}")
        
        elif args.vendor:
            # List products for vendor
            result = await client.get_vendor_products(args.vendor)
            if "error" in result:
                console.print(f"[error]Error: {result['error']}[/error]")
            elif isinstance(result, dict) and 'product' in result:
                products = result['product']
                display_list_in_columns(products, f"Products for {args.vendor}", "product")
        
        elif args.vendors:
            # List all vendors
            result = await client.get_vendors()
            if "error" in result:
                console.print(f"[error]Error: {result['error']}[/error]")
            elif isinstance(result, dict) and 'vendor' in result:
                display_vendor_list(result['vendor'])
        
        elif args.status:
            # Database status
            result = await client.get_db_update_status()
            if "error" in result:
                console.print(f"[error]Error: {result['error']}[/error]")
            else:
                console.print(Panel(Syntax(json.dumps(result, indent=2), "json"), 
                                  title="CVE Database Information", 
                                  border_style="green"))
        
        elif args.ping:
            # Test connection
            result = await client.ping()
            if result.get("status") == "ok":
                console.print("[success]✓ Server is running[/success]")
                console.print(f"Response time: {result.get('response_time_ms', 'Unknown')}ms")
            else:
                console.print("[error]✗ Server is not responding[/error]")
        
        else:
            console.print("[error]No command specified. Use -h for help.[/error]")
    
    except Exception as e:
        console.print(f"[error]Error: {str(e)}[/error]")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CVE MCP Client - Search and retrieve CVE vulnerability information",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Connection options
    parser.add_argument("--host", default="localhost", help="MCP server host")
    parser.add_argument("--port", type=int, default=8080, help="MCP server port")
    
    # Command options
    parser.add_argument("--cve", help="Search for a specific CVE ID")
    parser.add_argument("--latest", action="store_true", help="Get latest CVEs")
    parser.add_argument("--vendor", help="Vendor name")
    parser.add_argument("--product", help="Product name (use with --vendor)")
    parser.add_argument("--vendors", action="store_true", help="List all vendors")
    parser.add_argument("--status", action="store_true", help="Show database status")
    parser.add_argument("--ping", action="store_true", help="Test server connection")
    
    args = parser.parse_args()
    
    # Check if any command-line option is provided
    if any([args.cve, args.latest, args.vendor, args.vendors, args.status, args.ping]):
        # Single command mode
        asyncio.run(single_command_mode(args))
    else:
        # Interactive mode
        try:
            asyncio.run(interactive_mode(args.host, args.port))
        except KeyboardInterrupt:
            console.print("\n[info]Exiting...[/info]")
            sys.exit(0)


if __name__ == "__main__":
    main()