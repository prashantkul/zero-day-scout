#!/usr/bin/env python
"""
Command line utility for testing RAG queries with colored output and query suggestions.
"""

import sys
import os
import argparse
import time
import asyncio
import io
import logging
from typing import Optional, List, Tuple, Dict, Any
from dotenv import load_dotenv
import json
import re

# Rich library for beautiful terminal output
try:
    from rich.console import Console
    from rich.theme import Theme
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
    from rich.live import Live
    from rich.table import Table
    from rich.layout import Layout
    from rich.align import Align
    from rich.spinner import Spinner
    from rich.status import Status
    from rich.logging import RichHandler
    from rich import box
except ImportError:
    print("This utility requires the 'rich' library. Install with: pip install rich")
    sys.exit(1)

# Handle import paths whether running as a script or from another module
try:
    # Try direct import first (when run as a script directly)
    import sys
    import os
    # Add project root to path if not already there
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from src.rag.pipeline import VertexRagPipeline
    from config.config_manager import get_config
except ImportError:
    # Fallback for when run as a module (like from zero_day_hq.py)
    from src.rag.pipeline import VertexRagPipeline
    from config.config_manager import get_config
from vertexai.generative_models import GenerativeModel

# Custom theme for output
custom_theme = Theme(
    {
        "query": "bold bright_red",
        "response": "green",
        "suggestion": "yellow",
        "error": "bold red",
        "info": "blue",
        "time": "magenta",
        "step.complete": "green",
        "step.current": "yellow",
        "step.pending": "dim white",
        "progress.percentage": "magenta",
        "progress.elapsed": "cyan",
        "log.debug": "dim cyan",
        "log.info": "blue",
        "log.warning": "yellow",
        "log.error": "bold red",
    }
)

console = Console(theme=custom_theme)

# Setup logging with RichHandler - default to WARNING to avoid too much output
logging.basicConfig(
    level=logging.WARNING,  # Default to WARNING level
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_time=True)],
)

# Create logger
logger = logging.getLogger("zero-day-scout")
# Ensure the logger itself isn't filtered
logger.setLevel(logging.DEBUG)

# Create a StringIO object to capture logs for display in the UI
log_capture = io.StringIO()
log_capture_handler = logging.StreamHandler(log_capture)
log_capture_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
# Set the handler level to DEBUG to capture all logs
log_capture_handler.setLevel(logging.DEBUG)
logger.addHandler(log_capture_handler)

# Print a debug message to confirm logging is working
logger.debug("Logging system initialized")


def set_log_level(debug=False, verbose=False):
    """Set the appropriate log level based on debug and verbose flags."""
    # Find the console handler among the handlers
    console_handler = None
    for handler in logging.root.handlers:
        if isinstance(handler, RichHandler):
            console_handler = handler
            break

    # Set logger level - this determines what messages are created
    # We keep this at DEBUG to allow capturing all logs, regardless of display
    logger.setLevel(logging.DEBUG)

    # Set the console handler level - this determines what's displayed in the console
    if console_handler:
        if debug:
            console_handler.setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled for console display")
        elif verbose:
            console_handler.setLevel(logging.INFO)
            logger.info("Verbose logging enabled for console display")
        else:
            console_handler.setLevel(logging.WARNING)
            logger.debug("Standard logging mode (warnings and errors only)")
    else:
        # Fallback if no console handler found
        logger.warning("Console handler not found, setting root logger level")
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        elif verbose:
            logging.getLogger().setLevel(logging.INFO)
        else:
            logging.getLogger().setLevel(logging.WARNING)

    # The capture handler always stays at DEBUG level to capture everything for the logs panel
    # We want all logs to be available in the logs panel, regardless of console display

    return logging.getLogger().getEffectiveLevel()


def get_captured_logs() -> str:
    """Get the logs captured in the StringIO buffer."""
    return log_capture.getvalue()


def clear_captured_logs() -> None:
    """Clear the StringIO buffer containing captured logs."""
    log_capture.truncate(0)
    log_capture.seek(0)


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
    I want to use a Retrieval-Augmented Generation (RAG) system to search for security and vulnerability information.
    My original query is: "{query}"
    
    Generate 3 improved versions of this query that might yield better search results in a RAG system.
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


def format_execution_time(time_value: float) -> str:
    """Format execution time with proper units.
    
    Args:
        time_value: Either execution time in seconds, or a start time to calculate from
    """
    # Check if this is likely a timestamp (greater than 1 hour in seconds)
    # If so, calculate the difference from current time
    if time_value > 3600:
        execution_time = time.time() - time_value
    else:
        # Already a duration
        execution_time = time_value
        
    if execution_time < 0.001:
        return f"{execution_time * 1000000:.2f} μs"
    elif execution_time < 1:
        return f"{execution_time * 1000:.2f} ms"
    else:
        return f"{execution_time:.2f} s"


class StepTracker:
    """Track progress through a series of steps with visual feedback."""
    
    def __init__(self, steps: List[str]):
        """
        Initialize the step tracker with a list of steps.
        
        Args:
            steps: List of step descriptions
        """
        self.steps = steps
        self.current_step = 0
        self.step_times = [0.0] * len(steps)
        self.start_time = time.time()
        self.step_start_time = self.start_time
        
    def render(self) -> Table:
        """Render the current progress as a rich Table."""
        table = Table(box=box.ROUNDED, expand=True)
        table.add_column("Step", style="bold")
        table.add_column("Status", justify="center")
        
        for i, step in enumerate(self.steps):
            if i < self.current_step:
                # Completed step
                status = "[step.complete]✓[/step.complete]"
            elif i == self.current_step:
                # Current step
                status = "[step.current]►[/step.current]"
            else:
                # Pending step
                status = "[step.pending]○[/step.pending]"
                
            table.add_row(step, status)
            
        return table
    
    def next_step(self) -> int:
        """
        Move to the next step and record the time taken for the current step.
        
        Returns:
            The new current step index
        """
        if self.current_step < len(self.steps):
            # Record time for the completed step
            self.step_times[self.current_step] = time.time() - self.step_start_time
            self.current_step += 1
            self.step_start_time = time.time()
            
            # Update the processing panel to show progress
            self.update_processing_panel()
        
        return self.current_step
    
    def update_processing_panel(self):
        """Update the processing panel to reflect current step progress."""
        # This method can be used to dynamically update a Live display
        # Currently not implemented but available for future enhancements
        pass
    
    def complete(self) -> float:
        """
        Mark all remaining steps as complete.
        
        Returns:
            Total execution time in seconds
        """
        while self.current_step < len(self.steps):
            self.next_step()
            
        return time.time() - self.start_time


async def animated_progress(status_text: str, delay: float = 0.1) -> None:
    """Display an animated spinner with progress text."""
    spinner = Spinner("dots", text=status_text)
    with Live(spinner, refresh_per_second=10) as live:
        while True:
            live.update(spinner)
            await asyncio.sleep(delay)


