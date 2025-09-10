```aiexclude
. ~/google-photos-agent/set_env.sh

cd ~/google-photos-agent/agents

```

# Set variables specific to the MEMORY agent

```aiexclude
export IMAGE_TAG="latest"
export AGENT_NAME="memory_agent"
export IMAGE_NAME="memory-agent"
export IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"
export SERVICE_NAME="memory-agent"
export PUBLIC_URL="https://memory-agent-${PROJECT_NUMBER}.${REGION}.run.app"

echo "Building ${AGENT_NAME} agent..."
gcloud builds submit . \
  --config=cloudbuild-build.yaml \
  --project=${PROJECT_ID} \
  --region=${REGION} \
  --substitutions=_AGENT_NAME=${AGENT_NAME},_IMAGE_PATH=${IMAGE_PATH}

echo "Image built and pushed to: ${IMAGE_PATH}"
```


. ~/google-photos-agent/set_env.sh

cd ~/google-photos-agent/agents

# Set variables specific to the MEMORY agent

```aiexclude
export IMAGE_TAG="latest"
export AGENT_NAME="memory_agent"
export IMAGE_NAME="memory-agent"
export IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"
export SERVICE_NAME="memory-agent"
export PUBLIC_URL="https://memory-agent-${PROJECT_NUMBER}.${REGION}.run.app"


gcloud run deploy ${SERVICE_NAME} \
  --image=${IMAGE_PATH} \
  --platform=managed \
  --region=${REGION} \
  --set-env-vars="A2A_HOST=0.0.0.0" \
  --set-env-vars="A2A_PORT=8080" \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=${REGION}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --set-env-vars="PUBLIC_URL=${PUBLIC_URL}" \
  --allow-unauthenticated \
  --project=${PROJECT_ID} \
  --min-instances=1

```

```aiexclude
export SERVICE_ACCOUNT_NAME=$(gcloud compute project-info describe --format="value(defaultServiceAccount)")
gcloud storage buckets add-iam-policy-binding gs://photos-agent       --member=serviceAccount:$SERVICE_ACCOUNT_NAME      --role=roles/storage.objectCreator
gcloud storage buckets add-iam-policy-binding gs://photos-agent       --member=serviceAccount:$SERVICE_ACCOUNT_NAME      --role=roles/storage.objectViewer
```
