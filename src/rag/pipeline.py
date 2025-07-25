"""
RAG Pipeline for ingesting documents from GCS bucket and creating embeddings 
using Google Cloud Vertex AI RAG Engine with RagManagedDb.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Union, Set, Tuple
from pathlib import Path

from google.cloud import aiplatform
from vertexai import rag
from vertexai.generative_models import GenerativeModel

from config.config_manager import get_config

# Configure module logger
logger = logging.getLogger(__name__)


class VertexRagPipeline:
    """
    Manages the Retrieval-Augmented Generation (RAG) pipeline using Vertex AI.
    This pipeline ingests documents from a GCS bucket, creates embeddings using
    RagManagedDb, and provides a retrieval mechanism for answering queries.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        corpus_name: Optional[str] = None,
        embedding_model: Optional[str] = None,
        tracking_file: Optional[str] = None,
        use_cloud_tracking: Optional[bool] = None,
    ):
        """
        Initialize the RAG pipeline.

        Args:
            project_id: Google Cloud project ID (defaults to config value)
            location: Google Cloud region (defaults to config value)
            corpus_name: Name for the RAG corpus (defaults to config value)
            embedding_model: Name of the embedding model (defaults to config value)
            tracking_file: Path to file tracking ingested documents (defaults to .ingested_docs.json)
            use_cloud_tracking: Whether to use cloud storage for tracking (defaults to config value)
        """
        # Initialize required attributes upfront to prevent attribute errors
        self.ingested_documents = set()
        self.document_metadata = {}
        self.corpus = None
        self.cloud_tracking_path = None
        self.cloud_metadata_path = None
        
        # Initialize last_contexts to store retrieved contexts for display
        self.last_contexts = []
        
        # Load configuration
        config = get_config()

        # Set parameters from config if not provided
        self.project_id = project_id or config.get("project_id")
        self.location = location or config.get("location")
        self.corpus_name = corpus_name or config.get("corpus_name")
        self.embedding_model = embedding_model or config.get("embedding_model")
        self.document_prefixes = config.get("document_prefixes", [])

        # Document tracking settings
        self.use_cloud_tracking = use_cloud_tracking if use_cloud_tracking is not None else config.get("use_cloud_tracking", True)

        # Set up tracking file paths for both local and cloud
        if self.use_cloud_tracking:
            # Cloud tracking path - use a standard location in the bucket
            self.cloud_tracking_path = config.get("cloud_tracking_path", "tracking/ingested_docs.json")
            self.cloud_metadata_path = config.get("cloud_metadata_path", "tracking/document_metadata.json")

        # Local tracking is still supported as fallback
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.tracking_file = tracking_file or os.path.join(base_dir, ".ingested_docs.json")
        self.metadata_file = os.path.join(base_dir, ".document_metadata.json")

        # Load the ingested documents
        try:
            loaded_docs = self._load_ingested_documents()
            if loaded_docs:
                self.ingested_documents = loaded_docs
        except Exception as e:
            print(f"Warning: Could not load ingested documents: {e}")
            print("Starting with empty tracking information")
        
        # Initialize metadata tracking
        try:
            self._load_document_metadata()
        except Exception as e:
            print(f"Warning: Could not load document metadata: {e}")
            print("Starting with empty metadata tracking")

        # Initialize Vertex AI
        try:
            aiplatform.init(project=self.project_id, location=self.location)
        except Exception as e:
            print(f"Warning: Could not initialize Vertex AI: {e}")
            print("Some operations may not work correctly without Vertex AI initialization")

    def create_corpus(self) -> rag.RagCorpus:
        """
        Create a new RAG corpus using RagManagedDb for document storage and retrieval.
        
        Returns:
            The created RAG corpus
        """
        # Create the RAG corpus with default embedding model
        # The error suggests that custom publisher_model isn't supported yet
        # Using the create_corpus without specifying an embedding model
        try:
            self.corpus = rag.create_corpus(
                display_name=self.corpus_name,
            )
        except Exception as e:
            if "Publisher model is not allowed" in str(e):
                logger = logging.getLogger(__name__)
                logger.debug("Custom embedding model not supported. Trying with default embedding model.")
                # Try with standard endpoint
                self.corpus = rag.create_corpus(
                    display_name=self.corpus_name
                )
            else:
                # Re-raise if it's a different error
                raise e

        logger = logging.getLogger(__name__)
        logger.debug(f"Created RAG corpus: {self.corpus.name}")
        return self.corpus

    def print_ingested_documents(self) -> None:
        """
        Print the currently tracked ingested documents in a readable format.
        """
        if not self.ingested_documents:
            print("No documents have been ingested yet.")
            return
            
        print(f"\n===== Ingested Documents ({len(self.ingested_documents)}) =====")
        # Sort for consistent display
        sorted_docs = sorted(self.ingested_documents)
        for i, doc in enumerate(sorted_docs, 1):
            # Extract just the filename from the path for cleaner display
            filename = doc.split('/')[-1] if '/' in doc else doc
            print(f"{i}. {filename}")
            # Print the full path in a more subtle way
            print(f"   → {doc}")
        print("=" * 50)

    def _load_ingested_documents(self) -> Set[str]:
        """
        Load the set of previously ingested documents from cloud or local storage.
        If a corpus exists, verify against actual corpus contents.
        
        Returns:
            Set of ingested document paths
        """
        # Initialize empty set
        documents = set()
        corpus_exists = False
        corpus_id = None
        
        # Try to get corpus ID if corpus exists to filter documents by corpus
        try:
            corpus = self.get_corpus()
            if corpus and hasattr(corpus, 'name'):
                corpus_id = corpus.name
                print(f"Current corpus ID: {corpus_id}")
        except Exception as e:
            print(f"Could not get corpus ID: {e}")
            corpus_id = None

        # First try to get actual corpus contents as the source of truth
        try:
            # Check if corpus exists and we can access it
            try:
                corpus = self.get_corpus()
                corpus_exists = True
                print("Fetching document list from the RAG corpus...")
                # Get files from the corpus
                corpus_files = self.list_corpus_files()
                for file_info in corpus_files:
                    # Extract file paths from the corpus response
                    if hasattr(file_info, 'gcs_uri'):
                        documents.add(file_info.gcs_uri)
                    elif hasattr(file_info, 'uri'):
                        documents.add(file_info.uri)
                    elif hasattr(file_info, 'file_path'):
                        documents.add(file_info.file_path)
                    elif hasattr(file_info, 'name'):
                        documents.add(file_info.name)
                
                print(f"Found {len(documents)} documents in the corpus")
                
                # If we found documents in the corpus, update the tracking files and return
                if documents:
                    # Save this to tracking files for future reference
                    self._save_ingested_documents()
                    return documents
                    
            except Exception as corpus_e:
                print(f"Could not get corpus file list: {corpus_e}")
                print("Falling back to tracking files...")
        
            # If corpus exists but we couldn't get files, or corpus has no files,
            # try to load from tracking files as a fallback
            from src.rag.gcs_utils import GcsManager
            cloud_documents_loaded = False
            
            try:
                gcs_manager = GcsManager(project_id=self.project_id, bucket_name=None)
                cloud_data = gcs_manager.read_json(self.cloud_tracking_path)

                if cloud_data is not None:
                    # Handle both old format (list) and new format (dict with corpus_id)
                    if isinstance(cloud_data, dict) and 'documents' in cloud_data:
                        stored_corpus_id = cloud_data.get('corpus_id')
                        cloud_docs = cloud_data['documents']
                        
                        # Filter by corpus ID if available
                        if corpus_id and stored_corpus_id and corpus_id != stored_corpus_id:
                            print(f"Warning: Tracking file is for a different corpus.")
                            print(f"Current corpus: {corpus_id}")
                            print(f"Tracked corpus: {stored_corpus_id}")
                            print("Loading only documents that match current corpus paths.")
                            
                            # Only use documents that start with projects/{project_id}/locations/{location}/ragCorpora/{corpus_id}
                            cloud_docs = [doc for doc in cloud_docs if 
                                         (isinstance(doc, str) and 
                                         (doc.startswith(corpus_id) or 
                                          not doc.startswith('projects/')))] 
                    else:
                        # Legacy format - just a list of documents
                        cloud_docs = cloud_data
                    
                    print(f"Loaded {len(cloud_docs)} ingested documents from cloud storage")
                    documents.update(cloud_docs)
                    cloud_documents_loaded = True
            except Exception as cloud_e:
                print(f"Warning: Could not load ingested documents from cloud: {cloud_e}")
                print("Checking local tracking file...")
            
            # Only fall back to local file if cloud fails or if use_cloud_tracking is disabled
            # and we haven't already loaded cloud documents
            if not cloud_documents_loaded and (not self.use_cloud_tracking or 
                                              not documents):  # If cloud failed or is empty
                if os.path.exists(self.tracking_file):
                    with open(self.tracking_file, 'r') as f:
                        local_data = json.load(f)
                        
                        # Handle both old format (list) and new format (dict with corpus_id)
                        if isinstance(local_data, dict) and 'documents' in local_data:
                            stored_corpus_id = local_data.get('corpus_id')
                            local_docs = local_data['documents']
                            
                            # Filter by corpus ID if available
                            if corpus_id and stored_corpus_id and corpus_id != stored_corpus_id:
                                print(f"Warning: Local tracking file is for a different corpus.")
                                print(f"Current corpus: {corpus_id}")
                                print(f"Tracked corpus: {stored_corpus_id}")
                                print("Loading only documents that match current corpus paths.")
                                
                                # Only use documents that start with projects/{project_id}/locations/{location}/ragCorpora/{corpus_id}
                                local_docs = [doc for doc in local_docs if 
                                            (isinstance(doc, str) and 
                                            (doc.startswith(corpus_id) or 
                                             not doc.startswith('projects/')))]
                        else:
                            # Legacy format - just a list of documents
                            local_docs = local_data
                        
                        documents.update(local_docs)
                        print(f"Loaded {len(local_docs)} ingested documents from local file")
                else:
                    print(f"Local tracking file not found: {self.tracking_file}")
                    
            # If corpus exists and we have data from tracking files,
            # but they don't match, warn about inconsistency
            if corpus_exists and documents and not self.ingested_documents:
                print("WARNING: Tracking files show ingested documents, but corpus appears to be empty.")
                print("This could indicate an inconsistency. Consider using '/recreate corpus' or '/ingest force all'.")

            return documents

        except Exception as e:
            print(f"Warning: Could not load ingested documents: {e}")
            return set()

    def _save_ingested_documents(self) -> None:
        """
        Save the current set of ingested documents to cloud and/or local storage.
        Now includes corpus ID to track which corpus contains these documents.
        """
        # Get corpus ID if corpus exists
        corpus_id = None
        try:
            corpus = self.get_corpus()
            if corpus and hasattr(corpus, 'name'):
                corpus_id = corpus.name
        except Exception:
            corpus_id = None
            
        # Create tracking data with corpus ID
        tracking_data = {
            "corpus_id": corpus_id,
            "documents": list(self.ingested_documents)
        }
            
        cloud_save_succeeded = False

        # Always attempt to save to cloud storage, regardless of use_cloud_tracking setting
        # This ensures the tracking info is always accessible
        try:
            from src.rag.gcs_utils import GcsManager
            gcs_manager = GcsManager(project_id=self.project_id, bucket_name=None)
            gcs_manager.write_json(self.cloud_tracking_path, tracking_data)
            print(f"Saved {len(tracking_data['documents'])} ingested documents to cloud storage")
            cloud_save_succeeded = True
        except Exception as cloud_e:
            print(f"Warning: Could not save ingested documents to cloud: {cloud_e}")
            print("Will try saving to local tracking file")
        
        # Also save locally as backup in these cases:
        # 1. If cloud saving fails
        # 2. If use_cloud_tracking is disabled
        # 3. As an extra precaution even if cloud save succeeded
        try:
            with open(self.tracking_file, 'w') as f:
                json.dump(tracking_data, f)
                # Only print message if cloud save failed or was disabled
                if not cloud_save_succeeded or not self.use_cloud_tracking:
                    print(f"Saved {len(tracking_data['documents'])} ingested documents to local file")
        except Exception as e:
            if not cloud_save_succeeded:
                # This is a more serious error if cloud save also failed
                print(f"ERROR: Could not save ingested documents to local file: {e}")
                print("WARNING: No tracking information was saved. Document tracking may be lost.")
            else:
                # Less critical if cloud save succeeded
                print(f"Warning: Could not save local backup of ingested documents: {e}")

    def extract_document_metadata(self, gcs_path: str) -> Dict[str, Any]:
        """
        Extract metadata from document path and potentially content.
        
        Args:
            gcs_path: GCS path to the document
            
        Returns:
            Dictionary containing metadata like timestamp, source, etc.
        """
        import re
        import datetime
        from pathlib import Path
        
        metadata = {
            "source": gcs_path,
            "ingestion_timestamp": datetime.datetime.now().isoformat(),
        }
        
        # Extract filename from path
        filename = Path(gcs_path).name
        
        # Try to extract timestamp from filename
        # Common patterns: YYYY-MM-DD, YYYYMMDD, etc.
        date_patterns = [
            # ISO format: 2023-01-15
            r'(\d{4}-\d{2}-\d{2})',
            # Basic numeric: 20230115
            r'(\d{4}\d{2}\d{2})',
            # With separators: 2023_01_15
            r'(\d{4}[_\.]\d{2}[_\.]\d{2})',
            # Year-Month: 2023-01
            r'(\d{4}-\d{2}\b)',
            # Just year: 2023
            r'\b(\d{4})\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                date_str = match.group(1)
                try:
                    # Try to parse the date string
                    if len(date_str) == 4:  # Just year
                        date_obj = datetime.datetime.strptime(date_str, "%Y")
                        metadata["publication_date"] = date_str
                        metadata["publication_year"] = date_str
                    elif len(date_str) == 7 and "-" in date_str:  # Year-month
                        date_obj = datetime.datetime.strptime(date_str, "%Y-%m")
                        metadata["publication_date"] = date_str
                        metadata["publication_year"] = date_str[:4]
                        metadata["publication_month"] = date_str[5:7]
                    elif "-" in date_str and len(date_str) >= 10:  # YYYY-MM-DD
                        date_obj = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
                        metadata["publication_date"] = date_str[:10]
                        metadata["publication_year"] = date_str[:4]
                        metadata["publication_month"] = date_str[5:7]
                        metadata["publication_day"] = date_str[8:10]
                    elif "_" in date_str or "." in date_str:
                        # Handle different separators
                        clean_date = date_str.replace("_", "-").replace(".", "-")
                        date_obj = datetime.datetime.strptime(clean_date, "%Y-%m-%d")
                        metadata["publication_date"] = clean_date
                        parts = clean_date.split("-")
                        metadata["publication_year"] = parts[0]
                        if len(parts) > 1:
                            metadata["publication_month"] = parts[1]
                        if len(parts) > 2:
                            metadata["publication_day"] = parts[2]
                    elif len(date_str) == 8:  # YYYYMMDD
                        date_obj = datetime.datetime.strptime(date_str, "%Y%m%d")
                        metadata["publication_date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                        metadata["publication_year"] = date_str[:4]
                        metadata["publication_month"] = date_str[4:6]
                        metadata["publication_day"] = date_str[6:8]
                    
                    # Add timestamp for querying
                    metadata["timestamp"] = date_obj.timestamp()
                    break
                    
                except (ValueError, TypeError):
                    # If parsing fails, continue to the next pattern
                    continue
        
        # If no timestamp found, use current year
        if "publication_year" not in metadata:
            current_year = str(datetime.datetime.now().year)
            metadata["publication_year"] = current_year
            metadata["timestamp"] = datetime.datetime.now().timestamp()
        
        # Try to extract document type from file extension
        _, ext = os.path.splitext(filename)
        if ext:
            metadata["file_type"] = ext.lstrip('.').lower()
        
        return metadata
        
    def _load_document_metadata(self) -> None:
        """
        Load document metadata from cloud or local storage.
        """
        try:
            # Try cloud storage first if enabled
            if self.use_cloud_tracking and hasattr(self, 'cloud_metadata_path'):
                from src.rag.gcs_utils import GcsManager
                try:
                    gcs_manager = GcsManager(project_id=self.project_id, bucket_name=None)
                    cloud_metadata = gcs_manager.read_json(self.cloud_metadata_path)

                    if cloud_metadata:
                        #print(f"Loaded metadata for {len(cloud_metadata)} documents from cloud storage")
                        self.document_metadata = cloud_metadata
                        return
                except Exception as cloud_e:
                    print(f"Warning: Could not load document metadata from cloud: {cloud_e}")
                    print("Falling back to local metadata file")

            # Fall back to local file
            if hasattr(self, 'metadata_file') and os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    local_metadata = json.load(f)
                    self.document_metadata = local_metadata
                    #print(f"Loaded metadata for {len(local_metadata)} documents from local file")
                    return

        except Exception as e:
            print(f"Warning: Could not load document metadata: {e}")
            self.document_metadata = {}

    def _save_document_metadata(self) -> None:
        """
        Save document metadata to cloud and/or local storage.
        """
        if not hasattr(self, 'document_metadata') or not self.document_metadata:
            print("No document metadata to save")
            return
            
        cloud_save_succeeded = False

        # Always attempt to save to cloud storage for consistency
        if hasattr(self, 'cloud_metadata_path'):
            try:
                from src.rag.gcs_utils import GcsManager
                gcs_manager = GcsManager(project_id=self.project_id, bucket_name=None)
                gcs_manager.write_json(self.cloud_metadata_path, self.document_metadata)
                print(f"Saved metadata for {len(self.document_metadata)} documents to cloud storage")
                cloud_save_succeeded = True
            except Exception as cloud_e:
                print(f"Warning: Could not save document metadata to cloud: {cloud_e}")
                print("Will try saving to local metadata file")
        
        # Also save locally as backup
        if hasattr(self, 'metadata_file'):
            try:
                with open(self.metadata_file, 'w') as f:
                    json.dump(self.document_metadata, f, indent=2)
                    if not cloud_save_succeeded:
                        print(f"Saved metadata for {len(self.document_metadata)} documents to local file")
            except Exception as e:
                if not cloud_save_succeeded:
                    print(f"ERROR: Could not save document metadata to local file: {e}")
                else:
                    print(f"Warning: Could not save local backup of document metadata: {e}")
        
    def ingest_documents(self, gcs_paths: List[str], force_reingest: bool = False) -> Dict[str, Any]:
        """
        Ingest documents from GCS bucket into the RAG corpus.
        
        Args:
            gcs_paths: List of GCS paths (e.g., ["gs://bucket_name/folder/file.pdf"])
                If empty, reads from document_prefixes configured in settings.
            force_reingest: If True, will reingest documents even if they're in the tracking list
            
        Returns:
            Import operation details
        """
        if not self.corpus:
            self.create_corpus()

        # Use document prefixes if no paths provided
        if not gcs_paths:
            from src.rag.gcs_utils import GcsManager
            gcs_manager = GcsManager(project_id=self.project_id, bucket_name=None)

            all_paths = []
            for prefix in self.document_prefixes:
                paths = gcs_manager.list_files(prefix=prefix)
                all_paths.extend(paths)
                print(f"Found {len(paths)} documents with prefix '{prefix}'")

            gcs_paths = all_paths

        # Sometimes there can be a mismatch between the tracking file and actual ingested state
        # Especially after recreating the corpus but the tracking file still exists
        if force_reingest:
            new_documents = gcs_paths
            print(f"Force reingest is enabled - will ingest all {len(new_documents)} documents regardless of tracking")
        else:
            # Filter out already ingested documents
            new_documents = [path for path in gcs_paths if path not in self.ingested_documents]

        if not new_documents:
            print("No new documents to ingest.")
            return {"status": "skipped", "message": "No new documents to ingest"}

        print(f"Ingesting {len(new_documents)} new documents (skipping {len(gcs_paths) - len(new_documents)} already ingested)")

        # Handle Vertex AI's limitation of 25 documents per batch
        BATCH_SIZE = 25
        import_ops = []

        # Set up metadata tracking
        document_metadata = {}
        for doc_path in new_documents:
            metadata = self.extract_document_metadata(doc_path)
            document_metadata[doc_path] = metadata
            if "publication_date" in metadata:
                print(f"Extracted date for {Path(doc_path).name}: {metadata['publication_date']}")

        if len(new_documents) > BATCH_SIZE:
            print(f"Breaking ingestion into batches of {BATCH_SIZE} documents...")

            # Process in batches
            for i in range(0, len(new_documents), BATCH_SIZE):
                batch = new_documents[i:i+BATCH_SIZE]
                print(f"Processing batch {i//BATCH_SIZE + 1}/{(len(new_documents) + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} documents)")

                # Import files to the RAG corpus with metadata
                try:
                    # Create file metadata for this batch
                    file_metadata = {}
                    for doc_path in batch:
                        if doc_path in document_metadata:
                            file_metadata[doc_path] = document_metadata[doc_path]
                    
                    # Import files - API changed and may not support file_metadata anymore
                    try:
                        # Get chunking configuration from config
                        config = get_config()
                        chunk_size = config.get("chunk_size", 512)  # Default 512 if not specified
                        chunk_overlap = config.get("chunk_overlap", 100)  # Default 100 if not specified
                        
                        # Create a chunking config for better document processing
                        chunking_config = rag.ChunkingConfig(
                            chunk_size=chunk_size,
                            chunk_overlap=chunk_overlap
                        )
                        transformation_config = rag.TransformationConfig(chunking_config=chunking_config)
                        
                        # Try with the latest API that supports chunking config
                        try:
                            batch_op = rag.import_files(
                                self.corpus.name,
                                batch,
                                transformation_config=transformation_config
                            )
                            print(f"Using chunking with size={chunk_size}, overlap={chunk_overlap}")
                        except (TypeError, AttributeError) as chunking_error:
                            print(f"API doesn't support chunking config: {chunking_error}")
                            print("Falling back to basic import...")
                        
                        # Try with metadata (older API version)
                        if file_metadata:
                            batch_op = rag.import_files(
                                self.corpus.name,
                                batch,
                                file_metadata=file_metadata
                            )
                        else:
                            batch_op = rag.import_files(
                                self.corpus.name,
                                batch
                            )
                    except TypeError as type_error:
                        # If file_metadata is not accepted, remove it
                        if "unexpected keyword argument 'file_metadata'" in str(type_error):
                            print("API has changed: file_metadata parameter not supported. Using basic import.")
                            batch_op = rag.import_files(
                                self.corpus.name,
                                batch
                            )
                        else:
                            # If it's a different TypeError, re-raise
                            raise
                        
                    import_ops.append(batch_op)
                except Exception as e:
                    print(f"Error ingesting batch with metadata: {e}")
                    # Fallback to standard import without metadata
                    try:
                        batch_op = rag.import_files(
                            self.corpus.name,
                            batch
                        )
                        import_ops.append(batch_op)
                    except Exception as fallback_e:
                        print(f"Fallback import also failed: {fallback_e}")
                        # Continue with next batch

            # Return the last operation for status checking and consistency
            # (All operations are recorded in import_ops if detailed tracking is needed)
            import_op = import_ops[-1] if import_ops else None
        else:
            # Small enough for a single batch - use metadata
            try:
                # Create file metadata dictionary
                file_metadata = {doc_path: document_metadata[doc_path] 
                               for doc_path in new_documents 
                               if doc_path in document_metadata}
                
                # Import files - API changed and may not support file_metadata anymore
                try:
                    # Get chunking configuration from config
                    config = get_config()
                    chunk_size = config.get("chunk_size", 512)  # Default 512 if not specified
                    chunk_overlap = config.get("chunk_overlap", 100)  # Default 100 if not specified
                    
                    # Create a chunking config for better document processing
                    chunking_config = rag.ChunkingConfig(
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap
                    )
                    transformation_config = rag.TransformationConfig(chunking_config=chunking_config)
                    
                    # Try with the latest API that supports chunking config
                    try:
                        import_op = rag.import_files(
                            self.corpus.name,
                            new_documents,
                            transformation_config=transformation_config
                        )
                        print(f"Using chunking with size={chunk_size}, overlap={chunk_overlap}")
                    except (TypeError, AttributeError) as chunking_error:
                        print(f"API doesn't support chunking config: {chunking_error}")
                        print("Falling back to basic import...")
                        
                        # Try with metadata (older API version)
                        if file_metadata:
                            import_op = rag.import_files(
                                self.corpus.name,
                                new_documents,
                                file_metadata=file_metadata
                            )
                        else:
                            import_op = rag.import_files(
                                self.corpus.name,
                                new_documents
                            )
                except TypeError as type_error:
                    # If file_metadata is not accepted, remove it
                    if "unexpected keyword argument 'file_metadata'" in str(type_error):
                        print("API has changed: file_metadata parameter not supported. Using basic import.")
                        import_op = rag.import_files(
                            self.corpus.name,
                            new_documents
                        )
                    else:
                        # If it's a different TypeError, re-raise
                        raise
            except Exception as e:
                print(f"Error ingesting documents with metadata: {e}")
                # Fallback to standard import without metadata
                import_op = rag.import_files(
                    self.corpus.name,
                    new_documents
                )

        # Update tracking - also store metadata
        self.ingested_documents.update(new_documents)
        
        # If we have document_metadata field, update it
        if not hasattr(self, 'document_metadata'):
            self.document_metadata = {}
            # Try to load existing metadata
            self._load_document_metadata()
        
        # Update our metadata tracking
        self.document_metadata.update(document_metadata)
        
        # Save both ingested documents and metadata
        self._save_ingested_documents()
        self._save_document_metadata()

        print(f"Started document ingestion from: {new_documents}")
        return import_op

    def get_corpus(self) -> Optional[rag.RagCorpus]:
        """
        Get the current RAG corpus or create a new one if it doesn't exist.
        
        Returns:
            The RAG corpus
        """
        if not self.corpus:
            # Try to get existing corpus by name
            try:
                corpora = rag.list_corpora()
                for corpus in corpora:
                    if corpus.display_name == self.corpus_name:
                        self.corpus = corpus
                        break
            except Exception as e:
                print(f"Error retrieving existing corpus: {e}")

            # Create new corpus if not found
            if not self.corpus:
                raise ValueError(
                    f"Corpus '{self.corpus_name}' not found. Please create a the corpus before proceeding."
                )

        return self.corpus

    def delete_corpus(self) -> None:
        """
        Delete the current RAG corpus.
        """
        if self.corpus:
            rag.delete_corpus(self.corpus.name)
            self.corpus = None

    def recreate_corpus(self) -> None:
        """
        Recreate the RAG corpus by deleting and creating a new one.
        Also clears tracking information to maintain consistency.
        """
        # Delete the corpus
        if self.corpus:
            self.delete_corpus()
            
        # Clear tracking information
        self._clear_tracking_information()
            
        # Create a new corpus
        self.create_corpus()
        
    def _clear_tracking_information(self) -> None:
        """
        Clear all tracking information (ingested documents and metadata)
        from both cloud and local storage.
        """
        print("Clearing tracking information...")
        
        # Clear the in-memory tracking information
        self.ingested_documents = set()
        self.document_metadata = {}
        
        # Clear cloud tracking if enabled
        cloud_cleared = False
        if self.use_cloud_tracking:
            try:
                from src.rag.gcs_utils import GcsManager
                gcs_manager = GcsManager(project_id=self.project_id, bucket_name=None)
                
                # Clear documents tracking
                if hasattr(self, 'cloud_tracking_path'):
                    gcs_manager.write_json(self.cloud_tracking_path, [])
                    print(f"Cleared ingested documents list from cloud storage")
                    
                # Clear metadata tracking
                if hasattr(self, 'cloud_metadata_path'):
                    gcs_manager.write_json(self.cloud_metadata_path, {})
                    print(f"Cleared document metadata from cloud storage")
                    
                cloud_cleared = True
            except Exception as cloud_e:
                print(f"Warning: Could not clear cloud tracking information: {cloud_e}")
                
        # Always clear local tracking as well
        try:
            # For local tracking files, it's safest to completely remove them
            # rather than just emptying them
            if hasattr(self, 'tracking_file') and os.path.exists(self.tracking_file):
                os.remove(self.tracking_file)
                print(f"Removed local tracking file: {self.tracking_file}")
            else:
                print(f"No local tracking file found to remove")
                
            # Also remove metadata file if it exists
            if hasattr(self, 'metadata_file') and os.path.exists(self.metadata_file):
                os.remove(self.metadata_file)
                print(f"Removed local metadata file: {self.metadata_file}")
            else:
                print(f"No local metadata file found to remove")
                
        except Exception as e:
            if not cloud_cleared:
                print(f"ERROR: Could not clear local tracking information: {e}")
                print("WARNING: Tracking information may be inconsistent with corpus state")
            else:
                print(f"Warning: Could not clear local tracking information: {e}")
                
        print("Tracking information cleared successfully")
        
    def _extract_time_filter_from_query(self, query: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Extract time-based filters from the query and return the modified query and filter.
        
        Args:
            query: The original query string
            
        Returns:
            Tuple of (modified_query, time_filter_dict)
        """
        import re
        
        # Initialize the filter
        time_filter = {}
        modified_query = query
        
        # Pattern for "from YYYY to YYYY" or "between YYYY and YYYY"
        between_pattern = r'(?:from|between)\s+(\d{4})\s+(?:to|and|until|through)\s+(\d{4})'
        between_match = re.search(between_pattern, query, re.IGNORECASE)
        if between_match:
            start_year, end_year = between_match.groups()
            time_filter['between'] = (start_year, end_year)
            # Remove the matched text from the query
            modified_query = re.sub(between_pattern, '', query, flags=re.IGNORECASE).strip()
        
        # Pattern for "after YYYY" or "since YYYY"
        after_pattern = r'(?:after|since|from)\s+(\d{4})'
        after_match = re.search(after_pattern, modified_query, re.IGNORECASE)
        if after_match:
            year = after_match.group(1)
            time_filter['after'] = year
            # Remove the matched text from the query
            modified_query = re.sub(after_pattern, '', modified_query, flags=re.IGNORECASE).strip()
        
        # Pattern for "before YYYY" or "until YYYY" or "up to YYYY"
        before_pattern = r'(?:before|until|up to|through)\s+(\d{4})'
        before_match = re.search(before_pattern, modified_query, re.IGNORECASE)
        if before_match:
            year = before_match.group(1)
            time_filter['before'] = year
            # Remove the matched text from the query
            modified_query = re.sub(before_pattern, '', modified_query, flags=re.IGNORECASE).strip()
        
        # Pattern for "in YYYY" or "from YYYY" (without "to")
        year_pattern = r'(?:in|from|during|year)\s+(\d{4})'
        year_match = re.search(year_pattern, modified_query, re.IGNORECASE)
        if year_match:
            year = year_match.group(1)
            time_filter['year'] = year
            # Remove the matched text from the query
            modified_query = re.sub(year_pattern, '', modified_query, flags=re.IGNORECASE).strip()
            
        # Just a year mentioned directly
        direct_year_pattern = r'\b(20\d{2})\b'
        direct_year_match = re.search(direct_year_pattern, modified_query)
        if direct_year_match and not any(filter_type in time_filter for filter_type in ['between', 'after', 'before', 'year']):
            year = direct_year_match.group(1)
            time_filter['year'] = year
            # Remove the matched text from the query
            modified_query = re.sub(direct_year_pattern, '', modified_query).strip()
        
        # If no time filter was found, return the original query
        if not time_filter:
            return query, None
            
        # Clean up the modified query (remove double spaces, etc.)
        modified_query = re.sub(r'\s+', ' ', modified_query).strip()
        
        return modified_query, time_filter
        
    def _create_filter(self, distance_threshold: Optional[float] = None, time_filter: Optional[Dict[str, Any]] = None) -> rag.Filter:
        """
        Create a filter for RAG queries, combining distance threshold and time filters.
        
        Args:
            distance_threshold: Vector distance threshold
            time_filter: Time-based filter parameters
            
        Returns:
            RagFilter object
        """
        # Create base filter with distance threshold
        filter_args = {}
        if distance_threshold:
            filter_args["vector_distance_threshold"] = distance_threshold
            
        # Add metadata filters for time if provided
        if time_filter:
            metadata_filters = []
            
            # Metadata filtering disabled due to API incompatibility
            # TODO: Re-enable when vertexai.rag.MetadataFilter is available
            logger.info(f"Time filter requested but disabled: {time_filter}")
            
            # Add the metadata filters to the main filter
            if metadata_filters:
                filter_args["metadata_filters"] = metadata_filters
                
        # Create and return the filter
        return rag.Filter(**filter_args)

    def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        distance_threshold: Optional[float] = None,
        use_reranking: Optional[bool] = None,
        reranker_model: Optional[str] = None,
        time_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context from the RAG corpus based on the query.

        Args:
            query: The search query
            top_k: Number of top results to return (defaults to config value)
            distance_threshold: Vector distance threshold (defaults to config value)
            use_reranking: Whether to use reranking (defaults to config value)
            reranker_model: Model to use for reranking (defaults to config value)
            time_filter: Optional time filter parameters:
                - year: Filter by specific year (e.g., "2023")
                - after: Filter for documents after this year (e.g., "2020")
                - before: Filter for documents before this year (e.g., "2023")
                - between: Tuple of (start_year, end_year) for range filtering

        Returns:
            List of retrieved contexts with metadata
        """
        # Load config values if not provided
        config = get_config()
        top_k = top_k or config.get("top_k")
        distance_threshold = distance_threshold or config.get("distance_threshold")
        use_reranking = use_reranking if use_reranking is not None else config.get("use_reranking", False)
        reranker_model = reranker_model or config.get("reranker_model")

        # Ensure corpus exists
        self.get_corpus()

        # # Process query for time-based terms
        # processed_query, extracted_time_filter = self._extract_time_filter_from_query(query)
        
        # # Combine extracted time filter with provided time filter
        # if extracted_time_filter and not time_filter:
        #     time_filter = extracted_time_filter
        # elif extracted_time_filter and time_filter:
        #     # Merge the filters, with explicit parameters taking precedence
        #     time_filter = {**extracted_time_filter, **time_filter}
            
        # If time filter detected, modify the query to remove time references
        # if extracted_time_filter:
        #     query = processed_query
        #     print(f"Modified query: '{query}' with time filter: {time_filter}")

        # Configure retrieval with optional reranking
        retrieval_config_args = {
            "top_k": top_k,
            "filter": self._create_filter(distance_threshold),
        }

        # Add reranking if enabled
        if use_reranking and reranker_model:
            #print(f"Using reranking with model: {reranker_model}")
            try:
                retrieval_config_args["ranking"] = rag.Ranking(
                    rank_service=rag.RankService(
                        model_name=reranker_model
                    )
                )
            except Exception as e:
                if "Permission 'discoveryengine.rankingConfigs.rank' denied" in str(e):
                    print("Error: Missing Discovery Engine permissions. See README_RERANKING.md for setup instructions.")
                elif "Discovery Engine API has not been used" in str(e) or "it is disabled" in str(e):
                    print("Error: Discovery Engine API not enabled. See README_RERANKING.md for setup instructions.")
                else:
                    print(f"Error configuring reranking: {e}")
                print("Falling back to standard retrieval")
        else:
            print("Reranking not enabled")

        # Create retrieval config with or without reranking
        retrieval_config = rag.RagRetrievalConfig(**retrieval_config_args)

        # Perform retrieval
        response = rag.retrieval_query(
            rag_resources=[
                rag.RagResource(
                    rag_corpus=self.corpus.name,
                )
            ],
            text=query,
            rag_retrieval_config=retrieval_config
        )

        # According to the documentation, the response has a 'contexts' attribute
        # but it may not be directly iterable
        results = []

        try:
            # Print debug info about the response
            #print(f"Response type: {type(response).__name__}")
            # print(f"Response attributes: {dir(response)}")

            # Handle RagContexts specifically - it may have a different structure
            if hasattr(response, 'contexts'):
                contexts_obj = response.contexts
                #print(f"Contexts type: {type(contexts_obj).__name__}")
                # print(f"Contexts attributes: {dir(contexts_obj)}")

                # Try different ways to access the contexts

                # If contexts is directly a context object with text
                if hasattr(contexts_obj, 'text'):
                    results.append(contexts_obj)

                # If contexts has a contexts field (nested structure)
                elif hasattr(contexts_obj, 'contexts'):
                    nested_contexts = contexts_obj.contexts
                    # Check if nested_contexts is iterable
                    try:
                        for context in nested_contexts:
                            results.append(context)
                    except TypeError:
                        # If not iterable, it might be a single context
                        if hasattr(nested_contexts, 'text'):
                            results.append(nested_contexts)

                # If it has a get_contexts or similar method
                elif hasattr(contexts_obj, 'get_contexts') and callable(contexts_obj.get_contexts):
                    try:
                        contexts_list = contexts_obj.get_contexts()
                        for context in contexts_list:
                            results.append(context)
                    except Exception as e:
                        print(f"Error calling get_contexts: {e}")

                # If it has a data attribute
                elif hasattr(contexts_obj, 'data'):
                    data = contexts_obj.data
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        results.append(data)

                # Last resort: try direct attribute access for common patterns
                else:
                    # Try to access individual contexts by index if it supports item access
                    try:
                        # First check if it's directly iterable
                        try:
                            for context in contexts_obj:
                                results.append(context)
                        except TypeError:
                            # If not iterable, try indexed access with proper bounds checking
                            try:
                                # Check if it has a length or size
                                max_items = 10  # default limit
                                if hasattr(contexts_obj, '__len__'):
                                    max_items = min(len(contexts_obj), 10)
                                elif hasattr(contexts_obj, 'size'):
                                    max_items = min(contexts_obj.size, 10)
                                
                                # Try up to max_items with proper bounds checking
                                for i in range(max_items):
                                    try:
                                        context = contexts_obj[i]
                                        results.append(context)
                                    except (IndexError, TypeError, KeyError):
                                        break
                            except Exception:
                                # Final fallback - try to convert to list if possible
                                try:
                                    contexts_list = list(contexts_obj)
                                    results.extend(contexts_list)
                                except Exception:
                                    pass
                    except Exception:
                        pass

            # For backward compatibility
            elif hasattr(response, 'retrievals'):
                results = response.retrievals
            elif hasattr(response, 'retrieval_contexts'):
                results = response.retrieval_contexts
            else:
                print(f"Warning: Could not find expected contexts in response")

        except Exception as e:
            logger.error(f"Error processing response: {e}")
            print(f"Error processing response: {e}")
            # Return empty results instead of crashing
            results = []

        print(f"Found {len(results)} results")
        return results

    def generate_answer(
        self, 
        query: str, 
        model_name: Optional[str] = None, 
        temperature: Optional[float] = None,
        retrievals: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate an answer to a query by retrieving context and using LLM.
        
        Args:
            query: The user query
            model_name: Name of the generative model (defaults to config value)
            temperature: Temperature parameter (defaults to config value)
            retrievals: Optional pre-retrieved context (if None, will retrieve)
            
        Returns:
            Generated answer
        """
        # Load config values if not provided
        config = get_config()
        model_name = model_name or config.get("generative_model")
        temperature = temperature or config.get("temperature")

        # Retrieve context if not provided
        if retrievals is None:
            try:
                retrievals = self.retrieve_context(query)
            except Exception as e:
                print(f"Warning: Error retrieving context: {e}")
                retrievals = []

        # Ensure retrievals is always a list
        if not isinstance(retrievals, list):
            try:
                retrievals_list = list(retrievals)
                retrievals = retrievals_list
            except (TypeError, ValueError):
                # If conversion fails, wrap in a list if it has a text attribute
                if hasattr(retrievals, 'text'):
                    retrievals = [retrievals]
                else:
                    print(f"Warning: Could not convert retrievals to a list: {type(retrievals)}")
                    retrievals = []

        if not retrievals:
            return "No relevant information found."

        # Format context for the prompt - based on documentation format
        context_parts = []
        for r in retrievals:
            # According to docs, context should have a 'text' attribute
            if hasattr(r, "text"):
                context_parts.append(r.text)
            # For backward compatibility
            elif hasattr(r, "chunk") and hasattr(r.chunk, "data"):
                context_parts.append(r.chunk.data)
            elif hasattr(r, "content"):
                context_parts.append(r.content)
            else:
                print(f"Warning: Could not find text content in context object. Available fields: {dir(r)}")

        context = "\n\n".join(context_parts)

        # Create generative model
        model = GenerativeModel(model_name)

        # Generate response
        prompt = f"""
        Use the following information to answer the question.
        If you don't know the answer, just say "I don't have enough information to answer that."
        
        Context:
        {context}
        
        Question: {query}
        
        Answer:
        """

        # Use generation_config to set temperature
        response = model.generate_content(
            prompt, 
            generation_config={"temperature": temperature} if temperature is not None else None
        )
        return response.text

    def list_corpus_files(self) -> List[Dict[str, Any]]:
        """
        List all files imported into the RAG corpus.
        
        Returns:
            List of files with metadata
        """
        # Ensure corpus exists
        self.get_corpus()

        files = rag.list_files(self.corpus.name)
        return files

    def direct_rag_response(
        self,
        query: str,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        vector_distance_threshold: Optional[float] = None,
        use_reranking: Optional[bool] = None,
        reranker_model: Optional[str] = None
    ) -> str:
        """
        Generate a response using RAG Engine's direct integration with LLMs.
        
        Uses Vertex AI's RAG integration where the retrieval happens within
        the model call, rather than as separate retrieve-then-generate steps.
        
        Args:
            query: The user query
            model_name: Name of the generative model (defaults to config value)
            temperature: Temperature parameter (defaults to config value)
            top_k: Number of top results to return (defaults to config value)
            vector_distance_threshold: Optional similarity threshold (defaults to config value)
            use_reranking: Whether to use reranking (defaults to config value)
            reranker_model: Model to use for reranking (defaults to config value)

        Returns:
            Generated answer
        """
        # Load config values if not provided
        config = get_config()
        model_name = model_name or config.get("generative_model")
        temperature = temperature or config.get("temperature")
        top_k = top_k or config.get("top_k")
        vector_distance_threshold = vector_distance_threshold or config.get("distance_threshold")
        use_reranking = use_reranking if use_reranking is not None else config.get("use_reranking", False)
        reranker_model = reranker_model or config.get("reranker_model")

        # Ensure corpus exists
        self.get_corpus()

        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Using direct RAG integration for query: {query}")

            # In Vertex AI v1.92.0, we need to use a different approach for RAG integration
            # First, we get the contexts directly
            retrievals = self.retrieve_context(
                query=query,
                top_k=top_k,
                distance_threshold=vector_distance_threshold,
                use_reranking=use_reranking,
                reranker_model=reranker_model
            )
            
            # Store the contexts for display in the CLI without verbose logging
            self.last_contexts = retrievals.copy() if isinstance(retrievals, list) else list(retrievals) if retrievals else []
            
            # Only log the context count in debug mode
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Retrieved {len(self.last_contexts)} contexts for RAG")
                if self.last_contexts:
                    # Log detailed information in debug mode only
                    first_ctx = self.last_contexts[0]
                    logger.debug(f"Context type: {type(first_ctx).__name__}")
                    
                    has_uri = hasattr(first_ctx, 'uri')
                    has_text = hasattr(first_ctx, 'text')
                    has_score = hasattr(first_ctx, 'relevance_score') or hasattr(first_ctx, 'score')
                    logger.debug(f"Context has URI: {has_uri}, Text: {has_text}, Score: {has_score}")
                    
                    # Sample snippet in debug mode only
                    if has_text:
                        sample_text = first_ctx.text[:100] + "..." if len(first_ctx.text) > 100 else first_ctx.text
                        logger.debug(f"Sample text from first context: \"{sample_text}\"")
                    elif hasattr(first_ctx, 'chunk') and hasattr(first_ctx.chunk, 'data'):
                        sample_text = first_ctx.chunk.data[:100] + "..." if len(first_ctx.chunk.data) > 100 else first_ctx.chunk.data
                        logger.debug(f"Sample text from first context chunk: \"{sample_text}\"")
                    elif hasattr(first_ctx, 'content'):
                        sample_text = first_ctx.content[:100] + "..." if len(first_ctx.content) > 100 else first_ctx.content
                        logger.debug(f"Sample text from first context content: \"{sample_text}\"")
            
            # No print to stdout during normal operation

            if not retrievals:
                return "No relevant information found."

            # Format context for the model
            context_parts = []
            for r in retrievals:
                if hasattr(r, "text"):
                    context_parts.append(r.text)
                elif hasattr(r, "chunk") and hasattr(r.chunk, "data"):
                    context_parts.append(r.chunk.data)
                elif hasattr(r, "content"):
                    context_parts.append(r.content)
                else:
                    print(f"Warning: Could not find text content in context object. Available fields: {dir(r)}")

            context = "\n\n".join(context_parts)

            # Use generative model with the retrieved context
            # This simulates a direct integration by using the most recent contexts
            model = GenerativeModel(model_name)

            # Use a prompt that identifies this was retrieved with RAG
            prompt = f"""
            You are using direct RAG integration to answer this question.
            Use the following information accurately to answer the question.
            If you don't know the answer based on the context, say "I don't have enough information to answer that."

            Context from RAG{" with reranking" if use_reranking else ""}:
            {context}

            Question: {query}

            Answer:
            """

            # Generate response
            response = model.generate_content(
                prompt,
                generation_config={"temperature": temperature} if temperature is not None else None
            )

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Successfully generated response using direct RAG integration")
            return response.text

        except Exception as e:
            logger.error(f"Error in direct RAG integration: {e}")
            logger.warning("Falling back to manual RAG implementation...")

            # Fall back to the standard two-step approach
            return self.generate_answer(
                query=query,
                model_name=model_name,
                temperature=temperature
            )
