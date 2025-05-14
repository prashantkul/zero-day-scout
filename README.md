# Zero-Day Scout

A RAG-based security analysis system using Google Cloud Vertex AI RAG Engine.

## Project Overview

Zero-Day Scout is a Python project that implements a Retrieval-Augmented Generation (RAG) pipeline using Google Cloud Vertex AI RAG Engine. It ingests documents from Google Cloud Storage, creates embeddings, and provides a retrieval mechanism for answering security-related queries, with a focus on identifying zero-day vulnerabilities.

## Environment Setup

```bash
# Create a conda environment
conda create --name scout python=3.11

# Activate the environment
conda activate scout

# Install dependencies
pip install -r requirements.txt
# or with uv (which is listed as a dependency)
uv pip install -r requirements.txt

# Set up environment variables (copy template first)
cp .env.template .env
# Edit .env with your actual values
```

## Project Structure

- `config/`: Configuration files for the application
  - `constants.py`: Default configuration values
  - `config_manager.py`: Manages loading config from environment variables
- `src/`: Source code for the application
  - `rag/`: RAG pipeline implementation
    - `pipeline.py`: Main RAG pipeline using Vertex AI
    - `gcs_utils.py`: Utilities for working with Google Cloud Storage
  - `examples/`: Example usage scripts
- `tests/`: Test files for the application

## Configuration

Configuration is managed through environment variables and default values:

1. Copy `.env.template` to `.env` and edit with your values
2. Key environment variables:
   - `GOOGLE_CLOUD_PROJECT`: Your GCP project ID
   - `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account key
   - `GCS_BUCKET`: GCS bucket for document storage
   - `RAG_CORPUS_NAME`: Name for the RAG corpus
   - `DOCUMENT_PREFIXES`: Comma-separated list of GCS prefixes to scan for documents (e.g., "research/,papers/,publications/")

## Document Ingestion

### Document Prefixes

The system can be configured to ingest documents from specific prefixes in your GCS bucket:

1. Configure document prefixes in your `.env` file:
   ```
   DOCUMENT_PREFIXES=research/,papers/,publications/
   ```

2. Default prefixes are set in `config/constants.py` if not specified:
   ```python
   DEFAULT_DOCUMENT_PREFIXES = ["research/", "papers/", "publications/"]
   ```

3. To ingest documents from these prefixes, call the `ingest_documents` method with an empty list:
   ```python
   pipeline.ingest_documents([])  # Uses configured prefixes
   ```

### Duplicate Prevention

The system now tracks ingested documents to prevent duplicates:

1. Previously ingested documents are stored in a JSON file (`.ingested_docs.json` by default)
2. When ingesting documents, only new documents not previously ingested are processed
3. The tracking file path can be customized when initializing the pipeline:
   ```python
   pipeline = VertexRagPipeline(tracking_file="/custom/path/to/tracking.json")
   ```

## RAG Pipeline Usage

Basic usage of the RAG pipeline:

```python
from src.rag.pipeline import VertexRagPipeline

# Initialize pipeline
pipeline = VertexRagPipeline()

# Create corpus and ingest documents (uses configured prefixes)
corpus = pipeline.create_corpus()
pipeline.ingest_documents([])

# Or specify explicit GCS paths
pipeline.ingest_documents(["gs://your-bucket/specific-document.pdf"])

# Query the RAG pipeline
answer = pipeline.generate_answer("What are common zero-day vulnerabilities?")
print(answer)
```

Run the example scripts:

```bash
# Test document ingestion with prefixes and duplicate prevention
python -m src.examples.test_document_ingestion

# List existing files in GCS and run a query
python -m src.examples.rag_example --gcs-prefix documents --query "What are zero-day vulnerabilities?"

# Upload local documents to GCS and ingest them
python -m src.examples.rag_example --upload-dir ./local_documents --query "Explain zero-day exploits"
```

## Direct RAG Integration

For enhanced performance, the system supports direct RAG integration where retrieval happens within the model call:

```python
# Use direct RAG integration (with optional reranking)
answer = pipeline.direct_rag_response(
    query="What are the latest zero-day vulnerabilities?",
    use_reranking=True
)
```

See `README_RERANKING.md` for more information on setting up and using the reranking feature.

## Development Guidelines

When working with this codebase:

1. Always ensure proper authentication with Google Cloud
2. Update environment variables in .env for your specific setup
3. Follow the existing module structure for new features
4. Add tests for new functionality when implementing