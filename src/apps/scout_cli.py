#!/usr/bin/env python
"""
Command line utility for Zero-Day Scout Agentic RAG system.

This script provides a CLI interface to interact with the sequential agent system
for security vulnerability research.

For detailed documentation, see:
- README_SCOUT_CLI.md: Full documentation with feature details and setup instructions
- USAGE.md: Quick reference guide for commands and examples
"""

import sys
import os
import argparse
import time
import asyncio
import logging
import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Handle import paths whether running as a script or from another module
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Rich library for beautiful terminal output
try:
    from rich.console import Console
    from rich.theme import Theme
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    from rich.spinner import Spinner
    from rich.status import Status
    from rich.logging import RichHandler
    from rich.table import Table
    from rich import box
except ImportError:
    print("This utility requires the 'rich' library. Install with: pip install rich")
    sys.exit(1)

# Import our Scout Agent system
from src.scout_agent.agent import OrchestratorAgent
from config.config_manager import get_config
from vertexai.generative_models import GenerativeModel

# Import Markdown utilities
try:
    from src.apps.markdown_utils import export_results_to_markdown
    markdown_export_supported = True
except ImportError:
    markdown_export_supported = False
    print("Markdown export module not found. This feature will be disabled.")

# Custom theme for output
custom_theme = Theme(
    {
        "logo": "bright_red bold",
        "logo.tagline": "bright_yellow",
        "cmd": "bright_cyan",
        "cmd.desc": "bright_white",
        "query": "bold bright_red",
        "response": "green",
        "suggestion": "yellow",
        "error": "bold red",
        "info": "blue",
        "time": "magenta",
        "step.complete": "green",
        "step.current": "yellow",
        "step.pending": "dim white",
        "agent.planner": "cyan",
        "agent.researcher": "blue",
        "agent.analyst": "green",
        "rag.match": "bright_cyan",
        "rag.score": "bright_magenta",
        "rag.snippet": "bright_white",
        "md.success": "bright_green",
        "md.path": "bright_white",
        "md.error": "bright_red"
    }
)

console = Console(theme=custom_theme)

# Setup logging with RichHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)

# Create logger
logger = logging.getLogger("zero-day-scout")


def set_log_level(debug=False, verbose=False):
    """Set the appropriate log level based on debug and verbose flags."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    elif verbose:
        logging.getLogger().setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
        logger.info("Verbose logging enabled")
    else:
        logging.getLogger().setLevel(logging.WARNING)
        logger.setLevel(logging.WARNING)


def display_logo():
    """Display the Zero-Day Scout logo."""
    logo = """
[logo]
███████╗███████╗██████╗  ██████╗       ██████╗  █████╗ ██╗   ██╗    ███████╗ ██████╗ ██████╗ ██╗   ██╗████████╗
╚══███╔╝██╔════╝██╔══██╗██╔═══██╗      ██╔══██╗██╔══██╗╚██╗ ██╔╝    ██╔════╝██╔════╝██╔═══██╗██║   ██║╚══██╔══╝
  ███╔╝ █████╗  ██████╔╝██║   ██║█████╗██║  ██║███████║ ╚████╔╝     ███████╗██║     ██║   ██║██║   ██║   ██║   
 ███╔╝  ██╔══╝  ██╔══██╗██║   ██║╚════╝██║  ██║██╔══██║  ╚██╔╝      ╚════██║██║     ██║   ██║██║   ██║   ██║   
███████╗███████╗██║  ██║╚██████╔╝      ██████╔╝██║  ██║   ██║       ███████║╚██████╗╚██████╔╝╚██████╔╝   ██║   
╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝       ╚═════╝ ╚═╝  ╚═╝   ╚═╝       ╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝   
                                                                                                                
[/logo]

