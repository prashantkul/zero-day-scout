#!/usr/bin/env python
"""
Test script to compare direct RAG with and without reranking.
"""

import os
import sys
import time
from dotenv import load_dotenv

from src.rag.pipeline import VertexRagPipeline
from config.config_manager import get_config

def main():
    """Test the direct RAG response with reranking."""
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
        "What tools are used to find security issues?",
        "What are the key components of a RAG pipeline?",
        "What vulnerability types are most dangerous in JavaScript engines?"
    ]
    
    # Run tests for each query
    for i, query in enumerate(test_queries):
        print(f"\n\n{'='*80}")
        print(f"Test Query {i+1}: {query}")
        print(f"{'='*80}")
        
        # Test with direct RAG but without reranking
        print("\n--- Direct RAG without Reranking ---")
        start_time = time.time()
        try:
            answer = pipeline.direct_rag_response(
                query=query,
                use_reranking=False
            )
            retrieval_time = time.time() - start_time
            print(f"\nRetrieved and generated answer in {retrieval_time:.2f} seconds")
            print("\nAnswer (without reranking):")
            print(answer)
        except Exception as e:
            print(f"Error without reranking: {e}")
        
        # Test with direct RAG and reranking
        print("\n--- Direct RAG with Reranking ---")
        start_time = time.time()
        try:
            answer = pipeline.direct_rag_response(
                query=query,
                use_reranking=True
            )
            retrieval_time = time.time() - start_time
            print(f"\nRetrieved and generated answer in {retrieval_time:.2f} seconds")
            print("\nAnswer (with reranking):")
            print(answer)
        except Exception as e:
            print(f"Error with reranking: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())