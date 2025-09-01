import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, abort, flash, request, jsonify
from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
from google.api_core import exceptions
import humanize 
import uuid
import traceback
from dateutil import parser 


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_secret_key_for_dev")
DUMMY_PERSON_ID = "p01" 

load_dotenv()
# --- Spanner Configuration ---
INSTANCE_ID = "google-photos-instance" 
DATABASE_ID = "google-photos"
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = os.environ.get("APP_PORT","8080")


if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")

# --- Spanner Client Initialization ---
db = None
try:
    spanner_client = spanner.Client(project=PROJECT_ID)
    instance = spanner_client.instance(INSTANCE_ID)
    database = instance.database(DATABASE_ID)
    print(f"Attempting to connect to Spanner: {instance.name}/databases/{database.name}")

    # Ensure database exists - crucial check
    if not database.exists():
         print(f"Error: Database '{database.name}' does not exist in instance '{instance.name}'.")
         print("Please create the database and the required tables/schema.")
    else:
        print("Database connection check successful (database exists).")
        db = database

except exceptions.NotFound:
    print(f"Error: Spanner instance '{INSTANCE_ID}' not found in project '{PROJECT_ID}'.")
except Exception as e:
    print(f"An unexpected error occurred during Spanner initialization: {e}")

def run_query(sql, params=None, param_types=None, expected_fields=None): # Add expected_fields
    """
    Executes a SQL query against the Spanner database.

    Args:
        sql (str): The SQL query string.
        params (dict, optional): Dictionary of query parameters. Defaults to None.
        param_types (dict, optional): Dictionary mapping parameter names to their
                                      Spanner types (e.g., spanner.param_types.STRING).
                                      Defaults to None.
        expected_fields (list[str], optional): A list of strings representing the
                                                expected column names in the order
                                                they appear in the SELECT statement.
                                                Required if results.fields fails.
    """
    if not db:
        print("Error: Database connection is not available.")
        raise ConnectionError("Spanner database connection not initialized.")

    results_list = []
    print(f"--- Executing SQL ---")
    print(f"SQL: {sql}")
    if params:
        print(f"Params: {params}")
    print("----------------------")

    try:
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql(
                sql,
                params=params,
                param_types=param_types
            )

            field_names = expected_fields
            if not field_names:
                 print("Warning: expected_fields not provided to run_query. Attempting dynamic lookup.")
                 try:
                     field_names = [field.name for field in results.fields]
                 except AttributeError as e:
                     print(f"Error accessing results.fields even as fallback: {e}")
                     print("Cannot process results without field names.")
                     raise ValueError("Could not determine field names for query results.") from e


            print(f"Using field names: {field_names}")

            for row in results:
                # Now zip the known field names with the row values (which are lists)
                if len(field_names) != len(row):
                     print(f"Warning: Mismatch between number of field names ({len(field_names)}) and row values ({len(row)})")
                     print(f"Fields: {field_names}")
                     print(f"Row: {row}")
                     # Skip this row or handle error appropriately
                     continue # Skip malformed row for now
                results_list.append(dict(zip(field_names, row)))

            print(f"Query successful, fetched {len(results_list)} rows.")

    except (exceptions.NotFound, exceptions.PermissionDenied, exceptions.InvalidArgument) as spanner_err:
        print(f"Spanner Error ({type(spanner_err).__name__}): {spanner_err}")
        flash(f"Database error: {spanner_err}", "danger")
        return []
    except ValueError as e: # Catch the ValueError we might raise above
         print(f"Query Processing Error: {e}")
         flash("Internal error processing query results.", "danger")
         return []
    except Exception as e:
        print(f"An unexpected error occurred during query execution or processing: {e}")
        traceback.print_exc()
        flash(f"An unexpected server error occurred while fetching data.", "danger")
        raise e

    return results_list

def get_photos_by_person_db(person_id):
    """Fetch all photos owned by a person from Spanner."""
    sql = """
        SELECT p.photo_id, p.timestamp, p.location_name, p.photo_location
        FROM Photo AS p
        JOIN PersonOwnsPhoto AS pop ON p.photo_id = pop.photo_id
        WHERE pop.person_id = @person_id
        ORDER BY p.timestamp DESC
    """
    params = {"person_id": person_id}
    param_types_map = {"person_id": param_types.STRING}
    fields = ["photo_id", "timestamp", "location_name", "photo_location"]
    return run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)



