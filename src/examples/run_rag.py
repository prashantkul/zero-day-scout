#!/usr/bin/env python
"""
Interactive tool for RAG pipeline operations:
1. Ingest documents from GCS or upload local files
2. Query the corpus directly
3. Generate answers with RAG + LLM
4. List files in corpus
"""

import os
import json
import sys
import time
import argparse
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from src.rag.pipeline import VertexRagPipeline
from src.rag.gcs_utils import GcsManager
from config.config_manager import get_config


def parse_args():
    """Parse global command line arguments."""
    parser = argparse.ArgumentParser(
        description="RAG Pipeline Operations",
        add_help=False  # Don't show help automatically
    )
    parser.add_argument(
        "--project-id",
        type=str,
        help="Google Cloud project ID (defaults to env variable)",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        help="GCS bucket name (defaults to env variable)",
    )
    parser.add_argument(
        "--corpus-name",
        type=str,
        help="RAG corpus name (defaults to env variable)",
    )
    parser.add_argument(
        "--help", "-h",
        action="store_true",
        help="Show help message and exit",
    )
    
    # Only parse known args to allow for command-line use and interactive use
    args, _ = parser.parse_known_args()
    
    # Show help if requested
    if args.help:
        parser.print_help()
        sys.exit(0)
    
    return args


def display_menu():
    """Display the main menu and get user choice."""
    print("\n===== RAG Pipeline Operations =====")
    print("1. Ingest documents")
    print("2. Query corpus (retrieval only)")
    print("3. Generate answer (RAG + LLM)")
    print("4. List corpus files")
    print("0. Exit")
    
    while True:
        choice = input("\nEnter your choice (0-4): ").strip()
        if choice in ["0", "1", "2", "3", "4"]:
            return choice
        print("Invalid choice. Please enter a number between 0 and 4.")


def get_user_input(prompt, required=False, default=None):
    """Get user input with optional default value."""
    default_str = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"{prompt}{default_str}: ").strip()
        if not value and default is not None:
            return default
        if not value and required:
            print("This field is required.")
            continue
        return value


def get_bool_input(prompt, default=False):
    """Get a yes/no input from the user."""
    default_str = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not value:
            return default
        if value in ["y", "yes"]:
            return True
        if value in ["n", "no"]:
            return False
        print("Please enter Y/y for Yes or N/n for No.")


def ingest_documents(pipeline, gcs_manager):
    """Handle document ingestion operation."""
    print("\n----- Ingest Documents -----")
    
    # Ask for ingestion method
    print("\nChoose ingestion method:")
    print("1. Ingest from GCS bucket with prefix")
    print("2. Upload local directory to GCS and ingest")
    
    method = get_user_input("Enter your choice (1-2)", required=True)
    
    gcs_paths = []
    
    if method == "1":
        # Ingest from GCS
        prefix = get_user_input("Enter GCS prefix to filter files", required=True)
        
        print(f"\nListing files in GCS bucket {gcs_manager.bucket_name} with prefix {prefix}...")
        gcs_paths = gcs_manager.list_files(prefix)
        print(f"Found {len(gcs_paths)} files in GCS")
    
    elif method == "2":
        # Upload local directory
        local_dir = get_user_input("Enter local directory path", required=True)
        if not os.path.isdir(local_dir):
            print(f"Error: Directory {local_dir} does not exist")
            return
        
        gcs_prefix = get_user_input("Enter GCS prefix for uploaded files", default="documents")
        
        print(f"\nUploading files from {local_dir} to GCS bucket {gcs_manager.bucket_name}...")
        gcs_paths = gcs_manager.upload_directory(local_dir, gcs_prefix)
        print(f"Uploaded {len(gcs_paths)} files to GCS")
    
    else:
        print("Invalid choice.")
        return
    
    if not gcs_paths:
        print("No files found to ingest")
        return
    
    # Confirm ingestion
    if not get_bool_input(f"\nIngest {len(gcs_paths)} files into corpus?", default=True):
        print("Ingestion cancelled")
        return
    
    # Ingest documents
    print("\nIngesting documents into RAG corpus...")
    try:
        import_op = pipeline.ingest_documents(gcs_paths)
        
        # Ask if user wants to wait
        if get_bool_input("\nWait for ingestion to complete?", default=False):
            print("Waiting for ingestion to complete...")
            start_time = time.time()
            if import_op and hasattr(import_op, "operation"):
                import_op.operation.wait()
                elapsed = time.time() - start_time
                print(f"Ingestion completed in {elapsed:.2f} seconds")
            else:
                print("Operation doesn't support waiting")
        
        print(f"\nStarted ingestion of {len(gcs_paths)} documents")
        
    except Exception as e:
        print(f"Error ingesting documents: {e}")


