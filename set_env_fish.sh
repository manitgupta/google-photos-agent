#!/usr/bin/fish

# This script sets various Google Cloud related environment variables.
# It must be SOURCED to make the variables available in your current shell.
# Example: source ./set_env_fish.sh

# --- Configuration ---
set PROJECT_FILE "~/project_id.txt"
set SPANNER_INSTANCE_ID "google-photos-instance"
set SPANNER_DATABASE_ID "google-photos"
set GOOGLE_CLOUD_LOCATION "us-central1"
set REPO_NAME "google-photos-repo"
# ---------------------

echo "--- Setting Google Cloud Environment Variables ---"

# --- Authentication Check ---
echo "Checking gcloud authentication status..."
# Run a command that requires authentication (like listing accounts or printing a token)
# Redirect stdout and stderr to /dev/null so we don't see output unless there's a real error
if gcloud auth print-access-token > /dev/null 2>&1
  echo "gcloud is authenticated."
else
  echo "Error: gcloud is not authenticated."
  echo "Please log in by running: gcloud auth login"
  # Use 'return 1' instead of 'exit 1' because the script is meant to be sourced.
  # 'exit 1' would close your current terminal session.
  return 1
end
# --- --- --- --- --- ---

# 1. Check if project file exists
set PROJECT_FILE_PATH (eval echo $PROJECT_FILE) # Expand potential ~
if not test -f "$PROJECT_FILE_PATH"
  echo "Error: Project file not found at $PROJECT_FILE_PATH"
  echo "Please create $PROJECT_FILE_PATH containing your Google Cloud project ID."
  return 1 # Return 1 as we are sourcing
end

# 2. Set the default gcloud project configuration
set PROJECT_ID_FROM_FILE (cat "$PROJECT_FILE_PATH")
echo "Setting gcloud config project to: $PROJECT_ID_FROM_FILE"
# Adding --quiet; set -e will handle failure if the project doesn't exist or access is denied
gcloud config set project "$PROJECT_ID_FROM_FILE" --quiet

# 3. Export PROJECT_ID (Get from config to confirm it was set correctly)
set -x PROJECT_ID (gcloud config get project)
echo "Exported PROJECT_ID=$PROJECT_ID"

# 4. Export PROJECT_NUMBER
# Using --format to extract just the projectNumber value
set -x PROJECT_NUMBER (gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
echo "Exported PROJECT_NUMBER=$PROJECT_NUMBER"

# 5. Export SERVICE_ACCOUNT_NAME (Default Compute Service Account)
set -x SERVICE_ACCOUNT_NAME (gcloud compute project-info describe --format="value(defaultServiceAccount)")
if test -z "$SERVICE_ACCOUNT_NAME"
  echo "Error: Could not determine the default Compute Engine service account."
  echo "This can happen if the Compute Engine API has not been used in this project yet."
  echo "Please try enabling the API and waiting a few minutes, or create a dedicated service account."
  return 1
else
  echo "Exported SERVICE_ACCOUNT_NAME=$SERVICE_ACCOUNT_NAME"
end

# 6. Export SPANNER_INSTANCE_ID
# Use the variable defined in the configuration section
set -x SPANNER_INSTANCE_ID "$SPANNER_INSTANCE_ID"
echo "Exported SPANNER_INSTANCE_ID=$SPANNER_INSTANCE_ID"

# 7. Export SPANNER_DATABASE_ID
# Use the variable defined in the configuration section
set -x SPANNER_DATABASE_ID "$SPANNER_DATABASE_ID"
echo "Exported SPANNER_DATABASE_ID=$SPANNER_DATABASE_ID"

# 8. Export GOOGLE_CLOUD_PROJECT (Often used by client libraries)
# This is usually the same as PROJECT_ID
set -x GOOGLE_CLOUD_PROJECT "$PROJECT_ID"
echo "Exported GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"

# 9. Export GOOGLE_GENAI_USE_VERTEXAI
set -x GOOGLE_GENAI_USE_VERTEXAI "TRUE"
echo "Exported GOOGLE_GENAI_USE_VERTEXAI=$GOOGLE_GENAI_USE_VERTEXAI"

# 10. Export GOOGLE_CLOUD_LOCATION
set -x GOOGLE_CLOUD_LOCATION "$GOOGLE_CLOUD_LOCATION"
echo "Exported GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION"

# 11. Export REPO_NAME
set -x REPO_NAME "$REPO_NAME"
echo "Exported REPO_NAME=$REPO_NAME"

# 12. Export REGION
set -x REGION "$GOOGLE_CLOUD_LOCATION"
echo "Exported REGION=$GOOGLE_CLOUD_LOCATION"

echo "--- Environment setup complete ---"