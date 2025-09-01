
import os
import uuid
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateutil_parser
import time

from google.cloud import spanner
from google.api_core import exceptions

# --- Configuration ---
INSTANCE_ID = os.environ.get("SPANNER_INSTANCE_ID","google-photos-instance")
DATABASE_ID = os.environ.get("SPANNER_DATABASE_ID","google-photos")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

# --- Spanner Client Initialization ---
try:
  spanner_client = spanner.Client(project=PROJECT_ID)
  instance = spanner_client.instance(INSTANCE_ID)
  database = instance.database(DATABASE_ID)
  print(f"Targeting Spanner: {instance.name}/databases/{database.name}")
  if not database.exists():
    print(f"Error: Database '{DATABASE_ID}' does not exist. Please create it first.")
    database = None
  else:
    print("Database connection successful.")
except exceptions.NotFound:
  print(f"Error: Spanner instance '{INSTANCE_ID}' not found or missing permissions.")
  spanner_client = None; instance = None; database = None
except Exception as e:
  print(f"Error initializing Spanner client: {e}")
  spanner_client = None; instance = None; database = None

def run_ddl_statements(db_instance, ddl_list, operation_description):
  """Helper function to run DDL statements and handle potential errors."""
  if not db_instance:
    print(f"Skipping DDL ({operation_description}) - database connection not available.")
    return False
  print(f"\n--- Running DDL: {operation_description} ---")
  print("Statements:")
  # Print statements cleanly
  for i, stmt in enumerate(ddl_list):
    print(f"  [{i+1}] {stmt.strip()}") # Add numbering for clarity
  try:
    operation = db_instance.update_ddl(ddl_list)
    print("Waiting for DDL operation to complete...")
    operation.result(360) # Wait up to 6 minutes
    print(f"DDL operation '{operation_description}' completed successfully.")
    return True
  except (exceptions.FailedPrecondition, exceptions.AlreadyExists) as e:
    print(f"Warning/Info during DDL '{operation_description}': {type(e).__name__} - {e}")
    print("Continuing script execution (schema object might already exist or precondition failed).")
    return True
  except exceptions.InvalidArgument as e:
    print(f"ERROR during DDL '{operation_description}': {type(e).__name__} - {e}")
    print(">>> This indicates a DDL syntax error. The schema was NOT created/updated correctly. Stopping script. <<<")
    return False # Make syntax errors fatal
  except exceptions.DeadlineExceeded:
    print(f"ERROR during DDL '{operation_description}': DeadlineExceeded - Operation took too long.")
    return False
  except Exception as e:
    print(f"ERROR during DDL '{operation_description}': {type(e).__name__} - {e}")
    # Optionally print full traceback for debugging
    import traceback
    traceback.print_exc()
    print("Stopping script due to unexpected DDL error.")
    return False

