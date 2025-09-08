
import os
import uuid
import traceback
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, flash, request, jsonify
import humanize
from dateutil import parser
from google.cloud import storage

# --- Agent and DB Imports ---
from agents.social_profiling_agent import TEXT_TO_QUERY_AGENT
import db

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_secret_key_for_dev")
DUMMY_PERSON_ID = "p01"  # This represents the logged-in user, Rohan

load_dotenv()
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = os.environ.get("APP_PORT", "8080")

# --- GCS Client & Helper ---
storage_client = storage.Client()

def generate_signed_url(gcs_uri):
    if not gcs_uri or not gcs_uri.startswith("gs://"):
        return None
    try:
        bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
        blob = storage_client.bucket(bucket_name).blob(blob_name)
        return blob.generate_signed_url(version="v4", expiration=timedelta(minutes=60), method="GET")
    except Exception as e:
        app.logger.error(f"Failed to generate signed URL for {gcs_uri}: {e}")
        return None

# --- Custom Jinja Filter ---
@app.template_filter('humanize_datetime')
def _jinja2_filter_humanize_datetime(value, default="just now"):
    """
    Convert a datetime object to a human-readable relative time string.
    """
    if not value:
        return default

    dt_object = None
    if isinstance(value, str):
        try:
            dt_object = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            try:
                dt_object = parser.parse(value)
            except (parser.ParserError, TypeError, ValueError) as e:
                app.logger.warning(f"Could not parse date string '{value}' in humanize_datetime: {e}")
                return str(value)
    elif isinstance(value, datetime):
        dt_object = value
    else:
        return str(value)

    if dt_object is None:
        app.logger.warning(f"Date value '{value}' resulted in None dt_object in humanize_datetime.")
        return str(value)

    now = datetime.now(timezone.utc)
    if dt_object.tzinfo is None or dt_object.tzinfo.utcoffset(dt_object) is None:
        dt_object = dt_object.replace(tzinfo=timezone.utc)
    else:
        dt_object = dt_object.astimezone(timezone.utc)

    try:
        return humanize.naturaltime(now - dt_object)
    except TypeError:
        return dt_object.strftime("%Y-%m-%d %H:%M")

# --- Main Routes ---
@app.route('/')
def index():
    """Home page: Shows all photos owned by a person."""
    all_photos = []
    user = None
    people_in_photos = {}

    if not db.db:
        flash("Database connection not available. Cannot load page data.", "danger")
    else:
        try:
            user_data = db.get_person_by_id_db(DUMMY_PERSON_ID)
            if user_data:
                user = user_data[0]
                if user.get('photo_location'):
                    user['photo_location'] = generate_signed_url(user['photo_location'])
                    print(f"Generated signed URL for photo {user['person_id']}: {user['photo_location']}")

            all_photos = db.get_photos_by_person_db(DUMMY_PERSON_ID)
            for photo in all_photos:
                photo['photo_location'] = generate_signed_url(photo['photo_location'])

            photo_ids = [photo['photo_id'] for photo in all_photos]

            if photo_ids:
                people_data = db.get_people_in_photos_db(photo_ids)
                for person in people_data:
                    if person['photo_id'] not in people_in_photos:
                        people_in_photos[person['photo_id']] = []
                    people_in_photos[person['photo_id']].append(person['name'])

        except Exception as e:
            flash(f"Failed to load page data: {e}", "danger")
            all_photos = []
            user = None
            people_in_photos = {}

    return render_template(
        'index.html',
        photos=all_photos,
        user=user,
        people_in_photos=people_in_photos
    )

@app.route('/memories')
def memories():
    """Memories page: Shows all memories created by a user."""
    all_memories = []
    if not db.db:
        flash("Database connection not available. Cannot load page data.", "danger")
    else:
        try:
            all_memories = db.get_memories_by_user_db(DUMMY_PERSON_ID)
            for memory in all_memories:
                if memory.get('memory_media'):
                    signed_media = []
                    for media_uri in memory['memory_media']:
                        signed_url = generate_signed_url(media_uri)
                        if signed_url:
                            signed_media.append(signed_url)
                    memory['memory_media'] = signed_media
        except Exception as e:
            flash(f"Failed to load memories: {e}", "danger")
            all_memories = []

    return render_template('memories.html', memories=all_memories)

