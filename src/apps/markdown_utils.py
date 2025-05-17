"""
Markdown export utilities for the Scout CLI.
"""

import os
import logging
from typing import Dict, Any, Optional

# Configure module logger
logger = logging.getLogger(__name__)

def export_results_to_markdown(
    query: str,
    final_response: str,
    agent_outputs: Optional[Dict[str, Dict[str, str]]] = None,
    include_sources: bool = True,
    console = None
) -> str:
    """
    Export analysis results to Markdown.
    
    Args:
        query: The security query
        final_response: The final analysis
        agent_outputs: Outputs from individual agents
        include_sources: Whether to include research sources
        console: Rich console for output
        
    Returns:
        Path to the generated Markdown file
    """
    try:
        # Import here to avoid circular imports
        from src.apps.markdown_exporter import export_to_markdown
            
        # Generate the Markdown file
        md_path = export_to_markdown(
            query=query,
            final_response=final_response, 
            agent_outputs=agent_outputs,
            include_sources=include_sources
        )
        
        if md_path and os.path.exists(md_path):
            if console:
                console.print(f"[bright_green]Report successfully exported to Markdown:[/bright_green]")
                console.print(f"[bright_white]{md_path}[/bright_white]")
            logger.info(f"Report exported to Markdown: {md_path}")
            return md_path
        else:
            if console:
                console.print("[bright_red]Failed to generate Markdown report.[/bright_red]")
            logger.error("Failed to generate Markdown report")
            return ""
            
    except Exception as e:
        if console:
            console.print(f"[bright_red]Error exporting to Markdown: {e}[/bright_red]")
        logger.error(f"Error exporting to Markdown: {e}")
        return ""