def setup_base_schema_and_indexes(db_instance):
  """Creates the base relational tables and associated indexes."""
  ddl_statements = [
      # --- 1. Base Tables (No Graph Definition Here) ---
      """
      CREATE TABLE IF NOT EXISTS Person (
                              person_id STRING(36) NOT NULL,
                              name      STRING(MAX)
      ) PRIMARY KEY (person_id);
      ""","""
      CREATE TABLE IF NOT EXISTS Photo (
                             photo_id       STRING(36) NOT NULL,
                             timestamp      TIMESTAMP,
                             location_name  STRING(MAX),
                             photo_location STRING(MAX)
      ) PRIMARY KEY (photo_id);
      ""","""
      CREATE TABLE IF NOT EXISTS Memories (
                                memory_id          STRING(36) NOT NULL,
                                user_id            STRING(36) NOT NULL,
                                memory_title       STRING(MAX),
                                memory_description STRING(MAX),
                                creation_timestamp TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
                                CONSTRAINT fk_memories_user FOREIGN KEY (user_id) REFERENCES Person (person_id) ON DELETE CASCADE
      ) PRIMARY KEY (memory_id);
      ""","""
      CREATE TABLE IF NOT EXISTS PersonOwnsPhoto (
                                       person_id STRING(36) NOT NULL,
                                       photo_id  STRING(36) NOT NULL,
                                       CONSTRAINT fk_owns_person FOREIGN KEY (person_id) REFERENCES Person (person_id) ON DELETE CASCADE,
                                       CONSTRAINT fk_owns_photo FOREIGN KEY (photo_id) REFERENCES Photo (photo_id) ON DELETE CASCADE
      ) PRIMARY KEY (person_id, photo_id);
      ""","""
      CREATE TABLE IF NOT EXISTS PersonAppearsInPhoto (
                                            person_id STRING(36) NOT NULL,
                                            photo_id  STRING(36) NOT NULL,
                                            CONSTRAINT fk_appears_person FOREIGN KEY (person_id) REFERENCES Person (person_id) ON DELETE CASCADE,
                                            CONSTRAINT fk_appears_photo FOREIGN KEY (photo_id) REFERENCES Photo (photo_id) ON DELETE CASCADE
      ) PRIMARY KEY (person_id, photo_id);
      ""","""
      CREATE TABLE IF NOT EXISTS PersonPhotographedWithPerson (
                                                    person1_id STRING(36) NOT NULL,
                                                    person2_id STRING(36) NOT NULL,
                                                    frequency  INT64,
                                                    last_seen  TIMESTAMP,
                                                    CONSTRAINT fk_photographed_person1 FOREIGN KEY (person1_id) REFERENCES Person (person_id) ON DELETE CASCADE,
                                                    CONSTRAINT fk_photographed_person2 FOREIGN KEY (person2_id) REFERENCES Person (person_id) ON DELETE CASCADE,
                                                    CHECK (person1_id < person2_id)
      ) PRIMARY KEY (person1_id, person2_id);
      ""","""
      CREATE TABLE IF NOT EXISTS PersonRelationships (
                                           person1_id        STRING(36) NOT NULL,
                                           person2_id        STRING(36) NOT NULL,
                                           relationship_type STRING(MAX) NOT NULL,
                                           status            STRING(MAX),
                                           created_at        TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
                                           CONSTRAINT fk_relationship_person1 FOREIGN KEY (person1_id) REFERENCES Person (person_id) ON DELETE CASCADE,
                                           CONSTRAINT fk_relationship_person2 FOREIGN KEY (person2_id) REFERENCES Person (person_id) ON DELETE CASCADE,
                                           CHECK (person1_id < person2_id)
      ) PRIMARY KEY (person1_id, person2_id);
      """,
      # --- 2. Indexes ---
      "CREATE INDEX IF NOT EXISTS IDX_Photo_location_name ON Photo(location_name)",
      "CREATE INDEX IF NOT EXISTS IDX_Photo_timestamp ON Photo(timestamp DESC)",
      "CREATE INDEX IF NOT EXISTS IDX_PersonAppearsInPhoto_photo_id ON PersonAppearsInPhoto(photo_id)",
      "CREATE INDEX IF NOT EXISTS IDX_PersonPhotographedWithPerson_person2_id ON PersonPhotographedWithPerson(person2_id)",
      "CREATE INDEX IF NOT EXISTS IDX_PersonRelationships_person2_id_type ON PersonRelationships(person2_id, relationship_type)",
      "CREATE INDEX IF NOT EXISTS IDX_Memories_user_id_timestamp ON Memories(user_id, creation_timestamp DESC)",
  ]
  return run_ddl_statements(db_instance, ddl_statements, "Create Base Tables and Indexes")

