#!/usr/bin/env python
"""
Zero-Day HQ - Command Center for Security Research Tools

This script serves as a central hub for accessing different security research
capabilities offered by the Zero-Day Scout platform:
1. RAG System - For direct document retrieval and question answering
2. Agentic RAG - For deep security research using a multi-agent workflow
"""

import os
import sys
import argparse
import subprocess
import signal
from pathlib import Path

# Add the project root to the path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# Try to import rich for improved interface
try:
    from rich.console import Console
    from rich.theme import Theme
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich import box
    rich_available = True
except ImportError:
    rich_available = False
    print("For an enhanced interface, install the 'rich' library: pip install rich")

# Define paths to CLI scripts
SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "src", "apps")
RAG_CLI_PATH = os.path.join(SCRIPT_DIR, "rag_cli.py")
SCOUT_CLI_PATH = os.path.join(SCRIPT_DIR, "scout_cli.py")

# Custom theme if rich is available
if rich_available:
    custom_theme = Theme({
        "title": "bright_yellow bold",
        "option": "bright_green",
        "description": "bright_white",
        "detail": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "info": "blue",
        "header": "magenta bold",
    })
    console = Console(theme=custom_theme)


def check_requirements():
    """Check if required scripts exist."""
    missing_scripts = []
    
    if not os.path.exists(RAG_CLI_PATH):
        missing_scripts.append(RAG_CLI_PATH)
    
    if not os.path.exists(SCOUT_CLI_PATH):
        missing_scripts.append(SCOUT_CLI_PATH)
    
    if missing_scripts:
        if rich_available:
            console.print(f"[error]Error: The following required scripts were not found:[/error]")
            for script in missing_scripts:
                console.print(f"[error]- {script}[/error]")
            console.print("[info]Please ensure you're running from the Zero-Day Scout project root directory.[/info]")
        else:
            print("Error: The following required scripts were not found:")
            for script in missing_scripts:
                print(f"- {script}")
            print("Please ensure you're running from the Zero-Day Scout project root directory.")
        sys.exit(1)


def display_header():
    """Display the application header."""
    if rich_available:
        logo = """
[title]
███████╗███████╗██████╗  ██████╗       ██████╗  █████╗ ██╗   ██╗    ██╗  ██╗ ██████╗ 
╚══███╔╝██╔════╝██╔══██╗██╔═══██╗      ██╔══██╗██╔══██╗╚██╗ ██╔╝    ██║  ██║██╔═══██╗
  ███╔╝ █████╗  ██████╔╝██║   ██║█████╗██║  ██║███████║ ╚████╔╝     ███████║██║   ██║
 ███╔╝  ██╔══╝  ██╔══██╗██║   ██║╚════╝██║  ██║██╔══██║  ╚██╔╝      ██╔══██║██║▄▄ ██║
███████╗███████╗██║  ██║╚██████╔╝      ██████╔╝██║  ██║   ██║       ██║  ██║╚██████╔╝
╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝       ╚═════╝ ╚═╝  ╚═╝   ╚═╝       ╚═╝  ╚═╝ ╚══▀▀═╝ 
[/title]
"""
        console.print(logo)
        console.print("[title]COMMAND CENTER FOR ADVANCED SECURITY RESEARCH[/title]", justify="center")
        console.print("")
    else:
        print("\n========== ZERO-DAY HQ ==========")
        print("COMMAND CENTER FOR ADVANCED SECURITY RESEARCH\n")