def run_rag_query(
    query: str, 
    use_reranking: bool = False,
    debug: bool = False,
    verbose: bool = False,
    update_in_place: bool = True
) -> Tuple[str, float, Dict[str, Any]]:
    """
    Run a RAG query and return the response with execution time and step info.

    Args:
        query: The query to process
        use_reranking: Whether to use reranking
        debug: Show debug information
        verbose: Show verbose output including contexts

    Returns:
        Tuple of (response text, execution time in seconds, step metrics)
    """
    # Log the query and settings
    logger.info(f"Processing query: {query}")
    logger.info(
        f"Settings: reranking={use_reranking}, debug={debug}, verbose={verbose}"
    )

    # Set console height to compact value to avoid extra whitespace
    console.height = min(25, console.height)
    # Define the steps in the RAG process
    steps = [
        "Initializing RAG pipeline",
        "Embedding query",
        "Retrieving relevant documents",
        "Ranking results" if use_reranking else "Processing results",
        "Generating response"
    ]

    # Create a lookup for formatted step names displayed in the panel
    step_display_names = [
        "Initializing RAG pipeline",
        "Embedding your query",
        "Retrieving relevant documents",
        "Reranking results" if use_reranking else "Processing results",
        "Generating response"
    ]

    # Track the current active step for dynamic updates
    current_step = 0

    # Create a function to generate the step panel content
    def get_step_panel_content(active_step: int) -> str:
        content = "[bold blue]Processing your query...[/bold blue]\n"
        content += "[dim]The system is performing these steps:[/dim]\n"

        for i, step_name in enumerate(step_display_names):
            if i < active_step:  # Completed steps
                content += f"  [green]✓[/green] {step_name}\n"
            elif i == active_step:  # Current step
                content += f"  [bright_blue]►[/bright_blue] {step_name} [bright_blue](in progress...)[/bright_blue]\n"
            else:  # Pending steps
                content += f"  [dim]•[/dim] {step_name}\n"

        return content

    tracker = StepTracker(steps)

    # Create a visually appealing processing indicator with spinner
    with Status(f"[bold cyan]{query[:60] + '...' if len(query) > 60 else query}[/bold cyan]", 
               spinner="dots", 
               spinner_style="bright_blue") as status:
        # Show the step tracking animation with initial state
        processing_panel = Panel(
            get_step_panel_content(current_step),
            title="[info]✨ Processing Query ✨[/info]",
            border_style="blue",
            padding=(1, 2)
        )
        console.print(processing_panel)
        # Short pause to let the user see the steps
        time.sleep(0.5)

    # Create simple progress display with minimal height
    progress_table = Table.grid(padding=0)
    progress_table.add_column()

    # Initialize progress tracker and response text
    response_text = ""

    # Create a context manager to temporarily redirect standard output
    import io
    from contextlib import redirect_stdout

    # Start the query processing
    try:
        # Create a buffer to capture pipeline output
        buffer = io.StringIO()

        # Start timing the full execution
        start_time = time.time()

        # Use Live display for updating the progress in place
        if update_in_place:
            # Create a renderable function that generates the panel
            def get_progress_panel():
                return Panel(
                    get_step_panel_content(current_step),
                    title=f"[info]✨ Processing Query: {query[:40] + '...' if len(query) > 40 else query} ✨[/info]",
                    border_style="blue",
                    padding=(1, 2)
                )

            # Create a live display that updates in place
            with Live(get_progress_panel(), refresh_per_second=4) as live_display:
                # Step 1: Initialize pipeline
                pipeline = VertexRagPipeline()
                current_step += 1
                tracker.next_step()
                live_display.update(get_progress_panel())
                time.sleep(0.1)  # Small delay to ensure update is visible

                # Step 2: Query embedding
                current_step += 1
                tracker.next_step()
                live_display.update(get_progress_panel())
                time.sleep(0.1)  # Small delay to ensure update is visible

                # Step 3: Document retrieval
                current_step += 1 
                live_display.update(get_progress_panel())
                time.sleep(0.1)  # Small delay to ensure update is visible

                # Capture time filter information if available
                time_filter = None
                if hasattr(pipeline, "_extract_time_filter_from_query"):
                    _, extracted_time_filter = pipeline._extract_time_filter_from_query(
                        query
                    )
                    if extracted_time_filter:
                        time_filter = extracted_time_filter
                        logger.info(f"Time filter applied: {time_filter}")

                # Actually retrieve the contexts
                with redirect_stdout(buffer):
                    if use_reranking:
                        # This retrieval step gets contexts but doesn't rank yet
                        contexts = pipeline.retrieve_context(
                            query=query,
                            use_reranking=False,  # We'll do reranking in the next step
                            time_filter=time_filter,
                        )
                    else:
                        # Standard retrieval with ranking in one step
                        contexts = pipeline.retrieve_context(
                            query=query,
                            use_reranking=use_reranking,
                            time_filter=time_filter,
                        )

                tracker.next_step()

                # Step 4: Ranking/Processing results
                current_step += 1
                live_display.update(get_progress_panel())
                time.sleep(0.1)  # Small delay to ensure update is visible

                with redirect_stdout(buffer):
                    if use_reranking:
                        # Apply reranking in a separate step for visualization
                        contexts = pipeline.retrieve_context(
                            query=query,
                            use_reranking=True,
                            time_filter=(
                                time_filter if "time_filter" in locals() else None
                            ),
                        )

                tracker.next_step()

                # Step 5: Generate response
                current_step += 1
                live_display.update(get_progress_panel())
                time.sleep(0.1)  # Small delay to ensure update is visible

                response_text = pipeline.generate_answer(
                    query=query,
                    retrievals=contexts
                )

                # Show completion
                current_step = len(steps)  # Mark all steps as completed
                live_display.update(
                    Panel(
                        "[bold green]All steps completed successfully![/bold green]\n" +
                        get_step_panel_content(len(steps)),
                        title="[info]✨ Query Processing Complete ✨[/info]",
                        border_style="green",
                        padding=(1, 2)
                    )
                )
                time.sleep(0.5)  # Brief pause to show completion

        # For non-live display mode, use the original approach with consecutive panels
        else:
            # Create a status display for progress
            with Status(f"[bold cyan]{query[:60] + '...' if len(query) > 60 else query}[/bold cyan]", spinner="dots") as status:
                # Step 1: Initialize pipeline
                status.update("[bold blue]Initializing RAG pipeline...[/bold blue]")
                logger.debug("Initializing RAG pipeline")
                pipeline = VertexRagPipeline()
                logger.info("RAG pipeline initialized successfully")
                current_step += 1
                tracker.next_step()

                # Step 2: Query embedding
                status.update("[bold blue]Embedding your query...[/bold blue]")
                logger.debug(f"Embedding query: {query}")
                current_step += 1
                tracker.next_step()

                # Step 3: Document retrieval
                status.update("[bold blue]Retrieving relevant documents...[/bold blue]")
                logger.info("Retrieving relevant documents")
                current_step += 1

                # Capture time filter information if available
                time_filter = None
                if hasattr(pipeline, "_extract_time_filter_from_query"):
                    _, extracted_time_filter = pipeline._extract_time_filter_from_query(
                        query
                    )
                    if extracted_time_filter:
                        time_filter = extracted_time_filter
                        logger.info(f"Time filter applied: {time_filter}")

                with redirect_stdout(buffer):
                    if use_reranking:
                        # This retrieval step gets contexts but doesn't rank yet
                        contexts = pipeline.retrieve_context(
                            query=query,
                            use_reranking=False,  # We'll do reranking in the next step
                            time_filter=time_filter,
                        )
                    else:
                        # Standard retrieval with ranking in one step
                        contexts = pipeline.retrieve_context(
                            query=query,
                            use_reranking=use_reranking,
                            time_filter=time_filter,
                        )

                tracker.next_step()

                # Step 4: Ranking/Processing results
                step_message = "[bold blue]Reranking results...[/bold blue]" if use_reranking else "[bold blue]Processing results...[/bold blue]"
                status.update(step_message)
                current_step += 1

                with redirect_stdout(buffer):
                    if use_reranking:
                        # Apply reranking in a separate step for visualization
                        contexts = pipeline.retrieve_context(
                            query=query,
                            use_reranking=True,
                            time_filter=(
                                time_filter if "time_filter" in locals() else None
                            ),
                        )

                tracker.next_step()

                # Step 5: Generate response
                status.update("[bold blue]Generating response...[/bold blue]")
                logger.info("Generating response from retrieved documents")
                current_step += 1

                response_text = pipeline.generate_answer(
                    query=query,
                    retrievals=contexts
                )
                logger.info("Response generation completed")

                # Show completion
                status.update("[bold green]Processing complete![/bold green]")
        time.sleep(0.5)  # Brief pause to show completion

        # Complete all steps and calculate execution time
        execution_time = tracker.complete()

        # Get the captured pipeline output
        pipeline_output = buffer.getvalue()

        # Parse and format the pipeline output into something more readable
        pipeline_info = parse_pipeline_output(pipeline_output, use_reranking)

        # Return response, execution time, step timings, and contexts
        step_metrics = {
            "total_time": execution_time,
            "step_times": {steps[i]: tracker.step_times[i] for i in range(len(steps))},
            "contexts": contexts,  # Store retrieved contexts for display
            "context_count": len(contexts) if contexts else 0,
            "is_empty_response": is_empty_response(response_text),
            "debug": debug,
            "verbose": verbose,
            "formatted_time": format_execution_time(time.time() - start_time),
            "pipeline_info": pipeline_info,  # Store the formatted pipeline info
            "time_filter": (
                time_filter if "time_filter" in locals() and time_filter else None
            ),  # Include time filter if available
        }

        # Show debug information in the console if requested
        if debug or verbose:
            # Create a more attractive debug info panel
            pipeline_info = (
                metrics.get("pipeline_info", {}) if isinstance(metrics, dict) else {}
            )

            # Only show debug panel if we have useful info
            if pipeline_info:
                reranking_status = pipeline_info.get("reranking_status", "unknown")
                reranker_model = pipeline_info.get("reranker_model", "")
                context_count = pipeline_info.get("context_count", 0)
                response_type = pipeline_info.get("response_type", "")
                contexts_type = pipeline_info.get("contexts_type", "")
                errors = pipeline_info.get("errors", [])

                # Create a small info table for tech details
                info_table = Table.grid()
                info_table.add_column(style="dim")
                info_table.add_column(style="bold")

                info_table.add_row("Documents retrieved:", f"{context_count}")
                info_table.add_row("Reranking:", f"[{'green' if reranking_status == 'enabled' else 'yellow'}]{reranking_status.capitalize()}[/{'green' if reranking_status == 'enabled' else 'yellow'}]")
                if reranker_model:
                    info_table.add_row("Reranker model:", reranker_model)
                if response_type:
                    info_table.add_row("Response type:", response_type)
                if contexts_type:
                    info_table.add_row("Contexts type:", contexts_type)

                # Only show the debug panel in verbose mode or if there are errors
                if verbose or errors:
                    debug_content = info_table

                    # Add context previews in verbose mode
                    # Wrap in a panel for better visuals
                    debug_panel = Panel(
                        info_table,
                        title="RAG Pipeline Details",
                        border_style="dim blue",
                        expand=False
                    )
                    console.print(debug_panel)

                    # Show context preview as a separate panel if verbose
                    if verbose and contexts:
                        preview_panel = Panel(
                            format_context_preview(contexts),
                            title="Context Samples",
                            border_style="dim"
                        )
                        console.print(preview_panel)

        return response_text, execution_time, step_metrics

    except Exception as e:
        error_msg = f"Error processing query: {e}"

        # Show error in the progress panel
        error_panel = Panel(
            f"[bold red]Error during step: {step_display_names[current_step]}[/bold red]\n\n" +
            f"[red]{error_msg}[/red]\n\n" +
            get_step_panel_content(current_step),
            title="[error]⚠️ Query Processing Error ⚠️[/error]",
            border_style="red",
            padding=(1, 2)
        )

        if update_in_place and 'live_display' in locals():
            try:
                live_display.update(error_panel)
            except:
                console.print(error_panel)
        else:
            console.print(error_panel)

        # Provide more detailed error information
        if debug:
            console.print("[bold red]Debug Traceback:[/bold red]")
            import traceback
            console.print(f"[dim red]{traceback.format_exc()}[/dim red]")

        return f"Error: {str(e)}", time.time() - start_time, {
            "error": str(e),
            "debug": debug,
            "verbose": verbose,
            "contexts": [],
            "context_count": 0,
            "is_empty_response": True,
            "formatted_time": "error"
        }


def display_performance_metrics(metrics: Dict[str, Any]) -> Panel:
    """Create a panel with performance metrics visualization."""
    if "error" in metrics:
        return Panel("Error during processing", title="Performance Metrics", border_style="red")

    # Create a table for the metrics
    table = Table(box=box.SIMPLE)
    table.add_column("Step", style="bold")
    table.add_column("Time", justify="right", style="magenta")
    table.add_column("% of Total", justify="right")

    total_time = metrics["total_time"]
    step_times = metrics["step_times"]

    # Add rows for each step
    for step, duration in step_times.items():
        percentage = (duration / total_time) * 100 if total_time > 0 else 0
        bar = "█" * int(percentage / 2)  # Simple visualization
        table.add_row(
            step, 
            format_execution_time(duration),
            f"{percentage:.1f}% {bar}"
        )

    # Add total time
    table.add_row("Total", f"[bold]{format_execution_time(total_time)}[/bold]", "100%")

    # Add context information if available
    if "context_count" in metrics:
        table.add_row("", "", "")  # Empty row as separator
        table.add_row(
            f"Contexts retrieved", 
            f"[bold]{metrics['context_count']}[/bold]", 
            ""
        )

    # Add time filter information if available
    if "time_filter" in metrics and metrics["time_filter"]:
        table.add_row("", "", "")  # Empty row as separator

        time_filter = metrics["time_filter"]
        filter_desc = []

        if "year" in time_filter:
            filter_desc.append(f"Year: [bold]{time_filter['year']}[/bold]")
        if "after" in time_filter:
            filter_desc.append(f"After: [bold]{time_filter['after']}[/bold]")
        if "before" in time_filter:
            filter_desc.append(f"Before: [bold]{time_filter['before']}[/bold]")
        if "between" in time_filter:
            start, end = time_filter["between"]
            filter_desc.append(f"Between: [bold]{start}[/bold] and [bold]{end}[/bold]")

        if filter_desc:
            table.add_row(f"Time filter applied", f"[bold green]Yes[/bold green]", "")
            for desc in filter_desc:
                table.add_row("", desc, "")

    return Panel(table, title="Performance Metrics", border_style="blue")


def create_context_panel(metrics: Dict[str, Any]) -> Optional[Panel]:
    """Create a panel showing context information for empty responses."""
    # Only show for empty responses and when we have contexts
    if not metrics.get("is_empty_response", False) or "contexts" not in metrics:
        return None
        
    contexts = metrics["contexts"]
    
    # Get pipeline info if available
    pipeline_info = metrics.get("pipeline_info", {})
    reranking_status = pipeline_info.get("reranking_status", "unknown")
    reranker_model = pipeline_info.get("reranker_model", "")
    retrieved_count = pipeline_info.get("context_count", 0) or len(contexts) if contexts else 0
    errors = pipeline_info.get("errors", [])
    
    # Create a status string based on reranking
    status_color = "green" if reranking_status == "enabled" else "yellow"
    reranking_text = f"[{status_color}]Reranking: {reranking_status.capitalize()}[/{status_color}]"
    if reranking_status == "enabled" and reranker_model:
        reranking_text += f" ([dim]using {reranker_model}[/dim])"
    
    # Create header with retrieved counts
    retrieval_header = f"Retrieved [bold]{retrieved_count}[/bold] documents"
    
    if not contexts:
        content = (
            f"{reranking_text}\n\n"
            "[italic]No relevant documents were found in the corpus.[/italic]\n"
            "This suggests that your query might be outside the knowledge base scope."
        )
        
        if errors:
            content += "\n\n[bold red]Errors encountered:[/bold red]\n"
            content += "\n".join(f"[dim red]- {err}[/dim red]" for err in errors)
            
        return Panel(
            content,
            title="Why No Answer Was Found",
            border_style="yellow"
        )
    
    # Format context preview
    context_preview = format_context_preview(contexts)
    
    # Create content with pipeline info
    content = (
        f"{reranking_text}\n"
        f"{retrieval_header}\n\n"
        "[bold yellow]Limited or No Relevant Information Found[/bold yellow]\n\n"
        "The system retrieved some context but couldn't generate a specific answer from it.\n"
        "Here's what was retrieved:\n\n"
        f"{context_preview}\n\n"
        "[italic]Consider trying a more specific query or exploring related topics.[/italic]"
    )
    
    # Add any errors if they exist
    if errors:
        content += "\n\n[bold red]Errors encountered:[/bold red]\n"
        content += "\n".join(f"[dim red]- {err}[/dim red]" for err in errors)
    
    return Panel(
        content,
        title="Retrieved Context",
        border_style="yellow",
        expand=True
    )


def explain_reranking_benefits() -> Panel:
    """Create a panel explaining the benefits of reranking."""
    return Panel(
        "Reranking significantly improves your search results by:\n\n"
        "1. [bold]Improving relevance[/bold] - Reordering results based on semantic meaning\n"
        "2. [bold]Reducing false positives[/bold] - Filtering out less relevant matches\n"
        "3. [bold]Handling nuanced queries[/bold] - Better understanding of complex questions\n"
        "4. [bold]Contextual understanding[/bold] - Considering the full context of your query\n\n"
        "[dim]Reranking adds a small performance cost but significantly improves answer quality.[/dim]",
        title="Benefits of Reranking",
        border_style="green"
    )