# --- NEW: Function to create the property graph ---
def setup_graph_definition(db_instance):
  """Creates the Property Graph definition based on existing tables."""
  # NOTE: Graph name cannot contain hyphens if unquoted. Using PhotosGraph.
  ddl_statements = [
      # --- Create the Property Graph Definition (Using SOURCE/DESTINATION) ---
      # "DROP PROPERTY GRAPH IF EXISTS PhotosGraph", # Optional for dev
      """
      CREATE PROPERTY GRAPH IF NOT EXISTS PhotosGraph
          NODE TABLES (
            Person KEY (person_id),
            Photo KEY (photo_id)
          )
          EDGE TABLES (
            PersonOwnsPhoto AS Owns
              SOURCE KEY (person_id) REFERENCES Person (person_id)
              DESTINATION KEY (photo_id) REFERENCES Photo (photo_id),

            PersonAppearsInPhoto As AppearsIn
              SOURCE KEY (person_id) REFERENCES Person (person_id)
              DESTINATION KEY (photo_id) REFERENCES Photo (photo_id),

            PersonPhotographedWithPerson as PhotosGraphedWith
              SOURCE KEY (person1_id) REFERENCES Person (person_id)
              DESTINATION KEY (person2_id) REFERENCES Person (person_id),
            
            PersonRelationships as RelationShip
              SOURCE KEY (person1_id) REFERENCES Person (person_id)
              DESTINATION KEY (person2_id) REFERENCES Person (person_id),
          )
      """
  ]
  return run_ddl_statements(db_instance, ddl_statements, "Create Property Graph Definition")



# --- Data Generation / Insertion ---
def generate_uuid(): return str(uuid.uuid4())

