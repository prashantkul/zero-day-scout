"""
Markdown Export module for Zero-Day Scout.

This module provides functionality to export security analysis results to Markdown files.
"""

import os
import re
import time
import logging
import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Configure module logger
logger = logging.getLogger(__name__)

# Base directory for reports
REPORTS_DIR = os.path.abspath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "reports"
))


def ensure_reports_dir():
    """Ensure reports directory exists."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    logger.debug(f"Ensuring reports directory exists: {REPORTS_DIR}")


def generate_report_filename(query: str) -> str:
    """
    Generate a timestamped filename for the report based on the query.
    
    Args:
        query: The security query
        
    Returns:
        A filename for the report
    """
    # Clean query to create a valid filename
    clean_query = re.sub(r'[^\w\s-]', '', query)
    clean_query = re.sub(r'[\s-]+', '_', clean_query).strip('_')
    
    # Limit length
    if len(clean_query) > 50:
        clean_query = clean_query[:50]
    
    # Add timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    return f"security_report_{clean_query}_{timestamp}.md"


def export_to_markdown(
    query: str,
    final_response: str,
    agent_outputs: Optional[Dict[str, Dict[str, str]]] = None,
    include_sources: bool = True,
    filename: Optional[str] = None
) -> str:
    """
    Export security analysis results to a Markdown file.
    
    Args:
        query: The security query
        final_response: The final response text
        agent_outputs: Outputs from individual agents
        include_sources: Whether to include source information
        filename: Custom filename (if None, one will be generated)
        
    Returns:
        Path to the created Markdown file
    """
    # Make sure reports directory exists
    ensure_reports_dir()
    
    # Generate filename if not provided
    if not filename:
        filename = generate_report_filename(query)
        
    # Full path to the Markdown file
    md_path = os.path.join(REPORTS_DIR, filename)
    
    try:
        # Build content
        md_content = []
        
        # Add title
        md_content.append("# Zero-Day Scout Security Analysis\n")
        
        # Add timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        md_content.append(f"*Report generated on: {timestamp}*\n")
        
        # Add brief disclaimer at the top
        md_content.append("***AI-generated analysis for informational purposes only. Requires verification by security professionals.***\n")
        
        # Add query
        md_content.append("## Security Query\n")
        md_content.append(f"{query}\n")
        
        # Add divider
        md_content.append("---\n")
        
        # If we have agent outputs, include them
        if agent_outputs and isinstance(agent_outputs, dict):
            # Planner output
            if "security_planner" in agent_outputs and agent_outputs["security_planner"].get("output"):
                md_content.append("## Research Plan\n")
                planner_output = agent_outputs["security_planner"]["output"]
                md_content.append(f"{planner_output}\n")
            
            # Researcher output - Split to separate research findings from sources
            if "security_researcher" in agent_outputs and agent_outputs["security_researcher"].get("output"):
                researcher_output = agent_outputs["security_researcher"]["output"]
                
                # Split research findings from sources if present
                if "## Research Sources" in researcher_output:
                    parts = researcher_output.split("## Research Sources", 1)
                    research_content = parts[0].strip()
                    sources_content = "## Research Sources" + parts[1]
                    
                    # Add research findings
                    md_content.append("## Research Findings\n")
                    md_content.append(f"{research_content}\n")
                    
                    # Add sources if requested
                    if include_sources:
                        md_content.append(f"{sources_content}\n")
                else:
                    # Just add the whole content
                    md_content.append("## Research Findings\n")
                    md_content.append(f"{researcher_output}\n")
            
            # Analysis output
            if "security_analyst" in agent_outputs and agent_outputs["security_analyst"].get("output"):
                md_content.append("## Security Analysis\n")
                analyst_output = agent_outputs["security_analyst"]["output"]
                md_content.append(f"{analyst_output}\n")
                
            # Add divider
            md_content.append("---\n")
        
        # Add final response
        md_content.append("## Final Analysis\n")
        md_content.append(f"{final_response}\n")
        
        # Add disclaimer
        md_content.append("## DISCLAIMER\n")
        
        disclaimer_text = """
This report was generated by Zero-Day Scout, an autonomous security research agent that uses Retrieval-Augmented Generation (RAG) technology.
The information provided should be used for informational purposes only and verified by security professionals before implementation.
This is an AI-generated analysis and may not cover all aspects of the security topic. Security best practices and vulnerabilities
change over time, so ensure you consult current security resources and subject matter experts for critical security decisions.
Zero-Day Scout is designed to assist security research, not replace human expertise and judgment.
"""
        
        md_content.append(disclaimer_text)
        
        # Add footer
        md_content.append(f"\n*Generated by Zero-Day Scout Agentic RAG System on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        # Write content to file
        with open(md_path, 'w') as f:
            f.write('\n'.join(md_content))
        
        logger.info(f"Markdown report saved to: {md_path}")
        return md_path
        
    except Exception as e:
        logger.error(f"Error generating Markdown report: {e}")
        return ""