from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient

toolbox = ToolboxSyncClient("http://127.0.0.1:5000")

# Load single tool
# tools = toolbox.load_tool('search-hotels-by-location')

# Load all the tools
tools = toolbox.load_toolset('photo_search_toolset')

root_agent = Agent(
    name="hotel_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to search for photos given a user query in the spanner backend photos database"
    ),
    instruction=(
        "You are a helpful agent that interprets the user search query and uses the provided tools to fetch the links of the photos that match the user search requirements."
    ),
    tools=tools,
)