[logo.tagline]AGENTIC RAG SYSTEM FOR SECURITY VULNERABILITY RESEARCH[/logo.tagline]
"""
    console.print(logo)


def display_agent_structure():
    """Display information about the agent structure and workflow."""
    agent_table = Table(box=box.SIMPLE, expand=False)
    agent_table.add_column("[bold]Sequential Workflow[/bold]", style="bold cyan")
    agent_table.add_column("Description", style="bright_white")
    
    agent_table.add_row(
        "[agent.planner]Step 1: Planner Agent[/agent.planner]", 
        "Analyzes your query and creates a structured research plan"
    )
    agent_table.add_row(
        "[agent.researcher]Step 2: Research Agent[/agent.researcher]", 
        "Retrieves relevant information from security knowledge base"
    )
    agent_table.add_row(
        "[agent.analyst]Step 3: Analysis Agent[/agent.analyst]", 
        "Evaluates findings to provide actionable security insights"
    )
    
    console.print(Panel(agent_table, title="Agent Workflow", border_style="cyan"))


def display_commands(detailed=False):
    """
    Display available commands for the CLI.
    
    Args:
        detailed: Whether to show detailed help information
    """
    if not detailed:
        # Show basic command table
        commands_table = Table(box=box.SIMPLE, expand=False, show_header=False)
        commands_table.add_column("Command", style="cmd")
        commands_table.add_column("Description", style="cmd.desc")
        
        commands_table.add_row("/help", "Show help information (use /help detailed for more)")
        commands_table.add_row("/examples", "Show example security queries")
        commands_table.add_row("/exit, /quit", "Exit the application")
        commands_table.add_row("Ctrl+C", "Interrupt current operation or exit the application")
        commands_table.add_row("/suggest", "Get query improvement suggestions for your last query")
        commands_table.add_row("/enhance", "Enhance your last query for better results")
        commands_table.add_row("/debug", "Toggle debug logging")
        commands_table.add_row("/verbose", "Toggle verbose logging")
        commands_table.add_row("/agents", "Show agent structure and workflow information")
        commands_table.add_row("/rag", "Toggle RAG information display")
        commands_table.add_row("/plan", "Toggle execution plan display")
        commands_table.add_row("/export", "Export current results to Markdown")
        commands_table.add_row("/export auto", "Toggle automatic Markdown export")
        commands_table.add_row("/clear", "Clear the screen")
        
        console.print(Panel(commands_table, title="Available Commands", border_style="blue"))
    else:
        # Show detailed help from USAGE.md if it exists
        try:
            usage_path = os.path.join(os.path.dirname(__file__), "USAGE.md")
            if os.path.exists(usage_path):
                with open(usage_path, 'r') as f:
                    usage_content = f.read()
                    console.print(Panel(Markdown(usage_content), title="Zero-Day Scout CLI - Help", border_style="blue", expand=False))
            else:
                # Fall back to basic help if file doesn't exist
                display_commands(detailed=False)
                console.print("[yellow]Detailed help file not found.[/yellow]")
        except Exception as e:
            # If there's an error reading the file, fall back to basic help
            display_commands(detailed=False)
            console.print(f"[error]Error loading detailed help: {e}[/error]")
            
        # Always show agent structure since it's useful
        display_agent_structure()


def suggest_query_improvements(query: str, model_name: Optional[str] = None) -> List[str]:
    """
    Generate query improvement suggestions based on the original query.

    Args:
        query: The original user query
        model_name: Model to use for suggestions (defaults to config value)

    Returns:
        List of suggested improved queries
    """
    logger.info(f"Generating query improvement suggestions for: {query}")
    config = get_config()
    model_name = model_name or config.get("generative_model")

    # Use the generative model to suggest improvements
    model = GenerativeModel(model_name)

    prompt = f"""
    I want to use a security-focused Retrieval-Augmented Generation (RAG) system to search for 
    information about zero-day vulnerabilities and security threats.
    
    My original query is: "{query}"
    
    Generate 3 improved versions of this query that might yield better search results in the security RAG system.
    Focus on clarity, specificity, and using terms that would match security documentation.
    Return only the 3 alternative queries, one per line, with no additional text.
    """

    try:
        logger.debug(f"Sending suggestion prompt to model: {model_name}")
        response = model.generate_content(prompt)
        suggestions = [line.strip() for line in response.text.strip().split('\n') if line.strip()]
        logger.info(f"Generated {len(suggestions)} query suggestions")
        return suggestions[:3]  # Limit to 3 suggestions
    except Exception as e:
        error_msg = f"Error generating suggestions: {e}"
        logger.error(error_msg)
        console.print(f"[error]{error_msg}[/error]")
        return []


async def format_output_markdown(text, agent_type):
    """Format agent output as markdown with highlights based on agent type."""
    if not text:
        return ""
        
    # Create different formatting based on agent type
    if agent_type == "planner":
        # For planner, format structured plans, highlight headings, lists
        formatted = text.replace("Key Security Concepts:", "### Key Security Concepts:")
        formatted = formatted.replace("Context Analysis:", "### Context Analysis:")
        formatted = formatted.replace("Research Plan:", "### Research Plan:")
        formatted = formatted.replace("Analysis Requirements:", "### Analysis Requirements:")
    elif agent_type == "researcher":
        # For researcher, highlight findings, sources, data points
        formatted = text.replace("Research Findings:", "### Research Findings:")
        formatted = formatted.replace("Sources:", "#### Sources:")
        formatted = formatted.replace("Key Information:", "#### Key Information:")
    elif agent_type == "analyst":
        # For analyst, highlight analysis sections, recommendations, etc.
        formatted = text.replace("Analysis:", "### Analysis:")
        formatted = formatted.replace("Recommendations:", "### Recommendations:")
        formatted = formatted.replace("Vulnerability Assessment:", "### Vulnerability Assessment:")
    else:
        # Default formatting
        formatted = text
        
    return formatted


async def create_execution_plan(
    query: str,
    model_name: str = "gemini-2.5-flash-preview-04-17"
) -> str:
    """
    Create an execution plan for the query before processing it.
    
    Args:
        query: The security query to process
        model_name: The model to use for generating the plan
        
    Returns:
        A formatted execution plan as a string
    """
    with Status("[info]Creating execution plan...[/info]", spinner="dots"):
        try:
            # Use a smaller, faster model to create the plan
            config = get_config()
            planner_model = GenerativeModel(model_name or config.get("generative_model"))
            
            prompt = f"""
            I'm about to use an Agentic RAG system with a sequential workflow to research this security query:
            
            "{query}"
            
            Create a brief but insightful execution plan with these components:
            
            1. A breakdown of the security query to identify key concepts and objectives
            2. The 3-step workflow plan:
               - Step 1: Planner Agent - What specific aspects the planner will focus on
               - Step 2: Research Agent - What information sources and security data will be searched
               - Step 3: Analysis Agent - What kinds of security insights and recommendations will be prioritized
            3. Expected outcomes and deliverables
            
            Keep your plan concise (maximum 8-10 lines total), focused, and use bullet points where appropriate.
            """
            
            response = planner_model.generate_content(prompt)
            execution_plan = response.text.strip()
            
            return execution_plan
        except Exception as e:
            logger.warning(f"Error creating execution plan: {e}")
            # Return a basic plan if generation fails
            return f"Query: {query}\n\nBasic 3-step workflow:\n- Planning phase\n- Research phase\n- Analysis phase"


async def process_query(
    query: str, 
    model_name: str = "gemini-2.5-flash-preview-04-17", 
    verbose: bool = False, 
    show_agent_outputs: bool = True,
    show_rag: bool = True,
    show_plan: bool = True,
):
    """
    Process a security query through the agent system.
    
    Args:
        query: The security query to process
        model_name: The model to use for the agents
        verbose: Whether to show debugging information
        show_agent_outputs: Whether to show individual agent outputs
        show_rag: Whether to show RAG match information
        show_plan: Whether to show execution plan before processing
        
    Returns:
        Tuple of (final_response, agent_outputs) or None if there was an error
    """
    # Initialize the orchestrator agent
    with Status("[info]Initializing agent system...[/info]", spinner="dots") as status:
        try:
            orchestrator = OrchestratorAgent(model_name=model_name)
            status.update(f"[info]Using model: {model_name}[/info]")
        except Exception as e:
            console.print(f"[error]Error initializing agent system: {e}[/error]")
            return None
    
    # If show_plan is enabled, create and display execution plan
    if show_plan:
        try:
            # Generate the execution plan
            execution_plan = await create_execution_plan(query, model_name)
            
            # Display the plan in a highlighted panel
            console.print("\n[bold]Execution Plan:[/bold]")
            console.print(Panel(
                Markdown(execution_plan),
                title="[cyan]Query Execution Plan[/cyan]",
                border_style="cyan",
                expand=False
            ))
            
            # Ask for confirmation to proceed
            proceed = Prompt.ask("\n[bold cyan]Proceed with execution?[/bold cyan]", choices=["y", "n"], default="y")
            
            if proceed.lower() != "y":
                console.print("[info]Query execution canceled by user.[/info]")
                return "Query execution was canceled."
                
        except Exception as e:
            # If plan creation fails, just log and continue
            logger.warning(f"Error creating execution plan: {e}")
            console.print("[yellow]Could not create execution plan. Proceeding directly.[/yellow]")
    
    # Process the query - use a distinctive separator for clarity
    console.print("\n[bright_white]════════════════════════════════════════════[/bright_white]")
    console.print(f"[query]Processing query: '{query}'[/query]")
    console.print("[bright_white]════════════════════════════════════════════[/bright_white]\n")
    
    try:
        # Execute the query processing workflow
        with Status("[step.current]Starting agent workflow...[/step.current]", spinner="dots") as status:
            start_time = time.time()
            
            # Show status updates for each agent in the workflow
            status.update("[agent.planner]Planning security research strategy...[/agent.planner]")
            # Small delay to show the status change (for user experience)
            await asyncio.sleep(1)
            
            # Process query through the orchestrator
            # These status updates provide real-time feedback while the actual processing is running
            try:
                # Simulate the workflow progression visually for better UX
                # Step 1: The Planner agent
                status.update("[agent.planner]Planning security research strategy...[/agent.planner]")
                await asyncio.sleep(0.8)
                
                # Step 2: The Research agent with better status updates
                status.update("[agent.researcher]Retrieving relevant research...[/agent.researcher]")
                await asyncio.sleep(0.8)
                status.update("[agent.researcher]Analyzing security documents...[/agent.researcher]")
                await asyncio.sleep(0.8)
                
                # Step 3: The Analysis agent with better status updates
                status.update("[agent.analyst]Examining security implications...[/agent.analyst]")
                await asyncio.sleep(0.8)
                status.update("[agent.analyst]Developing security insights...[/agent.analyst]")
                await asyncio.sleep(0.8)
                
                # Final synthesis
                status.update("[step.current]Synthesizing final analysis...[/step.current]")
                await asyncio.sleep(0.5)
                
                # Process the query with the orchestrator - returns a dictionary
                result = await orchestrator.process_query(query)
                
                # The final response is in result["final_response"]
                # The agent outputs are in result["agent_outputs"]
                final_response = result["final_response"]
                agent_outputs = result["agent_outputs"]
                
            except Exception as workflow_error:
                # If there's an error in the workflow display, still try the actual processing
                console.print(f"[yellow]Warning: Workflow display error: {workflow_error}[/yellow]")
                result = await orchestrator.process_query(query)
                final_response = result["final_response"]
                agent_outputs = result["agent_outputs"]
            
            elapsed_time = time.time() - start_time
            status.update(f"[step.complete]✓ Analysis completed in {elapsed_time:.2f} seconds[/step.complete]")
            console.print("\n[bright_white]════════════════════════════════════════════[/bright_white]")
        
        # Display the results in a formatted way with panels
        if show_agent_outputs:
            console.print("\n[bold]Agent Workflow Execution:[/bold]")
            
            # Check if we have proper agent outputs to display
            if agent_outputs:
                # Create panels for each agent in the workflow
                # Planner agent output
                if agent_outputs["security_planner"]["output"]:
                    planner_md = await format_output_markdown(agent_outputs["security_planner"]["output"], "planner")
                    console.print(Panel(
                        Markdown(planner_md),
                        title="[agent.planner]Research Plan[/agent.planner]",
                        border_style="cyan",
                        expand=False
                    ))
                
                # Research agent output - will now show RAG retrieval information
                if agent_outputs["security_researcher"]["output"]:
                    researcher_md = await format_output_markdown(agent_outputs["security_researcher"]["output"], "researcher")
                    
                    # Parse for research sources information if present
                    sources_section = ""
                    research_content = researcher_md
                    
                    if "## Research Sources" in researcher_md:
                        # Split the research findings from the sources information
                        parts = researcher_md.split("## Research Sources", 1)
                        research_content = parts[0].strip()
                        sources_section = "## Research Sources" + parts[1]
                        
                        # Display research findings
                        console.print(Panel(
                            Markdown(research_content),
                            title="[agent.researcher]Research Findings[/agent.researcher]",
                            border_style="blue",
                            expand=False
                        ))
                        
                        # Display research sources information in a highlighted panel only if enabled
                        if show_rag:
                            console.print(Panel(
                                Markdown(sources_section),
                                title="[bright_cyan]Research Sources[/bright_cyan]",
                                border_style="cyan",
                                expand=False
                            ))
                    else:
                        # Display as usual if no RAG section found
                        console.print(Panel(
                            Markdown(researcher_md),
                            title="[agent.researcher]Research Findings[/agent.researcher]",
                            border_style="blue",
                            expand=False
                        ))
                
                # Analysis agent output
                if agent_outputs["security_analyst"]["output"]:
                    analyst_md = await format_output_markdown(agent_outputs["security_analyst"]["output"], "analyst")
                    console.print(Panel(
                        Markdown(analyst_md),
                        title="[agent.analyst]Security Analysis[/agent.analyst]",
                        border_style="green",
                        expand=False
                    ))
        
        # Return both final_response and agent_outputs so they can be used for export
        return (final_response, agent_outputs)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Query processing interrupted by user.[/bold yellow]")
        return None  # Return None for error cases
    except Exception as e:
        console.print(f"\n[error]Error processing query: {e}[/error]")
        if verbose:
            import traceback
            console.print(Panel(traceback.format_exc(), title="[error]Error Details[/error]", border_style="red"))
        return None


async def enhance_query(query: str, model_name: str) -> str:
    """
    Enhance the user's query for better results before processing.
    
    Args:
        query: The original user query
        model_name: The model to use for enhancing
        
    Returns:
        Enhanced query that's more specific and focused
    """
    with Status("[info]Enhancing your query...[/info]", spinner="dots") as status:
        # Generate query improvements
        suggestions = suggest_query_improvements(query, model_name)
        
        if not suggestions:
            return query  # Return original if no suggestions
            
        # Create enhanced query with enriched details
        config = get_config()
        enhanced_model = GenerativeModel(model_name or config.get("generative_model"))
        
        prompt = f"""
        I'm going to use an Agentic RAG system for security research.
        
        My original query is: "{query}"
        
        Here are some suggested improvements:
        {", ".join(suggestions)}
        
        Create an enhanced version of my query that combines the original intent with the best elements 
        from these suggestions. Make it specific, focused, and optimized for security research.
        
        Enhanced query (in 1-2 sentences):
        """
        
        try:
            response = enhanced_model.generate_content(prompt)
            enhanced_query = response.text.strip()
            return enhanced_query
        except KeyboardInterrupt:
            logger.warning("Query enhancement interrupted by user")
            console.print("[yellow]Query enhancement interrupted. Using original query.[/yellow]")
            return query  # Return original if interrupted
        except Exception as e:
            logger.warning(f"Query enhancement failed: {e}")
            return query  # Return original if enhancement fails


async def interactive_mode(
    model_name: str = "gemini-2.5-flash-preview-04-17", 
    verbose: bool = False, 
    show_rag: bool = True,
    show_plan: bool = True,
    auto_export_md: bool = False
):
    """
    Run the agent in interactive mode.
    
    Args:
        model_name: The model to use for the agents
        verbose: Whether to show debugging information
        show_rag: Whether to show RAG information in the output
        show_plan: Whether to show execution plan before processing
        auto_export_pdf: Whether to automatically export results to PDF
    """
    # Display logo and commands
    display_logo()
    console.print()
    
    # Show startup information
    with Status("[info]Loading Zero-Day Scout Agent system...[/info]", spinner="dots") as status:
        # Show loading sequence for better UX
        status.update("[info]Initializing system components...[/info]")
        time.sleep(0.5)
        
        status.update("[info]Loading security knowledge base...[/info]")
        time.sleep(0.5)
        
        status.update("[info]Configuring agent workflow...[/info]")
        time.sleep(0.5)
        
        status.update("[info]Setting up sequential agent pipeline...[/info]")
        time.sleep(0.5)
        
        status.update("[green]System ready![/green]")
    
    # Display agent structure and commands
    display_agent_structure()
    console.print()
    display_commands()
    
    console.print(f"\n[info]Using model: {model_name}[/info]")
    console.print("\nType your security query to get started, or type /help for available commands.")
    console.print()
    
    example_queries = [
        "What are the latest zero-day vulnerabilities in Apache Struts?",
        "How can organizations protect against Log4Shell vulnerabilities?",
        "What are the common exploit techniques for SQL injection?",
        "How can I detect if my system has been compromised by a zero-day exploit?",
        "What security vulnerabilities affect Docker containers?",
    ]
    
    last_query = None
    show_rag_info = show_rag  # Flag to control RAG information display
    show_execution_plan = show_plan  # Flag to control execution plan display
    auto_export = auto_export_md  # Flag to control auto Markdown export
    
    while True:
        try:
            query = Prompt.ask("\n[bold cyan]Scout Agent[/bold cyan]")
            
            # Process commands (starting with /)
            if query.startswith('/'):
                cmd = query.lower().strip()
                
                # Exit commands
                if cmd in ["/exit", "/quit", "/bye", "/q"]:
                    console.print("[info]Exiting Scout Agent CLI.[/info]")
                    break
                    
                # Help commands
                elif cmd.startswith("/help"):
                    # Check if detailed help requested
                    if "detailed" in cmd or "full" in cmd:
                        display_commands(detailed=True)
                    else:
                        display_commands(detailed=False)
                    continue
                    
                # Example queries
                elif cmd in ["/examples", "/example", "/ex"]:
                    console.print("\n[info]Example security queries:[/info]")
                    for i, example in enumerate(example_queries, 1):
                        console.print(f"  [suggestion]{i}. {example}[/suggestion]")
                    continue
                
                # Show agent structure
                elif cmd in ["/agents", "/agent", "/structure", "/workflow"]:
                    display_agent_structure()
                    continue
                    
                # Query suggestions
                elif cmd.startswith("/suggest"):
                    if not last_query:
                        console.print("[error]No previous query to suggest improvements for.[/error]")
                        continue
                        
                    with Status("[info]Generating query suggestions...[/info]", spinner="dots"):
                        suggestions = suggest_query_improvements(last_query, model_name)
                    
                    if suggestions:
                        console.print("\n[info]Suggested query improvements:[/info]")
                        suggestions_table = Table(box=box.SIMPLE, show_header=False)
                        suggestions_table.add_column("", style="suggestion")
                        
                        for i, suggestion in enumerate(suggestions, 1):
                            suggestions_table.add_row(f"{i}. {suggestion}")
                            
                        console.print(Panel(suggestions_table, title="Query Suggestions", border_style="yellow"))
                    else:
                        console.print("[error]Could not generate suggestions.[/error]")
                    continue
                
                # Enhance last query
                elif cmd.startswith("/enhance"):
                    if not last_query:
                        console.print("[error]No previous query to enhance.[/error]")
                        continue
                    
                    # Enhance the query
                    with Status("[info]Enhancing your query...[/info]", spinner="dots"):
                        enhanced_query = await enhance_query(last_query, model_name)
                    
                    if enhanced_query and enhanced_query != last_query:
                        console.print("\n[info]Enhanced query for better results:[/info]")
                        console.print(Panel(
                            f"[bold]Original:[/bold] {last_query}\n\n[bold]Enhanced:[/bold] {enhanced_query}",
                            title="Query Enhancement",
                            border_style="yellow"
                        ))
                        
                        # Ask if they want to use this query now
                        use_now = Prompt.ask("Process this enhanced query now?", choices=["y", "n"], default="n")
                        if use_now.lower() == "y":
                            # Process the enhanced query with display settings
                            response = await process_query(
                                enhanced_query, 
                                model_name, 
                                verbose, 
                                show_rag=show_rag_info,
                                show_plan=show_execution_plan
                            )
                            
                            if response:
                                # The formatted output is already displayed in process_query if show_agent_outputs=True
                                
                                # Display the final response with markdown formatting
                                console.print("\n[bold green]Agent Response:[/bold green]")
                                console.print(Panel(Markdown(response), title="[bold]Final Analysis[/bold]", border_style="green", expand=False))
                    else:
                        console.print("[info]Could not further enhance the query.[/info]")
                    continue
                    
                # Debug toggle
                elif cmd == "/debug":
                    # Toggle debug mode
                    current_level = logger.getEffectiveLevel()
                    if current_level == logging.DEBUG:
                        set_log_level(debug=False, verbose=False)
                        console.print("[info]Debug mode disabled[/info]")
                    else:
                        set_log_level(debug=True, verbose=False)
                        console.print("[info]Debug mode enabled[/info]")
                    continue
                
                # Verbose toggle
                elif cmd == "/verbose":
                    # Toggle verbose mode
                    current_level = logger.getEffectiveLevel()
                    if current_level == logging.INFO:
                        set_log_level(debug=False, verbose=False)
                        console.print("[info]Verbose mode disabled[/info]")
                    else:
                        set_log_level(debug=False, verbose=True)
                        console.print("[info]Verbose mode enabled[/info]")
                    continue
                
                # Toggle RAG information display
                elif cmd == "/rag":
                    show_rag_info = not show_rag_info
                    status_message = "enabled" if show_rag_info else "disabled"
                    console.print(f"[info]RAG information display {status_message}[/info]")
                    continue
                    
                # Toggle execution plan display
                elif cmd == "/plan":
                    show_execution_plan = not show_execution_plan
                    status_message = "enabled" if show_execution_plan else "disabled"
                    console.print(f"[info]Execution plan display {status_message}[/info]")
                    continue
                    
                # Export results to PDF
                elif cmd.startswith("/export"):
                    # Toggle auto-export if specified
                    if "auto" in cmd:
                        auto_export = not auto_export
                        status_message = "enabled" if auto_export else "disabled"
                        console.print(f"[info]Automatic Markdown export {status_message}[/info]")
                        continue
                        
                    if last_query is None:
                        console.print("[error]No query has been processed yet.[/error]")
                        continue
                        
                    # Check if we have results to export
                    if "final_response" not in locals() or not final_response or "agent_outputs" not in locals() or not agent_outputs:
                        console.print("[error]No results available to export.[/error]")
                        continue
                    
                    # Check if Markdown export is supported
                    if not markdown_export_supported:
                        console.print("[md.error]Markdown export not available.[/md.error]")
                        continue
                        
                    # Include sources by default, unless explicitly disabled
                    include_sources = True
                    if "no-sources" in cmd or "nosources" in cmd:
                        include_sources = False
                    
                    # Export to Markdown
                    from src.apps.markdown_utils import export_results_to_markdown
                    export_results_to_markdown(
                        query=last_query,
                        final_response=final_response,
                        agent_outputs=agent_outputs,
                        include_sources=include_sources,
                        console=console
                    )
                    continue
                    
                # Clear screen
                elif cmd == "/clear":
                    console.clear()
                    display_logo()
                    console.print()
                    display_commands()
                    continue
                
                # Unknown command
                else:
                    console.print(f"[error]Unknown command: {cmd}[/error]")
                    console.print("[info]Type /help to see available commands[/info]")
                    continue
            
            # Empty query
            if not query.strip():
                continue
                
            # Save query for suggestion feature
            last_query = query
            
            # QUERY ENHANCEMENT STEP - Improve query before sending to agents
            enhanced_query = await enhance_query(query, model_name)
            
            # If the query was enhanced, show the enhancement and ask for confirmation
            if enhanced_query != query:
                console.print("\n[info]I've enhanced your query for better results:[/info]")
                console.print(Panel(
                    f"[bold]Original:[/bold] {query}\n\n[bold]Enhanced:[/bold] {enhanced_query}",
                    title="Query Enhancement",
                    border_style="yellow"
                ))
                
                # Ask for user confirmation or modification
                confirmation = Prompt.ask("\n[bold cyan]Use this enhanced query?[/bold cyan] ([green]y[/green]/[red]n[/red]/[yellow]edit[/yellow])")
                
                if confirmation.lower() in ["y", "yes"]:
                    # Use the enhanced query
                    query_to_process = enhanced_query
                    console.print("\n[info]Using enhanced query[/info]")
                elif confirmation.lower() in ["e", "edit"]:
                    # Let user edit the query
                    edited_query = Prompt.ask("\n[bold cyan]Edit query[/bold cyan]", default=enhanced_query)
                    query_to_process = edited_query
                    console.print("\n[info]Using edited query[/info]")
                else:
                    # Use original query
                    query_to_process = query
                    console.print("\n[info]Using original query[/info]")
            else:
                # No enhancement, use original
                query_to_process = query
                
            # Process the query (enhanced or original) with display settings
            # Response will be a tuple of (final_response, agent_outputs) or None if error
            result = await process_query(
                query_to_process, 
                model_name, 
                verbose, 
                show_rag=show_rag_info,
                show_plan=show_execution_plan
            )
            
            if result:
                # Unpack the result tuple
                final_response, agent_outputs = result
                
                # Display the final response with markdown formatting
                console.print("\n[bold green]Agent Response:[/bold green]")
                console.print(Panel(Markdown(final_response), title="[bold]Final Analysis[/bold]", border_style="green", expand=False))
                
                # Suggest improvements
                console.print("\n[info]Type /suggest to get query improvement suggestions[/info]")
                
                # Auto-export to Markdown if enabled
                if auto_export and markdown_export_supported:
                    console.print("\n[info]Auto-exporting results to Markdown...[/info]")
                    from src.apps.markdown_utils import export_results_to_markdown
                    export_results_to_markdown(
                        query=query_to_process,
                        final_response=final_response,
                        agent_outputs=agent_outputs,
                        include_sources=True,
                        console=console
                    )
                
        except KeyboardInterrupt:
            # Ask for confirmation to exit
            console.print("\n[info]Ctrl+C detected. Do you want to exit?[/info]")
            try:
                confirm = Prompt.ask("[bold cyan]Exit?[/bold cyan]", choices=["y", "n"], default="y")
                if confirm.lower() == "y":
                    console.print("[info]Exiting Scout Agent CLI.[/info]")
                    break
                else:
                    console.print("[info]Continuing...[/info]")
                    continue
            except KeyboardInterrupt:
                # If user presses Ctrl+C again during confirmation, exit immediately
                console.print("\n[info]Exiting Scout Agent CLI.[/info]")
                break
        except Exception as e:
            console.print(f"\n[error]Error: {str(e)}[/error]")
            if verbose:
                import traceback
                console.print(Panel(traceback.format_exc(), title="[error]Error Details[/error]", border_style="red"))


async def main():
    """Run the agent system CLI."""
    # Set up signal handlers for graceful exit
    import signal
    
    # Define the handler function
    def signal_handler(sig, frame):
        console.print("\n[bold red]Ctrl+C pressed. Exiting...[/bold red]")
        sys.exit(0)
    
    # Register the signal handler for SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(
        description="Zero-Day Scout Agent CLI for security vulnerability research",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--query", "-q", 
        type=str, 
        default=None,
        help="Security query to process (if not provided, runs in interactive mode)"
    )
    
    parser.add_argument(
        "--model", "-m", 
        type=str, 
        default="gemini-2.5-flash-preview-04-17",
        help="Model to use for the agents"
    )
    
    parser.add_argument(
        "--enhance", "-e",
        action="store_true",
        help="Automatically enhance the query before processing"
    )
    
    parser.add_argument(
        "--no-enhancement", "-n",
        action="store_true",
        help="Skip query enhancement even in interactive mode"
    )
    
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--debug", "-d", 
        action="store_true", 
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--no-rag", 
        action="store_true", 
        help="Disable RAG match information display"
    )
    
    parser.add_argument(
        "--no-plan", 
        action="store_true", 
        help="Disable execution plan display before processing"
    )
    
    parser.add_argument(
        "--export-md", 
        action="store_true", 
        help="Automatically export results to Markdown"
    )
    
    parser.add_argument(
        "--no-sources", 
        action="store_true", 
        help="Exclude research sources from Markdown export"
    )
    
    args = parser.parse_args()
    
    # Set log level
    set_log_level(debug=args.debug, verbose=args.verbose)
    
    # Load environment variables
    load_dotenv()
    
    try:
        if args.query:
            # Process a single query
            # Display logo for consistency
            display_logo()
            console.print()
            
            query_to_process = args.query
            
            # Enhance the query if requested
            if args.enhance and not args.no_enhancement:
                console.print(f"\n[query]Original query: {args.query}[/query]")
                enhanced_query = await enhance_query(args.query, args.model)
                
                if enhanced_query != args.query:
                    console.print("\n[info]Enhanced query for better results:[/info]")
                    console.print(Panel(
                        f"[bold]Enhanced:[/bold] {enhanced_query}",
                        title="Query Enhancement",
                        border_style="yellow"
                    ))
                    query_to_process = enhanced_query
            
            # Process the query (original or enhanced) with display settings (unless disabled)
            response = await process_query(
                query_to_process, 
                args.model, 
                args.verbose or args.debug, 
                show_rag=not args.no_rag,
                show_plan=not args.no_plan
            )
            
            if response:
                # Display the result in a formatted way
                console.print("\n[bold green]Agent Response:[/bold green]")
                
                # Get result with agent outputs
                try:
                    # Initialize the orchestrator agent for accessing outputs
                    orchestrator = OrchestratorAgent(model_name=args.model)
                    
                    # Process the query to get all agent outputs
                    result = await orchestrator.process_query(query_to_process)
                    final_response = result["final_response"]
                    agent_outputs = result["agent_outputs"]
                    
                    # Display individual agent outputs
                    console.print("\n[bold]Agent Workflow Results:[/bold]")
                    
                    # Planner output
                    if agent_outputs.get("security_planner", {}).get("output"):
                        planner_md = await format_output_markdown(agent_outputs["security_planner"]["output"], "planner")
                        console.print(Panel(
                            Markdown(planner_md),
                            title="[agent.planner]Research Plan[/agent.planner]",
                            border_style="cyan",
                            expand=False
                        ))
                    
                    # Researcher output with RAG information
                    if agent_outputs.get("security_researcher", {}).get("output"):
                        researcher_md = await format_output_markdown(agent_outputs["security_researcher"]["output"], "researcher")
                        
                        # Parse for research sources information if present
                        if "## Research Sources" in researcher_md:
                            # Split the research findings from the sources information
                            parts = researcher_md.split("## Research Sources", 1)
                            research_content = parts[0].strip()
                            sources_section = "## Research Sources" + parts[1]
                            
                            # Display research findings
                            console.print(Panel(
                                Markdown(research_content),
                                title="[agent.researcher]Research Findings[/agent.researcher]",
                                border_style="blue",
                                expand=False
                            ))
                            
                            # Display research sources information in a highlighted panel only if enabled
                            if not args.no_rag:
                                console.print(Panel(
                                    Markdown(sources_section),
                                    title="[bright_cyan]Research Sources[/bright_cyan]",
                                    border_style="cyan",
                                    expand=False
                                ))
                        else:
                            # Display as usual if no RAG section found
                            console.print(Panel(
                                Markdown(researcher_md),
                                title="[agent.researcher]Research Findings[/agent.researcher]",
                                border_style="blue",
                                expand=False
                            ))
                    
                    # Display final response
                    formatted_md = await format_output_markdown(final_response, "analyst")
                    console.print(Panel(Markdown(formatted_md), title="[bold]Final Analysis[/bold]", border_style="green", expand=False))
                    
                    # Export to Markdown if requested
                    if args.export_md and markdown_export_supported:
                        console.print("\n[info]Exporting results to Markdown...[/info]")
                        from src.apps.markdown_utils import export_results_to_markdown
                        export_results_to_markdown(
                            query=query_to_process,
                            final_response=final_response,
                            agent_outputs=agent_outputs,
                            include_sources=not args.no_sources,
                            console=console
                        )
                except Exception as e:
                    # Fallback to simple formatting if the new method fails
                    if args.debug:
                        console.print(f"[yellow]Error accessing agent outputs: {e}[/yellow]")
                    formatted_md = await format_output_markdown(response, "analyst")
                    console.print(Panel(Markdown(formatted_md), title="[bold]Analysis[/bold]", border_style="green", expand=False))
                
        else:
            # Run in interactive mode with all flags
            await interactive_mode(
                args.model, 
                args.verbose or args.debug, 
                show_rag=not args.no_rag,
                show_plan=not args.no_plan,
                auto_export_md=args.export_md
            )
            
    except KeyboardInterrupt:
        console.print("\n[bold red]Process interrupted by user. Exiting.[/bold red]")
        return 0
    except Exception as e:
        console.print(f"\n[error]Error: {str(e)}[/error]")
        if args.debug:
            import traceback
            console.print(Panel(traceback.format_exc(), title="[error]Error Details[/error]", border_style="red"))
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))