# --- Custom Jinja Filter ---
@app.template_filter('humanize_datetime')
def _jinja2_filter_humanize_datetime(value, default="just now"):
    """
    Convert a datetime object to a human-readable relative time string.
    e.g., '5 minutes ago', '2 hours ago', '3 days ago'
    """
    if not value:
        return default
   
    dt_object = None
    if isinstance(value, str):
        try:
            # Attempt to parse ISO 8601 format.
            # .replace('Z', '+00:00') handles UTC 'Z' suffix for fromisoformat.
            dt_object = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            # Fallback to dateutil.parser for more general string formats
            try:
                dt_object = parser.parse(value)
            except (parser.ParserError, TypeError, ValueError) as e:
                app.logger.warning(f"Could not parse date string '{value}' in humanize_datetime: {e}")
                return str(value) # Return original string if unparseable
    elif isinstance(value, datetime):
        dt_object = value
    else:
        # If not a string or datetime, return its string representation
        return str(value)

    if dt_object is None: # Should have been handled, but as a safeguard
        app.logger.warning(f"Date value '{value}' resulted in None dt_object in humanize_datetime.")
        return str(value)

    now = datetime.now(timezone.utc)
    # Use dt_object for all datetime operations from here
    if dt_object.tzinfo is None or dt_object.tzinfo.utcoffset(dt_object) is None:
        # If dt_object is naive, assume it's UTC
        dt_object = dt_object.replace(tzinfo=timezone.utc)
    else:
        # Convert aware dates to UTC
        dt_object = dt_object.astimezone(timezone.utc)

    try:
        return humanize.naturaltime(now - dt_object)
    except TypeError:
        # Fallback or handle error if date calculation fails
        return dt_object.strftime("%Y-%m-%d %H:%M")

def add_memory_db(memory_id, user_id, memory_title, memory_description):
    """Inserts a new memory into the Spanner database."""
    if not db:
        print("Error: Database connection is not available for insert.")
        raise ConnectionError("Spanner database connection not initialized.")

    def _insert_memory(transaction):
        transaction.insert(
            table="Memories",
            columns=[
                "memory_id", "user_id", "memory_title", "memory_description",
                "creation_timestamp"
            ],
            values=[(
                memory_id, user_id, memory_title, memory_description,
                spanner.COMMIT_TIMESTAMP
            )]
        )
        print(f"Transaction attempting to insert memory_id: {memory_id}")

    try:
        db.run_in_transaction(_insert_memory)
        print(f"Successfully inserted memory_id: {memory_id}")
        return True
    except Exception as e:
        print(f"Error inserting memory (id: {memory_id}): {e}")
        return False

# --- Routes ---
@app.route('/')
def home():
    """Home page: Shows all photos owned by a person."""
    all_photos = []

    if not db:
        flash("Database connection not available. Cannot load page data.", "danger")
    else:
        try:
            all_photos = get_photos_by_person_db(DUMMY_PERSON_ID)
        except Exception as e:
             flash(f"Failed to load page data: {e}", "danger")
             # Ensure variables are defined even on error
             all_photos = []

    return render_template(
        'index.html',
        photos=all_photos,
    )

@app.route('/api/memories', methods=['POST'])
def add_memory_api():
    """
    API endpoint to add a new memory.
    Expects JSON body: {"user_id": "...", "memory_title": "...", "memory_description": "..."}
    """
    if not db:
        return jsonify({"error": "Database connection not available"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    required_fields = ["user_id", "memory_title", "memory_description"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    user_id = data['user_id']
    memory_title = data['memory_title']
    memory_description = data['memory_description']

    # Basic input validation
    if not all(isinstance(data[field], str) and data[field].strip() for field in required_fields):
        return jsonify({"error": "All fields must be non-empty strings"}), 400

    try:
        new_memory_id = str(uuid.uuid4())

        success = add_memory_db(
            memory_id=new_memory_id,
            user_id=user_id,
            memory_title=memory_title,
            memory_description=memory_description
        )

        if success:
            memory_data = {
                "message": "Memory added successfully",
                "memory_id": new_memory_id,
                "user_id": user_id,
                "memory_title": memory_title,
                "memory_description": memory_description,
                "creation_timestamp": datetime.now(timezone.utc).isoformat()
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


if __name__ == '__main__':
    # Check if db connection was successful before running
    if not db:
        print("\n--- Cannot start Flask app: Spanner database connection failed during initialization. ---")
        print("--- Please check GCP project, instance ID, database ID, permissions, and network connectivity. ---")
    else:
        print("\n--- Starting Flask Development Server ---")
        app.run(debug=True, host=APP_HOST, port=APP_PORT)