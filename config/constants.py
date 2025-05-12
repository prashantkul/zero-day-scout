"""
Constants and default configurations for the RAG pipeline.
"""

# Google Cloud settings
DEFAULT_PROJECT_ID = "privacy-ml-lab2"  # Set from environment variables
DEFAULT_LOCATION = "us-central1"

# RAG Engine settings
DEFAULT_CORPUS_NAME = "scout_corpus"
DEFAULT_EMBEDDING_MODEL = "text-embedding-005"
DEFAULT_GENERATIVE_MODEL = "gemini-2.5-flash-preview-04-17"

# Retrieval settings
DEFAULT_TOP_K = 5
DEFAULT_DISTANCE_THRESHOLD = 0.6
DEFAULT_TEMPERATURE = 0.2
DEFAULT_RERANKER_MODEL = "gemini-2.5-flash-preview-04-17"  # Using the same model as generative by default
DEFAULT_USE_RERANKING = False  # Disabled by default until full Discovery Engine permissions are set up

# GCS settings
DEFAULT_GCS_BUCKET = "rag-research-papers"  # Set during runtime