def insert_relational_data(db_instance):
    """Inserts the curated data into the new relational tables."""
    if not db_instance:
        print("Skipping data insertion - db connection unavailable.")
        return False
    print("\n--- Inserting Curated Data for Relational Tables ---")

    person_rows = [
        {'person_id': 'p01', 'name': 'Rohan'},
        {'person_id': 'p02', 'name': 'Priya'},
        {'person_id': 'p03', 'name': 'Vikram'},
        {'person_id': 'p04', 'name': 'Maya'},
        {'person_id': 'p05', 'name': 'Anjali'},
        {'person_id': 'p06', 'name': 'Sameer'},
        {'person_id': 'p07', 'name': 'Bruno'},
        {'person_id': 'p08', 'name': 'Zara'},
    ]

    person_relationships_rows = [
        {'person1_id': 'p01', 'person2_id': 'p02', 'relationship_type': 'FAMILY', 'status': 'CONFIRMED', 'created_at': '2015-01-10T10:00:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p03', 'relationship_type': 'FAMILY', 'status': 'CONFIRMED', 'created_at': '2015-01-10T10:00:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p04', 'relationship_type': 'FAMILY', 'status': 'CONFIRMED', 'created_at': '2015-01-10T10:00:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p05', 'relationship_type': 'FRIEND', 'status': 'CONFIRMED', 'created_at': '2017-08-21T18:30:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p06', 'relationship_type': 'FRIEND', 'status': 'CONFIRMED', 'created_at': '2017-09-01T12:00:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p07', 'relationship_type': 'PET', 'status': 'CONFIRMED', 'created_at': '2020-06-15T11:00:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p08', 'relationship_type': 'FRIEND', 'status': 'CONFIRMED', 'created_at': '2022-03-05T20:15:00Z'},
        {'person1_id': 'p02', 'person2_id': 'p03', 'relationship_type': 'FAMILY', 'status': 'CONFIRMED', 'created_at': '1995-12-02T14:00:00Z'},
        {'person1_id': 'p05', 'person2_id': 'p06', 'relationship_type': 'FRIEND', 'status': 'CONFIRMED', 'created_at': '2017-08-25T13:00:00Z'},
    ]

    photo_rows = [
        {'photo_id': 'ph01', 'timestamp': '2023-11-20T13:30:00Z', 'location_name': 'Goa, India', 'photo_location': 'gcs://my-photos-bucket/ph01.jpg'},
        {'photo_id': 'ph02', 'timestamp': '2021-11-04T20:00:00Z', 'location_name': 'Home, Delhi', 'photo_location': 'gcs://my-photos-bucket/ph02.jpg'},
        {'photo_id': 'ph03', 'timestamp': '2025-04-12T09:15:00Z', 'location_name': 'City Park', 'photo_location': 'gcs://my-photos-bucket/ph03.jpg'},
        {'photo_id': 'ph04', 'timestamp': '2018-02-18T16:45:00Z', 'location_name': 'College Campus', 'photo_location': 'gcs://my-photos-bucket/ph04.jpg'},
        {'photo_id': 'ph05', 'timestamp': '2024-07-26T11:50:00Z', 'location_name': 'Himalayan Trek', 'photo_location': 'gcs://my-photos-bucket/ph05.jpg'},
        {'photo_id': 'ph06', 'timestamp': '2025-01-15T19:30:00Z', 'location_name': 'Home, Delhi', 'photo_location': 'gcs://my-photos-bucket/ph06.jpg'},
    ]

    person_owns_photo_rows = [
        {'person_id': 'p01', 'photo_id': 'ph01'},
        {'person_id': 'p01', 'photo_id': 'ph02'},
        {'person_id': 'p01', 'photo_id': 'ph03'},
        {'person_id': 'p01', 'photo_id': 'ph04'},
        {'person_id': 'p01', 'photo_id': 'ph05'},
        {'person_id': 'p01', 'photo_id': 'ph06'},
    ]

    person_appears_in_photo_rows = [
        {'person_id': 'p01', 'photo_id': 'ph01'}, {'person_id': 'p05', 'photo_id': 'ph01'}, {'person_id': 'p06', 'photo_id': 'ph01'},
        {'person_id': 'p01', 'photo_id': 'ph02'}, {'person_id': 'p02', 'photo_id': 'ph02'}, {'person_id': 'p03', 'photo_id': 'ph02'}, {'person_id': 'p04', 'photo_id': 'ph02'},
        {'person_id': 'p01', 'photo_id': 'ph03'}, {'person_id': 'p07', 'photo_id': 'ph03'},
        {'person_id': 'p01', 'photo_id': 'ph04'}, {'person_id': 'p05', 'photo_id': 'ph04'},
        {'person_id': 'p01', 'photo_id': 'ph05'}, {'person_id': 'p06', 'photo_id': 'ph05'}, {'person_id': 'p08', 'photo_id': 'ph05'},
        {'person_id': 'p01', 'photo_id': 'ph06'}, {'person_id': 'p02', 'photo_id': 'ph06'}, {'person_id': 'p03', 'photo_id': 'ph06'},
    ]

    person_photographed_with_person_rows = [
        {'person1_id': 'p01', 'person2_id': 'p02', 'frequency': 2, 'last_seen': '2025-01-15T19:30:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p03', 'frequency': 2, 'last_seen': '2025-01-15T19:30:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p04', 'frequency': 1, 'last_seen': '2021-11-04T20:00:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p05', 'frequency': 2, 'last_seen': '2023-11-20T13:30:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p06', 'frequency': 2, 'last_seen': '2024-07-26T11:50:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p07', 'frequency': 1, 'last_seen': '2025-04-12T09:15:00Z'},
        {'person1_id': 'p01', 'person2_id': 'p08', 'frequency': 1, 'last_seen': '2024-07-26T11:50:00Z'},
        {'person1_id': 'p02', 'person2_id': 'p03', 'frequency': 2, 'last_seen': '2025-01-15T19:30:00Z'},
        {'person1_id': 'p02', 'person2_id': 'p04', 'frequency': 1, 'last_seen': '2021-11-04T20:00:00Z'},
        {'person1_id': 'p03', 'person2_id': 'p04', 'frequency': 1, 'last_seen': '2021-11-04T20:00:00Z'},
        {'person1_id': 'p05', 'person2_id': 'p06', 'frequency': 1, 'last_seen': '2023-11-20T13:30:00Z'},
        {'person1_id': 'p06', 'person2_id': 'p08', 'frequency': 1, 'last_seen': '2024-07-26T11:50:00Z'},
    ]

    memories_rows = [
        {'memory_id': 'mem01', 'user_id': 'p01', 'memory_title': 'Unforgettable Goa Trip!', 'memory_description': 'That amazing trip to Goa with Anjali and Sameer back in 2023. The beaches were incredible!', 'creation_timestamp': '2024-01-15T22:00:00Z'},
        {'memory_id': 'mem02', 'user_id': 'p01', 'memory_title': 'Diwali 2021', 'memory_description': 'A beautiful Diwali night with the whole family at home. Everyone looks so happy.', 'creation_timestamp': '2022-05-20T15:30:00Z'},
    ]

    def insert_data_txn(transaction):
        transaction.insert("Person", columns=("person_id", "name"), values=[(r["person_id"], r["name"]) for r in person_rows])
        transaction.insert("PersonRelationships", columns=("person1_id", "person2_id", "relationship_type", "status", "created_at"), values=[(r["person1_id"], r["person2_id"], r["relationship_type"], r["status"], r["created_at"]) for r in person_relationships_rows])
        transaction.insert("Photo", columns=("photo_id", "timestamp", "location_name", "photo_location"), values=[(r["photo_id"], r["timestamp"], r["location_name"], r["photo_location"]) for r in photo_rows])
        transaction.insert("PersonOwnsPhoto", columns=("person_id", "photo_id"), values=[(r["person_id"], r["photo_id"]) for r in person_owns_photo_rows])
        transaction.insert("PersonAppearsInPhoto", columns=("person_id", "photo_id"), values=[(r["person_id"], r["photo_id"]) for r in person_appears_in_photo_rows])
        transaction.insert("PersonPhotographedWithPerson", columns=("person1_id", "person2_id", "frequency", "last_seen"), values=[(r["person1_id"], r["person2_id"], r["frequency"], r["last_seen"]) for r in person_photographed_with_person_rows])
        transaction.insert("Memories", columns=("memory_id", "user_id", "memory_title", "memory_description", "creation_timestamp"), values=[(r["memory_id"], r["user_id"], r["memory_title"], r["memory_description"], r["creation_timestamp"]) for r in memories_rows])
        print(f"Transaction attempting to insert {len(person_rows)} person rows.")
        print(f"Transaction attempting to insert {len(person_relationships_rows)} person relationship rows.")
        print(f"Transaction attempting to insert {len(photo_rows)} photo rows.")
        print(f"Transaction attempting to insert {len(person_owns_photo_rows)} person owns photo rows.")
        print(f"Transaction attempting to insert {len(person_appears_in_photo_rows)} person appears in photo rows.")
        print(f"Transaction attempting to insert {len(person_photographed_with_person_rows)} person photographed with person rows.")
        print(f"Transaction attempting to insert {len(memories_rows)} memories rows.")

    try:
        db_instance.run_in_transaction(insert_data_txn)
        print("Transaction committed successfully.")
        return True
    except exceptions.Aborted as e:
        print(f"ERROR: Data insertion transaction aborted: {e}. Consider retrying.")
        return False
    except Exception as e:
        print(f"ERROR during data insertion transaction: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        print("Data insertion failed.")
        return False


# --- Main Execution ---
if __name__ == "__main__":
  print("Starting Spanner Relational Schema Setup Script...")
  start_time = time.time()

  if not database:
    print("\nCritical Error: Spanner database connection not established. Aborting.")
    exit(1)

  # --- Step 1: Create schema (No Drops) ---
  # Added IF NOT EXISTS to CREATE INDEX statements for robustness
  if not setup_base_schema_and_indexes(database):
    print("\nAborting script due to errors during base schema/index creation.")
    exit(1)

  # --- Step 2: Create graph definition ---
  # Run this in a separate DDL operation
  if not setup_graph_definition(database):
    print("\nAborting script due to errors during graph definition creation.")
    exit(1)

  # --- Step 3: Insert data into the base tables ---
  if not insert_relational_data(database):
    print("\nScript finished with errors during data insertion.")
    exit(1)

  end_time = time.time()
  print("\n-----------------------------------------")
  print("Script finished successfully!")
  print(f"Database '{DATABASE_ID}' on instance '{INSTANCE_ID}' has been set up with the relational schema and populated.")
  print(f"Total time: {end_time - start_time:.2f} seconds")
  print("-----------------------------------------")
