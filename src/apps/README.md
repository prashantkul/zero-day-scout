# Streamlit RAG Demo App

This directory contains a Streamlit app that demonstrates the RAG pipeline functionality.

## Running the App

To run the Streamlit app, first make sure you have set up your environment and installed the required dependencies:

```bash
# Make sure you're in the project root directory
cd /path/to/zero-day-scout

# Install the dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run src/apps/streamlit_app.py
```

## Features

The Streamlit app provides a web interface to:

1. **Query the RAG Pipeline**: Ask questions and get answers based on your corpus documents
2. **Ingest Documents**: Add documents from your GCS bucket to the RAG corpus
3. **View Corpus Files**: See what files are currently in your corpus

## Configuration

The app uses the configuration from your `.env` file, so make sure that's properly set up with:

- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GCS_BUCKET`
- Other RAG configuration settings

## Demo Notes

For a full demo of RAG capabilities:

1. Start by ingesting documents (use the "Ingest Documents" tab)
2. Once documents are ingested, ask questions (use the "Query RAG" tab)
3. View the context that was used to generate the answer
4. Try different settings like temperature and top_k

## Troubleshooting

If you encounter issues:

1. Check that the RAG Pipeline and GCS Manager are properly initialized (see sidebar)
2. Verify your credentials and permissions
3. Check that your corpus exists and has documents