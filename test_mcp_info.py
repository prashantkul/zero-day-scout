#!/usr/bin/env python
"""
Test script to check MCP server info and available tools.

This script connects to the MCP server via the /api/info endpoint
to list available tools without requiring a full agent setup.
"""

import os
import sys
import json
import argparse
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Create console for rich output
console = Console()

def get_mcp_info(host="localhost", port=8000):
    """Get MCP server info using the /api/info endpoint."""
    try:
        # First check the health endpoint
        health_url = f"http://{host}:{port}/health"
        console.print(f"Checking server health at {health_url}")
        
        try:
            health_response = requests.get(health_url, timeout=5)
            if health_response.status_code == 200:
                console.print("[green]✓ Server is healthy![/green]")
            else:
                console.print(f"[red]✗ Server health check failed with status {health_response.status_code}[/red]")
                return None
        except Exception as e:
            console.print(f"[red]✗ Error connecting to server health endpoint: {e}[/red]")
            return None
        
        # Now get the info endpoint
        info_url = f"http://{host}:{port}/api/info"
        console.print(f"Getting server info from {info_url}")
        
        response = requests.get(info_url, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[red]✗ Failed to get server info: Status {response.status_code}[/red]")
            return None
    except Exception as e:
        console.print(f"[red]✗ Error getting MCP server info: {e}[/red]")
        return None

def main():
    parser = argparse.ArgumentParser(description="Check MCP server info and available tools")
    parser.add_argument("--host", default="localhost", help="MCP server host")
    parser.add_argument("--port", type=int, default=8000, help="MCP server port")
    args = parser.parse_args()
    
    console.print("[bold cyan]===== MCP Server Info =====\n[/bold cyan]")
    
    info = get_mcp_info(args.host, args.port)
    if not info:
        console.print("[red]Failed to retrieve MCP server info[/red]")
        return 1
    
    # Display server info
    console.print(f"[green]✓ Connected to MCP server at {args.host}:{args.port}[/green]")
    console.print(f"[bold cyan]Server Name:[/bold cyan] {info.get('name', 'Unknown')}")
    console.print(f"[bold cyan]Version:[/bold cyan] {info.get('version', 'Unknown')}")
    
    # Display available tools
    tools = info.get('tools', [])
    if tools:
        console.print(f"\n[bold cyan]Available Tools ({len(tools)}):[/bold cyan]")
        
        table = Table(show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="green")
        
        for tool in tools:
            name = tool.get('name', 'Unknown')
            description = tool.get('description', 'No description')
            table.add_row(name, description)
        
        console.print(table)
    else:
        console.print("\n[yellow]No tools available on the server[/yellow]")
    
    console.print("\n[bold green]Test completed successfully![/bold green]")
    return 0

if __name__ == "__main__":
    sys.exit(main())