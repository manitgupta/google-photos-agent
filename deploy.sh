#!/bin/bash

# Exit on error
set -e

# Source environment variables
. ./set_env.sh

# Set image and service details
export IMAGE_NAME="google-photos-webapp"
export IMAGE_TAG="latest"
export IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"
export SERVICE_NAME="google-photos-agent"

# Submit the build to Cloud Build
echo "Submitting build..."
gcloud builds submit . --config cloudbuild.yaml \
  --substitutions=_REGION=${REGION},_REPO_NAME=${REPO_NAME},_IMAGE_NAME=${IMAGE_NAME},_TAG_NAME=${IMAGE_TAG} \
  --project=${PROJECT_ID}

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image=${IMAGE_PATH} \
  --platform=managed \
  --region=${REGION} \
  --allow-unauthenticated \
  --set-env-vars="SPANNER_INSTANCE_ID=${SPANNER_INSTANCE_ID}" \
  --set-env-vars="SPANNER_DATABASE_ID=${SPANNER_DATABASE_ID}" \
  --set-env-vars="APP_HOST=0.0.0.0" \
  --set-env-vars="APP_PORT=8080" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=${REGION}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=/app/key.json" \
  --project=${PROJECT_ID} \
  --min-instances=1

echo "Deployment complete."