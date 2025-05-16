"""
Tools for the Zero-Day Scout Agentic RAG system.

This module implements specialized tools for the agents:
- RagQueryTool: Interface to the VertexRagPipeline for information retrieval
- VulnerabilityAnalysisTool: Tool for analyzing security vulnerabilities
- CveLookupTool: Tool for looking up CVE information
"""

from typing import Dict, List, Any, Optional
import json
import logging
import inspect

from google.adk.tools import FunctionTool

from src.rag.pipeline import VertexRagPipeline

logger = logging.getLogger(__name__)


class RagQueryTool(FunctionTool):
    """
    Tool for querying the RAG system to retrieve security information.
    
    This tool provides an interface to the existing VertexRagPipeline,
    allowing agents to retrieve information from the security corpus.
    """
    
    def __init__(self):
        """Initialize the RAG query tool with a pipeline instance."""
        self._pipeline = None
        
        # Define the function that will be called by the tool
        def rag_query(
            query: str,
            use_reranking: bool = True,
            max_results: int = 5
        ) -> str:
            """
            Query the RAG system to find information about security vulnerabilities and zero-day exploits.
            
            Args:
                query: The security query to search for
                use_reranking: Whether to use reranking for better results
                max_results: Maximum number of results to return
                
            Returns:
                Retrieved information as formatted text
            """
            return self._execute_query(query, use_reranking, max_results)
        
        # Initialize the FunctionTool with our function
        super().__init__(func=rag_query)
    
    @property
    def pipeline(self) -> VertexRagPipeline:
        """Lazy-loaded RAG pipeline."""
        if self._pipeline is None:
            self._pipeline = VertexRagPipeline()
        return self._pipeline
    
    def _execute_query(self, query: str, use_reranking: bool = True, max_results: int = 5) -> str:
        """
        Execute a query against the RAG system.
        
        Args:
            query: The security query to search for
            use_reranking: Whether to use reranking for better results
            max_results: Maximum number of results to return
            
        Returns:
            Retrieved information as formatted text
        """
        if not query:
            return "Error: No query provided"
        
        try:
            logger.info(f"Executing RAG query: {query} (reranking: {use_reranking})")
            
            # Use direct RAG if available for better integration
            try:
                # First attempt with direct RAG integration
                response = self.pipeline.direct_rag_response(
                    query=query,
                    use_reranking=use_reranking
                )
                
                # Log RAG matches and information for visualization
                logger.info(f"Used direct RAG integration for query: {query}")
                
                # Format the response with RAG information for better display
                # Check if the pipeline has tracked contexts
                if hasattr(self.pipeline, 'last_contexts') and self.pipeline.last_contexts and len(self.pipeline.last_contexts) > 0:
                    rag_info = f"\n\n## Research Sources\n\n"
                    rag_info += "The following documents were retrieved to support this analysis:\n\n"
                    
                    # Log detailed information about contexts for debugging
                    logger.debug(f"Number of contexts: {len(self.pipeline.last_contexts)}")
                    for i, context in enumerate(self.pipeline.last_contexts[:5]):
                        logger.debug(f"Context {i+1} type: {type(context).__name__}")
                        logger.debug(f"Context {i+1} attributes: {dir(context)}")
                    
                    for i, context in enumerate(self.pipeline.last_contexts[:5], 1):
                        # Extract document information in a more concise format
                        
                        # Get document name (try to make it readable)
                        doc_name = "Document"
                        if hasattr(context, 'uri'):
                            doc_name = context.uri.split('/')[-1].replace('.txt', '').replace('_', ' ').replace('-', ' ')
                        elif hasattr(context, 'name'):
                            doc_name = context.name.split('/')[-1].replace('.txt', '').replace('_', ' ').replace('-', ' ')
                        elif hasattr(context, 'file_path'):
                            doc_name = context.file_path.split('/')[-1].replace('.txt', '').replace('_', ' ').replace('-', ' ')
                        
                        # Capitalize doc_name for readability
                        if doc_name and doc_name != "Document":
                            doc_name = ' '.join(word.capitalize() for word in doc_name.split())
                        
                        # Get relevance score if available
                        relevance_score = None
                        if hasattr(context, 'relevance_score'):
                            relevance_score = context.relevance_score
                        elif hasattr(context, 'score'):
                            relevance_score = context.score
                            
                        # Extract and format snippet
                        snippet = ""
                        if hasattr(context, 'text'):
                            snippet = context.text
                        elif hasattr(context, 'chunk') and hasattr(context.chunk, 'data'):
                            snippet = context.chunk.data
                        elif hasattr(context, 'content'):
                            snippet = context.content
                        
                        # Format a concise reference
                        if snippet:
                            # Clean and format the snippet for readability
                            snippet = snippet.replace('\n', ' ').strip()
                            while '  ' in snippet:
                                snippet = snippet.replace('  ', ' ')
                                
                            # Take a meaningful excerpt (first 150 chars)
                            excerpt = snippet[:150] + '...' if len(snippet) > 150 else snippet
                            
                            # Create a formatted reference
                            if relevance_score is not None:
                                rag_info += f"**{i+1}. {doc_name}** (Relevance: {relevance_score:.2f})\n"
                            else:
                                rag_info += f"**{i+1}. {doc_name}**\n"
                            
                            rag_info += f"*Excerpt:* \"{excerpt}\"\n\n"
                            
                            # Try to extract publication date if available
                            pub_date = None
                            if hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                                try:
                                    # Look for publication date in metadata
                                    if 'publication_date' in context.metadata:
                                        pub_date = context.metadata['publication_date']
                                    elif 'date' in context.metadata:
                                        pub_date = context.metadata['date']
                                except Exception:
                                    pass
                            
                            # Add publication date if available
                            if pub_date:
                                rag_info += f"*Published:* {pub_date}\n\n"
                    
                    # Add this RAG information to the response for display purposes
                    formatted_response = f"{response}\n\n{rag_info}"
                    return formatted_response
                
                # Add the contexts attribute to track them for future use
                if not hasattr(self.pipeline, 'last_contexts'):
                    self.pipeline.last_contexts = []
                
                # Return original response if no contexts available
                return response
            except Exception as e:
                logger.warning(f"Direct RAG failed, falling back to standard approach: {e}")
                
                # Fall back to standard approach
                contexts = self.pipeline.retrieve_context(
                    query=query,
                    top_k=max_results,
                    use_reranking=use_reranking
                )
                
                # Generate answer from contexts
                response = self.pipeline.generate_answer(
                    query=query,
                    retrievals=contexts
                )
                
                return response
                
        except Exception as e:
            logger.error(f"Error executing RAG query: {e}")
            return f"Error retrieving information: {str(e)}"


