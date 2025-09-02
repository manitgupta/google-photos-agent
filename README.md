# google-photos-agent
Sample project to demonstrate a request based agent that generates custom memories for you.

# Set up

### Run init 

```aiexclude
chmod +x ~/google-photos-agent/init.sh
chmod +x ~/google-photos-agent/set_env.sh
```

```aiexclude
cd ~/google-photos-agent
./init.sh
```

### Set project ID

```aiexclude
gcloud config set project $(cat ~/project_id.txt) --quiet
```

### Enable services

```
gcloud services enable  run.googleapis.com \
                        cloudfunctions.googleapis.com \
                        cloudbuild.googleapis.com \
                        artifactregistry.googleapis.com \
                        spanner.googleapis.com \
                        apikeys.googleapis.com \
                        iam.googleapis.com \
                        compute.googleapis.com \
                        aiplatform.googleapis.com \
                        cloudresourcemanager.googleapis.com
```

### Set env variables

```
export PROJECT_ID=$(gcloud config get project)
export PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
export SERVICE_ACCOUNT_NAME=$(gcloud compute project-info describe --format="value(defaultServiceAccount)")
export SPANNER_INSTANCE_ID="google-photos-instance"
export SPANNER_DATABASE_ID="google-photos"
export GOOGLE_CLOUD_PROJECT=$(gcloud config get project)
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_LOCATION="us-central1"
```

or for fish terminal 

```aiexclude
set -gx PROJECT_ID (gcloud config get project)
set -gx PROJECT_NUMBER (gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
set -gx SERVICE_ACCOUNT_NAME (gcloud compute project-info describe --format="value(defaultServiceAccount)")
set -gx SPANNER_INSTANCE_ID "google-photos-instance"
set -gx SPANNER_DATABASE_ID "google-photos"
set -gx GOOGLE_CLOUD_PROJECT (gcloud config get project)
set -gx GOOGLE_GENAI_USE_VERTEXAI TRUE
set -gx GOOGLE_CLOUD_LOCATION "us-central1"
```

### Enable permissions

```
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/spanner.admin"

# Spanner Database User
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/spanner.databaseUser"

# Artifact Registry Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/artifactregistry.admin"

# Cloud Build Editor
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/cloudbuild.builds.editor"

# Cloud Run Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/run.admin"

# IAM Service Account User
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/iam.serviceAccountUser"

# Vertex AI User
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/aiplatform.user"

# Logging Writer (to allow writing logs)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/logging.logWriter"


gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_NAME" \
  --role="roles/logging.viewer"

```

### Create Artifact repo 

```aiexclude
export REPO_NAME="google-photos-repo"
gcloud artifacts repositories create $REPO_NAME \
  --repository-format=docker \
  --location=us-central1 \
  --description="Docker repository for Google Photos Memory Agent"
```

### Setup graph database

```aiexclude
. ~/google-photos-agent/set_env.sh
```

```aiexclude
gcloud spanner instances create $SPANNER_INSTANCE_ID \
  --config=regional-us-central1 \
  --description="Google Photos Instance" \
  --processing-units=100 \
  --edition=ENTERPRISE
  ```

```
gcloud spanner databases create $SPANNER_DATABASE_ID \
  --instance=$SPANNER_INSTANCE_ID \
  --database-dialect=GOOGLE_STANDARD_SQL
```

### Spanner permissions

```aiexclude
echo "Granting Spanner read/write access to ${SERVICE_ACCOUNT_NAME} for database ${SPANNER_DATABASE_ID}..."

gcloud spanner databases add-iam-policy-binding ${SPANNER_DATABASE_ID} \
  --instance=${SPANNER_INSTANCE_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}" \
  --role="roles/spanner.databaseUser" \
  --project=${PROJECT_ID}
```

### Setup Python env and load mock data

```aiexclude
source ~/google-photos-agent/set_env.sh
cd ~/google-photos-agent
python -m venv env
source env/bin/activate
pip install -r requirements.txt
cd google-photos
python setup.py
```

or for fish terminal 

```aiexclude
source ~/google-photos-agent/set_env_fish.sh
cd ~/google-photos-agent
python -m venv env
source env/bin/activate.fish
pip install -r requirements.txt
cd google-photos
python setup.py
```

Note: Verify if `set_env.sh` has correctly set the environment variables!
