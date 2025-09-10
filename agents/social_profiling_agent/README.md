## Setup and Deployment
## Step 1: Install Python Dependencies
Create a virtual environment and install the required packages.

```aiexclude
# From your project root directory
python -m venv env
source env/bin/activate
pip install -r agents/social_profiling_agent/requirements.txt
```

## Step 2: Deploy the MCP Toolbox Server
First, we will deploy the service that makes your tools.yaml available over the network.

Prerequisites
- You are in your project's root directory (google-photos-agent).
- Your tools.yaml file is located at agents/social_profiling_agent/tools.yaml.
- Your gcloud CLI is authenticated and configured with the correct project.

#### Deployment Steps:
1. Create a Google Cloud Secret from tools.yaml: This securely stores your tool definitions.
```aiexclude
gcloud secrets create social-profiling-tools --data-file=agents/social_profiling_agent/tools.yaml
```

2. Define Service Account: Create a dedicated identity for the toolbox service.
```aiexclude
gcloud iam service-accounts create toolbox-identity
```

3. Grant Permissions: Allow the service account to access the secret and connect to Spanner.
```aiexclude
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member serviceAccount:toolbox-identity@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member serviceAccount:toolbox-identity@$PROJECT_ID.iam.gserviceaccount.com \
  --role roles/spanner.databaseUser
```

4. Deploy to Cloud Run: Deploy the official, pre-built toolbox container image.
```aiexclude
# The name for the toolbox service
export TOOLBOX_SERVICE_NAME="social-profiling-toolbox"

# Official container image for the MCP Toolbox
export TOOLBOX_IMAGE="us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest"

gcloud run deploy ${TOOLBOX_SERVICE_NAME} \
  --image=${TOOLBOX_IMAGE} \
  --service-account="toolbox-identity@$PROJECT_ID.iam.gserviceaccount.com" \
  --region="${REGION}" \
  --set-secrets="/app/tools.yaml=social-profiling-tools:latest" \
  --args="--tools_file=/app/tools.yaml,--address=0.0.0.0,--port=8080" \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"

echo "✅ MCP Toolbox Server deployed."
```

5. Get the Toolbox URL: Once deployed, retrieve and save the URL of the toolbox service. We will need it for the next step.
```aiexclude
export TOOLBOX_URL=$(gcloud run services describe ${TOOLBOX_SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')
echo "MCP Toolbox is running at: ${TOOLBOX_URL}"
```


## Step 3: Deploy the Social Profiling Agent A2A Service
Now, we will deploy the agent itself, which will connect to the toolbox service we just launched.

#### Prerequisites
- You have successfully completed Part 1.
- The TOOLBOX_URL environment variable is set in your shell.

#### Deployment Steps
1. Create Service Account: Create a dedicated identity for the agent service itself.
```aiexclude
gcloud iam service-accounts create social-profiling-identity
```

2. Grant Invoker Permission: Allow the agent's service account to call the toolbox service.
```aiexclude
gcloud run services add-iam-policy-binding ${TOOLBOX_SERVICE_NAME} \
    --member="serviceAccount:social-profiling-identity@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region="${REGION}"
```

3. Build and Deploy the Agent: Run the deployment script from your project's root directory. This script now uses the new service account and includes the fixes.
```aiexclude
#!/bin/bash

# --- Agent-Specific Variables ---
export AGENT_NAME="social_profiling_agent"
export IMAGE_NAME="social-profiling-agent"
export SERVICE_NAME="social-profiling-agent"
export IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:latest"
export PUBLIC_URL="https://$(echo ${SERVICE_NAME} | sed 's/_/-/g')-$(echo $PROJECT_NUMBER).$(echo $REGION).run.app"

# --- 1. Build Container ---
echo "Building container for ${AGENT_NAME}..."
gcloud builds submit . \
  --config="agents/social_profiling_agent/cloudbuild.yaml" \
  --project="${PROJECT_ID}" \
  --substitutions=_IMAGE_PATH="${IMAGE_PATH}"

echo "✅ Image built: ${IMAGE_PATH}"

# --- 2. Deploy Container to Cloud Run ---
echo "Deploying ${SERVICE_NAME} to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_PATH}" \
  --service-account="social-profiling-identity@${PROJECT_ID}.iam.gserviceaccount.com" \
  --platform=managed \
  --region="${REGION}" \
  --allow-unauthenticated \
  --project="${PROJECT_ID}" \
  --min-instances=1 \
  --set-env-vars="A2A_HOST=0.0.0.0" \
  --set-env-vars="A2A_PORT=8080" \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=${REGION}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars="PUBLIC_URL=${PUBLIC_URL}" \
  --set-env-vars="TOOLBOX_URL=${TOOLBOX_URL}"

echo "✅ Deployment complete."
echo "Agent is running at: $(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')"
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

