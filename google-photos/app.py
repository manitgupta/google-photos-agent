import os
import uuid
import sys
import traceback
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, flash, request, jsonify, redirect, url_for
import humanize
from dateutil import parser
from google.cloud import storage

# --- Agent Integration ---
# Suggestion: For a more robust setup, consider structuring your project as a
# Python package to avoid using sys.path.append.
# e.g., /photo-app
#       /app.py
#       /agent/agent.py
#       /templates/
# Then you could use a clean "from agent.agent import root_agent"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    # Assuming the agent file is in a sub-directory named 'social_profiling_agent'
    from social_profiling_agent.agent import root_agent
    from google.adk.agents import AgentError
    print("Successfully imported ADK agent.")
except (ImportError, ModuleNotFoundError) as e:
    print(f"CRITICAL ERROR: Could not import the ADK agent. Details: {e}")
    root_agent = None
    # Define a placeholder class for AgentError if the import fails
    class AgentError(Exception):
        pass

# Import database functions from db.py
import db

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_secret_key_for_dev")
# In a real application, the user_id would come from a session after login.
# This should be replaced with a proper authentication system.
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
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1), # Increased expiration for better user experience
            method="GET",
        )
        return signed_url
    except Exception as e:
        app.logger.error(f"Failed to generate signed URL for {gcs_uri}: {e}")
        return None

# --- Custom Jinja Filter ---
@app.template_filter('humanize_datetime')
def _jinja2_filter_humanize_datetime(value, default="just now"):
    if not value:
        return default
    # Simplified parsing logic
    try:
        dt_object = parser.parse(value).astimezone(timezone.utc)
        return humanize.naturaltime(datetime.now(timezone.utc) - dt_object)
    except (parser.ParserError, TypeError, ValueError):
        return str(value)

def invoke_photo_agent(query: str, user_id: str) -> dict:
    """
    Invokes the photo agent, processes results, and handles errors.
    Returns a dictionary with the result data, type, and any errors.
    """
    if not root_agent:
        return {"data": None, "type": "error", "error": "Agent is not available."}

    try:
        user_data = db.get_person_by_id_db(user_id)
        if not user_data:
            return {"data": None, "type": "error", "error": "User not found."}
        user_name = user_data[0]['name']

        full_prompt = f"The logged in user is {user_name}. {query}"
        app.logger.info(f"Invoking agent with prompt: '{full_prompt}'")
        result = root_agent.invoke(full_prompt)
        app.logger.info(f"Agent returned result: {result}")

        if isinstance(result, list) and all(isinstance(item, dict) for item in result):
            for photo in result:
                if photo.get('photo_location'):
                    photo['photo_location'] = generate_signed_url(photo['photo_location'])
            return {"data": result, "type": "photos", "error": None}
        elif isinstance(result, str):
            return {"data": result, "type": "text", "error": None}
        else:
            return {"data": str(result), "type": "text", "error": "Agent returned an unexpected data format."}

    except AgentError as e:
        app.logger.error(f"AgentError during agent invocation: {e}")
        # Provide a more user-friendly error message
        return {"data": None, "type": "error", "error": "I had trouble processing that request. Please try rephrasing your query."}
    except Exception as e:
        app.logger.error(f"Unexpected error invoking agent: {e}\n{traceback.format_exc()}")
        return {"data": None, "type": "error", "error": "An unexpected internal error occurred."}

# --- Routes ---
@app.route('/')
def index():
    """Home page: Shows all photos owned by a person. Search is handled by the frontend."""
    all_photos = []
    user = None
    people_in_photos = {}
    search_query = request.args.get('q', '') # Get search query for pre-filling the input

    try:
        user_data = db.get_person_by_id_db(DUMMY_USER_ID)
        if user_data:
            user = user_data[0]
            if user.get('photo_location'):
                user['photo_location'] = generate_signed_url(user['photo_location'])

        # IMPROVEMENT: The search logic is now handled entirely by the frontend JavaScript.
        # This route is only responsible for loading the initial page with all photos.
        all_photos = db.get_photos_by_person_db(DUMMY_USER_ID)
        for photo in all_photos:
            photo['photo_location'] = generate_signed_url(photo['photo_location'])

        photo_ids = [photo['photo_id'] for photo in all_photos]
        if photo_ids:
            people_data = db.get_people_in_photos_db(photo_ids)
            for person in people_data:
                photo_id = person['photo_id']
                if photo_id not in people_in_photos:
                    people_in_photos[photo_id] = []
                people_in_photos[photo_id].append(person['name'])

    except Exception as e:
        flash(f"Failed to load page data: {e}", "danger")
        app.logger.error(f"Error on index page: {e}\n{traceback.format_exc()}")

    return render_template(
        'index.html',
        photos=all_photos,
        user=user,
        people_in_photos=people_in_photos,
        search_query=search_query
    )

@app.route('/search', methods=['GET'])
def search():
    """Redirects from the generic header search bar to the main page search."""
    query = request.args.get('q', '')
    # This redirects to the home page (index) and adds the search term as a URL parameter.
    # The JavaScript in index.html will see this parameter and can choose to auto-run the search.
    return redirect(url_for('index', q=query))

@app.route('/memories')
def memories():
    # This route seems fine, no changes needed for agent integration.
    return render_template('memories.html', memories=[])

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    """API endpoint for both the chatbot and the home page search."""
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "Invalid request: 'message' field is required."}), 400

    user_message = data['message'].strip()
    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    # This single endpoint now serves both use cases cleanly.
    agent_result = invoke_photo_agent(user_message, DUMMY_USER_ID)

    if agent_result["error"]:
        # Return a 500 status for server-side errors
        return jsonify({"error": agent_result["error"]}), 500

    return jsonify({
        "response_type": agent_result["type"],
        "data": agent_result["data"]
    })

# The /api/memories route seems fine, no changes needed.
@app.route('/api/memories', methods=['POST'])
def add_memory_api():
    # ... (existing code from your file)
    # This is placeholder as it's not relevant to the agent integration review.
    return jsonify({"message": "Not implemented for this review"}), 200


if __name__ == '__main__':
    if not db.db:
        print("Database connection failed. Please check your configuration and credentials.")
    else:
        app.run(debug=True, host=APP_HOST, port=APP_PORT)