def list_research_papers(pipeline=None, prefix=None, detailed=False):
    """
    List research papers from GCS.
    
    Args:
        pipeline: An existing VertexRagPipeline instance (optional)
        prefix: Optional prefix to filter results
        detailed: Whether to show detailed paper information
    """
    # Create pipeline if not provided
    if not pipeline:
        with Status("[info]Initializing pipeline...[/info]", spinner="dots") as status:
            try:
                pipeline = VertexRagPipeline()
            except Exception as e:
                console.print(f"[error]Error initializing pipeline: {e}[/error]")
                return
    
    # Create GCS manager
    gcs_manager = None
    try:
        from src.rag.gcs_utils import GcsManager
        gcs_manager = GcsManager(project_id=pipeline.project_id, bucket_name=None)
    except Exception as e:
        console.print(f"[error]Error initializing GCS manager: {e}[/error]")
        return
    
    # Get document prefixes from config
    config = get_config()
    doc_prefixes = config.get("document_prefixes", [])
    
    with Status("[info]Retrieving papers from GCS...[/info]", spinner="dots") as status:
        try:
            # Collect papers by prefix
            papers_by_prefix = {}
            all_papers = set()
            
            # If specific prefix provided, only check that one
            prefixes_to_check = [prefix] if prefix else doc_prefixes
            
            for p in prefixes_to_check:
                papers = gcs_manager.list_files(prefix=p)
                if papers:
                    # Filter out directories (which usually end with /)
                    papers = [paper for paper in papers if not paper.endswith('/')]
                    papers_by_prefix[p] = papers
                    all_papers.update(papers)
            
            if not all_papers:
                console.print("[yellow]No research papers found.[/yellow]")
                return
            
            # Get ingested papers for comparison
            ingested_papers = set()
            if hasattr(pipeline, 'ingested_documents'):
                ingested_papers = pipeline.ingested_documents
            
            # Create table for displaying papers
            table = Table(
                title=f"[bold]Research Papers in GCS[/bold] (Found: {len(all_papers)})",
                box=box.ROUNDED,
                expand=True
            )
            
            table.add_column("Prefix", style="cyan")
            table.add_column("Paper Name", style="green")
            table.add_column("Status", style="yellow")
            if detailed:
                table.add_column("Path", style="blue")
                table.add_column("Size", style="magenta")
            
            # Organize papers by prefix for display
            for prefix, papers in papers_by_prefix.items():
                console.print(f"[info]Found {len(papers)} papers in prefix '{prefix}'[/info]")
                
                for i, paper in enumerate(papers):
                    # Extract filename from path
                    filename = paper.split('/')[-1]
                    
                    # Determine if paper has been ingested
                    status_str = "[green]Ingested[/green]" if paper in ingested_papers else "[dim]Not Ingested[/dim]"
                    
                    # Get paper size if detailed view is requested
                    size_str = ""
                    if detailed:
                        try:
                            # Get file metadata from GCS
                            bucket_name = paper.split('/')[2]
                            blob_name = '/'.join(paper.split('/')[3:])
                            
                            bucket = gcs_manager.client.bucket(bucket_name)
                            blob = bucket.blob(blob_name)
                            blob.reload()
                            
                            # Format size
                            size_bytes = blob.size
                            if size_bytes < 1024:
                                size_str = f"{size_bytes} B"
                            elif size_bytes < 1024 * 1024:
                                size_str = f"{size_bytes/1024:.1f} KB"
                            else:
                                size_str = f"{size_bytes/(1024*1024):.1f} MB"
                        except Exception:
                            size_str = "Unknown"
                    
                    # Add row to table
                    if detailed:
                        table.add_row(
                            prefix if i == 0 else "", 
                            filename, 
                            status_str,
                            paper,
                            size_str
                        )
                    else:
                        table.add_row(
                            prefix if i == 0 else "", 
                            filename, 
                            status_str
                        )
            
            console.print(table)
            
            # Show summary
            console.print(f"\n[bold]Summary:[/bold]")
            ingested_count = len(all_papers.intersection(ingested_papers))
            not_ingested = len(all_papers) - ingested_count
            console.print(f"Total papers: {len(all_papers)}")
            console.print(f"Ingested: [green]{ingested_count}[/green]")
            console.print(f"Not ingested: [yellow]{not_ingested}[/yellow]")
            
        except Exception as e:
            console.print(f"[error]Error listing research papers: {e}[/error]")


def clear_tracking_files():
    """
    Completely remove tracking files (both local and cloud).
    
    Returns:
        Success status as boolean and message string
    """
    success = False
    message = ""
    
    try:
        logger.info("Clearing tracking files")
        
        # Create pipeline to get tracking file paths
        try:
            pipeline = VertexRagPipeline()
        except Exception as e:
            logger.error(f"Error creating pipeline: {e}")
            console.print(f"[yellow]Could not initialize VertexRagPipeline. Falling back to default paths.[/yellow]")
            
            # Create a minimal pipeline object with just the tracking file paths
            class MinimalPipeline:
                pass
                
            pipeline = MinimalPipeline()
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            pipeline.tracking_file = os.path.join(base_dir, ".ingested_docs.json")
            pipeline.metadata_file = os.path.join(base_dir, ".document_metadata.json")
        
        # Clear from cloud if available
        if hasattr(pipeline, 'cloud_tracking_path') and pipeline.cloud_tracking_path:
            try:
                from src.rag.gcs_utils import GcsManager
                gcs_manager = GcsManager(project_id=pipeline.project_id, bucket_name=None)
                
                # Write empty lists to cloud tracking files to clear them
                gcs_manager.write_json(pipeline.cloud_tracking_path, [])
                logger.info(f"Cleared cloud tracking file: {pipeline.cloud_tracking_path}")
                
                # Also clear metadata if available
                if hasattr(pipeline, 'cloud_metadata_path') and pipeline.cloud_metadata_path:
                    gcs_manager.write_json(pipeline.cloud_metadata_path, {})
                    logger.info(f"Cleared cloud metadata file: {pipeline.cloud_metadata_path}")
            except Exception as e:
                error_msg = f"Could not clear cloud tracking files: {e}"
                logger.warning(error_msg)
                message = error_msg
        
        # Remove local tracking file if it exists
        if hasattr(pipeline, 'tracking_file') and pipeline.tracking_file:
            if os.path.exists(pipeline.tracking_file):
                os.remove(pipeline.tracking_file)
                logger.info(f"Removed local tracking file: {pipeline.tracking_file}")
            else:
                logger.info(f"Local tracking file not found: {pipeline.tracking_file}")
                
        # Remove local metadata file if it exists
        if hasattr(pipeline, 'metadata_file') and pipeline.metadata_file:
            if os.path.exists(pipeline.metadata_file):
                os.remove(pipeline.metadata_file)
                logger.info(f"Removed local metadata file: {pipeline.metadata_file}")
            else:
                logger.info(f"Local metadata file not found: {pipeline.metadata_file}")
                
        success = True
        if not message:
            message = "Successfully cleared all tracking files"
            
    except Exception as e:
        error_msg = f"Error clearing tracking files: {e}"
        logger.error(error_msg)
        message = error_msg
        
    return success, message


def recreate_corpus(pipeline=None, clear_tracking=True):
    """
    Drop and recreate the RAG corpus.
    
    Args:
        pipeline: An existing VertexRagPipeline instance (optional)
        clear_tracking: Whether to clear tracking files after recreation (default: True)
        
    Returns:
        Success status as boolean
    """
    logger.debug("Starting corpus recreation process")

    # Create pipeline if not provided
    if not pipeline:
        logger.debug("No pipeline provided, initializing a new one")
        with Status("[info]Initializing pipeline...[/info]", spinner="dots") as status:
            try:
                pipeline = VertexRagPipeline()
                logger.debug(
                    f"Pipeline initialized with project_id={pipeline.project_id}, location={pipeline.location}"
                )
            except Exception as e:
                error_msg = f"Error initializing pipeline: {e}"
                logger.error(error_msg)
                console.print(f"[error]{error_msg}[/error]")
                return False

    with Status("[info]Recreating corpus...[/info]", spinner="dots") as status:
        try:
            # Check if corpus exists
            logger.debug(f"Checking if corpus '{pipeline.corpus_name}' exists")
            status.update("[info]Checking for existing corpus...[/info]")
            try:
                existing_corpus = pipeline.get_corpus()
                corpus_name = existing_corpus.name if existing_corpus else None

                if corpus_name:
                    logger.debug(f"Found existing corpus: {corpus_name}")
                    # Temporarily pause the status display
                    status.stop()

                    # Show a more prominent confirmation dialog
                    console.print("\n")
                    console.print(
                        Panel(
                            f"[bold red]WARNING: CORPUS DELETION[/bold red]\n\n"
                            f"This will delete the existing corpus '[bold]{pipeline.corpus_name}[/bold]' and all its contents.\n"
                            f"All ingested documents will need to be re-ingested.\n\n"
                            "[bold]Type 'y' to confirm or 'n' to cancel.[/bold]",
                            title="[bold red]⚠️ Confirmation Required ⚠️[/bold red]",
                            border_style="red",
                            padding=(1, 2),
                        )
                    )

                    # Get confirmation with a clearer prompt
                    console.print(
                        "[bold red]Proceed with corpus deletion?[/bold red] [y/n] ",
                        end="",
                    )
                    confirm = input().lower().strip()

                    # Resume the status display with updated message
                    if confirm in ["y", "yes"]:
                        status.start()
                        status.update(
                            f"[info]Confirmed corpus deletion, proceeding...[/info]"
                        )
                    else:
                        logger.info("Corpus recreation cancelled by user")
                        console.print("[yellow]Corpus recreation cancelled.[/yellow]")
                        return False

                    # Delete the corpus
                    try:
                        logger.debug(f"Deleting corpus: {corpus_name}")
                        status.update(
                            f"[info]Deleting corpus '{pipeline.corpus_name}'...[/info]"
                        )
                        from vertexai import rag

                        rag.delete_corpus(corpus_name)
                        logger.info(f"Successfully deleted corpus: {corpus_name}")

                        # Pause status to show success message
                        status.stop()
                        console.print(
                            f"\n[green]Successfully deleted corpus '{pipeline.corpus_name}'[/green]"
                        )
                        # Resume status with new message
                        status.start()
                        status.update("[info]Creating new corpus...[/info]")
                    except Exception as delete_error:
                        # Handle deletion error
                        status.stop()
                        error_msg = f"Error deleting corpus: {delete_error}"
                        logger.error(error_msg)
                        console.print(f"\n[error]{error_msg}[/error]")
                        console.print(
                            "[yellow]Attempting to proceed with corpus creation anyway...[/yellow]"
                        )
                        status.start()
                        status.update("[info]Creating new corpus...[/info]")
                else:
                    logger.debug("No existing corpus found with the specified name")

            except Exception as e:
                error_msg = f"Could not find or delete existing corpus: {e}"
                logger.warning(error_msg)
                console.print(f"[yellow]{error_msg}[/yellow]")
                console.print("[yellow]Proceeding with corpus creation...[/yellow]")

            # Create a new corpus
            logger.debug(f"Creating new corpus with name: {pipeline.corpus_name}")
            status.update("[info]Creating new corpus...[/info]")

            try:
                corpus = pipeline.create_corpus()
                logger.info(f"Successfully created new corpus: {corpus.name}")

                # Pause status to show final success message
                status.stop()
                console.print(
                    f"\n[green]Successfully created new corpus: {corpus.name}[/green]"
                )
                
                # Clear tracking files if requested
                if clear_tracking:
                    console.print("[info]Clearing tracking files...[/info]")
                    clear_success, clear_message = clear_tracking_files()
                    if clear_success:
                        console.print("[green]Successfully cleared tracking files[/green]")
                    else:
                        console.print(f"[yellow]Warning: {clear_message}[/yellow]")

                logger.debug("Corpus recreation completed successfully")
                return True
            except Exception as create_error:
                # Handle creation error
                status.stop()
                error_msg = f"Error creating corpus: {create_error}"
                logger.error(error_msg)
                logger.debug(f"Creation error details: ", exc_info=True)
                console.print(f"\n[error]{error_msg}[/error]")
                return False

        except Exception as e:
            error_msg = f"Error recreating corpus: {e}"
            logger.error(error_msg)
            logger.debug(f"Stack trace: ", exc_info=True)
            console.print(f"[error]{error_msg}[/error]")
            return False