def query_corpus(pipeline):
    """Handle direct query operation."""
    print("\n----- Query Corpus (Retrieval Only) -----")
    
    query = get_user_input("Enter your query", required=True)
    top_k = get_user_input("Number of results to retrieve", default="5")
    
    try:
        top_k = int(top_k)
    except ValueError:
        print("Invalid number, using default")
        top_k = 5
    
    show_raw = get_bool_input("Show raw retrieval data?", default=False)
    
    print(f"\nQuerying corpus with: {query}")
    
    try:
        retrievals = pipeline.retrieve_context(
            query=query,
            top_k=top_k
        )
        
        # Ensure retrievals is a list
        if not isinstance(retrievals, list):
            try:
                retrievals_list = list(retrievals)
                retrievals = retrievals_list
            except (TypeError, ValueError):
                # If conversion fails, wrap in a list if it has a text attribute
                if hasattr(retrievals, 'text'):
                    retrievals = [retrievals]
                else:
                    retrievals = []
                    print("Warning: Could not convert retrievals to a list")
        
        if not retrievals:
            print("No results found")
            return
        
        # Output results
        print(f"\nFound {len(retrievals)} results:")
        for i, retrieval in enumerate(retrievals):
            print(f"\n--- Result {i+1} ---")
            
            if show_raw:
                # Show more detailed metadata based on RAG Engine documentation
                # According to docs, contexts have source_uri and text attributes
                source_uri = "N/A"
                score = "N/A"
                
                if hasattr(retrieval, "source_uri"):
                    source_uri = retrieval.source_uri
                elif hasattr(retrieval, "rag_file_id"):
                    source_uri = retrieval.rag_file_id
                elif hasattr(retrieval, "file_id"):
                    source_uri = retrieval.file_id
                
                if hasattr(retrieval, "score"):
                    score = retrieval.score
                elif hasattr(retrieval, "distance"):
                    score = retrieval.distance
                
                print(f"Source URI: {source_uri}")
                print(f"Score/Distance: {score}")
                
                # Display any other available metadata
                for attr_name in dir(retrieval):
                    if attr_name.startswith('_') or attr_name in ['source_uri', 'text', 'score']:
                        continue
                    
                    attr = getattr(retrieval, attr_name)
                    if not callable(attr) and not isinstance(attr, (dict, list, tuple)):
                        print(f"{attr_name}: {attr}")
            
            # Always show the content - based on documentation
            if hasattr(retrieval, "text"):
                print("\nContent:")
                print(retrieval.text)
            # For backward compatibility
            elif hasattr(retrieval, "chunk") and hasattr(retrieval.chunk, "data"):
                print("\nContent:")
                print(retrieval.chunk.data)
            elif hasattr(retrieval, "content"):
                print("\nContent:")
                print(retrieval.content)
            else:
                print("\nContent: [No content field found]")
                print(f"Available fields: {dir(retrieval)}")
            
    except Exception as e:
        print(f"Error querying corpus: {e}")


