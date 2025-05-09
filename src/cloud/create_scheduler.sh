#!/bin/bash
# Script to create or update a Cloud Scheduler job for the RAG ingestion service

set -e  # Exit on error

# Default values
SERVICE_URL=""
REGION="us-central1"
JOB_NAME="rag-daily-ingestion"
SCHEDULE="0 2 * * *"
GCS_PREFIX=""
TIME_ZONE="America/Los_Angeles"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --url=*)
      SERVICE_URL="${1#*=}"
      shift
      ;;
    --region=*)
      REGION="${1#*=}"
      shift
      ;;
    --job-name=*)
      JOB_NAME="${1#*=}"
      shift
      ;;
    --schedule=*)
      SCHEDULE="${1#*=}"
      shift
      ;;
    --prefix=*)
      GCS_PREFIX="${1#*=}"
      shift
      ;;
    --time-zone=*)
      TIME_ZONE="${1#*=}"
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --url=URL              Service URL (required)"
      echo "  --region=REGION        GCP region (default: us-central1)"
      echo "  --job-name=NAME        Scheduler job name (default: rag-daily-ingestion)"
      echo "  --schedule=SCHEDULE    Cron schedule (default: 0 2 * * *)"
      echo "  --prefix=PREFIX        GCS path prefix (default: none)"
      echo "  --time-zone=TIMEZONE   Timezone (default: America/Los_Angeles)"
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
echo "RAG Ingestion Scheduler Setup"
echo "====================================="
echo ""

# Get project info
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
  echo "Error: No project ID found. Please set a default project with:"
  echo "  gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

# Check if SERVICE_URL is provided
if [ -z "$SERVICE_URL" ]; then
  echo "Error: Service URL is required. Please provide it with --url=URL"
  echo "You can find the service URL by running:"
  echo "  gcloud run services describe rag-ingestion-service --region=$REGION --format='value(status.url)'"
  exit 1
fi

echo "Setting up Cloud Scheduler job for RAG ingestion service"
echo "Project: $PROJECT_ID"
echo "Service URL: $SERVICE_URL"
echo ""

# Create message body file
TEMP_MESSAGE_FILE=$(mktemp)
if [ -n "$GCS_PREFIX" ]; then
  echo "{\"prefix\": \"$GCS_PREFIX\", \"wait_for_completion\": false}" > "$TEMP_MESSAGE_FILE"
  echo "Using GCS prefix: $GCS_PREFIX"
else
  echo "{\"wait_for_completion\": false}" > "$TEMP_MESSAGE_FILE"
  echo "No GCS prefix specified (will ingest all files)"
fi

# Verify service account exists
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# Check if scheduler job already exists
if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" &>/dev/null; then
  echo "Updating existing scheduler job: $JOB_NAME"
  gcloud scheduler jobs update http "$JOB_NAME" \
    --schedule="$SCHEDULE" \
    --uri="$SERVICE_URL/ingest" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --oidc-service-account-email="$SERVICE_ACCOUNT" \
    --message-body-from-file="$TEMP_MESSAGE_FILE" \
    --location="$REGION" \
    --time-zone="$TIME_ZONE"
else
  echo "Creating new scheduler job: $JOB_NAME"
  gcloud scheduler jobs create http "$JOB_NAME" \
    --schedule="$SCHEDULE" \
    --uri="$SERVICE_URL/ingest" \
    --http-method=POST \
    --oidc-service-account-email="$SERVICE_ACCOUNT" \
    --message-body-from-file="$TEMP_MESSAGE_FILE" \
    --location="$REGION" \
    --time-zone="$TIME_ZONE"
fi

# Clean up temp file
rm "$TEMP_MESSAGE_FILE"

echo ""
echo "Scheduler job setup complete!"
echo "Job: $JOB_NAME"
echo "Schedule: $SCHEDULE ($TIME_ZONE)"
echo "Next run time: $(gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" --format='value(nextRunTime)')"
echo ""