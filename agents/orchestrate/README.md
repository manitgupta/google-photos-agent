

### Set up remote address for all the other agents

```aiexclude
. ~/google-photos-agent/set_env.sh
source ~/google-photos-agent/env/bin/activate

export MEMORY_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep memory-agent)
export SOCIAL_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep social-agent)

export REMOTE_AGENT_ADDRESSES=${MEMORY_AGENT_URL},${SOCIAL_AGENT_URL}

cd  ~/google-photos-agent/agents
sed -i "s|^\(O\?REMOTE_AGENT_ADDRESSES\)=.*|REMOTE_AGENT_ADDRESSES=${REMOTE_AGENT_ADDRESSES}|" ~/google-photos-agent/agents/orchestrate/.env
```

### Running locally 

```aiexclude
adk web
```

Select the "orchestrate" agent in the UI and provide it a prompt.

### Running on Agent engine on Vertex AI

Execute the following command to deploy the Orchestrator agent to Agent Engine. Make sure the REMOTE_AGENT_ADDRESSES environment variable (containing the URLs of your Planner, Platform, and Social agents on Cloud Run) is still correctly set from the previous section.

```aiexclude
cd ~/google-photos-agent/agents/
. ~/google-photos-agent/set_env.sh

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
    --role="roles/viewer"


source ~/google-photos-agent/env/bin/activate
export MEMORY_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep memory-agent)
export SOCIAL_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep social-agent)

export REMOTE_AGENT_ADDRESSES=${MEMORY_AGENT_URL},${SOCIAL_AGENT_URL}
sed -i "s|^\(O\?REMOTE_AGENT_ADDRESSES\)=.*|REMOTE_AGENT_ADDRESSES=${REMOTE_AGENT_ADDRESSES}|" ~/google-photos-agent/agents/orchestrate/.env

adk deploy agent_engine \
--display_name "orchestrate-agent" \
--project $GOOGLE_CLOUD_PROJECT \
--region $GOOGLE_CLOUD_LOCATION \
--staging_bucket gs://$GOOGLE_CLOUD_PROJECT-agent-engine \
--trace_to_cloud \
--requirements_file orchestrate/requirements.txt \
orchestrate
```

### Sample prompt 

```aiexclude
You are an expert collage creator for a user named Rohan.
Your task is to design a fun collage for Rohan based on his request.

Here are the details for the collage to be made:
- Friends that should be in the collage: Anjali, Priya

Your process should be:
1. Analyze the provided friend names. If you have access to a tool to get their photographs, please use it.
2. Based on the fetched photos, if you have access to a tool to create a collage out of them, please use it.
3. If you don't find any photos, inform that you will be not able to create a collage.
```