def ingest_documents(
    pipeline=None,
    prefix=None,
    specific_paths=None,
    recreate_first=False,
    force_reingest=False,
):
    """
    Ingest documents into the RAG corpus.

    Args:
        pipeline: An existing VertexRagPipeline instance (optional)
        prefix: Optional prefix to ingest documents from
        specific_paths: List of specific GCS paths to ingest
        recreate_first: Whether to recreate the corpus before ingestion
        force_reingest: Whether to force reingestion of already tracked documents

    Returns:
        Success status as boolean
    """
    # Create pipeline if not provided
    if not pipeline:
        with Status("[info]Initializing pipeline...[/info]", spinner="dots") as status:
            try:
                pipeline = VertexRagPipeline()
            except Exception as e:
                console.print(f"[error]Error initializing pipeline: {e}[/error]")
                return False

    # Recreate corpus if requested
    if recreate_first:
        console.print("[info]Recreating corpus before ingestion...[/info]")
        corpus_success = recreate_corpus(pipeline=pipeline)
        if not corpus_success:
            console.print("[error]Failed to recreate corpus. Aborting ingestion.[/error]")
            return False
        console.print("[green]Corpus recreation successful. Proceeding with ingestion...[/green]")

    with Status("[info]Ingesting documents...[/info]", spinner="dots") as status:
        try:
            # Determine which documents to ingest
            gcs_paths = []

            # If specific paths provided, use those
            if specific_paths:
                gcs_paths = specific_paths
                status.update(f"[info]Ingesting {len(gcs_paths)} specified documents...[/info]")

            # If prefix provided, list files with that prefix
            elif prefix:
                from src.rag.gcs_utils import GcsManager
                gcs_manager = GcsManager(project_id=pipeline.project_id, bucket_name=None)
                gcs_paths = gcs_manager.list_files(prefix=prefix)

                if not gcs_paths:
                    console.print(f"[yellow]No documents found with prefix '{prefix}'.[/yellow]")
                    return False

                status.update(f"[info]Found {len(gcs_paths)} documents with prefix '{prefix}'.[/info]")

            # Otherwise use default document prefixes from config
            else:
                status.update("[info]Using configured document prefixes...[/info]")
                # Empty list will cause pipeline to use the configured prefixes
                gcs_paths = []

            # Display what will be ingested
            if specific_paths or prefix:
                # Show a preview of the files to be ingested
                preview_limit = min(5, len(gcs_paths))
                preview_files = [path.split('/')[-1] for path in gcs_paths[:preview_limit]]
                preview_str = ", ".join(preview_files)

                if len(gcs_paths) > preview_limit:
                    preview_str += f", and {len(gcs_paths) - preview_limit} more"

                console.print(f"[info]Ingesting documents: {preview_str}[/info]")

            # Track the count of already ingested documents
            ingested_before = len(pipeline.ingested_documents) if hasattr(pipeline, 'ingested_documents') else 0

            # Perform ingestion
            if force_reingest:
                console.print(
                    "[yellow]Force reingestion enabled - will reingest all documents[/yellow]"
                )
            import_op = pipeline.ingest_documents(
                gcs_paths, force_reingest=force_reingest
            )

            # Determine if any new documents were ingested
            ingested_after = len(pipeline.ingested_documents) if hasattr(pipeline, 'ingested_documents') else 0
            newly_ingested = ingested_after - ingested_before

            # Display results
            if isinstance(import_op, dict) and import_op.get("status") == "skipped":
                console.print("[yellow]No new documents to ingest - all documents have already been ingested.[/yellow]")
                return True

            console.print(f"[green]Successfully started ingestion of {newly_ingested} new documents.[/green]")

            # Ask if we should wait for completion
            try:
                if hasattr(import_op, "operation") and sys.stdin.isatty():
                    wait = Prompt.ask("[info]Wait for ingestion to complete?[/info] (y/n)").lower() in ('y', 'yes')
                    if wait:
                        with Status("[info]Waiting for ingestion to complete...[/info]", spinner="dots") as wait_status:
                            import_op.operation.wait()
                        console.print("[green]Ingestion completed successfully![/green]")
            except KeyboardInterrupt:
                console.print("\n[yellow]Waiting for ingestion was interrupted. The ingestion is still in progress.[/yellow]")
                return True

            return True

        except Exception as e:
            console.print(f"[error]Error ingesting documents: {e}[/error]")
            return False


def list_ingested_documents(pipeline=None):
    """
    List documents that have been ingested into the RAG corpus.
    
    Args:
        pipeline: An existing VertexRagPipeline instance (optional)
    """
    # Create pipeline if not provided
    if not pipeline:
        with Status("[info]Initializing pipeline...[/info]", spinner="dots") as status:
            try:
                pipeline = VertexRagPipeline()
            except Exception as e:
                console.print(f"[error]Error initializing pipeline: {e}[/error]")
                return

    with Status("[info]Retrieving ingested documents...[/info]", spinner="dots") as status:
        try:
            # Get tracking information - include more details about where docs are tracked
            tracking_file = pipeline.tracking_file if hasattr(pipeline, 'tracking_file') else None
            cloud_tracking_path = (
                pipeline.cloud_tracking_path
                if hasattr(pipeline, "cloud_tracking_path")
                else None
            )
            
            # Handle the case where ingested_documents attribute may be missing
            if not hasattr(pipeline, 'ingested_documents'):
                console.print('[yellow]Warning: Pipeline does not have ingested_documents attribute. Initializing it.[/yellow]')
                pipeline.ingested_documents = set()
            ingested_docs = pipeline.ingested_documents
            
            # Get current corpus ID for filtering
            current_corpus_id = None
            try:
                corpus = pipeline.get_corpus()
                if corpus and hasattr(corpus, 'name'):
                    current_corpus_id = corpus.name
            except Exception as e:
                console.print(f"[yellow]Could not get corpus ID: {e}[/yellow]")
            
            # Filter documents by corpus ID - only if the corpus is set
            corpus_docs = []
            gs_docs = []
            for doc in ingested_docs:
                if isinstance(doc, str):
                    if doc.startswith('projects/') and current_corpus_id:
                        # For documents with project paths, only include ones matching current corpus
                        if doc.startswith(current_corpus_id):
                            corpus_docs.append(doc)
                    else:
                        # For GCS paths, always include
                        gs_docs.append(doc)
                        
            # Create filtered list showing only relevant documents
            filtered_docs = corpus_docs + gs_docs

            # Try to check if cloud tracking exists - for informational purposes
            cloud_tracking_exists = False
            if cloud_tracking_path:
                try:
                    from src.rag.gcs_utils import GcsManager

                    gcs_manager = GcsManager(
                        project_id=pipeline.project_id, bucket_name=None
                    )

                    # Just check if the file exists, don't read it
                    cloud_tracking_exists = gcs_manager.file_exists(cloud_tracking_path)
                except Exception:
                    # Ignore errors here, just for informational display
                    pass

            # Get corpus files from the RAG engine
            try:
                corpus_files = pipeline.list_corpus_files()
                corpus_files = list(corpus_files) if corpus_files else []
            except Exception as e:
                console.print(f"[yellow]Could not retrieve corpus files from Vertex AI: {e}[/yellow]")
                corpus_files = []

            # Display tracking information with more details
            status.stop()  # Stop the spinner to show tracking info

            # Create a tracking info panel
            tracking_table = Table(box=box.SIMPLE)
            tracking_table.add_column("Tracking Type", style="cyan", width=20)
            tracking_table.add_column("Path", style="white")
            tracking_table.add_column("Status", style="green", width=12)

            if cloud_tracking_path:
                cloud_status = (
                    "[green]Found[/green]"
                    if cloud_tracking_exists
                    else "[yellow]Not found[/yellow]"
                )
                tracking_table.add_row(
                    "Cloud Tracking", cloud_tracking_path, cloud_status
                )

            if tracking_file:
                local_exists = os.path.exists(tracking_file)
                local_status = (
                    "[green]Found[/green]"
                    if local_exists
                    else "[yellow]Not found[/yellow]"
                )
                tracking_table.add_row("Local Tracking", tracking_file, local_status)

            console.print(
                Panel(
                    tracking_table,
                    title="[info]Document Tracking Information[/info]",
                    border_style="blue",
                )
            )

            # Add information about the state of tracking
            missing_tracking = not tracking_file and not cloud_tracking_path
            empty_tracking = len(ingested_docs) == 0
            empty_corpus = len(corpus_files) == 0
            
            if empty_tracking and empty_corpus:
                if missing_tracking:
                    console.print("[yellow]No tracking files found and corpus appears to be empty.[/yellow]")
                    console.print("[info]You might need to ingest documents first or recreate the corpus.[/info]")
                else:
                    console.print("[yellow]No ingested documents found in tracking or corpus.[/yellow]")
                    console.print("[info]Try using /ingest all to add documents or check your configuration.[/info]")
                return
                
            # Warn about inconsistency between tracking and corpus
            if empty_tracking != empty_corpus:
                console.print(
                    "[yellow]Warning: Inconsistency between tracking files and corpus content![/yellow]"
                )
                if empty_tracking and not empty_corpus:
                    console.print(
                        "[info]Corpus contains documents but tracking files are empty. Use /sync rebuild to fix.[/info]"
                    )
                elif not empty_tracking and empty_corpus:
                    console.print(
                        "[info]Tracking files contain documents but corpus appears empty. Use /recreate corpus then /ingest all.[/info]"
                    )

            # Resume status for the rest of the function
            status.start()

            # Create table for ingested documents from tracking
            if filtered_docs:
                tracking_table = Table(
                    title=f"[bold]Tracked Ingested Documents[/bold] (Count: {len(filtered_docs)})",
                    box=box.ROUNDED,
                    expand=True
                )

                tracking_table.add_column("Prefix", style="cyan")
                tracking_table.add_column("Document Name", style="green")
                tracking_table.add_column("Full Path", style="blue")

                # Group documents by prefix for better display
                docs_by_prefix = {}
                for doc in filtered_docs:
                    # Extract prefix (up to the second-to-last path component)
                    path_parts = doc.split('/')
                    
                    if doc.startswith('projects/'):  
                        # For Vertex AI RAG document paths
                        # Format: projects/{project_id}/locations/{location}/ragCorpora/{corpus_id}/ragFiles/{file_id}
                        if len(path_parts) >= 7:
                            prefix = "Corpus Document"
                            # Add corpus ID to make it clear which corpus this belongs to
                            if current_corpus_id:
                                prefix = f"Current Corpus Document"
                        else:
                            prefix = "Unknown Corpus Path"
                    elif len(path_parts) > 4:  # gs://bucket/prefix/filename
                        prefix = '/'.join(path_parts[:-1]) + '/'
                    else:
                        prefix = '/'.join(path_parts[:-1]) + '/'

                    if prefix not in docs_by_prefix:
                        docs_by_prefix[prefix] = []

                    docs_by_prefix[prefix].append(doc)

                # Add rows to table organized by prefix
                for prefix, docs in docs_by_prefix.items():
                    for i, doc in enumerate(docs):
                        # Extract filename from path
                        if doc.startswith('projects/'):
                            # For Vertex AI RAG document paths
                            filename = f"File {i+1}"
                            # Try to extract file ID for a more useful name
                            path_parts = doc.split('/')
                            if len(path_parts) >= 7 and path_parts:
                                file_id = path_parts[-1]
                                # Add a safety check for empty file_id
                                if file_id:
                                    filename = f"File {file_id[:min(8, len(file_id))]}"
                        else:
                            path_parts = doc.split('/')
                            filename = path_parts[-1] if path_parts else "Unknown"

                        tracking_table.add_row(
                            prefix if i == 0 else "",
                            filename,
                            doc
                        )

                console.print(tracking_table)

            # Create table for corpus files from Vertex AI
            if corpus_files:
                corpus_table = Table(
                    title=f"[bold]Vertex AI RAG Corpus Files[/bold] (Count: {len(corpus_files)})",
                    box=box.ROUNDED,
                    expand=True
                )

                corpus_table.add_column("ID", style="dim")
                corpus_table.add_column("Name", style="green")
                corpus_table.add_column("State", style="yellow")

                for file_info in corpus_files:
                    file_id = file_info.name if hasattr(file_info, "name") else "Unknown"
                    display_name = file_info.display_name if hasattr(file_info, "display_name") else "Unknown"
                    state = file_info.state if hasattr(file_info, "state") else "Unknown"

                    corpus_table.add_row(file_id, display_name, state)

                console.print(corpus_table)

        except Exception as e:
            console.print(f"[error]Error listing ingested documents: {e}[/error]")


