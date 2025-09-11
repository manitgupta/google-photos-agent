

### Set up remote address for all the other agents

**Note**: First ensure that all the other agents are deployed and running by cloud run by following
their individual README files.

```aiexclude
. ~/google-photos-agent/set_env.sh
source ~/google-photos-agent/env/bin/activate
cd  ~/google-photos-agent/agents

export MEMORY_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep memory-agent)
export SOCIAL_PROFILING_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep social-profiling-agent)
export PHOTOS_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep photos-agent)

export REMOTE_AGENT_ADDRESSES=${MEMORY_AGENT_URL},${SOCIAL_PROFILING_AGENT_URL},${PHOTOS_AGENT_URL}
```

```aiexclude
echo "REMOTE_AGENT_ADDRESSES=${REMOTE_AGENT_ADDRESSES}" > orchestrate/.env
echo "PROJECT_NUMBER=${PROJECT_NUMBER}" >> orchestrate/.env
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


export MEMORY_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep memory-agent)
export SOCIAL_PROFILING_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep social-profiling-agent)
export PHOTOS_AGENT_URL=$(gcloud run services list --platform=managed --region=us-central1 --format='value(URL)' | grep photos-agent)

export REMOTE_AGENT_ADDRESSES=${MEMORY_AGENT_URL},${SOCIAL_PROFILING_AGENT_URL},${PHOTOS_AGENT_URL}
```

```aiexclude
echo "REMOTE_AGENT_ADDRESSES=${REMOTE_AGENT_ADDRESSES}" > orchestrate/.env
echo "PROJECT_NUMBER=${PROJECT_NUMBER}" >> orchestrate/.env
```

```aiexclude
adk deploy agent_engine \
--display_name "orchestrate-agent" \
--project $GOOGLE_CLOUD_PROJECT \
--region $GOOGLE_CLOUD_LOCATION \
--staging_bucket gs://$GOOGLE_CLOUD_PROJECT-agent-engine \
--trace_to_cloud \
--requirements_file orchestrate/requirements.txt \
orchestrate
```

### Sample prompt #1

```aiexclude
The current logged in user is Rohan.
Your task is to design a fun collage for Rohan based on his request.

Here are the details for the collage to be made:
- Friends that should be in the collage: Anjali, Priya
- Once the collage is created, post it to the Google Photos app

Your process should be:
1. Analyze the provided friend names. If you have access to a tool to get their photographs, please use it.
2. Based on the fetched photos, if you have access to a tool to create a collage out of them, please use it.
3. Based on the created collage, if you have access to a tool that posts the collage to the Google photos app, please use it.
4. If you don't find any photos, inform that you will be not able to create a collage.
```

### Sample prompt #2

```aiexclude
The current logged in user is Rohan.
Your task is to design a fun collage for Rohan based on his request.

Here are the details for the collage to be made:
- People that should be in the collage: Relatives of Rohan
- Once the collage is created, post it to the Google Photos app

Your process should be:
1. Analyze the input request. If you have access to a tool to get the names of relevant people, please use it.
2. Analyze the determined names. If you have access to a tool to get their photographs, please use it.
3. Based on the fetched photos, if you have access to a tool to create a collage out of them, please use it.
4. Based on the created collage, if you have access to a tool that posts the collage to the Google photos app, please use it.
5. If you don't find any photos, inform that you will be not able to create a collage.
```