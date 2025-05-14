"""
Cloud Run service for scheduled document ingestion.
This service can be deployed to Cloud Run and triggered by Cloud Scheduler.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from src.rag.pipeline import VertexRagPipeline
from src.rag.gcs_utils import GcsManager
from config.config_manager import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)

# Initialize RAG pipeline and GCS manager
pipeline = None
gcs_manager = None

def initialize_services():
    """Initialize RAG pipeline and GCS manager."""
    global pipeline, gcs_manager
    
    try:
        if pipeline is None:
            pipeline = VertexRagPipeline()
            logger.info(f"Initialized RAG pipeline with corpus: {pipeline.corpus_name}")
        
        if gcs_manager is None:
            gcs_manager = GcsManager()
            logger.info(f"Initialized GCS manager with bucket: {gcs_manager.bucket_name}")
        
        return True
    except Exception as e:
        logger.error(f"Error initializing services: {e}")
        return False


def ingest_documents(prefix: Optional[str] = None, wait_for_completion: bool = False, batch_size: int = 25) -> Dict[str, Any]:
    """
    Ingest documents from GCS bucket with optional prefix.

    Args:
        prefix: Optional GCS path prefix to filter files
        wait_for_completion: Whether to wait for ingestion to complete
        batch_size: Maximum number of GCS URIs to ingest at once (max 25)

    Returns:
        Dictionary with ingestion status and details
    """
    try:
        # List files in GCS bucket
        logger.info(f"Listing files with prefix: {prefix or 'None'}")
        gcs_paths = gcs_manager.list_files(prefix)

        # Handle potential pager objects
        if not isinstance(gcs_paths, list):
            try:
                gcs_paths = list(gcs_paths)
            except Exception:
                temp_paths = []
                for path in gcs_paths:
                    temp_paths.append(path)
                gcs_paths = temp_paths

        if not gcs_paths:
            logger.warning("No files found to ingest")
            return {
                "status": "warning",
                "message": "No files found to ingest",
                "files_count": 0
            }

        # Ensure batch size is within limits
        batch_size = min(batch_size, 25)  # Maximum 25 GCS URIs per batch

        # Split into batches to handle the 25 URI limit
        total_files = len(gcs_paths)
        batches = [gcs_paths[i:i + batch_size] for i in range(0, total_files, batch_size)]

        logger.info(f"Starting ingestion of {total_files} files in {len(batches)} batches")

        import_ops = []
        successful_batches = 0
        failed_batches = 0
        total_batches = len(batches)

        # Process each batch
        for i, batch in enumerate(batches):
            logger.info(f"Processing batch {i+1}/{total_batches} with {len(batch)} files")
            try:
                import_op = pipeline.ingest_documents(batch)
                import_ops.append(import_op)
                successful_batches += 1

                # Wait for batch completion if requested
                if wait_for_completion and import_op and hasattr(import_op, "operation"):
                    logger.info(f"Waiting for batch {i+1} to complete...")
                    import_op.operation.wait()
                    logger.info(f"Batch {i+1} completed successfully")
            except Exception as batch_error:
                logger.error(f"Error in batch {i+1}: {batch_error}")
                failed_batches += 1
                # Continue with next batch despite errors

        # Check if we have any successful operations
        if successful_batches == 0:
            raise Exception(f"All {total_batches} ingestion batches failed")

        # Log summary
        if failed_batches > 0:
            logger.warning(f"{failed_batches} out of {total_batches} batches failed")

        completion_status = "completed" if wait_for_completion else "started"
        success_message = f"Ingestion {completion_status}: {successful_batches} successful batches, {failed_batches} failed batches"

        return {
            "status": "success",
            "message": success_message,
            "files_count": total_files,
            "batches_count": total_batches,
            "successful_batches": successful_batches,
            "failed_batches": failed_batches,
            "files": gcs_paths
        }

    except Exception as e:
        logger.error(f"Error ingesting documents: {e}")
        return {
            "status": "error",
            "message": f"Error ingesting documents: {str(e)}"
        }


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200


@app.route('/ingest', methods=['POST'])
def ingest_endpoint():
    """
    Endpoint to trigger document ingestion.
    
    Expected JSON payload:
    {
        "prefix": "optional/gcs/prefix",
        "wait_for_completion": false,
        "batch_size": 25
    }
    """
    # Initialize services if needed
    if not initialize_services():
        return jsonify({
            "status": "error",
            "message": "Failed to initialize services"
        }), 500
    
    try:
        # Parse request data
        data = request.get_json() or {}
        prefix = data.get('prefix')
        wait_for_completion = data.get('wait_for_completion', False)
        batch_size = data.get('batch_size', 25)

        # Log request
        logger.info(f"Received ingestion request: prefix={prefix}, wait={wait_for_completion}, batch_size={batch_size}")

        # Perform ingestion
        result = ingest_documents(prefix, wait_for_completion, batch_size)
        
        # Return response
        if result.get('status') == 'error':
            return jsonify(result), 500
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error processing ingestion request: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error processing request: {str(e)}"
        }), 500


@app.route('/', methods=['GET', 'POST'])
def default_handler():
    """
    Default handler for Cloud Scheduler HTTP requests.
    Can be triggered by Cloud Scheduler or manually.
    """
    if request.method == 'GET':
        return jsonify({
            "status": "success",
            "message": "Ingestion service is running. Send a POST request to /ingest to trigger ingestion."
        }), 200
    
    # For POST requests, treat as an ingestion request with default parameters
    return ingest_endpoint()


if __name__ == '__main__':
    # Initialize services at startup
    initialize_services()
    
    # Get port from environment or default to 8080
    port = int(os.environ.get('PORT', 8080))
    
    # Run Flask app
    app.run(host='0.0.0.0', port=port, debug=False)