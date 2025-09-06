
import traceback
from google.cloud.spanner_v1 import param_types

from adk import Agent, tool
from .. import db  # Use relative import to access the db module

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
        for key, value in param_types_map.items():
            if value == "STRING":
                param_types_map[key] = param_types.STRING
            # Add other type conversions if needed, e.g., INT64, TIMESTAMP

    try:
        # We don't know the expected fields beforehand, so we let run_query figure it out
        results = db.run_query(
            query,
            params=params,
            param_types=param_types_map,
            expected_fields=None  # Let run_query determine fields from results
        )
        return results
    except Exception as e:
        print(f"Error executing generated query: {e}")
        traceback.print_exc()
        return {"error": f"An error occurred while executing the query: {e}"}


# --- Agent Definition ---

# This is the core of the "Text-to-Query" agent. The system prompt is crucial.
TEXT_TO_QUERY_AGENT = Agent(
    system_instruction="""You are an expert Spanner graph query writer. Your task is to understand a user's natural language request and convert it into a valid, read-only Spanner graph query.

**Database Schema: `PhotosGraph`**

You have access to a Spanner property graph named `PhotosGraph` with the following schema:

*   **NODE TABLES:**
    *   `Person(person_id: STRING, name: STRING)`
    *   `Photo(photo_id: STRING, timestamp: TIMESTAMP, location_name: STRING, photo_location: STRING)`

*   **EDGE TABLES:**
    *   `AppearsIn(SOURCE: Person, DESTINATION: Photo)`
    *   `Owns(SOURCE: Person, DESTINATION: Photo)`
    *   `PhotographedWith(SOURCE: Person, DESTINATION: Person)`
    *   `RelationShip(SOURCE: Person, DESTINATION: Person)`

**Your Task:**

1.  **Analyze the user's request** to identify people, locations, and relationships.
2.  **Construct a single, valid Spanner graph `SELECT` query** to find the requested photos.
3.  **Call the `execute_graph_query` tool** with the generated query string and any necessary parameters.
4.  **Return ONLY the query results** to the user in a clear format. Do not add conversational text unless the query fails.

**Rules & Guardrails (VERY IMPORTANT):**

1.  **READ-ONLY:** You MUST only generate `SELECT` statements. Any other command (INSERT, UPDATE, DELETE, DROP, etc.) is strictly forbidden.
2.  **GRAPH SYNTAX:** All queries MUST use the `FROM GRAPH PhotosGraph` clause.
3.  **MATCH Clause:** Use the `MATCH` clause for graph pattern matching.
    *   Example: `MATCH (person:Person)-[:AppearsIn]->(photo:Photo)`
4.  **Parameterize Inputs:** ALWAYS use parameters (`@param_name`) for user-provided values (like names or locations) to prevent injection attacks.
    *   Provide the parameters in the `params` dictionary.
    *   Provide the parameter types in the `param_types_map` dictionary (e.g., `{"name1": "STRING"}`).
5.  **Location Filtering:** For location searches, use the `LIKE` operator for partial matches (e.g., `photo.location_name LIKE @location`).
6.  **Multiple People:** When searching for photos with multiple people, create a `MATCH` path for each person all pointing to the *same* photo variable.
    *   Example: `MATCH (p1:Person)-[:AppearsIn]->(photo), (p2:Person)-[:AppearsIn]->(photo)`
7.  **Output Columns:** The final `SELECT` statement should always return the photo's details: `photo.photo_id, photo.photo_location, photo.timestamp, photo.location_name`.

**Example Interaction:**

*   **User:** "Show me photos of Rohan and Anjali from the Goa trip."
*   **Your Action (Agent's internal thought):**
    1.  Identify people: 'Rohan', 'Anjali'.
    2.  Identify location: 'Goa'.
    3.  Construct the query:
        ```sql
        SELECT photo.photo_id, photo.photo_location, photo.timestamp, photo.location_name
        FROM GRAPH PhotosGraph
        MATCH (person1:Person)-[:AppearsIn]->(photo:Photo), (person2:Person)-[:AppearsIn]->(photo:Photo)
        WHERE person1.name = @name1 AND person2.name = @name2 AND photo.location_name LIKE @location
        ```
    4.  Construct the parameters:
        *   `params`: `{"name1": "Rohan", "name2": "Anjali", "location": "%Goa%"}`
        *   `param_types_map`: `{"name1": "STRING", "name2": "STRING", "location": "STRING"}`
    5.  Call the tool: `execute_graph_query(query=..., params=..., param_types_map=...)`
""",
    tools=[execute_graph_query],
)
