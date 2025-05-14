#!/usr/bin/env python
"""
Test script for document ingestion with prefixes and duplicate prevention.
"""

import os
import sys
from dotenv import load_dotenv

from src.rag.pipeline import VertexRagPipeline
from src.rag.gcs_utils import GcsManager
from config.config_manager import get_config

def main():
    """Test the document ingestion functionality."""
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    config = get_config()
    print(f"Document prefixes configured: {config.get('document_prefixes')}")
    
    # Initialize GCS manager
    try:
        gcs_manager = GcsManager()
        print(f"Initialized GCS manager for bucket: {gcs_manager.bucket_name}")
    except Exception as e:
        print(f"Error initializing GCS manager: {e}")
        return 1
    
    # List all documents in the bucket
    try:
        all_docs = gcs_manager.list_files()
        print(f"Total documents in bucket: {len(all_docs)}")
    except Exception as e:
        print(f"Error listing documents: {e}")
        return 1
    
    # List documents by prefix
    prefixes = config.get("document_prefixes")
    for prefix in prefixes:
        try:
            prefix_docs = gcs_manager.list_files(prefix=prefix)
            print(f"Documents with prefix '{prefix}': {len(prefix_docs)}")
            if prefix_docs:
                print(f"Sample documents: {prefix_docs[:3]}")
        except Exception as e:
            print(f"Error listing documents with prefix '{prefix}': {e}")
    
    # Initialize RAG pipeline
    try:
        pipeline = VertexRagPipeline()
        print(f"Initialized RAG pipeline with corpus: {pipeline.corpus_name}")
        print(f"Using document prefixes: {pipeline.document_prefixes}")
        print(f"Tracking ingested documents in: {pipeline.tracking_file}")
        print(f"Currently tracked documents: {len(pipeline.ingested_documents)}")
    except Exception as e:
        print(f"Error initializing RAG pipeline: {e}")
        return 1
    
    # Test first ingestion (should ingest documents)
    try:
        print("\n=== First Ingestion Test (should ingest new documents) ===")
        # Pass empty list to use prefixes
        import_op = pipeline.ingest_documents([])
        print(f"Ingestion result: {import_op}")
        print(f"Total tracked documents after ingestion: {len(pipeline.ingested_documents)}")
    except Exception as e:
        print(f"Error during first ingestion: {e}")
    
    # Test second ingestion (should skip duplicates)
    try:
        print("\n=== Second Ingestion Test (should skip duplicates) ===")
        import_op = pipeline.ingest_documents([])
        print(f"Ingestion result: {import_op}")
    except Exception as e:
        print(f"Error during second ingestion: {e}")
    
    # Test ingestion with specific path
    try:
        print("\n=== Testing Ingestion with Specific Path ===")
        # Get first document from any prefix
        test_doc = None
        for prefix in prefixes:
            docs = gcs_manager.list_files(prefix=prefix)
            if docs:
                test_doc = docs[0]
                break
        
        if test_doc:
            # Test if it's already ingested
            already_ingested = test_doc in pipeline.ingested_documents
            print(f"Test document: {test_doc}")
            print(f"Already ingested: {already_ingested}")
            
            # Try to ingest it
            import_op = pipeline.ingest_documents([test_doc])
            print(f"Ingestion result: {import_op}")
        else:
            print("No test document found in any prefix")
    except Exception as e:
        print(f"Error during specific path ingestion: {e}")
    
    print("\nDocument ingestion test completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())