class VulnerabilityAnalysisTool(FunctionTool):
    """
    Tool for analyzing text to identify security vulnerabilities.
    
    This tool uses specialized models to identify potential security
    vulnerabilities in the provided text and assess their severity.
    """
    
    def __init__(self):
        """Initialize the vulnerability analysis tool."""
        
        # Define the function that will be called by the tool
        def vulnerability_analysis(
            text: str,
            severity_threshold: str = "medium"
        ) -> str:
            """
            Analyze text to identify potential security vulnerabilities and their severity.
            
            Args:
                text: The text to analyze for vulnerabilities
                severity_threshold: Minimum severity level to report (low, medium, high, critical)
                
            Returns:
                Analysis results with identified vulnerabilities
            """
            return self._analyze_vulnerabilities(text, severity_threshold)
            
        # Initialize the FunctionTool with our function
        super().__init__(func=vulnerability_analysis)
    
    def _analyze_vulnerabilities(self, text: str, severity_threshold: str = "medium") -> str:
        """
        Analyze text for security vulnerabilities.
        
        Args:
            text: The text to analyze for vulnerabilities
            severity_threshold: Minimum severity level to report
            
        Returns:
            Analysis results with identified vulnerabilities
        """
        if not text:
            return "Error: No text provided for analysis"
        
        try:
            logger.info(f"Analyzing text for vulnerabilities (threshold: {severity_threshold})")
            
            # In a full implementation, this would use specialized security models
            # For now, we'll return a placeholder response
            # This would be replaced with actual analysis logic
            
            return (
                "Vulnerability Analysis Results:\n\n"
                "The provided text was analyzed for security vulnerabilities. "
                "This is a placeholder for actual vulnerability analysis, which would "
                "use specialized security models to identify and classify potential issues."
            )
            
        except Exception as e:
            logger.error(f"Error in vulnerability analysis: {e}")
            return f"Error analyzing vulnerabilities: {str(e)}"


class CveLookupTool(FunctionTool):
    """
    Tool for looking up CVE (Common Vulnerabilities and Exposures) information.
    
    This tool provides access to CVE information from public databases,
    allowing agents to retrieve details about known vulnerabilities.
    """
    
    def __init__(self):
        """Initialize the CVE lookup tool."""
        
        # Define the function that will be called by the tool
        def cve_lookup(
            cve_id: Optional[str] = None,
            keywords: Optional[str] = None,
            max_results: int = 5
        ) -> str:
            """
            Look up information about CVEs (Common Vulnerabilities and Exposures).
            
            Args:
                cve_id: Specific CVE ID to look up (e.g., CVE-2023-1234)
                keywords: Keywords to search for related CVEs
                max_results: Maximum number of results to return
                
            Returns:
                Retrieved CVE information
            """
            return self._lookup_cve(cve_id, keywords, max_results)
            
        # Initialize the FunctionTool with our function
        super().__init__(func=cve_lookup)
    
    def _lookup_cve(self, cve_id: Optional[str] = None, keywords: Optional[str] = None, max_results: int = 5) -> str:
        """
        Look up CVE information.
        
        Args:
            cve_id: Specific CVE ID to look up
            keywords: Keywords to search for related CVEs
            max_results: Maximum number of results to return
            
        Returns:
            Retrieved CVE information
        """
        if not cve_id and not keywords:
            return "Error: Either a CVE ID or search keywords must be provided"
        
        try:
            if cve_id:
                logger.info(f"Looking up CVE: {cve_id}")
            else:
                logger.info(f"Searching CVEs with keywords: {keywords}")
            
            # In a full implementation, this would query CVE databases
            # For now, we'll return a placeholder response
            # This would be replaced with actual CVE lookup logic
            
            return (
                "CVE Lookup Results:\n\n"
                "This is a placeholder for actual CVE lookup functionality, which would "
                "query public CVE databases to retrieve vulnerability information. "
                "In a full implementation, this would return details about the requested CVEs."
            )
            
        except Exception as e:
            logger.error(f"Error in CVE lookup: {e}")
            return f"Error looking up CVE information: {str(e)}"