def display_menu():
    """Display the main menu and return the user's choice."""
    if rich_available:
        # Create a table for options
        table = Table(box=box.ROUNDED, expand=False, show_header=False)
        table.add_column("Option", style="option", justify="center")
        table.add_column("Description", style="description")
        table.add_column("Details", style="detail")
        
        table.add_row(
            "1", 
            "RAG System", 
            "Direct document retrieval & question answering"
        )
        table.add_row(
            "2", 
            "Agentic RAG", 
            "Deep security research with multi-agent workflow"
        )
        table.add_row("q", "Quit", "Exit the application")
        
        console.print(Panel(table, title="[header]Available Research Tools[/header]", border_style="blue"))
        
        # Get user choice
        choice = Prompt.ask("\n[info]Select an option[/info]", choices=["1", "2", "q"], default="1")
        return choice
    else:
        print("\nAvailable Research Tools:")
        print("1. RAG System - Direct document retrieval & question answering")
        print("2. Agentic RAG - Deep security research with multi-agent workflow")
        print("q. Quit - Exit the application")
        
        while True:
            choice = input("\nSelect an option [1/2/q]: ").strip().lower()
            if choice in ["1", "2", "q"]:
                return choice
            print("Invalid choice. Please enter 1, 2, or q.")


def launch_rag_cli(args=None):
    """Launch the RAG CLI with optional arguments."""
    cmd = [sys.executable, RAG_CLI_PATH]
    
    # Add any passed arguments
    if args:
        cmd.extend(args)
    
    try:
        if rich_available:
            console.print("[info]Launching RAG System...[/info]")
        else:
            print("Launching RAG System...")
        
        # Set environment variables to ensure proper Python path
        env = os.environ.copy()
        env["PYTHONPATH"] = project_root
            
        subprocess.run(cmd, env=env)
    except Exception as e:
        if rich_available:
            console.print(f"[error]Error launching RAG CLI: {e}[/error]")
        else:
            print(f"Error launching RAG CLI: {e}")


def launch_scout_cli(args=None):
    """Launch the Scout CLI with optional arguments."""
    cmd = [sys.executable, SCOUT_CLI_PATH]
    
    # Add any passed arguments
    if args:
        cmd.extend(args)
    
    try:
        if rich_available:
            console.print("[info]Launching Agentic RAG System...[/info]")
        else:
            print("Launching Agentic RAG System...")
        
        # Set environment variables to ensure proper Python path
        env = os.environ.copy()
        env["PYTHONPATH"] = project_root
            
        subprocess.run(cmd, env=env)
    except Exception as e:
        if rich_available:
            console.print(f"[error]Error launching Scout CLI: {e}[/error]")
        else:
            print(f"Error launching Scout CLI: {e}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Zero-Day HQ - Command Center for Security Research Tools")
    parser.add_argument("--rag", action="store_true", help="Launch RAG CLI directly")
    parser.add_argument("--agent", action="store_true", help="Launch Scout Agent CLI directly")
    parser.add_argument("--args", nargs=argparse.REMAINDER, help="Arguments to pass to the launched CLI")
    
    return parser.parse_args()


def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) gracefully."""
    if rich_available:
        console.print("\n[info]Exiting Zero-Day HQ. Goodbye![/info]")
    else:
        print("\nExiting Zero-Day HQ. Goodbye!")
    sys.exit(0)

def main():
    """Main function for the Zero-Day HQ application."""
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Parse arguments
    args = parse_arguments()
    
    # Check if required scripts exist
    check_requirements()
    
    # Handle direct launch flags
    if args.rag:
        launch_rag_cli(args.args)
        return
    
    if args.agent:
        launch_scout_cli(args.args)
        return
    
    # Display header and menu
    display_header()
    
    try:
        while True:
            choice = display_menu()
            
            if choice == "1":
                launch_rag_cli()
            elif choice == "2":
                launch_scout_cli()
            elif choice == "q":
                if rich_available:
                    console.print("[info]Exiting Zero-Day HQ. Goodbye![/info]")
                else:
                    print("Exiting Zero-Day HQ. Goodbye!")
                break
    except KeyboardInterrupt:
        # This should be caught by the signal handler, but just in case
        if rich_available:
            console.print("\n[info]Exiting Zero-Day HQ. Goodbye![/info]")
        else:
            print("\nExiting Zero-Day HQ. Goodbye!")
        return 0


if __name__ == "__main__":
    main()