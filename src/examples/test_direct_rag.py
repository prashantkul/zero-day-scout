#!/usr/bin/env python
"""
Test script for the direct RAG integration in VertexRagPipeline.
"""

import os
import sys
from dotenv import load_dotenv

from src.rag.pipeline import VertexRagPipeline
from config.config_manager import get_config

def main():
    """Test the direct_rag_response function."""
    # Load environment variables
    load_dotenv()
    
    # Initialize RAG pipeline
    try:
        pipeline = VertexRagPipeline()
        print(f"Initialized RAG pipeline with corpus: {pipeline.corpus_name}")
    except Exception as e:
        print(f"Error initializing RAG pipeline: {e}")
        return 1
    
    # Test queries
    test_queries = [
        "What are the most common zero-day vulnerabilities?",
        "How are zero-day vulnerabilities detected?",
        "What tools are used to find security issues?"
    ]
    
    for i, test_query in enumerate(test_queries):
        print(f"\n\n=== Test Query {i+1}: {test_query} ===")
        
        try:
            # Test direct RAG response
            print("\nTesting direct_rag_response...")
            direct_answer = pipeline.direct_rag_response(query=test_query)
            print("\n=== Direct RAG Response ===")
            print(direct_answer)
            
            # For comparison, test standard approach
            print("\nTesting generate_answer for comparison...")
            standard_answer = pipeline.generate_answer(query=test_query)
            print("\n=== Standard RAG Response ===")
            print(standard_answer)
            
        except Exception as e:
            print(f"Error with query '{test_query}': {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())