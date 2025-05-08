#!/bin/bash
# Script to deploy the RAG ingestion service to Cloud Run

# Set variables
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="rag-ingestion-service"
SERVICE_ACCOUNT="${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:$(date +%Y%m%d-%H%M%S)"

# Print configuration
echo "Deploying RAG ingestion service with the following configuration:"
echo "  Project ID: ${PROJECT_ID}"
echo "  Region: ${REGION}"
echo "  Service Name: ${SERVICE_NAME}"
echo "  Service Account: ${SERVICE_ACCOUNT}"
echo "  Image Name: ${IMAGE_NAME}"
echo ""

# Check if service account exists, create if it doesn't
if ! gcloud iam service-accounts describe ${SERVICE_ACCOUNT} &>/dev/null; then
    echo "Creating service account ${SERVICE_ACCOUNT}..."
    gcloud iam service-accounts create ${SERVICE_NAME} \
      --description="Service account for RAG ingestion service" \
      --display-name="RAG Ingestion Service"
    
    # Grant required permissions
    echo "Granting required permissions..."
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
      --member="serviceAccount:${SERVICE_ACCOUNT}" \
      --role="roles/storage.admin"
    
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
      --member="serviceAccount:${SERVICE_ACCOUNT}" \
      --role="roles/aiplatform.user"
else
    echo "Service account ${SERVICE_ACCOUNT} already exists."
fi

# Build the container image
echo "Building container image..."
docker build -t ${IMAGE_NAME} .

# Push to Container Registry
echo "Pushing image to Container Registry..."
docker push ${IMAGE_NAME}

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image=${IMAGE_NAME} \
  --region=${REGION} \
  --platform=managed \
  --memory=2Gi \
  --cpu=1 \
  --timeout=540s \
  --max-instances=10 \
  --min-instances=0 \
  --service-account=${SERVICE_ACCOUNT} \
  --set-env-vars=PROJECT_ID=${PROJECT_ID} \
  --no-allow-unauthenticated

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)')
echo "Service deployed at: ${SERVICE_URL}"

# Ask about creating a scheduler job
read -p "Do you want to create a Cloud Scheduler job to trigger this service? (y/n) " CREATE_SCHEDULER
if [[ "${CREATE_SCHEDULER}" == "y" ]]; then
    # Setup for scheduler job
    JOB_NAME="rag-daily-ingestion"
    
    # Ask for schedule
    read -p "Enter cron schedule (default: 0 2 * * * - run at 2 AM daily): " SCHEDULE
    SCHEDULE=${SCHEDULE:-"0 2 * * *"}
    
    # Ask for GCS prefix
    read -p "Enter GCS path prefix to use for ingestion (default: documents/): " PREFIX
    PREFIX=${PREFIX:-"documents/"}
    
    # Create scheduler job
    echo "Creating Cloud Scheduler job with schedule: ${SCHEDULE}"
    if gcloud scheduler jobs describe ${JOB_NAME} --location=${REGION} &>/dev/null; then
        # Update existing job
        gcloud scheduler jobs update http ${JOB_NAME} \
          --schedule="${SCHEDULE}" \
          --uri="${SERVICE_URL}/ingest" \
          --http-method=POST \
          --oidc-service-account-email=${SERVICE_ACCOUNT} \
          --message-body="{\"prefix\": \"${PREFIX}\", \"wait_for_completion\": false}" \
          --location=${REGION} \
          --time-zone=America/Los_Angeles
    else
        # Create new job
        gcloud scheduler jobs create http ${JOB_NAME} \
          --schedule="${SCHEDULE}" \
          --uri="${SERVICE_URL}/ingest" \
          --http-method=POST \
          --oidc-service-account-email=${SERVICE_ACCOUNT} \
          --message-body="{\"prefix\": \"${PREFIX}\", \"wait_for_completion\": false}" \
          --location=${REGION} \
          --time-zone=America/Los_Angeles
    fi
    
    echo "Cloud Scheduler job '${JOB_NAME}' created/updated successfully."
fi

echo ""
echo "Deployment complete!"
echo ""
echo "To test the service, run:"
echo "TOKEN=\$(gcloud auth print-identity-token)"
echo "curl -X POST ${SERVICE_URL}/ingest \\"
echo "  -H \"Authorization: Bearer \${TOKEN}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"prefix\": \"documents/test/\", \"wait_for_completion\": true}'"