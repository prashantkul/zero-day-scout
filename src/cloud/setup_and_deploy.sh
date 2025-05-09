#!/bin/bash
# Script to set up permissions and deploy the RAG ingestion service using Cloud Build

set -e  # Exit on error

# Default values
REGION="us-central1"
SKIP_IAM=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region=*)
      REGION="${1#*=}"
      shift
      ;;
    --skip-iam)
      SKIP_IAM=true
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --region=REGION        GCP region (default: us-central1)"
      echo "  --skip-iam             Skip IAM setup (use if permissions already set)"
      echo "  --help                 Show this help message"
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
echo "RAG Ingestion Service Setup & Deploy"
echo "====================================="
echo ""

# Get project info
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
  echo "Error: No project ID found. Please set a default project with:"
  echo "  gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "Setting up RAG ingestion service for project: $PROJECT_ID"
echo "Region: $REGION"
echo ""


# Confirm deployment
echo "Ready to deploy the RAG ingestion service to Cloud Run."
echo "Note: Cloud Scheduler setup will be a separate step after deployment."
echo ""

read -p "Continue with deployment? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
  echo "Deployment cancelled."
  exit 0
fi

# Trigger Cloud Build with substitutions
echo "Triggering Cloud Build deployment..."
gcloud builds submit --config=src/cloud/cloudbuild-deploy.yaml --substitutions=_REGION=$REGION .

echo ""
echo "Deployment started!"
echo ""
echo "After deployment completes, please follow the instructions in the README.md"
echo "to set up Cloud Scheduler for the RAG ingestion service."
echo ""