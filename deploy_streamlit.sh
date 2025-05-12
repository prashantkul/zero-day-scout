#!/bin/bash
# Script to deploy the Streamlit RAG app to Cloud Run

set -e  # Exit on error

# Default values
REGION="us-central1"
GCS_BUCKET="rag-research-papers"
RAG_CORPUS_NAME="scout_corpus"
SERVICE_ACCOUNT="174522850388-compute@developer.gserviceaccount.com"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region=*)
      REGION="${1#*=}"
      shift
      ;;
    --gcs-bucket=*)
      GCS_BUCKET="${1#*=}"
      shift
      ;;
    --corpus-name=*)
      RAG_CORPUS_NAME="${1#*=}"
      shift
      ;;
    --service-account=*)
      SERVICE_ACCOUNT="${1#*=}"
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --region=REGION            GCP region (default: us-central1)"
      echo "  --gcs-bucket=BUCKET        GCS bucket for documents (default: rag-research-papers)"
      echo "  --corpus-name=NAME         RAG corpus name (default: scout_corpus)"
      echo "  --service-account=EMAIL    Service account email (default: 174522850388-compute@developer.gserviceaccount.com)"
      echo "  --help                     Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help to see available options"
      exit 1
      ;;
  esac
done

# Print banner
echo "====================================="
echo "RAG Streamlit App Deployment"
echo "====================================="
echo ""

# Get project info
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
  echo "Error: No project ID found. Please set a default project with:"
  echo "  gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "Deploying RAG Streamlit app for project: $PROJECT_ID"
echo "Region: $REGION"
echo "GCS Bucket: $GCS_BUCKET"
echo "RAG Corpus Name: $RAG_CORPUS_NAME"
echo "Service Account: $SERVICE_ACCOUNT"
echo ""

# Confirm deployment
echo "Ready to deploy the RAG Streamlit app to Cloud Run."
echo ""

read -p "Continue with deployment? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
  echo "Deployment cancelled."
  exit 0
fi

# Trigger Cloud Build with substitutions
echo "Triggering Cloud Build deployment..."
gcloud builds submit --config=src/apps/cloudbuild-streamlit.yaml \
  --substitutions=_REGION=$REGION,_GCS_BUCKET=$GCS_BUCKET,_RAG_CORPUS_NAME=$RAG_CORPUS_NAME,_SERVICE_ACCOUNT=$SERVICE_ACCOUNT .

echo ""
echo "Deployment started!"
echo ""
echo "After deployment completes, you can access your Streamlit app at the Cloud Run URL."
echo ""