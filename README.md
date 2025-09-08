# google-photos-agent
Sample project to demonstrate a request based agent that generates custom memories for you.

# Project Setup

This section covers the one-time setup for your Google Cloud project.

### 1. Initialize the Environment

Run the initialization script and source the environment setup file. This will set essential environment variables for subsequent commands.

```bash
# From the project root directory
chmod +x ./init.sh
chmod +x ./set_env.sh
./init.sh
source ./set_env.sh
```

### 2. Set Project ID

Ensure your gcloud CLI is configured to use your correct Google Cloud project.

```bash
gcloud config set project $(cat ~/project_id.txt) --quiet
```

### 3. Enable Google Cloud Services

Enable all the necessary APIs for the application to function.

```bash
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

### 4. Set Up Spanner Database

Create the Spanner instance and database required for the application.

```bash
# Create the Spanner Instance
gcloud spanner instances create $SPANNER_INSTANCE_ID \
  --config=regional-us-central1 \
  --description="Google Photos Instance" \
  --processing-units=100 \
  --edition=ENTERPRISE

# Create the Spanner Database
gcloud spanner databases create $SPANNER_DATABASE_ID \
  --instance=$SPANNER_INSTANCE_ID \
  --database-dialect=GOOGLE_STANDARD_SQL
```

# Local Development

This section explains how to run the complete application (Flask frontend and ADK agent) on your local machine. This requires two terminal windows.

### 1. Prerequisites

Complete these steps before running the application.

**A. Authenticate for Local Development**

The agent calls Google AI models using your personal user credentials. Authenticate with gcloud and grant your user the necessary Spanner permissions.

```bash
# Log in with Application Default Credentials
gcloud auth application-default login

# Grant your user account Spanner access
# Replace [YOUR_EMAIL_ACCOUNT] with the email you used to log in
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:[YOUR_EMAIL_ACCOUNT]" \
    --role="roles/spanner.databaseUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:[YOUR_EMAIL_ACCOUNT]" \
    --role="roles/spanner.databaseReader"
```
**Note:** The `set_env.sh` script is configured to unset the `GOOGLE_APPLICATION_CREDENTIALS` variable, which is required for this authentication method to work correctly.

**B. Install Python Dependencies**

Set up a virtual environment and install the required packages.

```bash
# From the project root directory
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

**C. Load Mock Data**

Run the setup script to populate the Spanner database and upload a sample image to Cloud Storage.

```bash
# From the project root directory
cd google-photos
python setup.py
cd .. 
```

**D. Download and Configure the Agent Toolbox**

The agent relies on the MCP Toolbox to interact with its tools.

1.  **Download the Toolbox Binary:** From the `agents/social-profiling-agent` directory, run the command for your OS.

    *   **macOS (Apple Silicon):**
        ```bash
        curl -L -o toolbox https://storage.googleapis.com/genai-toolbox/v0.8.0/darwin/arm64/toolbox
        chmod +x toolbox
        ```
    *   **macOS (Intel):**
        ```bash
        curl -L -o toolbox https://storage.googleapis.com/genai-toolbox/v0.8.0/darwin/amd64/toolbox
        chmod +x toolbox
        ```
    *   **Linux (x86_64):**
        ```bash
        curl -L -o toolbox https://storage.googleapis.com/genai-toolbox/v0.8.0/linux/amd64/toolbox
        chmod +x toolbox
        ```

### 2. Running the Application

**A. Terminal 1: Start the Toolbox Server**

This server allows the agent to execute its tools.

```bash
# cd into the agent directory
cd google-photos/social-profiling-agent

# Start the server
./toolbox --tools-file "tools.yaml" --log-level DEBUG
```
Leave this terminal running.

**B. Terminal 2: Start the Flask Web Application**

This runs the main Python web server.

```bash
# Make sure you are in the project root and your venv is active
source ./set_env.sh # Ensure environment variables are set

# cd into the application directory
cd google-photos

# Run the Flask app
python app.py
```
You can now access the web application at the URL shown in the terminal (usually `http://127.0.0.1:8080`). The search bar and chatbot will now be fully functional, powered by the integrated agent.

# Deploy to Cloud Run

If you want to deploy the application to a public URL instead of running it locally, you can use the provided deployment script.

### 1. Create Artifact Repository

```bash
gcloud artifacts repositories create $REPO_NAME \
  --repository-format=docker \
  --location=us-central1 \
  --description="Docker repository for Google Photos Memory Agent"
```

### 2. Grant Service Account Permissions

The Cloud Run service needs permissions to access other Google Cloud services.

```bash
# Grant all necessary roles to the default Compute Service Account
export SERVICE_ACCOUNT_NAME=$(gcloud compute project-info describe --format="value(defaultServiceAccount)")

gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME" --role="roles/spanner.databaseUser"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME" --role="roles/artifactregistry.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME" --role="roles/cloudbuild.builds.editor"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME" --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME" --role="roles/iam.serviceAccountUser"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME" --role="roles/logging.logWriter"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_NAME" --role="roles/storage.admin"
```

### 3. Deploy

Run the deployment script. This will build the container image and deploy it to Cloud Run.

```bash
# From the project root directory
./deploy.sh
```
After the script completes, it will output the public URL for your running application.