@app.route('/chatbot')
def chatbot():
    """Chatbot page: Renders the chatbot interface."""
    return render_template('chatbot.html')

# --- API Routes ---
@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    """
    API endpoint for the advanced Social Profiling Agent.
    Injects user context into the prompt before calling the agent.
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "Invalid request: 'message' field is required."}), 400

    user_message = data['message']
    user_context_statement = ""

    # --- CONTEXT INJECTION ---
    # Fetch the current user's name to provide context to the agent.
    try:
        user_data = db.get_person_by_id_db(DUMMY_PERSON_ID)
        if user_data and user_data[0].get('name'):
            user_name = user_data[0]['name']
            user_context_statement = f" For context, my name is {user_name}."
        else:
            app.logger.warning(f"Could not find user name for person ID: {DUMMY_PERSON_ID}")
    except Exception as e:
        app.logger.error(f"Error fetching user context: {e}")

    # In app.py, inside /api/chatbot
    try:
        agent_response = TEXT_TO_QUERY_AGENT.chat(prompt_with_context)

        photo_results = []
        if agent_response.tool_outputs:
            tool_output = agent_response.tool_outputs[0].output

            # Check for error from the tool
            if isinstance(tool_output, dict) and 'error' in tool_output:
                app.logger.error(f"Agent tool error: {tool_output['error']}")
                return jsonify({"error": "Sorry, I encountered a problem while searching for your photos."}), 500

            # ... process successful results ...

    except Exception as e:
        app.logger.error(f"An unexpected error occurred in the agent: {e}")
        return jsonify({"error": "An unexpected error occurred with the AI agent."}), 500

    # Append the context to the user's message
    prompt_with_context = user_message + user_context_statement
    app.logger.info(f"Sending prompt to agent: '{prompt_with_context}'")

    # Pass the augmented prompt to the agent
    agent_response = TEXT_TO_QUERY_AGENT.chat(prompt_with_context)

    photo_results = []
    if agent_response.tool_outputs:
        tool_output = agent_response.tool_outputs[0].output
        if isinstance(tool_output, list):
            photo_results = tool_output
            for photo in photo_results:
                if photo.get('photo_location'):
                    photo['photo_url'] = generate_signed_url(photo['photo_location'])

    return jsonify({
        "agent_text_response": agent_response.text,
        "photo_results": photo_results
    })

@app.route('/api/memories', methods=['POST'])
def add_memory_api():
    # ... (implementation remains the same)
    return jsonify({}), 500

# --- Main Execution & Demo ---
def main():
    """
    Demonstrates a sample query with automatic context injection.
    """
    print("--- Running a sample Text-to-Query agent query ---")
    # The user just asks a simple question
    sample_query = "Show me photos of my cousins from the Goa trip."
    print(f"User Query: \"{sample_query}\"")

    # --- CONTEXT INJECTION (DEMO) ---
    user_context_statement = ""
    try:
        user_data = db.get_person_by_id_db(DUMMY_PERSON_ID)
        if user_data and user_data[0].get('name'):
            user_name = user_data[0]['name']
            user_context_statement = f" For context, my name is {user_name}."
    except Exception as e:
        print(f"Could not fetch user context for demo: {e}")

    prompt_with_context = sample_query + user_context_statement
    print(f"Augmented Prompt sent to agent: \"{prompt_with_context}\"")

    # Pass the augmented prompt to the agent
    response = TEXT_TO_QUERY_AGENT.chat(prompt_with_context)

    print("\n--- Agent's Final Response ---")
    print(response.text)

    if response.tool_outputs:
        photo_list = response.tool_outputs[0].output
        if isinstance(photo_list, list) and photo_list:
            print("\n--- Final Structured List of Photos (with Signed URLs) ---")
            for photo in photo_list:
                if photo.get('photo_location'):
                    photo['photo_url'] = generate_signed_url(photo['photo_location'])
            print(json.dumps(photo_list, indent=2))
        else:
            print(f"\n--- Query executed, but no photos found or an error occurred ---\n{photo_list}")
    else:
        print("\n--- Agent did not call a tool. ---")

if __name__ == '__main__':
    if not db.db:
        print("\n--- Cannot start: Spanner database connection failed. ---")
    else:
        main()
        print("\n\n--- Starting Flask Development Server ---")
        app.run(debug=True, host=APP_HOST, port=APP_PORT)
