import os
import traceback
from datetime import datetime, timezone
from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
from google.api_core import exceptions
from flask import flash

# --- Spanner Configuration ---
INSTANCE_ID = "google-photos-instance"
DATABASE_ID = "google-photos"
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")

# --- Spanner Client Initialization ---
db = None
try:
    spanner_client = spanner.Client(project=PROJECT_ID)
    instance = spanner_client.instance(INSTANCE_ID)
    database = instance.database(DATABASE_ID)
    print(f"Attempting to connect to Spanner: {instance.name}/databases/{database.name}")

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

def run_query(sql, params=None, param_types=None, expected_fields=None):
    """
    Executes a SQL query against the Spanner database.
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
                if len(field_names) != len(row):
                    print(f"Warning: Mismatch between number of field names ({len(field_names)}) and row values ({len(row)})")
                    print(f"Fields: {field_names}")
                    print(f"Row: {row}")
                    continue
                results_list.append(dict(zip(field_names, row)))

            print(f"Query successful, fetched {len(results_list)} rows.")

    except (exceptions.NotFound, exceptions.PermissionDenied, exceptions.InvalidArgument) as spanner_err:
        print(f"Spanner Error ({type(spanner_err).__name__}): {spanner_err}")
        flash(f"Database error: {spanner_err}", "danger")
        return []
    except ValueError as e:
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

def get_memories_by_user_db(user_id):
    """Fetch all memories for a user from Spanner."""
    sql = """
        SELECT memory_id, memory_title, memory_description, creation_timestamp, memory_media
        FROM Memories
        WHERE user_id = @user_id
        ORDER BY creation_timestamp DESC
    """
    params = {"user_id": user_id}
    param_types_map = {"user_id": param_types.STRING}
    fields = ["memory_id", "memory_title", "memory_description", "creation_timestamp", "memory_media"]
    return run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)

def get_person_by_id_db(person_id):
    """Fetch a person's details from Spanner."""
    sql = "SELECT person_id, name, photo_location FROM Person WHERE person_id = @person_id"
    params = {"person_id": person_id}
    param_types_map = {"person_id": param_types.STRING}
    fields = ["person_id", "name", "photo_location"]
    return run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)

def get_people_in_photos_db(photo_ids):
    """Fetch all people who appear in a list of photos."""
    sql = """
        SELECT pa.photo_id, p.name
        FROM PersonAppearsInPhoto AS pa
        JOIN Person AS p ON pa.person_id = p.person_id
        WHERE pa.photo_id IN UNNEST(@photo_ids)
    """
    params = {"photo_ids": photo_ids}
    param_types_map = {"photo_ids": param_types.Array(param_types.STRING)}
    fields = ["photo_id", "name"]
    return run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)


def get_person_by_name_db(person_name):
    """Fetch a person's details from Spanner by name."""
    sql = "SELECT person_id, name FROM Person WHERE LOWER(name) = LOWER(@person_name)"
    params = {"person_name": person_name}
    param_types_map = {"person_name": param_types.STRING}
    fields = ["person_id", "name"]
    return run_query(sql, params=params, param_types=param_types_map, expected_fields=fields)


def add_memory_db(memory_id, user_id, memory_title, memory_description, memory_media):
    """Inserts a new memory into the Spanner database."""
    if not db:
        print("Error: Database connection is not available for insert.")
        raise ConnectionError("Spanner database connection not initialized.")

    def _insert_memory(transaction):
        transaction.insert(
            table="Memories",
            columns=[
                "memory_id", "user_id", "memory_title", "memory_description",
                "creation_timestamp", "memory_media"
            ],
            values=[(
                memory_id, user_id, memory_title, memory_description,
                spanner.COMMIT_TIMESTAMP, memory_media
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