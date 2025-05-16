"""
PDF Export module for Zero-Day Scout.

This module provides functionality to export security analysis results to PDF files.
"""

import os
import re
import time
import logging
import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.platypus import PageBreak, Image, ListFlowable, ListItem
    reportlab_available = True
except ImportError:
    reportlab_available = False
    logging.warning("ReportLab not available. PDF export will not work.")

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
    
    return f"security_report_{clean_query}_{timestamp}.pdf"


def markdown_to_reportlab(md_text: str) -> List[Any]:
    """
    Convert markdown text to ReportLab flowables.
    
    Args:
        md_text: Markdown-formatted text
        
    Returns:
        List of ReportLab flowables
    """
    if not reportlab_available:
        return []
        
    styles = getSampleStyleSheet()
    
    # Add custom styles
    styles.add(ParagraphStyle(
        name='Heading1',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=12
    ))
    
    styles.add(ParagraphStyle(
        name='Heading2',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10
    ))
    
    styles.add(ParagraphStyle(
        name='Heading3',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=8
    ))
    
    styles.add(ParagraphStyle(
        name='CodeBlock',
        parent=styles['Code'],
        fontSize=9,
        fontName='Courier',
        leftIndent=20,
        rightIndent=20,
        spaceAfter=8,
        spaceBefore=8,
        backColor=colors.lightgrey
    ))
    
    # Split content into lines
    lines = md_text.split('\n')
    flowables = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Headers
        if line.startswith('# '):
            flowables.append(Paragraph(line[2:], styles['Heading1']))
            flowables.append(Spacer(1, 6))
        elif line.startswith('## '):
            flowables.append(Paragraph(line[3:], styles['Heading2']))
            flowables.append(Spacer(1, 4))
        elif line.startswith('### '):
            flowables.append(Paragraph(line[4:], styles['Heading3']))
            flowables.append(Spacer(1, 2))
            
        # Bold and italic
        elif '**' in line or '*' in line or '__' in line or '_' in line:
            # Replace markdown with HTML for ReportLab
            line = line.replace('**', '<b>').replace('**', '</b>')
            line = line.replace('__', '<b>').replace('__', '</b>')
            line = line.replace('*', '<i>').replace('*', '</i>')
            line = line.replace('_', '<i>').replace('_', '</i>')
            flowables.append(Paragraph(line, styles['Normal']))
            
        # Regular paragraph
        elif line:
            flowables.append(Paragraph(line, styles['Normal']))
            
        # Code blocks - indented or fenced
        elif i + 1 < len(lines) and (lines[i+1].startswith('    ') or lines[i+1].startswith('```')):
            if lines[i+1].startswith('```'):
                # Skip the opening fence
                i += 1
                code_lines = []
                i += 1
                # Collect until closing fence
                while i < len(lines) and not lines[i].startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                code_text = '<br/>'.join(code_lines)
                flowables.append(Paragraph(code_text, styles['CodeBlock']))
            else:
                # Indented code
                code_lines = []
                while i + 1 < len(lines) and lines[i+1].startswith('    '):
                    code_lines.append(lines[i+1][4:])  # Remove indent
                    i += 1
                code_text = '<br/>'.join(code_lines)
                flowables.append(Paragraph(code_text, styles['CodeBlock']))
        
        # Add some spacing between paragraphs
        if line:
            flowables.append(Spacer(1, 6))
            
        i += 1
        
    return flowables


