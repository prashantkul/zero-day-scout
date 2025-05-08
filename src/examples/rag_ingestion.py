"""
Example script demonstrating how to use the RAG pipeline.
"""

import argparse
import os
from dotenv import load_dotenv

from src.rag.pipeline import VertexRagPipeline
from src.rag.gcs_utils import GcsManager
from config.config_manager import get_config


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="RAG pipeline example")
    
    # GCS options
    parser.add_argument(
        "--gcs-bucket",
        type=str,
        help="GCS bucket name (overrides environment variable)",
    )
    parser.add_argument(
        "--gcs-prefix",
        type=str,
        default="",
        help="GCS path prefix for documents",
    )
    
    # Local upload options
    parser.add_argument(
        "--upload-dir",
        type=str,
        help="Local directory to upload to GCS",
    )
    
    # RAG options
    parser.add_argument(
        "--corpus-name",
        type=str,
        help="Name for the RAG corpus (overrides environment variable)",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Query to run against the RAG pipeline",
    )
    
    return parser.parse_args()


def main():
    """Run the RAG pipeline example."""
    # Load environment variables
    load_dotenv()
    
    # Parse arguments
    args = parse_args()
    
    # Update config if args provided
    config = get_config()
    if args.gcs_bucket:
        config.update("gcs_bucket", args.gcs_bucket)
    if args.corpus_name:
        config.update("corpus_name", args.corpus_name)
    
    # Initialize GCS manager
    gcs_manager = GcsManager()
    
    # Upload files if requested
    gcs_paths = []

    

    if args.upload_dir:
        print(f"Uploading files from {args.upload_dir} to GCS...")
        gcs_paths = gcs_manager.upload_directory(args.upload_dir, args.gcs_prefix)
        print(f"Uploaded {len(gcs_paths)} files to GCS")
    else:
        # List existing files in GCS
        print(f"Listing existing files in GCS with prefix {args.gcs_prefix}...")
        gcs_paths = gcs_manager.list_files(args.gcs_prefix)
        print(f"Found {len(gcs_paths)} files in GCS at: {args.gcs_prefix}")
    
    # Initialize RAG pipeline
    print("Initializing RAG pipeline...")
    pipeline = VertexRagPipeline()
    
    # Create or get corpus
    print("Retrieving RAG corpus...")
    corpus = pipeline.get_corpus()
    print(f"Using corpus: {corpus.name} , {corpus.display_name} , {corpus.description}")
    
    # Ingest documents if paths found
    if gcs_paths:
        print("Ingesting documents into RAG corpus...")
        pipeline.ingest_documents(gcs_paths)
    
    # Run query if provided
    if args.query:
        print(f"Running query: {args.query}")
        answer = pipeline.generate_answer(args.query)
        print(f"\nAnswer: {answer}")
    

if __name__ == "__main__":
    main()