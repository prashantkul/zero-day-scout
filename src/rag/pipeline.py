"""
RAG Pipeline for ingesting documents from GCS bucket and creating embeddings 
using Google Cloud Vertex AI RAG Engine with RagManagedDb.
"""

import os
from typing import List, Dict, Any, Optional, Union

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
    ):
        """
        Initialize the RAG pipeline.

        Args:
            project_id: Google Cloud project ID (defaults to config value)
            location: Google Cloud region (defaults to config value)
            corpus_name: Name for the RAG corpus (defaults to config value)
            embedding_model: Name of the embedding model (defaults to config value)
        """
        # Load configuration
        config = get_config()

        # Set parameters from config if not provided
        self.project_id = project_id or config.get("project_id")
        self.location = location or config.get("location")
        self.corpus_name = corpus_name or config.get("corpus_name")
        self.embedding_model = embedding_model or config.get("embedding_model")
        self.corpus = None

        # Initialize Vertex AI
        aiplatform.init(project=self.project_id, location=self.location)

    def create_corpus(self) -> rag.RagCorpus:
        """
        Create a new RAG corpus using RagManagedDb for document storage and retrieval.
        
        Returns:
            The created RAG corpus
        """
        # Configure embedding model
        embedding_model_config = rag.RagEmbeddingModelConfig(
            vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                publisher_model=f"publishers/google/models/{self.embedding_model}"
            )
        )

        # Create the RAG corpus with RagManagedDb
        self.corpus = rag.create_corpus(
            display_name=self.corpus_name,
            backend_config=rag.RagVectorDbConfig(
                rag_embedding_model_config=embedding_model_config
            ),
        )

        print(f"Created RAG corpus: {self.corpus.name}")
        return self.corpus

    def ingest_documents(self, gcs_paths: List[str]) -> Dict[str, Any]:
        """
        Ingest documents from GCS bucket into the RAG corpus.
        
        Args:
            gcs_paths: List of GCS paths (e.g., ["gs://bucket_name/folder/file.pdf"])
            
        Returns:
            Import operation details
        """
        if not self.corpus:
            self.create_corpus()

        # Import files to the RAG corpus
        import_op = rag.import_files(
            self.corpus.name,
            gcs_paths
        )

        print(f"Started document ingestion from: {gcs_paths}")
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
        distance_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context from the RAG corpus based on the query.
        
        Args:
            query: The search query
            top_k: Number of top results to return (defaults to config value)
            distance_threshold: Vector distance threshold (defaults to config value)
            
        Returns:
            List of retrieved contexts with metadata
        """
        # Load config values if not provided
        config = get_config()
        top_k = top_k or config.get("top_k")
        distance_threshold = distance_threshold or config.get("distance_threshold")

        # Ensure corpus exists
        self.get_corpus()

        # Configure retrieval
        retrieval_config = rag.RagRetrievalConfig(
            top_k=top_k,
            filter=rag.Filter(vector_distance_threshold=distance_threshold),
        )

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
            print(f"Response attributes: {dir(response)}")
            
            # Handle RagContexts specifically - it may have a different structure
            if hasattr(response, 'contexts'):
                contexts_obj = response.contexts
                print(f"Contexts type: {type(contexts_obj).__name__}")
                print(f"Contexts attributes: {dir(contexts_obj)}")
                
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
        top_k: Optional[int] = None
    ) -> str:
        """
        Generate a response using RAG Engine's direct integration with LLMs.
        
        Args:
            query: The user query
            model_name: Name of the generative model (defaults to config value)
            temperature: Temperature parameter (defaults to config value)
            top_k: Number of top results to return (defaults to config value)
            
        Returns:
            Generated answer
        """
        # Load config values if not provided
        config = get_config()
        model_name = model_name or config.get("generative_model")
        temperature = temperature or config.get("temperature")
        top_k = top_k or config.get("top_k")

        # Instead of direct integration (which might not be supported),
        # we'll use the two-step approach: retrieve then generate
        try:
            # First, retrieve relevant documents
            print(f"Retrieving context for: {query}")
            retrievals = self.retrieve_context(
                query=query,
                top_k=top_k
            )
            
            print(f"Found {len(retrievals)} results for direct RAG")
            
            # Then, generate a response using the retrieved context
            return self.generate_answer(
                query=query,
                model_name=model_name,
                temperature=temperature,
                retrievals=retrievals
            )
            
        except Exception as e:
            print(f"Error in direct RAG integration: {e}")
            print("Falling back to alternative implementation...")
            
            try:
                # Alternative implementation: try to use safety_settings approach
                # Create generative model
                model = GenerativeModel(model_name)
                
                # First retrieve context
                retrievals = self.retrieve_context(
                    query=query,
                    top_k=top_k
                )
                
                # Format context
                context_parts = []
                for r in retrievals:
                    if hasattr(r, "text"):
                        context_parts.append(r.text)
                    elif hasattr(r, "chunk") and hasattr(r.chunk, "data"):
                        context_parts.append(r.chunk.data)
                    elif hasattr(r, "content"):
                        context_parts.append(r.content)
                
                context = "\n\n".join(context_parts)
                
                # Create prompt with context
                prompt = f"""
                Use the following information to answer the question.
                If you don't know the answer, just say "I don't have enough information to answer that."
                
                Context:
                {context}
                
                Question: {query}
                
                Answer:
                """
                
                # Generate response
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": temperature} if temperature is not None else None
                )
                
                return response.text
                
            except Exception as fallback_error:
                return f"Unable to generate response with RAG integration: {fallback_error}"
