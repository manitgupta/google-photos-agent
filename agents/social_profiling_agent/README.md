## Setup and Deployment
### Step 1: Install Python Dependencies
Create a virtual environment and install the required packages.

```aiexclude
# From your project root directory
python -m venv env
source env/bin/activate
pip install -r agents/social_profiling_agent/requirements.txt
```

### Step 2: Create cloudbuild.yaml
The deployment script requires a Cloud Build configuration file. Create a file named cloudbuild.yaml inside the social-profiling-agent/ directory with the following content:

```aiexclude
# social-profiling-agent/cloudbuild.yaml
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', '${_IMAGE_PATH}', '--file=social-profiling-agent/Dockerfile', '.']
images:
- '${_IMAGE_PATH}'
```

### Step 3: Build and Deploy the Agent to Cloud Run
The following script will containerize the agent using its Dockerfile, push the image to Google Artifact Registry, and deploy it as a secure Cloud Run service.

```aiexclude
#!/bin/bash

# --- Configuration ---
# Ensure these environment variables are set in your shell
# source ./set_env.sh 

# --- Agent-Specific Variables ---
export AGENT_NAME="social-profiling-agent"
export IMAGE_NAME="social-profiling-agent"
export SERVICE_NAME="social-profiling-agent"

export IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:latest"
# Note: The PROJECT_NUMBER is required for the default Cloud Run URL format
export PUBLIC_URL="https://$(echo $SERVICE_NAME)-$(echo $PROJECT_NUMBER)-$(echo $REGION).run.app"


# --- 1. Build the Docker Image using Cloud Build ---
echo "Building container for ${AGENT_NAME}..."
# This assumes you have a cloudbuild.yaml in the agent directory
gcloud builds submit . \
  --config="agents/social_profiling_agent/cloudbuild.yaml" \
  --project="${PROJECT_ID}" \
  --substitutions=_IMAGE_PATH="${IMAGE_PATH}"

echo "✅ Image built and pushed to: ${IMAGE_PATH}"


# --- 2. Deploy the Container to Cloud Run ---
echo "Deploying ${SERVICE_NAME} to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_PATH}" \
  --platform=managed \
  --region="${REGION}" \
  --allow-unauthenticated \
  --project="${PROJECT_ID}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars="SPANNER_INSTANCE_ID=${SPANNER_INSTANCE_ID}" \
  --set-env-vars="SPANNER_DATABASE_ID=${SPANNER_DATABASE_ID}" \
  --set-env-vars="PUBLIC_URL=${PUBLIC_URL}"

echo "✅ Deployment complete."
echo "Agent is now running at: $(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')"

```

## Verification
Once deployed, you can verify that the agent is running correctly using the A2A Inspector tool or curl.

### Get Service URL
```aiexclude
gcloud run services describe social-profiling-agent \
  --platform managed \
  --region YOUR_REGION \
  --format 'value(status.url)'

```

### Check Agent Card with curl
```aiexclude
curl YOUR_SERVICE_URL/.well-known/agent.json | jq

```

This should return the JSON AgentCard defined in a2a_server.py.

### Test with A2A Inspector
1. Open the A2A Inspector UI.
2. Paste your service URL and click Connect.
3. Go to the Chat tab.
4. Send a valid message, for example:
```aiexclude
The logged in user is Rohan. Find photos of my family in Goa, India.
```
The agent should respond with a JSON object containing the photo details from your Spanner database.

