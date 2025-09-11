```aiexclude
. ~/google-photos-agent/set_env.sh
cd ~/google-photos-agent/tools/google-photos
```

```aiexclude
export IMAGE_TAG="latest"
export MCP_IMAGE_NAME="mcp-tool-server"
export IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${MCP_IMAGE_NAME}:${IMAGE_TAG}"
export SERVICE_NAME="photos-tool-server"
export GOOGLE_PHOTOS_BASE_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep google-photos-agent)

gcloud builds submit . \
  --tag=${IMAGE_PATH} \
  --project=${PROJECT_ID}

```

```aiexclude
gcloud run deploy ${SERVICE_NAME} \
  --image=${IMAGE_PATH} \
  --platform=managed \
  --region=${REGION} \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_PHOTOS_BASE_URL=${GOOGLE_PHOTOS_BASE_URL}" \
  --set-env-vars="APP_HOST=0.0.0.0" \
  --set-env-vars="APP_PORT=8080" \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=${REGION}" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --project=${PROJECT_ID} \
  --min-instances=1

export MCP_SERVER_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep photos-tool-server)/sse
```