def export_to_pdf(
    query: str,
    final_response: str,
    agent_outputs: Optional[Dict[str, Dict[str, str]]] = None,
    include_sources: bool = True,
    filename: Optional[str] = None
) -> str:
    """
    Export security analysis results to a PDF file.
    
    Args:
        query: The security query
        final_response: The final response text
        agent_outputs: Outputs from individual agents
        include_sources: Whether to include source information
        filename: Custom filename (if None, one will be generated)
        
    Returns:
        Path to the created PDF file
    """
    if not reportlab_available:
        logger.error("ReportLab not available. Cannot export to PDF.")
        return ""
    
    # Make sure reports directory exists
    ensure_reports_dir()
    
    # Generate filename if not provided
    if not filename:
        filename = generate_report_filename(query)
        
    # Full path to the PDF file
    pdf_path = os.path.join(REPORTS_DIR, filename)
    
    try:
        # Create PDF document
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Build content
        styles = getSampleStyleSheet()
        elements = []
        
        # Add title
        title_style = styles["Title"]
        elements.append(Paragraph("Zero-Day Scout Security Analysis", title_style))
        elements.append(Spacer(1, 12))
        
        # Add timestamp
        date_style = styles["Normal"]
        date_style.alignment = 1  # Center alignment
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elements.append(Paragraph(f"Report generated on: {timestamp}", date_style))
        elements.append(Spacer(1, 24))
        
        # Add brief disclaimer at the top
        brief_disclaimer_style = ParagraphStyle(
            name='BriefDisclaimer',
            parent=styles['Italic'],
            alignment=1,  # Center alignment
            textColor=colors.dark_red,
            fontSize=10,
            spaceAfter=12
        )
        
        brief_disclaimer = "AI-generated analysis for informational purposes only. Requires verification by security professionals."
        elements.append(Paragraph(brief_disclaimer, brief_disclaimer_style))
        elements.append(Spacer(1, 12))
        
        # Add query
        elements.append(Paragraph("Security Query:", styles["Heading2"]))
        elements.append(Paragraph(query, styles["Normal"]))
        elements.append(Spacer(1, 18))
        
        # Add divider
        elements.append(Paragraph("<hr/>", styles["Normal"]))
        elements.append(Spacer(1, 18))
        
        # If we have agent outputs, include them
        if agent_outputs and isinstance(agent_outputs, dict):
            # Add workflow stages
            
            # Planner output
            if "security_planner" in agent_outputs and agent_outputs["security_planner"].get("output"):
                elements.append(Paragraph("Research Plan:", styles["Heading2"]))
                planner_output = agent_outputs["security_planner"]["output"]
                
                # Convert markdown to reportlab elements
                planner_elements = markdown_to_reportlab(planner_output)
                elements.extend(planner_elements)
                elements.append(Spacer(1, 18))
            
            # Researcher output - Split to separate research findings from sources
            if "security_researcher" in agent_outputs and agent_outputs["security_researcher"].get("output"):
                researcher_output = agent_outputs["security_researcher"]["output"]
                
                # Split research findings from sources if present
                if "## Research Sources" in researcher_output:
                    parts = researcher_output.split("## Research Sources", 1)
                    research_content = parts[0].strip()
                    sources_content = "## Research Sources" + parts[1]
                    
                    # Add research findings
                    elements.append(Paragraph("Research Findings:", styles["Heading2"]))
                    research_elements = markdown_to_reportlab(research_content)
                    elements.extend(research_elements)
                    elements.append(Spacer(1, 18))
                    
                    # Add sources if requested
                    if include_sources:
                        elements.append(Paragraph("Research Sources:", styles["Heading2"]))
                        sources_elements = markdown_to_reportlab(sources_content)
                        elements.extend(sources_elements)
                        elements.append(Spacer(1, 18))
                else:
                    # Just add the whole content
                    elements.append(Paragraph("Research Findings:", styles["Heading2"]))
                    research_elements = markdown_to_reportlab(researcher_output)
                    elements.extend(research_elements)
                    elements.append(Spacer(1, 18))
            
            # Analysis output
            if "security_analyst" in agent_outputs and agent_outputs["security_analyst"].get("output"):
                elements.append(Paragraph("Security Analysis:", styles["Heading2"]))
                analyst_output = agent_outputs["security_analyst"]["output"]
                analyst_elements = markdown_to_reportlab(analyst_output)
                elements.extend(analyst_elements)
                elements.append(Spacer(1, 18))
                
            # Add divider
            elements.append(Paragraph("<hr/>", styles["Normal"]))
            elements.append(Spacer(1, 18))
        
        # Add final response
        elements.append(Paragraph("Final Analysis:", styles["Heading2"]))
        final_elements = markdown_to_reportlab(final_response)
        elements.extend(final_elements)
        
        # Add disclaimer
        elements.append(Spacer(1, 36))
        elements.append(Paragraph("DISCLAIMER", styles["Heading3"]))
        
        disclaimer_style = ParagraphStyle(
            name='Disclaimer',
            parent=styles['Normal'],
            textColor=colors.dark_red,
            fontSize=9,
            spaceAfter=12,
            borderWidth=1,
            borderColor=colors.lightgrey,
            borderPadding=5,
            borderRadius=5
        )
        
        disclaimer_text = """
        This report was generated by Zero-Day Scout, an autonomous security research agent that uses Retrieval-Augmented Generation (RAG) technology.
        The information provided should be used for informational purposes only and verified by security professionals before implementation.
        This is an AI-generated analysis and may not cover all aspects of the security topic. Security best practices and vulnerabilities
        change over time, so ensure you consult current security resources and subject matter experts for critical security decisions.
        Zero-Day Scout is designed to assist security research, not replace human expertise and judgment.
        """
        
        elements.append(Paragraph(disclaimer_text, disclaimer_style))
        
        # Add footer
        elements.append(Spacer(1, 24))
        footer_text = f"Generated by Zero-Day Scout Agentic RAG System on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        footer_style = styles["Normal"]
        footer_style.alignment = 1  # Center alignment
        footer_style.fontSize = 8
        elements.append(Paragraph(footer_text, footer_style))
        
        # Build PDF
        doc.build(elements)
        
        logger.info(f"PDF report saved to: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return ""


def is_available() -> bool:
    """Check if PDF export is available (ReportLab is installed)."""
    return reportlab_available