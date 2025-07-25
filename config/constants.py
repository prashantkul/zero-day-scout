"""
Constants and default configurations for the RAG pipeline.
"""

# Google Cloud settings
DEFAULT_PROJECT_ID = "privacy-ml-lab2"  # Set from environment variables
DEFAULT_LOCATION = "us-central1"

# RAG Engine settings
DEFAULT_CORPUS_NAME = "scout_corpus"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_GENERATIVE_MODEL = "gemini-2.5-flash"

# Retrieval settings
DEFAULT_TOP_K = 5
DEFAULT_DISTANCE_THRESHOLD = 0.6
DEFAULT_TEMPERATURE = 0.2
DEFAULT_RERANKER_MODEL = (
    "gemini-2.5-flash"  # Using the same model as generative by default
)
DEFAULT_USE_RERANKING = False  # Disabled by default until full Discovery Engine permissions are set up

# Document chunking settings
DEFAULT_CHUNK_SIZE = 512  # Default size of each document chunk in tokens
DEFAULT_CHUNK_OVERLAP = 100  # Default overlap between chunks in tokens

# GCS settings
DEFAULT_GCS_BUCKET = "rag-research-papers"  # Set during runtime
DEFAULT_DOCUMENT_PREFIXES = [
    "arxiv_security_papers/",
    "uploaded_papers/",
    "cves/",
]  # Default document prefixes to scan
DEFAULT_USE_CLOUD_TRACKING = True  # Whether to store ingestion tracking in cloud
DEFAULT_CLOUD_TRACKING_PATH = "tracking/ingested_docs.json"  # Path to tracking file in GCS bucket

# MCP Server settings
MCP_SERVER_HOST = "0.0.0.0"  # Default binding address for the MCP server
MCP_SERVER_CLIENT_HOST = "localhost"  # Default client connection address
MCP_SERVER_PORT = 8080  # Default port for the MCP server
MCP_SERVER_TRANSPORT = "streamable-http"  # Default transport protocol (streamable-http or sse)

# MCP Timeout settings
MCP_REQUEST_TIMEOUT = 180  # Default timeout for MCP requests in seconds
MCP_LIST_TIMEOUT = 90      # Default timeout for list operations in seconds
MCP_CONNECT_TIMEOUT = 30   # Default timeout for initial connection in seconds
MCP_RETRY_COUNT = 3        # Number of retries for failed operations
