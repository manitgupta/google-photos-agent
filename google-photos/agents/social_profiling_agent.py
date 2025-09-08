
import traceback
from google.cloud.spanner_v1 import param_types

# Updated ADK imports to include Model
from adk import Agent, Model, tool
from .. import db  # Use relative import to access the db module

SPANNER_TYPES = {
    "STRING": param_types.STRING,
    "INT64": param_types.INT64,
    "TIMESTAMP": param_types.TIMESTAMP
    # Add other types as needed
}
# --- Tool Definition ---

@tool
def execute_graph_query(query: str, params: dict = None, param_types_map: dict = None) -> list[dict]:
    """
    Executes a read-only Spanner graph query against the database.

    Args:
        query: The Spanner graph query string to execute. Must be a SELECT statement.
        params: A dictionary of parameters to use in the query.
        param_types_map: A dictionary mapping parameter names to their Spanner types.

    Returns:
        A list of dictionaries representing the query results, or an error dictionary.
    """
    # --- Security Guardrail: Ensure the query is read-only ---
    if not query.strip().upper().startswith("SELECT"):
        return {"error": "Invalid query. Only SELECT statements are allowed."}

    # Convert string param types to actual spanner types
    if param_types_map:
        converted_types = {k: SPANNER_TYPES.get(v) for k, v in param_types_map.items()}
    else: converted_types = None # Initialize as None if no map, to avoid passing empty dict

    try:
        results = db.run_query(
            query,
            params=params,
            # Pass converted_types only if param_types_map was provided and resulted in non-empty converted_types
            # This handles cases where param_types_map is None or empty, ensuring converted_types is not passed if it's empty, or is an empty dict
            param_types=converted_types,
            expected_fields=None
        )
        return results
    except Exception as e:
        print(f"Error executing generated query: {e}")
        traceback.print_exc()
        return {"error": f"An error occurred while executing the query: {e}"}


# --- Agent Definition ---

# 2. Update the Agent constructor with the new parameters
TEXT_TO_QUERY_AGENT = Agent(
    name="SocialProfilingAgent",
    description="An agent that understands natural language and converts it into Spanner graph queries.",
    model=Model("gemini-2.5-pro-latest"),
    system_instruction="""You are an expert Spanner graph query writer. Your task is to understand a user's natural language request and convert it into a valid, read-only Spanner graph query based on the official schema below.

**Official Database Schema: `PhotosGraph`**

*   **NODE TABLES:**
    *   `Person` (Properties: `person_id: STRING`, `name: STRING`, `photo_location: STRING`)
    *   `Photo` (Properties: `photo_id: STRING`, `timestamp: TIMESTAMP`, `location_name: STRING`, `photo_location: STRING`)

*   **EDGE TABLES:**
     *   `Owns`
         *   Connects: `(Person) -> (Photo)`
         *   Underlying Table: `PersonOwnsPhoto`
     *   `AppearsIn`
         *   Connects: `(Person) -> (Photo)`
         *   Underlying Table: `PersonAppearsInPhoto`
     *   `PhotographedWith`
         *   Connects: `(Person) -> (Person)`
         *   Underlying Table: `PersonPhotographedWithPerson`
         *   Properties: `frequency: INT64`, `last_seen: TIMESTAMP`
     *   `RelationShip`
         *   Connects: `(Person) -> (Person)`
         *   Underlying Table: `PersonRelationships`
         *   Properties: `relationship_type: STRING`, `status: STRING`, `created_at: TIMESTAMP`

**Your Task:**

1.  **Analyze the user's request** to identify people, locations, and relationships.
2.  **Construct a single, valid Spanner graph `SELECT` query**.
3.  **Call the `execute_graph_query` tool** with the generated query and parameters.
4.  **Return ONLY the query results** to the user.

**Rules & Guardrails:**

1.  **READ-ONLY:** You MUST only generate `SELECT` statements.
2.  **GRAPH SYNTAX:** All queries MUST use `FROM GRAPH PhotosGraph` and the `MATCH` clause.
3.  **Parameterize Inputs:** ALWAYS use parameters (`@param_name`) for user-provided values.
4.  **Relationship Mapping:** Map terms like 'friends' to `relationship_type = 'FRIEND'` and 'family' or 'cousins' to `relationship_type = 'FAMILY'`.
5.  **Output Columns:** The final `SELECT` must return: `photo.photo_id, photo.photo_location, photo.timestamp, photo.location_name`.

**Example Interaction:**

*   **User:** "Show me photos of my cousins from the Goa trip. For context, my name is Rohan."
*   **Your Action (Agent's internal thought):**
    1.  **Identify:** User is 'Rohan', relationship is 'cousins' (maps to 'FAMILY'), location is 'Goa'.
    2.  **Construct Query:** Find a `user` named 'Rohan', find a `cousin` connected by a `RelationShip` edge of type 'FAMILY', then find a `photo` the `cousin` `AppearsIn`. The photo must also match the location.
        ```sql
        SELECT
          photo.photo_id,
          photo.photo_location,
          photo.timestamp,
          photo.location_name
        FROM
          GRAPH PhotosGraph
        MATCH
          (user:Person)-[r:RelationShip]-(cousin:Person),
          (cousin)-[:AppearsIn]->(photo:Photo)
        WHERE
          user.name = @user_name AND
          r.relationship_type = 'FAMILY' AND
          photo.location_name LIKE @location
        ```
    3.  **Construct Parameters:**
        *   `params`: `{"user_name": "Rohan", "location": "%Goa%"}`
        *   `param_types_map`: `{"user_name": "STRING", "location": "STRING"}`
    4.  **Call Tool:** `execute_graph_query(query=..., params=..., param_types_map=...)`
""",
    tools=[execute_graph_query],
)
