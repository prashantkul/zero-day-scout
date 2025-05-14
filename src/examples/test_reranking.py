#!/usr/bin/env python
"""
Test script to compare different reranking approaches in the RAG pipeline.
"""

import os
import sys
import time
from dotenv import load_dotenv

from src.rag.pipeline import VertexRagPipeline
from config.config_manager import get_config

def main():
    """Test the reranking functionality by comparing approaches."""
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
    
    # Configuration for testing
    config = get_config()
    model_name = config.get("generative_model")
    reranker_model = config.get("reranker_model")
    top_k_values = [5, 10, 20]
    
    # Set up test scenarios
    scenarios = [
        {"name": "Standard RAG without reranking", "use_reranking": False, "top_k": 10},
        {"name": "RAG with reranking", "use_reranking": True, "top_k": 10},
        {"name": "RAG with reranking and higher top-k", "use_reranking": True, "top_k": 20}
    ]
    
    # Run tests for each query
    for i, query in enumerate(test_queries):
        print(f"\n\n{'='*80}")
        print(f"Test Query {i+1}: {query}")
        print(f"{'='*80}")
        
        # Run each scenario
        for scenario in scenarios:
            name = scenario["name"]
            use_reranking = scenario["use_reranking"]
            top_k = scenario["top_k"]
            
            print(f"\n{'-'*40}")
            print(f"Scenario: {name}")
            print(f"{'-'*40}")
            print(f"Configuration: top_k={top_k}, use_reranking={use_reranking}")
            
            # Time the retrieval
            start_time = time.time()
            try:
                # Get contexts
                retrievals = pipeline.retrieve_context(
                    query=query,
                    top_k=top_k,
                    use_reranking=use_reranking,
                    reranker_model=reranker_model
                )
                
                retrieval_time = time.time() - start_time
                print(f"Retrieved {len(retrievals)} contexts in {retrieval_time:.2f} seconds")
                
                # Show first 2 contexts
                print("\nTop contexts:")
                for j, context in enumerate(retrievals[:2]):
                    print(f"\nContext {j+1}:")
                    if hasattr(context, "text"):
                        # Show first 200 characters
                        text = context.text[:200] + "..." if len(context.text) > 200 else context.text
                        print(text)
                    elif hasattr(context, "content"):
                        text = context.content[:200] + "..." if len(context.content) > 200 else context.content
                        print(text)
                
                # Generate answer
                print("\nGenerating answer...")
                answer = pipeline.generate_answer(
                    query=query,
                    model_name=model_name,
                    retrievals=retrievals
                )
                
                print("\nAnswer:")
                print(answer)
                
            except Exception as e:
                print(f"Error in scenario '{name}': {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())