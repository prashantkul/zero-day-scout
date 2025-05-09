#!/bin/bash
# Script to set up IAM permissions for the RAG ingestion service

set -e  # Exit on error

# Print banner
echo "====================================="
echo "RAG Ingestion Service IAM Setup"
echo "====================================="
echo ""

# Get project info
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
  echo "Error: No project ID found. Please set a default project with:"
  echo "  gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "Setting up IAM permissions for project: $PROJECT_ID"
echo ""

# Enable required IAM APIs
echo "Enabling IAM API..."
gcloud services enable iam.googleapis.com

# Set up service account permissions
echo "Setting up service account permissions..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CLOUD_BUILD_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"
DEFAULT_SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# Grant roles to Default SA
echo "Granting logging Writer role to Default SA..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$DEFAULT_SA" \
  --role="roles/logging.logWriter"

# Grant roles to Cloud Build SA
echo "Granting Cloud Run Admin role to Cloud Build SA..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/run.admin"

echo "Granting Service Account User role to Cloud Build SA..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/iam.serviceAccountUser"

echo "Granting Cloud Scheduler Admin role to Cloud Build SA..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/cloudscheduler.admin"

echo "Service account permissions set up successfully."
echo ""