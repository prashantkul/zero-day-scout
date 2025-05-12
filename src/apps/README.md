# Streamlit RAG Demo App

This directory contains a Streamlit app that demonstrates the RAG pipeline functionality.

## Running the App Locally

To run the Streamlit app, first make sure you have set up your environment and installed the required dependencies:

```bash
# Make sure you're in the project root directory
cd /path/to/zero-day-scout

# Install the dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run src/apps/streamlit_app.py
```

## Deploying to Cloud Run

You can deploy the Streamlit app to Google Cloud Run to make it accessible as a web service:

### Option 1: Using the Deployment Script

```bash
# Make the script executable
chmod +x src/apps/deploy_streamlit.sh

# Deploy with default settings
./src/apps/deploy_streamlit.sh

# Or deploy with custom settings
./src/apps/deploy_streamlit.sh --region=us-west1 --gcs-bucket=my-bucket --corpus-name=my-corpus
```

### Option 2: Manual Deployment

```bash
# Deploy using gcloud builds
gcloud builds submit --config=src/apps/cloudbuild-streamlit.yaml \
  --substitutions=_REGION=us-central1,_GCS_BUCKET=your-bucket,_RAG_CORPUS_NAME=your-corpus .
```

## Environment Variables for Cloud Run

The Cloud Run deployment uses the following environment variables:

- `PROJECT_ID`: Set automatically from your Google Cloud project
- `GCS_BUCKET`: GCS bucket name for document storage
- `RAG_CORPUS_NAME`: Name of your RAG corpus

## Features

The Streamlit app provides a web interface to:

1. **Query the RAG Pipeline**: Ask questions and get answers based on your corpus documents
2. **Ingest Documents**: Add documents from your GCS bucket to the RAG corpus
3. **View Corpus Files**: See what files are currently in your corpus

## Configuration

When running locally, the app uses the configuration from your `.env` file, so make sure that's properly set up with:

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