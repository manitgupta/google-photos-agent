import os
import sys
import uuid
import traceback
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import Flask, render_template, flash, request, jsonify, redirect, url_for, Response, stream_with_context
import humanize
from dateutil import parser
from google.cloud import storage
import json
import callagent

# --- Agent Integration (Corrected based on user-provided example) ---
try:
    from agents.social_profiling_agent import root_agent
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
DUMMY_PERSON_ID = "p01"

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
            expiration=timedelta(minutes=60),
            method="GET",
        )
        return signed_url
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

# --- Routes ---
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

@app.route('/search')                                                                                                                                                                                     
def search():
    return redirect(url_for('index'))

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
                    # memory_media is a single string, not a list
                    signed_url = generate_signed_url(memory['memory_media'])
                    if signed_url:
                        memory['memory_media'] = signed_url
        except Exception as e:
            flash(f"Failed to load memories: {e}", "danger")
            all_memories = []

    return render_template('memories.html', memories=all_memories)

@app.route('/chatbot')
def chatbot():
    """Chatbot page: Renders the chatbot interface."""
    return render_template('chatbot.html')

@app.route('/api/memories', methods=['POST'])
def add_memory_api():
    """
    API endpoint to add a new memory.
    """
    if not db.db:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    required_fields = ["user_id", "memory_title", "memory_description", "memory_media"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    user_name = data['user_id']
    memory_title = data['memory_title']
    memory_description = data['memory_description']
    memory_media = data['memory_media']

    if not all(isinstance(data[field], str) and data[field].strip() for field in required_fields):
        return jsonify({"error": "All fields must be non-empty strings"}), 400

    if not isinstance(memory_media, str):
        return jsonify({"error": "memory_media must be a string (GCS URI)"}), 400

    try:
        person_data = db.get_person_by_name_db(user_name)
        if not person_data:
            return jsonify({"error": f"Person '{user_name}' not found"}), 404
        user_id = person_data[0]['person_id']

        new_memory_id = str(uuid.uuid4())
        success = db.add_memory_db(
            memory_id=new_memory_id,
            user_id=user_id,
            memory_title=memory_title,
            memory_description=memory_description,
            memory_media=memory_media
        )

        if success:
            memory_data = {
                "message": "Memory added successfully",
                "memory_id": new_memory_id,
                "user_id": user_id,
                "memory_title": memory_title,
                "memory_description": memory_description,
                "creation_timestamp": datetime.now(timezone.utc).isoformat(),
                "memory_media": memory_media
            }
            return jsonify(memory_data), 201
        else:
            return jsonify({"error": "Failed to save memory to the database"}), 500

    except ConnectionError as e:
        print(f"ConnectionError during memory add: {e}")
        return jsonify({"error": "Database connection error during operation"}), 503
    except Exception as e:
        print(f"Unexpected error processing add memory request: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred"}), 500

@app.route('/api/chatbot', methods=['GET'])
def api_chatbot():
    """API endpoint for the chatbot."""
    user_message = request.args.get('message')
    if not user_message:
        return jsonify({"error": "Invalid request"}), 400

    def generate():
        user_data = db.get_person_by_id_db(DUMMY_PERSON_ID)
        user_name = user_data[0]['name'] if user_data else 'Rohan'
        for event in callagent.call_orchestrator_agent(user_name, user_message):
            yield f"data: {json.dumps(event)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/api/generate-signed-url', methods=['POST'])
def api_generate_signed_url():
    data = request.get_json()
    if not data or 'gcs_uri' not in data:
        return jsonify({'error': 'Missing gcs_uri'}), 400
    signed_url = generate_signed_url(data['gcs_uri'])
    if signed_url:
        return jsonify({'signed_url': signed_url})
    else:
        return jsonify({'error': 'Failed to generate signed URL'}), 500


if __name__ == '__main__':
    if not db.db:
        print("\n--- Cannot start Flask app: Spanner database connection failed during initialization. ---")
        print("--- Please check GCP project, instance ID, database ID, permissions, and network connectivity. ---")
    else:
        print("\n--- Starting Flask Development Server ---")
        app.run(debug=True, host=APP_HOST, port=APP_PORT)
