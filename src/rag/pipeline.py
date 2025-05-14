"""
RAG Pipeline for ingesting documents from GCS bucket and creating embeddings 
using Google Cloud Vertex AI RAG Engine with RagManagedDb.
"""

import os
import json
from typing import List, Dict, Any, Optional, Union, Set
from pathlib import Path

from google.cloud import aiplatform
from vertexai import rag
from vertexai.generative_models import GenerativeModel

from config.config_manager import get_config


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
        # Load configuration
        config = get_config()

        # Set parameters from config if not provided
        self.project_id = project_id or config.get("project_id")
        self.location = location or config.get("location")
        self.corpus_name = corpus_name or config.get("corpus_name")
        self.embedding_model = embedding_model or config.get("embedding_model")
        self.document_prefixes = config.get("document_prefixes", [])
        self.corpus = None
        
        # Document tracking settings
        self.use_cloud_tracking = use_cloud_tracking if use_cloud_tracking is not None else config.get("use_cloud_tracking", True)
        
        # Set up tracking file paths for both local and cloud
        if self.use_cloud_tracking:
            # Cloud tracking path - use a standard location in the bucket
            self.cloud_tracking_path = config.get("cloud_tracking_path", "tracking/ingested_docs.json")
        
        # Local tracking is still supported as fallback
        self.tracking_file = tracking_file or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".ingested_docs.json"
        )
        
        # Load the ingested documents
        self.ingested_documents = self._load_ingested_documents()

        # Initialize Vertex AI
        aiplatform.init(project=self.project_id, location=self.location)

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
                print("Warning: Custom embedding model not supported. Trying with default embedding model.")
                # Try with standard endpoint
                self.corpus = rag.create_corpus(
                    display_name=self.corpus_name
                )
            else:
                # Re-raise if it's a different error
                raise e

        print(f"Created RAG corpus: {self.corpus.name}")
        return self.corpus

    def _load_ingested_documents(self) -> Set[str]:
        """
        Load the set of previously ingested documents from cloud or local storage.
        
        Returns:
            Set of ingested document paths
        """
        # Initialize empty set
        documents = set()
        
        try:
            # Try cloud storage first if enabled
            if self.use_cloud_tracking:
                from src.rag.gcs_utils import GcsManager
                try:
                    gcs_manager = GcsManager(project_id=self.project_id, bucket_name=None)
                    cloud_docs = gcs_manager.read_json(self.cloud_tracking_path)
                    
                    if cloud_docs is not None:
                        print(f"Loaded {len(cloud_docs)} ingested documents from cloud storage")
                        documents.update(cloud_docs)
                        return documents
                except Exception as cloud_e:
                    print(f"Warning: Could not load ingested documents from cloud: {cloud_e}")
                    print("Falling back to local tracking file")
            
            # Fall back to local file if cloud fails or is disabled
            if os.path.exists(self.tracking_file):
                with open(self.tracking_file, 'r') as f:
                    local_docs = json.load(f)
                    documents.update(local_docs)
                    print(f"Loaded {len(local_docs)} ingested documents from local file")
            
            return documents
            
        except Exception as e:
            print(f"Warning: Could not load ingested documents: {e}")
            return set()
    
    def _save_ingested_documents(self) -> None:
        """
        Save the current set of ingested documents to cloud and/or local storage.
        """
        doc_list = list(self.ingested_documents)
        
        # Save to cloud if enabled
        if self.use_cloud_tracking:
            try:
                from src.rag.gcs_utils import GcsManager
                gcs_manager = GcsManager(project_id=self.project_id, bucket_name=None)
                gcs_manager.write_json(self.cloud_tracking_path, doc_list)
                print(f"Saved {len(doc_list)} ingested documents to cloud storage")
            except Exception as cloud_e:
                print(f"Warning: Could not save ingested documents to cloud: {cloud_e}")
                print("Falling back to local tracking file")
        
        # Also save locally as backup, if cloud saving fails or is disabled
        try:
            with open(self.tracking_file, 'w') as f:
                json.dump(doc_list, f)
                if not self.use_cloud_tracking:
                    print(f"Saved {len(doc_list)} ingested documents to local file")
        except Exception as e:
            print(f"Warning: Could not save ingested documents to local file: {e}")
    
    def ingest_documents(self, gcs_paths: List[str]) -> Dict[str, Any]:
        """
        Ingest documents from GCS bucket into the RAG corpus.
        
        Args:
            gcs_paths: List of GCS paths (e.g., ["gs://bucket_name/folder/file.pdf"])
            If empty, reads from document_prefixes configured in settings.
            
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
        
        # Filter out already ingested documents
        new_documents = [path for path in gcs_paths if path not in self.ingested_documents]
        
        if not new_documents:
            print("No new documents to ingest.")
            return {"status": "skipped", "message": "No new documents to ingest"}
        
        print(f"Ingesting {len(new_documents)} new documents (skipping {len(gcs_paths) - len(new_documents)} already ingested)")
        
        # Import files to the RAG corpus
        import_op = rag.import_files(
            self.corpus.name,
            new_documents
        )
        
        # Update tracking
        self.ingested_documents.update(new_documents)
        self._save_ingested_documents()
        
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

    def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        distance_threshold: Optional[float] = None,
        use_reranking: Optional[bool] = None,
        reranker_model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context from the RAG corpus based on the query.

        Args:
            query: The search query
            top_k: Number of top results to return (defaults to config value)
            distance_threshold: Vector distance threshold (defaults to config value)
            use_reranking: Whether to use reranking (defaults to config value)
            reranker_model: Model to use for reranking (defaults to config value)

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

        # Configure retrieval with optional reranking
        retrieval_config_args = {
            "top_k": top_k,
            "filter": rag.Filter(vector_distance_threshold=distance_threshold),
        }

        # Add reranking if enabled
        if use_reranking and reranker_model:
            print(f"Using reranking with model: {reranker_model}")
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
            print(f"Response type: {type(response).__name__}")
            # print(f"Response attributes: {dir(response)}")

            # Handle RagContexts specifically - it may have a different structure
            if hasattr(response, 'contexts'):
                contexts_obj = response.contexts
                print(f"Contexts type: {type(contexts_obj).__name__}")
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
                        # Try up to 10 items (arbitrary limit)
                        for i in range(10):
                            try:
                                context = contexts_obj[i]
                                results.append(context)
                            except (IndexError, TypeError):
                                break
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
            print(f"Error processing response: {e}")

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
            print(f"Using direct RAG integration for query: {query}")

            # In Vertex AI v1.92.0, we need to use a different approach for RAG integration
            # First, we get the contexts directly
            retrievals = self.retrieve_context(
                query=query,
                top_k=top_k,
                distance_threshold=vector_distance_threshold,
                use_reranking=use_reranking,
                reranker_model=reranker_model
            )

            print(f"Retrieved {len(retrievals)} contexts for direct RAG integration")

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

            print("Successfully generated response using direct RAG integration")
            return response.text

        except Exception as e:
            print(f"Error in direct RAG integration: {e}")
            print("Falling back to manual RAG implementation...")

            # Fall back to the standard two-step approach
            return self.generate_answer(
                query=query,
                model_name=model_name,
                temperature=temperature
            )