def display_logs_panel():
    """Display a panel with captured logs."""
    logs = get_captured_logs()
    if not logs:
        logs = "No logs captured yet."

    # Create table for logs with better formatting
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("Time", style="dim", width=12)
    table.add_column("Level", style="bold", width=10)
    table.add_column("Message", style="none")

    # Parse log entries
    has_logs = False
    for log_line in logs.strip().split("\n"):
        if not log_line.strip():
            continue

        has_logs = True
        try:
            # Try to parse log line format: '2023-05-14 12:34:56,789 - INFO - Message'
            parts = log_line.split(" - ", 2)
            if len(parts) == 3:
                time_str, level, message = parts
                # Use appropriate color based on log level
                if level == "DEBUG":
                    level_style = "dim cyan"
                elif level == "INFO":
                    level_style = "blue"
                elif level == "WARNING":
                    level_style = "yellow"
                elif level == "ERROR":
                    level_style = "bold red"
                elif level == "CRITICAL":
                    level_style = "bold white on red"
                else:
                    level_style = "default"

                table.add_row(
                    time_str, f"[{level_style}]{level}[/{level_style}]", message
                )
            else:
                # Fallback for unparseable lines
                table.add_row("", "", log_line)
        except Exception:
            # Fallback for any parsing errors
            table.add_row("", "", log_line)

    if not has_logs:
        logs_panel = Panel(
            "[dim]No logs captured yet at current logging level.[/dim]\n\n"
            "Logs will appear when:\n"
            "- In verbose mode: INFO level logs and above\n"
            "- In debug mode: DEBUG level logs and above\n"
            "- Otherwise: Only WARNING and ERROR logs\n\n"
            "Change logging level with 'debug' or 'verbose' commands.",
            title="[bold blue]System Logs[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
    else:
        logs_panel = Panel(
            table,
            title=f"[bold blue]System Logs[/bold blue] (Level: {logging.getLevelName(logger.getEffectiveLevel())})",
            border_style="blue",
            padding=(1, 2),
        )

    console.print(logs_panel)


def interactive_mode(use_reranking: bool = True, debug: bool = False, verbose: bool = False):
    """Run the CLI in interactive mode for multiple queries with improved UI."""
    # Show the logo first
    show_logo()

    # Set appropriate log level based on debug/verbose flags
    log_level = set_log_level(debug, verbose)

    # Log initialization
    logger.info("Starting Zero-Day Scout in interactive mode")
    logger.info(
        f"Settings: Reranking={use_reranking}, Debug={debug}, Verbose={verbose}, Log level={logging.getLevelName(log_level)}"
    )

    # Display command information
    console.print(
        Panel(
            "[info]Zero-Day Scout RAG Query Interface[/info]\n"
            "Type [bold]/exit[/bold] or [bold]/quit[/bold] to exit. Type [bold]/suggestions[/bold] to see query suggestions.\n"
            "Type [bold]/help[/bold] to see all available commands. Type [bold]/logs[/bold] to display system logs.\n"
            "All commands now start with [bold]/[/bold] to distinguish them from queries.",
            title="Interactive Mode",
            border_style="blue",
        )
    )

    # Create a more attractive status header with version and settings
    header = Panel(
        "[bold white]Vertex AI RAG Engine[/bold white]\n"
        "[dim]Your intelligent document assistant[/dim]\n\n"
        f"[{'green' if use_reranking else 'yellow'}]Reranking: {'Enabled' if use_reranking else 'Disabled'}[/{'green' if use_reranking else 'yellow'}]\n"
        f"[{'green' if debug else 'dim'}]Debug Mode: {'Enabled' if debug else 'Disabled'}[/{'green' if debug else 'dim'}]\n"
        f"[{'green' if verbose else 'dim'}]Verbose Mode: {'Enabled' if verbose else 'Disabled'}[/{'green' if verbose else 'dim'}]",
        title="[bold blue]Zero-Day Scout v1.0[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(header)

    # Always enable reranking by default
    if not use_reranking:
        use_reranking = True
        console.print("[green]Reranking enabled for better results![/green]")
        console.print(explain_reranking_benefits())

    # Display available commands at startup
    commands_panel = Panel(
        "[bold]Available Commands:[/bold]\n\n"
        "[bold cyan]Queries:[/bold cyan]\n"
        "• Enter any question to run a RAG query\n"
        "• [bold]/suggestions[/bold] - Get query improvement suggestions\n"
        "• [bold]/history[/bold] - Show previous queries\n\n"
        "[bold cyan]Document Management:[/bold cyan]\n"
        "• [bold]/papers[/bold] - List research papers in GCS\n"
        "• [bold]/ingested[/bold] - List ingested documents\n"
        "• [bold]/sync[/bold] - Synchronize document tracking files\n"
        "• [bold]/sync rebuild[/bold] - Rebuild tracking from actual corpus contents\n"
        "• [bold]/ingest all[/bold] - Ingest documents from all configured prefixes\n"
        "• [bold]/ingest force all[/bold] - Force reingestion of all documents\n"
        "• [bold]/recreate corpus[/bold] - Drop and recreate the RAG corpus\n"
        "• [bold]/clear tracking[/bold] - Remove all document tracking files\n\n"
        "[bold cyan]Settings:[/bold cyan]\n"
        "• [bold]/reranking[/bold] - Toggle reranking on/off\n"
        "• [bold]/debug[/bold] - Toggle debug mode\n"
        "• [bold]/verbose[/bold] - Toggle verbose mode\n"
        "• [bold]/clear[/bold] - Clear the screen\n"
        "• [bold]/logs[/bold] - Display system logs\n"
        "• [bold]/help[/bold] - Show all commands\n"
        "• [bold]/exit[/bold] or [bold]/quit[/bold] - Exit the application",
        title="[bold]Zero-Day Scout CLI[/bold]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(commands_panel)

    # Command history
    history = []

    # Create pipeline once for reuse
    pipeline = None
    try:
        with Status("[info]Initializing pipeline...[/info]", spinner="dots") as status:
            pipeline = VertexRagPipeline()
    except Exception as e:
        console.print(f"[error]Error initializing pipeline: {e}[/error]")

    while True:
        try:
            # Create a more visually appealing prompt for user input with integrated input area
            prompt_panel = Panel(
                "[bold bright_red]What would you like to know about security vulnerabilities?[/bold bright_red]\n"
                "[dim]Type a question, command, or 'help' for assistance[/dim]",
                title="[bold green]🔍 Ask Zero-Day Scout[/bold green]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
                expand=False
            )
            console.print("\n" + "─" * console.width)  # Add a separator line
            console.print(prompt_panel)

            # Create a panel with an input style border
            input_panel = Panel(
                "  ", # Placeholder spaces to create height
                title="[bold bright_red]Enter your query below[/bold bright_red]",
                title_align="left",
                border_style="red",
                padding=(0, 1)
            )
            console.print(input_panel)

            # Position cursor for input with indicator for command mode
            console.print("[bold green]❯[/bold green] ", end="")

            # Get user input - check if the last query was a command
            last_was_command = getattr(interactive_mode, "last_was_command", False)
            if last_was_command:
                # Show a helpful indicator that we're in command mode
                query = Prompt.ask("", default="/")
            else:
                query = Prompt.ask("")

            # Store whether this is a command for next iteration
            interactive_mode.last_was_command = query.startswith("/")

            # Display the query in a styled panel if it's not empty
            if query.strip():
                # Create a panel with the user's input inside
                query_panel = Panel(
                    f"[bold bright_red]{query}[/bold bright_red]",
                    title="[bold bright_red]Your Query[/bold bright_red]",
                    title_align="left",
                    border_style="red",
                    padding=(1, 2)
                )
                console.print(query_panel)

            # Skip processing if the query is empty
            if not query.strip():
                continue

            # Add a visual separator
            console.print("[dim]" + "─" * console.width + "[/dim]")

            if query.lower() in ('exit', 'quit'):
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting Zero-Day Scout[/yellow]")
            sys.exit(0)

        # Define minimum word requirement for queries
        MIN_QUERY_WORDS = 3

        # Check if it's a command (starts with /)
        is_command = query.startswith("/")
        command = query[1:].lower() if is_command else query.lower()

        # Handle commands with the / prefix
        if is_command and command == "help":
            help_panel = Panel(
                "Available commands:\n"
                "[bold]/help[/bold] - Show this help menu\n"
                "[bold]/exit[/bold] or [bold]/quit[/bold] - Exit the application\n"
                "[bold]/suggestions[/bold] - Get query improvement suggestions\n"
                "[bold]/history[/bold] - Show query history\n"
                "\n[bold cyan]Document Management:[/bold cyan]\n"
                "[bold]/papers[/bold] - List research papers in GCS\n"
                "[bold]/papers detailed[/bold] - List research papers with detailed information\n"
                "[bold]/papers <prefix>[/bold] - List research papers from a specific prefix\n"
                "[bold]/ingested[/bold] - List ingested documents\n"
                "[bold]/sync[/bold] - Synchronize document tracking between cloud and local storage\n"
                "[bold]/ingest all[/bold] - Ingest documents from all configured prefixes\n"
                "[bold]/ingest prefix <prefix>[/bold] - Ingest documents from a specific prefix\n"
                "[bold]/ingest gs://<path>[/bold] - Ingest specific document(s)\n"
                "[bold]/recreate corpus[/bold] - Drop and recreate the RAG corpus\n"
                "\n[bold cyan]Settings:[/bold cyan]\n"
                f"[bold]/reranking[/bold] - {'Disable' if use_reranking else 'Enable'} reranking (reranking is enabled by default)\n"
                f"[bold]/debug[/bold] - {'Disable' if debug else 'Enable'} debug mode\n"
                f"[bold]/verbose[/bold] - {'Disable' if verbose else 'Enable'} verbose mode with context display\n"
                "[bold]/clear[/bold] - Clear the screen\n"
                "[bold]/logs[/bold] - Display system logs",
                title="Help",
                border_style="blue",
            )
            console.print(help_panel)
            continue

        if is_command and command == "reranking":
            # Toggle reranking
            use_reranking = not use_reranking
            status = "[green]enabled[/green]" if use_reranking else "[yellow]disabled[/yellow]"
            console.print(f"Reranking is now {status}")

            # Show the benefits if disabling
            if not use_reranking:
                console.print(explain_reranking_benefits())
            continue

        if is_command and command == "debug":
            # Toggle debug mode
            debug = not debug
            status = "[green]enabled[/green]" if debug else "[yellow]disabled[/yellow]"
            console.print(f"Debug mode is now {status}")
            # Update log level when toggling debug mode
            set_log_level(debug, verbose)
            continue

        if is_command and command == "verbose":
            # Toggle verbose mode
            verbose = not verbose
            status = "[green]enabled[/green]" if verbose else "[yellow]disabled[/yellow]"
            console.print(f"Verbose mode is now {status}")
            # Update log level when toggling verbose mode
            set_log_level(debug, verbose)
            if verbose:
                console.print("[dim]Contexts will be shown after each query[/dim]")
            continue

        if is_command and command == "suggestions":
            last_query = getattr(interactive_mode, 'last_query', None)
            if last_query:
                with Status("[suggestion]Generating query suggestions...[/suggestion]", spinner="dots") as status:
                    suggestions = suggest_query_improvements(last_query)

                if suggestions:
                    suggestion_panel = Panel(
                        "\n".join(f"[suggestion]{i}. {suggestion}[/suggestion]" for i, suggestion in enumerate(suggestions, 1)),
                        title="Suggested Query Improvements",
                        border_style="yellow"
                    )
                    console.print(suggestion_panel)
                else:
                    console.print("[error]Couldn't generate suggestions[/error]")
            else:
                console.print("[error]No previous query to suggest improvements for[/error]")
            continue

        if is_command and command == "history":
            if history:
                history_table = Table(box=box.SIMPLE)
                history_table.add_column("#", style="dim")
                history_table.add_column("Query", style="cyan")

                for i, item in enumerate(history, 1):
                    history_table.add_row(str(i), item)

                console.print(Panel(history_table, title="Query History", border_style="blue"))
            else:
                console.print("[info]No query history yet[/info]")
            continue

        if is_command and command == "clear":
            console.clear()
            console.print(header)
            continue

        if is_command and command == "logs":
            display_logs_panel()
            continue

        # Handle research papers listing
        if is_command and command.startswith("papers"):
            parts = command.split()
            if len(parts) > 1:
                if parts[1].lower() == 'detailed':
                    list_research_papers(pipeline=pipeline, detailed=True)
                else:
                    # Assume the second part is a prefix
                    prefix = parts[1]
                    list_research_papers(pipeline=pipeline, prefix=prefix)
            else:
                list_research_papers(pipeline=pipeline)
            continue

        # Handle ingested documents listing
        if is_command and command == "ingested":
            list_ingested_documents(pipeline=pipeline)
            continue

        # Handle corpus recreation command with options
        if is_command and command.startswith("recreate corpus"):
            # Check for the "clear" option
            clear_tracking = "clear" in command
            if clear_tracking:
                console.print("[bold yellow]Will clear all tracking files after recreating corpus[/bold yellow]")
            recreate_corpus(pipeline=pipeline, clear_tracking=clear_tracking)
            continue
            
        # Handle clear tracking command
        if is_command and command == "clear tracking":
            console.print("[bold yellow]Warning: This will remove all document tracking files![/bold yellow]")
            confirm = Prompt.ask("Are you sure you want to continue? (y/n)").lower() in ["y", "yes"]
            if confirm:
                success, message = clear_tracking_files()
                if success:
                    console.print("[green]Successfully cleared all tracking files[/green]")
                else:
                    console.print(f"[error]Error: {message}[/error]")
            else:
                console.print("[info]Operation cancelled[/info]")
            continue

        # Handle document ingestion commands
        if is_command and command.startswith("ingest"):
            parts = command.split()
            if len(parts) > 1:
                # Check for force option
                force_reingest = "force" in [p.lower() for p in parts]

                # Extract prefix or specific paths
                if parts[1].lower() == 'all':
                    # Ingest using all configured prefixes
                    console.print("[info]Ingesting documents from all configured prefixes...[/info]")
                    # Ask if user wants to recreate corpus first - only for "ingest all"
                    recreate = Prompt.ask(
                        "[yellow]Do you want to recreate the corpus before ingestion?[/yellow] (y/n)"
                    ).lower() in ('y', 'yes')
                    ingest_documents(
                        pipeline=pipeline,
                        recreate_first=recreate,
                        force_reingest=force_reingest,
                    )
                elif parts[1].lower() == 'force' and len(parts) > 2 and parts[2].lower() == 'all':
                    # Force reingest all documents
                    console.print("[bold yellow]Force reingestion enabled - will reingest all documents[/bold yellow]")
                    # Ask if user wants to recreate corpus first
                    recreate = Prompt.ask(
                        "[yellow]Do you want to recreate the corpus before ingestion?[/yellow] (y/n)"
                    ).lower() in ('y', 'yes')
                    ingest_documents(
                        pipeline=pipeline,
                        recreate_first=recreate,
                        force_reingest=True,
                    )
                elif parts[1].lower() == 'prefix' and len(parts) > 2:
                    # Find the prefix - it could be after 'force'
                    prefix_idx = 2
                    if parts[2].lower() == "force" and len(parts) > 3:
                        prefix_idx = 3

                    prefix = parts[prefix_idx]
                    console.print(f"[info]Ingesting documents from prefix '{prefix}'...[/info]")
                    ingest_documents(
                        pipeline=pipeline, prefix=prefix, force_reingest=force_reingest
                    )
                elif parts[1].startswith("gs://") or (
                    len(parts) > 2 and parts[2].startswith("gs://")
                ):
                    # Ingest specific GCS paths - no corpus recreation
                    paths = [p for p in parts[1:] if p.startswith('gs://')]
                    console.print(f"[info]Ingesting {len(paths)} specific documents...[/info]")
                    ingest_documents(
                        pipeline=pipeline,
                        specific_paths=paths,
                        force_reingest=force_reingest,
                    )
                else:
                    console.print(
                        "[yellow]Invalid ingest command. Try '/ingest all', '/ingest prefix <prefix>', or '/ingest gs://<path>'[/yellow]"
                    )
            else:
                # Show help for ingest command
                ingest_help = Panel(
                    "Ingest command usage:\n"
                    "  [bold]/ingest all[/bold] - Ingest documents from all configured prefixes\n"
                    "  [bold]/ingest prefix <prefix>[/bold] - Ingest documents from a specific prefix\n"
                    "  [bold]/ingest gs://<path>[/bold] - Ingest specific document(s)\n\n"
                    "Note: Only with [bold]/ingest all[/bold], you'll be asked if you want to recreate the corpus.\n"
                    "Recreating the corpus deletes and rebuilds it completely.\n\n"
                    "Examples:\n"
                    "  /ingest all\n"
                    "  /ingest prefix uploaded_papers/\n"
                    "  /ingest gs://rag-research-papers/research/paper.pdf",
                    title="Ingest Command Help",
                    border_style="blue",
                )
                console.print(ingest_help)
            continue

        # Handle exit/quit commands
        if is_command and (command == "exit" or command == "quit"):
            break

        # Handle tracking sync command
        if is_command and command.startswith("sync"):
            # Check if it's a rebuild
            parts = command.split()
            rebuild = len(parts) > 1 and parts[1].lower() == "rebuild"
            
            console.print("[info]Synchronizing document tracking files...[/info]")
            if rebuild:
                console.print("[bold yellow]Rebuilding tracking from corpus contents...[/bold yellow]")
                
            success, message, doc_count = sync_tracking_files(verbose=True, rebuild=rebuild)
            if success and doc_count > 0:
                console.print(
                    f"[green]✓[/green] Tracking files synchronized successfully with {doc_count} documents."
                )
            continue

        # If it's a command that we don't recognize, show an error
        if is_command:
            console.print(f"[error]Unknown command: /{command}[/error]")
            console.print(
                "[info]Type [bold]/help[/bold] to see available commands[/info]"
            )
            continue

        # If it's not a command, treat it as a query

        # Check if the query meets the minimum word requirement
        word_count = len(query.split())
        if word_count < MIN_QUERY_WORDS:
            console.print(
                f"[error]Your query is too short. Please use at least {MIN_QUERY_WORDS} words for a meaningful search.[/error]"
            )
            console.print(
                "[info]Short queries often lead to poor search results. Try to be more specific.[/info]"
            )
            continue

        # Save the query for suggestions and add to history
        interactive_mode.last_query = query
        history.append(query)

        # Process the query
        console.print(f"\n[query]Query: {query}[/query]")
        # Log before query execution
        logger.info(f"Starting RAG query: {query}")
        response, execution_time, metrics = run_rag_query(query, use_reranking, debug, verbose, update_in_place=True)
        # Log after query completion
        logger.info(
            f"Query completed in {metrics.get('formatted_time', 'unknown time')}"
        )

        # Check if this is an empty response that needs more context
        if metrics.get("is_empty_response", False):
            # Show context panel for empty responses
            context_panel = create_context_panel(metrics)
            if context_panel:
                console.print(context_panel)

        # Display the response in a prominent panel with appropriate coloring
        # Use yellow for empty responses
        border_style = "yellow" if metrics.get("is_empty_response", False) else "green"
        title_color = "yellow" if metrics.get("is_empty_response", False) else "green"

        # Use the pre-calculated formatted time
        formatted_time = metrics.get("formatted_time", "unknown time")
        
        # Extract source citations if contexts are available
        contexts = metrics.get("contexts", [])
        source_citations = extract_source_citations(contexts)

        # Combine response with source citations - use proper spacing
        formatted_response = response
        if source_citations:
            # Add a clear separator to distinguish response from sources
            if not formatted_response.endswith("\n"):
                formatted_response += "\n"
            formatted_response += "\n" + "-" * 50 + source_citations

        response_panel = Panel(
            Markdown(formatted_response),
            title=f"[bold {title_color}]Response[/bold {title_color}] (completed in [time]{formatted_time}[/time])",
            border_style=border_style,
            expand=True,
            padding=(1, 2)
        )

        # Display immediately without extra spacing
        console.print(response_panel)

        # Automatically offer suggestions after each query
        console.print("\n[suggestion]Would you like to see suggested query improvements? (y/n)[/suggestion]")
        try:
            want_suggestions = Prompt.ask("").lower() in ('y', 'yes')
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting Zero-Day Scout[/yellow]")
            sys.exit(0)

        if want_suggestions:
            with Status("[suggestion]Generating query suggestions...[/suggestion]", spinner="dots") as status:
                suggestions = suggest_query_improvements(query)

            if suggestions:
                console.print("\n[suggestion]Suggested query improvements:[/suggestion]")
                for i, suggestion in enumerate(suggestions, 1):
                    console.print(f"[suggestion]{i}. {suggestion}[/suggestion]")

                # Allow user to select a suggestion
                console.print("\n[suggestion]Enter a [bold]number[/bold] to use a suggestion, or press Enter to continue[/suggestion]")
                try:
                    selection = Prompt.ask("")

                    if selection.isdigit() and 1 <= int(selection) <= len(suggestions):
                        selected_query = suggestions[int(selection) - 1]
                        interactive_mode.last_query = selected_query
                        history.append(selected_query)

                        console.print(f"\n[info]Processing suggested query: [query]{selected_query}[/query][/info]")

                        # Process the query with step tracking and handle possible Ctrl+C
                        try:
                            # Log before query execution of a suggestion
                            logger.info(
                                f"Starting RAG query with suggested query: {selected_query}"
                            )
                            response, execution_time, metrics = run_rag_query(selected_query, use_reranking, debug, verbose, update_in_place=True)
                            # Log after query completion
                            logger.info(
                                f"Suggested query completed in {metrics.get('formatted_time', 'unknown time')}"
                            )
                        except KeyboardInterrupt:
                            logger.warning("Query processing interrupted by user")
                            console.print("\n[yellow]Query processing interrupted[/yellow]")
                            graceful_exit()

                        # Check if this is an empty response that needs more context
                        if metrics.get("is_empty_response", False):
                            # Show context panel for empty responses
                            context_panel = create_context_panel(metrics)
                            if context_panel:
                                console.print(context_panel)

                        # Display the response in a prominent panel with appropriate coloring
                        # Use yellow for empty responses
                        border_style = "yellow" if metrics.get("is_empty_response", False) else "green"
                        title_color = "yellow" if metrics.get("is_empty_response", False) else "green"

                        # Extract source citations if contexts are available
                        contexts = metrics.get("contexts", [])
                        source_citations = extract_source_citations(contexts)

                        # Combine response with source citations - use proper spacing
                        formatted_response = response
                        if source_citations:
                            # Add a clear separator to distinguish response from sources
                            if not formatted_response.endswith("\n"):
                                formatted_response += "\n"
                            formatted_response += "\n" + "-" * 50 + source_citations

                        response_panel = Panel(
                            Markdown(formatted_response),
                            title=f"[bold {title_color}]Response[/bold {title_color}] (completed in [time]{metrics.get('formatted_time', 'unknown time')}[/time])",
                            border_style=border_style,
                            expand=True,
                            padding=(1, 2)
                        )

                        # Display immediately without extra spacing
                        console.print(response_panel)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Exiting Zero-Day Scout[/yellow]")
                    sys.exit(0)


# Global ASCII art logo for use throughout the application
LOGO_ART = """
███████╗███████╗██████╗  ██████╗       ██████╗  █████╗ ██╗   ██╗
╚══███╔╝██╔════╝██╔══██╗██╔═══██╗      ██╔══██╗██╔══██╗╚██╗ ██╔╝
  ███╔╝ █████╗  ██████╔╝██║   ██║█████╗██║  ██║███████║ ╚████╔╝ 
 ███╔╝  ██╔══╝  ██╔══██╗██║   ██║╚════╝██║  ██║██╔══██║  ╚██╔╝  
███████╗███████╗██║  ██║╚██████╔╝      ██████╔╝██║  ██║   ██║   
╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝       ╚═════╝ ╚═╝  ╚═╝   ╚═╝   
███████╗ ██████╗ ██████╗ ██╗   ██╗████████╗
██╔════╝██╔════╝██╔═══██╗██║   ██║╚══██╔══╝
███████╗██║     ██║   ██║██║   ██║   ██║   
╚════██║██║     ██║   ██║██║   ██║   ██║   
███████║╚██████╗╚██████╔╝╚██████╔╝   ██║   
╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝   
"""

def show_logo():
    """Show the logo with proper spacing to ensure it's visible."""
    console.print(f"\n[bold cyan]{LOGO_ART}[/bold cyan]")
    console.print(Align.center("[bold blue]Vertex AI RAG Engine CLI[/bold blue]"))
    console.print("")  # Add empty line after logo


def show_splash_screen():
    """Display a splash screen with animation."""
    # Create fancy splash screen with more space for the logo
    splash = Layout()
    splash.split_column(
        Layout(name="logo", size=15),  # Increased size to prevent cutting off
        Layout(name="tagline", size=1),
        Layout(name="loading", size=1),
        Layout(name="footer", size=1),
    )
    
    splash["logo"].update(Align.center(f"[bold cyan]{LOGO_ART}[/bold cyan]", vertical="middle"))
    splash["tagline"].update(Align.center("[bold blue]Vertex AI RAG Engine CLI[/bold blue]", vertical="middle"))
    splash["footer"].update(Align.center("[dim]Press CTRL+C to exit[/dim]", vertical="middle"))
    
    loading_steps = [
        "Initializing environment...",
        "Loading configuration...",
        "Preparing RAG engine...",
        "Ready!"
    ]
    
    try:
        with Live(splash, refresh_per_second=10, console=console) as live:
            for step in loading_steps:
                splash["loading"].update(Align.center(f"[yellow]{step}[/yellow]", vertical="middle"))
                time.sleep(0.8)  # Longer delay to keep logo visible
            
            # Keep the logo visible with "Press any key to continue..." message
            splash["loading"].update(Align.center("[green]Ready![/green]", vertical="middle"))
            splash["footer"].update(Align.center("[bold white]Press Enter to continue or CTRL+C to exit[/bold white]", vertical="middle"))
            
            # Wait for Enter key
            try:
                input()
            except KeyboardInterrupt:
                console.print("\n[yellow]Exiting Zero-Day Scout[/yellow]")
                sys.exit(0)
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting Zero-Day Scout[/yellow]")
        sys.exit(0)
    
    # Don't clear the screen to keep the logo
    # Just add a separator
    console.print("\n" + "=" * 80 + "\n")


def is_empty_response(response: str) -> bool:
    """Check if a response indicates no information was found."""
    # Common phrases that indicate no information was found
    empty_indicators = [
        "i don't have enough information",
        "no relevant information found",
        "cannot answer",
        "don't have sufficient information",
        "unable to provide", 
        "no information available",
        "no specific information",
        "no data found",
        "not enough context"
    ]
    
    response_lower = response.lower()
    return any(indicator in response_lower for indicator in empty_indicators)


def parse_pipeline_output(output: str, use_reranking: bool) -> Dict[str, Any]:
    """
    Parse the raw pipeline output and extract useful information.
    
    Args:
        output: The captured stdout from the pipeline
        use_reranking: Whether reranking was enabled
        
    Returns:
        Dictionary with structured information from the pipeline output
    """
    info = {
        "reranking_status": "enabled" if use_reranking else "disabled",
        "reranker_model": "",
        "context_count": 0,
        "response_type": "",
        "contexts_type": "",
        "errors": []
    }
    
    # Parse output line by line
    for line in output.strip().split("\n"):
        if not line:
            continue
            
        if "Using reranking with model:" in line:
            info["reranker_model"] = line.split(":", 1)[1].strip()
        elif "Response type:" in line:
            info["response_type"] = line.split(":", 1)[1].strip()
        elif "Contexts type:" in line:
            info["contexts_type"] = line.split(":", 1)[1].strip()
        elif "Found" in line and "results" in line:
            try:
                count = int(line.split()[1])
                info["context_count"] = count
            except (ValueError, IndexError):
                pass
        elif "Error:" in line:
            info["errors"].append(line.strip())
    
    return info


def format_context_preview(contexts: List[Any]) -> str:
    """Format retrieved contexts for display in debug mode."""
    if not contexts:
        return "[dim italic]No contexts retrieved[/dim italic]"
        
    preview = []
    for i, ctx in enumerate(contexts[:3], 1):  # Show first 3 contexts
        # Try different possible attributes based on context object structure
        content = None
        if hasattr(ctx, "text"):
            content = ctx.text
        elif hasattr(ctx, "content"):
            content = ctx.content
        elif hasattr(ctx, "chunk") and hasattr(ctx.chunk, "data"):
            content = ctx.chunk.data
            
        if content:
            # Truncate long texts
            if len(content) > 300:
                content = content[:300] + "..."
            
            # Format with metadata if available
            if hasattr(ctx, "metadata"):
                meta = ctx.metadata
                source = meta.get("source", "Unknown source")
                gcs_uri = None
                
                # Try to extract GCS URI from metadata
                if "uri" in meta:
                    gcs_uri = meta["uri"]
                elif "gcs_uri" in meta:
                    gcs_uri = meta["gcs_uri"]
                elif "url" in meta:
                    gcs_uri = meta["url"]
                elif isinstance(source, str) and source.startswith("gs://"):
                    gcs_uri = source
                
                source_info = source
                if gcs_uri:
                    # Convert the GCS URI to a hyperlink if possible
                    if gcs_uri.startswith("gs://"):
                        # Split URL and add safety checks
                        uri_parts = gcs_uri.split("/")
                        if len(uri_parts) > 2:
                            bucket_name = uri_parts[2]
                            object_path = "/".join(uri_parts[3:] if len(uri_parts) > 3 else [])
                        gcs_url = f"https://storage.cloud.google.com/{bucket_name}/{object_path}"
                        source_info = f"[link={gcs_url}]{source}[/link]"
                
                preview.append(f"[bold]Context {i}[/bold] (from {source_info}):\n[dim]{content}[/dim]\n")
            else:
                preview.append(f"[bold]Context {i}[/bold]:\n[dim]{content}[/dim]\n")
    
    if len(contexts) > 3:
        preview.append(f"[dim italic]...and {len(contexts) - 3} more contexts[/dim italic]")
        
    if not preview:
        return "[dim italic]Contexts retrieved but content not accessible[/dim italic]"
        
    return "\n".join(preview)


def extract_source_citations(contexts: List[Any]) -> str:
    """Extract source citations from contexts for display with the response."""
    if not contexts:
        return ""
    
    # Extract unique sources with their hyperlinks
    sources = []
    seen_sources = set()
    
    for ctx in contexts:
        # Based on the observed context structure, extract relevant information
        source_name = None
        source_uri = None
        
        # Get source display name (from the actual context structure)
        if hasattr(ctx, "source_display_name") and ctx.source_display_name:
            source_name = ctx.source_display_name
        
        # Get source URI (from the actual context structure)
        if hasattr(ctx, "source_uri") and ctx.source_uri:
            source_uri = ctx.source_uri
            
            # Extract filename from URI if no display name
            if not source_name and isinstance(source_uri, str):
                uri_parts = source_uri.split('/')
                if uri_parts and len(uri_parts) > 0:
                    source_name = uri_parts[-1] if uri_parts[-1] else "Unknown"
        
        # If we couldn't get a source name or URI, try to create a generic one
        if not source_name:
            # Use a generic name based on context content
            if hasattr(ctx, "text") and ctx.text:
                # Create a preview from the text
                preview = ctx.text.strip()[:30]
                source_name = f"Document containing '{preview}...'"
            else:
                # Completely generic label
                source_name = f"Context {len(sources) + 1}"
        
        # Skip if this source has already been seen
        if source_name in seen_sources:
            continue
            
        seen_sources.add(source_name)
        
        # Format source citation - simpler format without Rich markup to ensure compatibility
        if source_uri and isinstance(source_uri, str) and source_uri.startswith("gs://"):
            # Create hyperlink to GCS bucket
            try:
                # Split URL and add safety checks
                uri_parts = source_uri.split("/")
                if len(uri_parts) > 2:
                    bucket_name = uri_parts[2]
                    object_path = "/".join(uri_parts[3:] if len(uri_parts) > 3 else [])
                # Remove spaces or problematic chars in URL
                object_path = object_path.replace(" ", "%20")
                gcs_url = f"https://storage.cloud.google.com/{bucket_name}/{object_path}"
                
                # Add formatted citation - use a more explicit source reference
                display_name = source_name
                if len(display_name) > 30:
                    display_name = display_name[:27] + "..."
                    
                sources.append(f"Document: {display_name} (URL: {gcs_url})")
            except Exception as e:
                # If URL creation fails, just use the source name
                display_name = source_name
                if len(display_name) > 40:
                    display_name = display_name[:37] + "..."
                sources.append(f"Document: {display_name}")
        else:
            # Just add the source name without link
            display_name = source_name
            if len(display_name) > 40:
                display_name = display_name[:37] + "..."
            sources.append(f"Document: {display_name}")
    
    if not sources:
        return ""
        
    # Format the citations section in a plain-text way that will survive any rendering issues
    citations = "\n\nSources:\n"
    for i, source in enumerate(sources, 1):
        citations += f"{i}. {source}\n"
        
    return citations


def graceful_exit(signum=None, frame=None):
    """Handle exit signals gracefully."""
    logger.info("Application exit requested")
    console.print("\n[yellow]Exiting Zero-Day Scout[/yellow]")
    logger.info("Application shutdown complete")
    sys.exit(0)


def sync_tracking_files(verbose=False, rebuild=False):
    """
    Synchronize tracking files between cloud and local storage.
    Ensures that the tracking files match the actual corpus contents.

    Args:
        verbose: Whether to display console information about the sync
        rebuild: Whether to rebuild tracking from corpus contents

    Returns:
        Tuple of (success, message, doc_count) where success is a boolean indicating if sync was successful
    """
    sync_status = {"success": False, "message": "", "doc_count": 0}

    try:
        logger.info("Synchronizing document tracking files")

        status_obj = None
        if verbose:
            status_obj = Status(
                "[info]Synchronizing document tracking files...[/info]", spinner="dots"
            )
            status_obj.start()

        # Initialize pipeline to get access to tracking information
        pipeline = VertexRagPipeline()
        
        # First try to get the actual corpus contents if rebuild is requested
        if rebuild:
            if verbose and status_obj:
                status_obj.update("[info]Getting corpus contents from Vertex AI...[/info]")
                
            try:
                # Try to get corpus contents directly
                logger.info("Attempting to get corpus files from Vertex AI")
                # Make sure all required attributes are initialized
                required_attrs = ['ingested_documents', 'document_metadata', 'tracking_file', 'metadata_file']
                for attr in required_attrs:
                    if not hasattr(pipeline, attr):
                        if attr in ['ingested_documents', 'document_metadata']:
                            setattr(pipeline, attr, set() if attr == 'ingested_documents' else {})
                        else:
                            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                            if attr == 'tracking_file':
                                setattr(pipeline, attr, os.path.join(base_dir, ".ingested_docs.json"))
                            elif attr == 'metadata_file':
                                setattr(pipeline, attr, os.path.join(base_dir, ".document_metadata.json"))
                        logger.info(f"Initialized missing {attr} attribute")
                    
                try:
                    corpus_files = pipeline.list_corpus_files()
                    
                    # Extract document paths from corpus files
                    corpus_docs = []
                    for file_info in corpus_files:
                        # Extract file paths from the corpus response
                        if hasattr(file_info, 'gcs_uri'):
                            corpus_docs.append(file_info.gcs_uri)
                        elif hasattr(file_info, 'uri'):
                            corpus_docs.append(file_info.uri)
                        elif hasattr(file_info, 'file_path'):
                            corpus_docs.append(file_info.file_path)
                        elif hasattr(file_info, 'name'):
                            corpus_docs.append(file_info.name)
                except Exception as list_error:
                    logger.error(f"Error listing corpus files: {list_error}")
                    if verbose and status_obj:
                        status_obj.update("[info]Could not list corpus files, falling back to GCS bucket listing...[/info]")
                    
                    # Fallback to listing files in the GCS bucket
                    from src.rag.gcs_utils import GcsManager
                    gcs_manager = GcsManager(project_id=pipeline.project_id, bucket_name=None)
                    corpus_docs = []
                    
                    # Use document prefixes from config
                    for prefix in pipeline.document_prefixes:
                        paths = gcs_manager.list_files(prefix=prefix)
                        corpus_docs.extend(paths)
                        logger.info(f"Found {len(paths)} documents with prefix '{prefix}'")
                        
                    logger.info(f"Using GCS bucket listing as fallback: found {len(corpus_docs)} documents")
                    if verbose and status_obj:
                        status_obj.update(f"[info]Found {len(corpus_docs)} documents in GCS bucket[/info]")
                        
                # Save to both cloud and local
                if corpus_docs:
                    logger.info(f"Found {len(corpus_docs)} documents in corpus")
                    sync_status["doc_count"] = len(corpus_docs)
                    
                    # Save to cloud first
                    if hasattr(pipeline, "cloud_tracking_path") and pipeline.cloud_tracking_path:
                        from src.rag.gcs_utils import GcsManager
                        gcs_manager = GcsManager(project_id=pipeline.project_id, bucket_name=None)
                        gcs_manager.write_json(pipeline.cloud_tracking_path, corpus_docs)
                        logger.info(f"Updated cloud tracking with {len(corpus_docs)} documents from corpus")
                    
                    # Then save to local
                    if hasattr(pipeline, "tracking_file") and pipeline.tracking_file:
                        with open(pipeline.tracking_file, "w") as f:
                            json.dump(corpus_docs, f, indent=2)
                        logger.info(f"Updated local tracking with {len(corpus_docs)} documents from corpus")
                        
                    sync_status["success"] = True
                    sync_status["message"] = f"Successfully rebuilt tracking with {len(corpus_docs)} documents from corpus"
                    
                    if verbose and status_obj:
                        status_obj.update(f"[info]Found and synced {len(corpus_docs)} documents from corpus[/info]")
                        
                    # Return here as we've rebuilt tracking from corpus
                    if verbose and status_obj:
                        status_obj.stop()
                    return sync_status["success"], sync_status["message"], sync_status["doc_count"]
                    
                else:
                    logger.info("No documents found in corpus")
                    if verbose and status_obj:
                        status_obj.update("[info]No documents found in corpus, checking tracking files...[/info]")
            except Exception as corpus_e:
                logger.error(f"Error getting corpus files: {corpus_e}")
                if verbose and status_obj:
                    status_obj.update("[info]Could not get corpus files, checking tracking files...[/info]")
                
        # If we're here, either rebuild failed or wasn't requested
        # Fall back to synchronizing between cloud and local tracking files
        if hasattr(pipeline, "cloud_tracking_path") and pipeline.cloud_tracking_path:
            # Get the cloud tracking file
            try:
                from src.rag.gcs_utils import GcsManager

                gcs_manager = GcsManager(
                    project_id=pipeline.project_id, bucket_name=None
                )

                # Check if cloud tracking exists
                if gcs_manager.file_exists(pipeline.cloud_tracking_path):
                    # Get the cloud data
                    cloud_docs = gcs_manager.read_json(pipeline.cloud_tracking_path)
                    if cloud_docs:
                        logger.info(
                            f"Found {len(cloud_docs)} documents in cloud tracking"
                        )
                        sync_status["doc_count"] = len(cloud_docs)

                        # Save to local file for synchronization
                        if (
                            hasattr(pipeline, "tracking_file")
                            and pipeline.tracking_file
                        ):
                            try:
                                local_path = pipeline.tracking_file
                                with open(local_path, "w") as f:
                                    json.dump(cloud_docs, f, indent=2)
                                logger.info(
                                    f"Successfully synchronized {len(cloud_docs)} documents to local tracking file"
                                )
                                sync_status["success"] = True
                                sync_status["message"] = (
                                    f"Successfully synchronized {len(cloud_docs)} documents from cloud storage"
                                )
                            except Exception as e:
                                error_msg = f"Could not write local tracking file: {e}"
                                logger.warning(error_msg)
                                sync_status["message"] = error_msg
                    else:
                        sync_status["success"] = True
                        sync_status["message"] = "No documents found in cloud tracking"
                else:
                    logger.info(
                        "No cloud tracking file found. No synchronization needed."
                    )
                    sync_status["success"] = True
                    sync_status["message"] = (
                        "No cloud tracking file found. No synchronization needed."
                    )
            except Exception as e:
                error_msg = f"Error synchronizing tracking files: {e}"
                logger.warning(error_msg)
                sync_status["message"] = error_msg
        else:
            sync_status["success"] = True
            sync_status["message"] = (
                "Cloud tracking not configured. No synchronization performed."
            )
    except Exception as e:
        error_msg = f"Could not synchronize tracking files: {e}"
        logger.warning(error_msg)
        sync_status["message"] = error_msg

    # Display sync information if requested
    if verbose and sync_status["message"]:
        if status_obj:
            status_obj.stop()
            
        if sync_status["success"]:
            console.print(f"[green]✓[/green] {sync_status['message']}")
        else:
            console.print(f"[yellow]![/yellow] {sync_status['message']}")
    elif verbose and status_obj:
        status_obj.stop()

    return sync_status["success"], sync_status["message"], sync_status["doc_count"]


def main():
    """Main entry point for the CLI utility."""
    # Default to WARNING level initially
    logger.setLevel(logging.WARNING)

    # Log application startup
    logger.warning("Starting Zero-Day Scout CLI application")

    # Parse command line arguments first to check for verbose flag
    parser = argparse.ArgumentParser(description="Zero-Day Scout RAG Query CLI")
    parser.add_argument(
        "--debug", "-d", action="store_true", help="Show debug information"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output including contexts",
    )

    # Parse arguments only to check for verbose/debug flags
    # We'll do a full parse later
    try:
        args, _ = parser.parse_known_args()
        verbose_startup = args.debug or args.verbose
    except:
        verbose_startup = False

    # Synchronize tracking files at startup
    sync_result = sync_tracking_files(verbose=verbose_startup)

    # Set the verbose flag based on the sync result for debugging
    if sync_result and verbose_startup:
        success, message, doc_count = sync_result
        if doc_count > 0:
            console.print(f"[info]Ready with {doc_count} tracked documents.[/info]")

    # Set up signal handlers for graceful exit
    import signal
    signal.signal(signal.SIGINT, graceful_exit)  # Handle Ctrl+C

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Zero-Day Scout RAG Query CLI")
    parser.add_argument("--query", "-q", help="Query to process")
    parser.add_argument("--no-reranking", action="store_true", help="Disable reranking (not recommended)")
    # For backward compatibility
    parser.add_argument("--reranking", "-r", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--suggest", "-s", action="store_true", help="Suggest query improvements")
    parser.add_argument("--no-splash", action="store_true", help="Skip splash screen")
    parser.add_argument("--debug", "-d", action="store_true", help="Show debug information")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output including contexts")
    parser.add_argument("--papers", action="store_true", help="List research papers in GCS")
    parser.add_argument("--papers-detailed", action="store_true", help="List research papers with detailed information")
    parser.add_argument("--papers-prefix", help="List research papers with the specified prefix")
    parser.add_argument("--ingested", action="store_true", help="List ingested documents")
    parser.add_argument("--ingest-all", action="store_true", help="Ingest documents from all configured prefixes")
    parser.add_argument("--ingest-prefix", help="Ingest documents from the specified prefix")
    parser.add_argument("--ingest-paths", nargs='+', help="Ingest specific document paths (space-separated list of gs:// URLs)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reingestion of documents even if they're in the tracking list",
    )
    parser.add_argument("--recreate-before-ingest", action="store_true", help="Recreate the corpus before ingestion")
    parser.add_argument("--recreate-corpus", action="store_true", help="Drop and recreate the RAG corpus")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Print a message about Ctrl+C
    console.print("[dim]Press Ctrl+C at any time to exit[/dim]")

    # Show splash screen unless disabled
    if not args.no_splash and not args.query:
        show_splash_screen()

    # Wrap the entire execution in a try block to handle any exceptions gracefully
    try:
        # Handle papers-related commands first
        if args.papers or args.papers_detailed or args.papers_prefix:
            show_logo()
            if args.papers_prefix:
                list_research_papers(prefix=args.papers_prefix, detailed=args.papers_detailed)
            else:
                list_research_papers(detailed=args.papers_detailed)
            return 0

        # Handle ingested documents listing
        if args.ingested:
            show_logo()
            list_ingested_documents()
            return 0

        # Handle corpus recreation command
        if args.recreate_corpus:
            show_logo()
            console.print("[info]Recreating RAG corpus...[/info]")
            success = recreate_corpus()
            return 0 if success else 1

        # Handle document ingestion commands
        if args.ingest_all or args.ingest_prefix or args.ingest_paths:
            show_logo()

            # Recreation of corpus only applies to ingesting all documents
            recreate_first = False

            # Check if force reingestion is requested
            if args.force:
                console.print(
                    "[bold yellow]Force reingestion enabled - will reingest all documents[/bold yellow]"
                )

            if args.ingest_paths:
                # Ingest specific paths - no corpus recreation
                console.print(f"[info]Ingesting {len(args.ingest_paths)} specific documents...[/info]")
                success = ingest_documents(
                    specific_paths=args.ingest_paths, force_reingest=args.force
                )
            elif args.ingest_prefix:
                # Ingest from specific prefix - no corpus recreation
                console.print(f"[info]Ingesting documents from prefix '{args.ingest_prefix}'...[/info]")
                success = ingest_documents(
                    prefix=args.ingest_prefix, force_reingest=args.force
                )
            else:  # args.ingest_all
                # Ingest using all configured prefixes - optional corpus recreation
                console.print("[info]Ingesting documents from all configured prefixes...[/info]")
                # Only for ingest-all, check if recreate is requested
                recreate_first = args.recreate_before_ingest
                if recreate_first:
                    console.print("[info]Will recreate corpus before ingestion[/info]")
                success = ingest_documents(
                    recreate_first=recreate_first, force_reingest=args.force
                )

            return 0 if success else 1

        if args.query:
            # Single query mode - show logo
            show_logo()

            # Set appropriate log level based on command-line flags
            set_log_level(args.debug, args.verbose)

            console.print(f"[bold bright_red]Query: {args.query}[/bold bright_red]")

            # Always enable reranking by default unless explicitly disabled
            # Handle both the new --no-reranking flag and the legacy --reranking flag
            use_reranking = True
            if args.no_reranking:
                use_reranking = False
            elif hasattr(args, 'reranking') and args.reranking:
                use_reranking = True

            if use_reranking:
                console.print("[green]Reranking enabled for better results![/green]")
                if sys.stdin.isatty():  # Only show benefits if running in interactive terminal
                    console.print(explain_reranking_benefits())
            else:
                console.print("[yellow]Reranking disabled (not recommended)[/yellow]")

            if args.suggest:
                with Status("[suggestion]Generating query suggestions...[/suggestion]", spinner="dots") as status:
                    suggestions = suggest_query_improvements(args.query)

                if suggestions:
                    suggestion_panel = Panel(
                        "\n".join(f"[suggestion]{i}. {suggestion}[/suggestion]" for i, suggestion in enumerate(suggestions, 1)),
                        title="Suggested Query Improvements",
                        border_style="yellow"
                    )
                    console.print(suggestion_panel)

                    console.print("\n[suggestion]Enter a [bold]number[/bold] to use a suggestion, or press Enter to use original query[/suggestion]")
                    try:
                        selection = Prompt.ask("")

                        if selection.isdigit() and 1 <= int(selection) <= len(suggestions):
                            query = suggestions[int(selection) - 1]
                            console.print(f"\n[info]Using suggested query: [query]{query}[/query][/info]")
                        else:
                            query = args.query
                    except KeyboardInterrupt:
                        graceful_exit()
                else:
                    query = args.query
                    console.print("[info]No suggestions available, using original query[/info]")
            else:
                query = args.query

            # Process the query with step tracking
            try:
                response, execution_time, metrics = run_rag_query(
                    query, 
                    use_reranking, 
                    args.debug, 
                    args.verbose,
                    update_in_place=True
                )
            except KeyboardInterrupt:
                console.print("\n[yellow]Query processing interrupted[/yellow]")
                graceful_exit()

            # Check if this is an empty response that needs more context
            if metrics.get("is_empty_response", False):
                # Show context panel for empty responses
                context_panel = create_context_panel(metrics)
                if context_panel:
                    console.print(context_panel)

            # Display the response in a prominent panel with appropriate coloring
            # Use yellow for empty responses
            border_style = "yellow" if metrics.get("is_empty_response", False) else "green"
            title_color = "yellow" if metrics.get("is_empty_response", False) else "green"

            # Extract source citations if contexts are available
            contexts = metrics.get("contexts", [])
            source_citations = extract_source_citations(contexts)

            # Combine response with source citations - use proper spacing
            formatted_response = response
            if source_citations:
                # Add a clear separator to distinguish response from sources
                if not formatted_response.endswith("\n"):
                    formatted_response += "\n"
                formatted_response += "\n" + "-" * 50 + source_citations

            response_panel = Panel(
                Markdown(formatted_response),
                title=f"[bold {title_color}]Response[/bold {title_color}] (completed in [time]{metrics.get('formatted_time', 'unknown time')}[/time])",
                border_style=border_style,
                expand=True,
                padding=(1, 2)
            )

            # Display immediately without extra spacing
            console.print(response_panel)
        else:
            # Interactive mode - will handle its own KeyboardInterrupt
            try:
                # Set the log level based on command-line flags before entering interactive mode
                set_log_level(args.debug, args.verbose)

                # Determine reranking setting (enabled by default unless explicitly disabled)
                use_reranking = not args.no_reranking
                interactive_mode(use_reranking, args.debug, args.verbose)
            except KeyboardInterrupt:
                graceful_exit()

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        graceful_exit()
    except Exception as e:
        # Handle all other exceptions
        console.print(f"[error]Error: {e}[/error]")
        if args and args.debug:
            import traceback
            console.print(f"[dim red]{traceback.format_exc()}[/dim red]")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
