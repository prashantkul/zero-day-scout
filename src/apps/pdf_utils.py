"""
PDF export utilities for the Scout CLI.
"""

import os
import logging
from typing import Dict, Any, Optional

# Configure module logger
logger = logging.getLogger(__name__)

def export_results_to_pdf(
    query: str,
    final_response: str,
    agent_outputs: Optional[Dict[str, Dict[str, str]]] = None,
    include_sources: bool = True,
    console = None
) -> str:
    """
    Export analysis results to PDF.
    
    Args:
        query: The security query
        final_response: The final analysis
        agent_outputs: Outputs from individual agents
        include_sources: Whether to include research sources
        console: Rich console for output
        
    Returns:
        Path to the generated PDF file
    """
    try:
        # Import here to avoid circular imports
        from src.apps.pdf_exporter import export_to_pdf, is_available
        
        if not is_available():
            if console:
                console.print("[pdf.error]PDF export not available. Install reportlab package to enable this feature.[/pdf.error]")
            logger.error("PDF export not available. Install reportlab package to enable this feature.")
            return ""
            
        # Generate the PDF
        pdf_path = export_to_pdf(
            query=query,
            final_response=final_response, 
            agent_outputs=agent_outputs,
            include_sources=include_sources
        )
        
        if pdf_path and os.path.exists(pdf_path):
            if console:
                console.print(f"[pdf.success]Report successfully exported to PDF:[/pdf.success]")
                console.print(f"[pdf.path]{pdf_path}[/pdf.path]")
            logger.info(f"Report exported to PDF: {pdf_path}")
            return pdf_path
        else:
            if console:
                console.print("[pdf.error]Failed to generate PDF report.[/pdf.error]")
            logger.error("Failed to generate PDF report")
            return ""
            
    except Exception as e:
        if console:
            console.print(f"[pdf.error]Error exporting to PDF: {e}[/pdf.error]")
        logger.error(f"Error exporting to PDF: {e}")
        return ""