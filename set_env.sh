#!/bin/bash

# This script sets various Google Cloud related environment variables.
# It must be SOURCED to make the variables available in your current shell.
# Example: source ./set_env.sh

# --- Configuration ---
PROJECT_FILE="~/project_id.txt"
SPANNER_INSTANCE_ID="google-photos-instance"
SPANNER_DATABASE_ID="google-photos"
GOOGLE_CLOUD_LOCATION="us-central1"
REPO_NAME="google-photos-repo"
# ---------------------

echo "--- Setting Google Cloud Environment Variables ---"

# --- Authentication Check ---
echo "Checking gcloud authentication status..."
# For local development with the social-profiling-agent, we use Application Default Credentials
# Check if the user is logged in for ADC
if gcloud auth application-default print-access-token > /dev/null 2>&1; then
  echo "gcloud is authenticated with Application Default Credentials."
else
  echo "Warning: gcloud not authenticated for Application Default Credentials."
  echo "Please run 'gcloud auth application-default login' for local agent testing."
fi
# --- --- --- --- --- ---


# 1. Check if project file exists
PROJECT_FILE_PATH=$(eval echo $PROJECT_FILE) # Expand potential ~
if [ ! -f "$PROJECT_FILE_PATH" ]; then
  echo "Error: Project file not found at $PROJECT_FILE_PATH"
  echo "Please create $PROJECT_FILE_PATH containing your Google Cloud project ID."
  return 1 # Return 1 as we are sourcing
fi

# 2. Set the default gcloud project configuration
PROJECT_ID_FROM_FILE=$(cat "$PROJECT_FILE_PATH")
echo "Setting gcloud config project to: $PROJECT_ID_FROM_FILE"
# Adding --quiet; set -e will handle failure if the project doesn't exist or access is denied
gcloud config set project "$PROJECT_ID_FROM_FILE" --quiet

# 3. Export PROJECT_ID (Get from config to confirm it was set correctly)
export PROJECT_ID=$(gcloud config get project)
echo "Exported PROJECT_ID=$PROJECT_ID"

# 4. Export PROJECT_NUMBER
# Using --format to extract just the projectNumber value
export PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
echo "Exported PROJECT_NUMBER=$PROJECT_NUMBER"

# 5. Unset GOOGLE_APPLICATION_CREDENTIALS for local development
# This ensures that the Application Default Credentials are used.
echo "Unsetting GOOGLE_APPLICATION_CREDENTIALS for local agent development."
unset GOOGLE_APPLICATION_CREDENTIALS


# 5. Export SERVICE_ACCOUNT_NAME (Default Compute Service Account)
export SERVICE_ACCOUNT_NAME=$(gcloud compute project-info describe --format="value(defaultServiceAccount)")
if [ -z "$SERVICE_ACCOUNT_NAME" ]; then
  echo "Error: Could not determine the default Compute Engine service account."
  echo "This can happen if the Compute Engine API has not been used in this project yet."
  echo "Please try enabling the API and waiting a few minutes, or create a dedicated service account."
  return 1
else
  echo "Exported SERVICE_ACCOUNT_NAME=$SERVICE_ACCOUNT_NAME"
fi

# 6. Create Service Account Key
if [ -z "$SERVICE_ACCOUNT_NAME" ]; then
  echo "Error: SERVICE_ACCOUNT_NAME is not set. Cannot create a key."
  return 1
fi

KEY_FILE=~/key.json

echo "Checking for existing key file at $KEY_FILE..."
if [ -f "$KEY_FILE" ]; then
  echo "Key file already exists. Skipping creation."
else
  echo "Creating new service account key..."
  gcloud iam service-accounts keys create "$KEY_FILE" --iam-account="$SERVICE_ACCOUNT_NAME"
fi

# 7. Copy key to google-photos directory
cp $KEY_FILE google-photos/key.json

# 8. Export GOOGLE_APPLICATION_CREDENTIALS
export GOOGLE_APPLICATION_CREDENTIALS="$KEY_FILE"
echo "Exported GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS"

# 9. Export SPANNER_INSTANCE_ID
# Use the variable defined in the configuration section
export SPANNER_INSTANCE_ID="$SPANNER_INSTANCE_ID"
echo "Exported SPANNER_INSTANCE_ID=$SPANNER_INSTANCE_ID"

# 10. Export SPANNER_DATABASE_ID
# Use the variable defined in the configuration section
export SPANNER_DATABASE_ID="$SPANNER_DATABASE_ID"
echo "Exported SPANNER_DATABASE_ID=$SPANNER_DATABASE_ID"

# 11. Export GOOGLE_CLOUD_PROJECT (Often used by client libraries)
# This is usually the same as PROJECT_ID
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
echo "Exported GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"

# 12. Export GOOGLE_GENAI_USE_VERTEXAI
export GOOGLE_GENAI_USE_VERTEXAI="TRUE"
echo "Exported GOOGLE_GENAI_USE_VERTEXAI=$GOOGLE_GENAI_USE_VERTEXAI"

# 13. Export GOOGLE_CLOUD_LOCATION
export GOOGLE_CLOUD_LOCATION="$GOOGLE_CLOUD_LOCATION"
echo "Exported GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION"

# 14. Export REPO_NAME
export REPO_NAME="$REPO_NAME"
echo "Exported REPO_NAME=$REPO_NAME"

# 16. Export REGION
export REGION="$GOOGLE_CLOUD_LOCATION"
echo "Exported REGION=$GOOGLE_CLOUD_LOCATION"

echo "--- Environment setup complete ---"