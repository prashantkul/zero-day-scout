# Scheduled RAG Ingestion on Google Cloud Run

This guide explains how to set up a scheduled RAG document ingestion service on Google Cloud Run, triggered by Cloud Scheduler.

## Architecture

The solution consists of:

1. **Cloud Run Service**: A containerized service that ingests documents from GCS into the RAG corpus
2. **Cloud Scheduler**: A cron job that triggers the ingestion service on a schedule
3. **Service Account**: For authentication and authorization
4. **Container Registry**: To store the container image

## Prerequisites

- Google Cloud account and project
- Required permissions:
  - Cloud Run Admin
  - Cloud Scheduler Admin
  - Service Account User
  - Storage Admin
  - Vertex AI User
- gcloud CLI installed and configured

## Setup Steps

### 1. Create a Service Account

```bash
# Create service account
gcloud iam service-accounts create rag-ingestion-service \
  --description="Service account for RAG ingestion service" \
  --display-name="RAG Ingestion Service"

# Grant required permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:rag-ingestion-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:rag-ingestion-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Optional: Grant more granular permissions based on your needs
```

### 2. Build and Deploy the Service

#### Option A: Manual Deployment

```bash
# Build the container image
docker build -t gcr.io/YOUR_PROJECT_ID/rag-ingestion-service:v1 .

# Push to Container Registry
docker push gcr.io/YOUR_PROJECT_ID/rag-ingestion-service:v1

# Deploy to Cloud Run
gcloud run deploy rag-ingestion-service \
  --image=gcr.io/YOUR_PROJECT_ID/rag-ingestion-service:v1 \
  --region=us-central1 \
  --platform=managed \
  --memory=2Gi \
  --cpu=1 \
  --timeout=540s \
  --max-instances=10 \
  --min-instances=0 \
  --service-account=rag-ingestion-service@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars=PROJECT_ID=YOUR_PROJECT_ID \
  --no-allow-unauthenticated
```

#### Option B: Using Cloud Build

```bash
# Update the cloudbuild.yaml file with your project-specific values
# Then run:
gcloud builds submit --config src/cloud/cloudbuild.yaml
```

### 3. Set Up Cloud Scheduler

```bash
# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe rag-ingestion-service --region=us-central1 --format='value(status.url)')

# Create a scheduler job
gcloud scheduler jobs create http rag-daily-ingestion \
  --schedule="0 2 * * *" \
  --uri="${SERVICE_URL}/ingest" \
  --http-method=POST \
  --oidc-service-account-email=rag-ingestion-service@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --message-body='{"prefix": "documents/", "wait_for_completion": false}' \
  --location=us-central1 \
  --time-zone=America/Los_Angeles
```

## Configuration Options

The ingestion service accepts the following parameters:

- `prefix`: (Optional) GCS path prefix to filter files (e.g., "research_papers/")
- `wait_for_completion`: (Optional) Whether to wait for ingestion to complete (default: false)

Example payload:
```json
{
  "prefix": "documents/new/",
  "wait_for_completion": false
}
```

## Schedule Format

Cloud Scheduler uses [cron syntax](https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules):

- `0 2 * * *`: Run at 2:00 AM every day
- `0 */6 * * *`: Run every 6 hours
- `0 0 * * MON`: Run at midnight every Monday

## Testing the Service

You can test the service by making a POST request to the /ingest endpoint:

```bash
# Get authentication token
TOKEN=$(gcloud auth print-identity-token)

# Make request to the service
curl -X POST ${SERVICE_URL}/ingest \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"prefix": "documents/test/", "wait_for_completion": true}'
```

## Monitoring and Logs

- View Cloud Run logs:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=rag-ingestion-service" --limit=10
  ```

- View Cloud Scheduler job history:
  ```bash
  gcloud scheduler jobs describe rag-daily-ingestion --location=us-central1
  ```

## Troubleshooting

- **Authentication Issues**: Check the service account permissions
- **Timeouts**: Adjust the Cloud Run timeout setting if ingestion takes longer
- **Memory Errors**: Increase the memory allocation for the Cloud Run service
- **Missing Files**: Verify the GCS bucket and prefix are correct