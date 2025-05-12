# Using Reranker in RAG Pipeline

This document explains how to use the reranker functionality in the RAG pipeline.

## Prerequisites

Before you can use the reranker, you must enable the Discovery Engine API and set up proper permissions in your Google Cloud project. Follow these steps:

1. Enable the Discovery Engine API:
   - Go to https://console.developers.google.com/apis/api/discoveryengine.googleapis.com/overview?project=[YOUR_PROJECT_ID]
   - Click "Enable" to activate the Discovery Engine API
   - Wait a few minutes for the change to propagate

2. Grant necessary permissions:
   - Go to IAM & Admin in the Google Cloud Console
   - Find your service account (or user account that's running the code)
   - Add the following roles:
     - Discovery Engine Admin
     - Discovery Engine Editor
     - Discovery Engine Ranking Admin
     - Discovery Engine Service Agent

3. Create a ranking configuration (if it doesn't exist):
   - Go to the Discovery Engine section in Google Cloud Console
   - Select "Ranking configurations"
   - Create a default ranking configuration if one doesn't exist

## Configuring Reranking

After enabling the Discovery Engine API, you can enable reranking by:

1. Setting the environment variable:
   ```
   export RAG_USE_RERANKING=true
   ```

2. Or updating the `constants.py` file:
   ```python
   DEFAULT_USE_RERANKING = True
   ```

3. Specifying the reranker model (optional):
   ```python
   DEFAULT_RERANKER_MODEL = "gemini-2.5-flash-preview-04-17"  # Or another compatible model
   ```

## Using Reranking in Code

### Direct RAG Response

```python
from src.rag.pipeline import VertexRagPipeline

pipeline = VertexRagPipeline()
answer = pipeline.direct_rag_response(
    query="What are zero-day vulnerabilities?",
    use_reranking=True
)
print(answer)
```

### Custom Retrieval

```python
from src.rag.pipeline import VertexRagPipeline

pipeline = VertexRagPipeline()
contexts = pipeline.retrieve_context(
    query="What are zero-day vulnerabilities?",
    top_k=10,
    use_reranking=True
)
# Process contexts as needed
```

## Testing Reranking

Use the provided test scripts to compare results with and without reranking:

```bash
# Test direct RAG response with reranking
python -m src.examples.test_direct_reranking

# Compare different reranking approaches
python -m src.examples.test_reranking
```

## Troubleshooting

If you see errors like:

```
PermissionDenied('Discovery Engine API has not been used in project [YOUR_PROJECT_ID] before or it is disabled.')
```

Make sure you have enabled the Discovery Engine API as described in the Prerequisites section.