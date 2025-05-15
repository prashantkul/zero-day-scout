"""
Utilities for working with Google Cloud Storage.
"""

import os
import json
from typing import List, Optional, Any

from google.cloud import storage

from config.config_manager import get_config


class GcsManager:
    """
    Manages operations with Google Cloud Storage for the RAG pipeline.
    """
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        bucket_name: Optional[str] = None
    ):
        """
        Initialize GCS manager.
        
        Args:
            project_id: Google Cloud project ID (defaults to config value)
            bucket_name: GCS bucket name (defaults to config value)
        """
        # Load configuration
        config = get_config()
        
        self.project_id = project_id or config.get("project_id")
        self.bucket_name = bucket_name or config.get("gcs_bucket")
        
        # Initialize GCS client
        self.client = storage.Client(project=self.project_id)
        
        # Validate bucket name
        if not self.bucket_name:
            raise ValueError("GCS bucket name not provided. Set GCS_BUCKET environment variable or provide it when initializing.")
    
    def list_files(self, prefix: Optional[str] = None) -> List[str]:
        """
        List files in the GCS bucket with optional prefix filter.
        
        Args:
            prefix: Optional path prefix to filter results
            
        Returns:
            List of GCS file paths (gs://bucket/path/to/file)
        """
        # Get bucket
        bucket = self.client.get_bucket(self.bucket_name)

        if not prefix:
            prefix = ""
        
        # List blobs with prefix
        blobs = bucket.list_blobs(prefix=prefix)
        
        # Format paths as gs:// URLs
        return [f"gs://{self.bucket_name}/{blob.name}" for blob in blobs]
    
    def upload_file(self, local_path: str, gcs_path: Optional[str] = None) -> str:
        """
        Upload a local file to GCS bucket.
        
        Args:
            local_path: Path to local file
            gcs_path: Optional destination path in GCS (defaults to filename)
            
        Returns:
            GCS path of uploaded file (gs://bucket/path/to/file)
        """
        # Get bucket
        bucket = self.client.get_bucket(self.bucket_name)
        
        # Determine GCS path
        if not gcs_path:
            gcs_path = os.path.basename(local_path)
            
        # Upload file
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)
        
        # Return full GCS path
        return f"gs://{self.bucket_name}/{gcs_path}"
    
    def upload_directory(self, local_dir: str, gcs_prefix: Optional[str] = None) -> List[str]:
        """
        Upload all files in a local directory to GCS bucket.
        
        Args:
            local_dir: Path to local directory
            gcs_prefix: Optional prefix for GCS paths
            
        Returns:
            List of GCS paths for uploaded files
        """
        # Get bucket
        bucket = self.client.get_bucket(self.bucket_name)
        
        # Determine GCS prefix
        if not gcs_prefix:
            gcs_prefix = os.path.basename(local_dir.rstrip("/"))
            
        # Track uploaded files
        uploaded_files = []
        
        # Upload files
        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                
                # Determine relative path
                rel_path = os.path.relpath(local_path, local_dir)
                gcs_path = os.path.join(gcs_prefix, rel_path)
                
                # Upload file
                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(local_path)
                
                # Add to list
                uploaded_files.append(f"gs://{self.bucket_name}/{gcs_path}")
        
        return uploaded_files
        
    def read_json(self, gcs_path: str) -> Any:
        """
        Read JSON data from a file in GCS.
        
        Args:
            gcs_path: Path to the file in GCS (e.g., 'tracking/ingested_docs.json')
            
        Returns:
            Parsed JSON content or None if file doesn't exist
        """
        # Get bucket
        bucket = self.client.get_bucket(self.bucket_name)
        
        # Get blob
        blob = bucket.blob(gcs_path)
        
        # Check if file exists
        if not blob.exists():
            return None
        
        # Download and parse JSON
        content = blob.download_as_text()
        return json.loads(content)
    
    def write_json(self, gcs_path: str, data: Any) -> None:
        """
        Write JSON data to a file in GCS.
        
        Args:
            gcs_path: Path to the file in GCS (e.g., 'tracking/ingested_docs.json')
            data: Data to write (must be JSON serializable)
        """
        # Get bucket
        bucket = self.client.get_bucket(self.bucket_name)
        
        # Get blob
        blob = bucket.blob(gcs_path)
        
        # Convert data to JSON
        content = json.dumps(data, indent=2)
        
        # Upload JSON
        blob.upload_from_string(content, content_type='application/json')
        
    def file_exists(self, gcs_path: str) -> bool:
        """
        Check if a file exists in GCS.
        
        Args:
            gcs_path: Path to the file in GCS (e.g., 'documents/file.txt')
            
        Returns:
            True if the file exists, False otherwise
        """
        # Get bucket
        bucket = self.client.get_bucket(self.bucket_name)
        
        # Get blob
        blob = bucket.blob(gcs_path)
        
        # Check if file exists
        return blob.exists()