def generate_answer(pipeline):
    """Handle answer generation operation."""
    print("\n----- Generate Answer (RAG + LLM) -----")
    
    # Get user query
    query = get_user_input("Enter your query", required=True)
    
    # Advanced options
    show_advanced = get_bool_input("Show advanced options?", default=False)
    
    top_k = 5
    temperature = None
    model_name = None
    use_direct = False
    show_context = False
    
    if show_advanced:
        # Get advanced options
        top_k_input = get_user_input("Number of results to retrieve", default="5")
        try:
            top_k = int(top_k_input)
        except ValueError:
            print("Invalid number, using default")
        
        temp_input = get_user_input("Temperature (0.0-1.0)", default="")
        if temp_input:
            try:
                temperature = float(temp_input)
            except ValueError:
                print("Invalid temperature, using default")
        
        model_name = get_user_input("Model name (leave empty for default)", default="")
        if not model_name:
            model_name = None
        
        use_direct = get_bool_input("Use direct RAG integration?", default=False)
        show_context = get_bool_input("Show retrieved context?", default=False)
    
    print(f"\nGenerating answer for: {query}")
    
    try:
        # Retrieve context if showing it
        retrievals = None
        if show_context:
            retrievals = pipeline.retrieve_context(
                query=query,
                top_k=top_k
            )
            
            # Ensure retrievals is a list
            if not isinstance(retrievals, list):
                try:
                    retrievals_list = list(retrievals)
                    retrievals = retrievals_list
                except (TypeError, ValueError):
                    # If conversion fails, wrap in a list if it has a text attribute
                    if hasattr(retrievals, 'text'):
                        retrievals = [retrievals]
                    else:
                        retrievals = []
                        print("Warning: Could not convert retrievals to a list")
            
            print("\n=== Retrieved Context ===")
            for i, retrieval in enumerate(retrievals):
                print(f"\n--- Context {i+1} ---")
                
                # Based on RAG Engine documentation
                if hasattr(retrieval, "text"):
                    print(retrieval.text)
                # For backward compatibility
                elif hasattr(retrieval, "chunk") and hasattr(retrieval.chunk, "data"):
                    print(retrieval.chunk.data)
                elif hasattr(retrieval, "content"):
                    print(retrieval.content)
                else:
                    print("[Content field not found in context object]")
                    print(f"Available fields: {dir(retrieval)}")
            print("\n=== Generated Answer ===")
        
        # Generate answer
        if use_direct:
            answer = pipeline.direct_rag_response(
                query=query,
                model_name=model_name,
                temperature=temperature,
                top_k=top_k
            )
        else:
            answer = pipeline.generate_answer(
                query=query,
                model_name=model_name,
                temperature=temperature,
                retrievals=retrievals
            )
        
        print(answer)
        
    except Exception as e:
        print(f"Error generating answer: {e}")


def list_files(pipeline):
    """Handle list corpus files operation."""
    print("\n----- List Corpus Files -----")
    
    format_json = get_bool_input("Output as JSON? (otherwise text format)", default=False)
    
    try:
        files = pipeline.list_corpus_files()
        
        if not files:
            print("No files found in corpus")
            return
        
        if format_json:
            # Output as JSON
            file_data = []
            for file_info in files:
                file_data.append({
                    "id": file_info.name,
                    "display_name": file_info.display_name,
                    "state": file_info.state,
                    "metadata": file_info.metadata if hasattr(file_info, "metadata") else {}
                })
            print(json.dumps(file_data, indent=2))
        else:
            # Output as text
            print(f"Found {len(files)} files in corpus:")
            for i, file_info in enumerate(files):
                print(f"\n--- File {i+1} ---")
                print(f"ID: {file_info.name}")
                print(f"Display name: {file_info.display_name}")
                print(f"State: {file_info.state}")
                if hasattr(file_info, "metadata") and file_info.metadata:
                    print("Metadata:")
                    for key, value in file_info.metadata.items():
                        print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"Error listing corpus files: {e}")


def main():
    # Load environment variables
    load_dotenv()
    
    # Parse global arguments
    args = parse_args()
    
    # Update config with command line arguments
    config = get_config()
    if args.project_id:
        config.update("project_id", args.project_id)
    if args.bucket:
        config.update("gcs_bucket", args.bucket)
    if args.corpus_name:
        config.update("corpus_name", args.corpus_name)
    
    # Initialize RAG pipeline
    try:
        pipeline = VertexRagPipeline()
        print(f"Initialized RAG pipeline with corpus: {pipeline.corpus_name}")
    except Exception as e:
        print(f"Error initializing RAG pipeline: {e}")
        return 1
    
    # Initialize GCS manager
    try:
        gcs_manager = GcsManager()
        print(f"Connected to GCS bucket: {gcs_manager.bucket_name}")
    except Exception as e:
        print(f"Error connecting to GCS: {e}")
        return 1
    
    # Main loop
    while True:
        choice = display_menu()
        
        if choice == "0":
            print("Exiting...")
            break
        elif choice == "1":
            ingest_documents(pipeline, gcs_manager)
        elif choice == "2":
            query_corpus(pipeline)
        elif choice == "3":
            generate_answer(pipeline)
        elif choice == "4":
            list_files(pipeline)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())