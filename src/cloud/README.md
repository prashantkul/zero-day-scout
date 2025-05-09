# Scheduled RAG Ingestion on Google Cloud Run

This guide explains how to set up a scheduled RAG document ingestion service on Google Cloud Run, triggered by Cloud Scheduler, using Cloud Build for automated deployment.

## Architecture

The solution consists of:

1. **Cloud Build**: Automates the deployment process
2. **Cloud Run Service**: A containerized service that ingests documents from GCS into the RAG corpus
3. **Cloud Scheduler**: A cron job that triggers the ingestion service on a schedule
4. **Service Account**: For authentication and authorization
5. **Container Registry**: To store the container image

## Prerequisites

- Google Cloud account and project
- Required permissions:
  - Cloud Build Editor
  - Cloud Run Admin
  - Cloud Scheduler Admin
  - Service Account User
  - Storage Admin
  - Vertex AI User
- gcloud CLI installed and configured

## Deployment Process (Two-Step)

We've divided the deployment into two separate steps to avoid any issues with Cloud Build variable substitutions:

1. **Deploy the RAG ingestion service to Cloud Run**
2. **Create a Cloud Scheduler job to trigger regular ingestion**

This two-step approach is specifically designed to avoid Cloud Build variable substitution errors that can occur when trying to use the SERVICE_URL variable in the Cloud Build configuration.

### Step 1: Deploy the Service

Use the setup script which:
- Enables all required APIs
- Sets up necessary service account permissions
- Triggers the Cloud Build deployment for the Cloud Run service

```bash
# Make scripts executable (if needed)
chmod +x src/cloud/*.sh

# Run with default settings (us-central1 region)
./src/cloud/setup_and_deploy.sh

# Or customize the region
./src/cloud/setup_and_deploy.sh --region=us-west1
```

Available options:
- `--region`: GCP region (default: us-central1)

### Step 2: Set Up Cloud Scheduler

Once the service is deployed, set up a Cloud Scheduler job to trigger it regularly:

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe rag-ingestion-service --region=us-central1 --format='value(status.url)')

# Create the scheduler job with default settings
./src/cloud/create_scheduler.sh --url=$SERVICE_URL

# Or customize the scheduler
./src/cloud/create_scheduler.sh --url=$SERVICE_URL --schedule="*/10 8-17 * * *" --prefix="research_papers/"
```

Available options:
- `--url`: Service URL (required)
- `--region`: GCP region (default: us-central1)
- `--job-name`: Scheduler job name (default: rag-daily-ingestion)
- `--schedule`: Cron schedule (default: */10 8-17 * * *  Minute: Every 10 minutes and Hour: From 8 to 17 PDT)
- `--prefix`: GCS path prefix (default: none, which ingests all files)
- `--time-zone`: Timezone (default: America/Los_Angeles)

## Manual Setup (Alternative)

If you prefer to run the steps manually:

1. Enable required APIs:

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  aiplatform.googleapis.com
```

2. Grant Cloud Build service account the necessary permissions:

```bash
# Get the Cloud Build service account
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CLOUD_BUILD_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/cloudscheduler.admin"
```

3. Deploy with Cloud Build:

```bash
# From project root directory
gcloud builds submit --config=src/cloud/cloudbuild-deploy.yaml --substitutions=_REGION=us-central1 .
```

4. Create a Cloud Scheduler job:

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe rag-ingestion-service --region=us-central1 --format='value(status.url)')

# Create a scheduler job
gcloud scheduler jobs create http rag-daily-ingestion \
  --schedule="0 2 * * *" \
  --uri="${SERVICE_URL}/ingest" \
  --http-method=POST \
  --oidc-service-account-email=rag-ingestion-service@$PROJECT_ID.iam.gserviceaccount.com \
  --message-body='{"wait_for_completion": false}' \
  --location=us-central1 \
  --time-zone=America/Los_Angeles
```

## Cloud Build Configuration

The Cloud Build deployment (`cloudbuild-deploy.yaml`) includes:

- Building and pushing the Docker container image
- Creating the service account if it doesn't exist
- Deploying the service to Cloud Run
- Displaying the service URL for subsequent scheduler setup

## Ingestion API

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
  -d '{"wait_for_completion": true}'
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

### General Issues

- **Authentication Issues**: Check the service account permissions
- **Timeouts**: Adjust the Cloud Run timeout setting if ingestion takes longer
- **Memory Errors**: Increase the memory allocation for the Cloud Run service
- **Missing Files**: Verify the GCS bucket and prefix are correct

### Cloud Build Substitution Errors

If you encounter an error like:
```
ERROR: (gcloud.builds.submit) INVALID_ARGUMENT: generic::invalid_argument: invalid value for 'build.substitutions': key in the template "SERVICE_URL" is not a valid built-in substitution
```

This happens because Cloud Build only supports specific predefined substitution variables, plus custom variables that start with underscore (like `_REGION`). 

Our solution:
1. We've simplified the Cloud Build configuration to avoid using `SERVICE_URL` as a substitution variable
2. We've split the deployment into two separate steps:
   - First deploy the service using Cloud Build
   - Then retrieve the service URL and set up the scheduler manually

If you still encounter substitution issues:
- Ensure you're using the latest version of the deployment scripts
- Double-check that the Cloud Build configuration doesn't use any undefined substitution variables
- Only use built-in variables like `$PROJECT_ID`, `$BUILD_ID`, etc., or custom variables starting with underscore (e.g., `${_REGION}`)