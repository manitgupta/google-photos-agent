import os
import uuid
import traceback
from datetime import datetime, timezone, timedelta
import asyncio
import json

from dotenv import load_dotenv
from flask import Flask, render_template, flash, request, jsonify, redirect, url_for
import humanize
from dateutil import parser
from google.cloud import storage

# --- Agent Integration (Corrected based on user-provided example) ---
try:
    from social_profiling_agent.agent import root_agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    # FIX: Use the correct import path from the 'google-genai' library,
    # as shown in the user's working example.
    from google.genai import types as genai_types

    # Set up the required Runner and Session Service
    session_service = InMemorySessionService()
    agent_runner = Runner(
        agent=root_agent,
        app_name="google-photos-agent",
        session_service=session_service
    )
    print("Successfully imported and configured ADK agent with Runner.")

except ImportError as e:
    print(f"CRITICAL ERROR: Could not import the ADK agent/runner. The agent will be disabled. Details: {e}")
    root_agent = None
    agent_runner = None

# Import database functions from db.py
import db

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_secret_key_for_dev")
# In a real application, the user_id would come from a session after login.
DUMMY_USER_ID = "p01"

load_dotenv()
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = os.environ.get("APP_PORT", "8080")

# --- Initialize Google Cloud Storage Client ---
storage_client = storage.Client()

def generate_signed_url(gcs_uri):
    """Generates a signed URL for a GCS object."""
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        return None
    try:
        bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        # Generate a URL that is valid for 1 hour
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET",
        )
        return signed_url
    except Exception as e:
        app.logger.error(f"Failed to generate signed URL for {gcs_uri}: {e}")
        return None

# --- Custom Jinja Filter ---
@app.template_filter('humanize_datetime')
def _jinja2_filter_humanize_datetime(value, default="just now"):
    if not value: return default
    dt_object = parser.parse(value) if isinstance(value, str) else value
    if dt_object.tzinfo is None: dt_object = dt_object.replace(tzinfo=timezone.utc)
    return humanize.naturaltime(datetime.now(timezone.utc) - dt_object)


def invoke_photo_agent(query: str, user_id: str) -> dict:
    """
    Invokes the photo agent using the ADK Runner, processes results, and handles errors.
    """
    if not agent_runner:
        return {"data": None, "type": "error", "error": "Agent is not available due to an import error."}

    async def run_agent_async():
        session_id = str(uuid.uuid4())
        # FIX: Use the correctly imported 'genai_types' to create the message Content
        user_content = genai_types.Content(role='user', parts=[genai_types.Part(text=full_prompt)])
        final_response = "Agent did not provide a final response."

        # Iterate through the async events from the runner
        async for event in agent_runner.run_async(user_id=user_id, session_id=session_id, new_message=user_content):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response = event.content.parts[0].text
                elif event.actions and event.actions.escalate:
                    error_msg = event.error_message or 'No specific message.'
                    raise Exception(f"Agent escalated with error: {error_msg}")
                break
        return final_response

    try:
        user_data = db.get_person_by_id_db(user_id)
        if not user_data:
            return {"data": None, "type": "error", "error": "User not found."}
        user_name = user_data[0]['name']

        full_prompt = f"The logged in user is {user_name}. {query}"
        app.logger.info(f"Invoking agent with prompt: {full_prompt}")

        # Run the async function from our synchronous code
        result_text = asyncio.run(run_agent_async())
        app.logger.info(f"Agent runner returned result: {result_text}")

        # The runner will likely return the tool output as a JSON string.
        # We need to try and parse it.
        try:
            result_data = json.loads(result_text)
            if isinstance(result_data, list):
                # It's a list of photos from a tool call
                for photo in result_data:
                    if photo.get('photo_location'):
                        photo['photo_location'] = generate_signed_url(photo['photo_location'])
                return {"data": result_data, "type": "photos", "error": None}
            else:
                # It's some other JSON, treat as text
                return {"data": result_text, "type": "text", "error": None}
        except (json.JSONDecodeError, TypeError):
            # The result was not JSON, so it's a direct text response.
            return {"data": result_text, "type": "text", "error": None}

    except Exception as e:
        app.logger.error(f"An exception occurred during agent invocation: {e}\n{traceback.format_exc()}")
        return {"data": None, "type": "error", "error": "An unexpected error occurred while processing your request."}


# --- Routes ---
@app.route('/')
def index():
    all_photos = []
    user = None
    people_in_photos = {}
    search_query = request.args.get('q', '')

    try:
        user_data = db.get_person_by_id_db(DUMMY_USER_ID)
        if user_data:
            user = user_data[0]
            if user.get('photo_location'):
                user['photo_location'] = generate_signed_url(user['photo_location'])

        all_photos = db.get_photos_by_person_db(DUMMY_USER_ID)
        for photo in all_photos:
            photo['photo_location'] = generate_signed_url(photo['photo_location'])

        photo_ids = [photo['photo_id'] for photo in all_photos]
        if photo_ids:
            people_data = db.get_people_in_photos_db(photo_ids)
            for person in people_data:
                people_in_photos.setdefault(person['photo_id'], []).append(person['name'])

    except Exception as e:
        flash(f"Failed to load page data: {e}", "danger")
        app.logger.error(f"Error on index page: {e}\n{traceback.format_exc()}")

    return render_template('index.html', photos=all_photos, user=user, people_in_photos=people_in_photos, search_query=search_query)

@app.route('/search')
def search():
    """Handles search form submission and redirects to the homepage with query."""
    query = request.args.get('q', '')
    return redirect(url_for('index', q=query))

@app.route('/memories')
def memories():
    return render_template('memories.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    """API endpoint for both search and chatbot."""
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "Invalid request"}), 400

    user_message = data['message'].strip()
    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    agent_result = invoke_photo_agent(user_message, DUMMY_USER_ID)

    if agent_result["error"]:
        return jsonify({"error": agent_result["error"]}), 500

    return jsonify({
        "response_type": agent_result["type"],
        "data": agent_result["data"]
    })

if __name__ == '__main__':
    if not db.db:
        print("\n--- Cannot start Flask app: Spanner database connection failed. ---")
    else:
        print("\n--- Starting Flask Development Server ---")
        app.run(debug=True, host=APP_HOST, port=APP_PORT)