import asyncio
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams
import logging 
import os
import nest_asyncio 


# Load environment variables from .env file in the parent directory
# Place this near the top, before using env vars like API keys
load_dotenv()
MCP_SERVER_URL=os.environ.get("MCP_SERVER_URL", "http://0.0.0.0:8080/sse")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
 
# --- Global variables ---
# Define them first, initialize as None
root_agent: LlmAgent | None = None
exit_stack: AsyncExitStack | None = None


async def get_tools_async():
  print("Attempting to connect to MCP Filesystem server...")
  """Gets tools from the File System MCP Server."""
  tools =  MCPToolset(
      connection_params=SseServerParams(url=MCP_SERVER_URL, headers={})
  )
  log.info("MCP Toolset created successfully.")

  return tools
 

async def get_agent_async():
  """
  Asynchronously creates the MCP Toolset and the LlmAgent.

  Returns:
      tuple: (LlmAgent instance, AsyncExitStack instance for cleanup)
  """
  tools = await get_tools_async()

  root_agent = LlmAgent(
      model='gemini-2.5-flash', # Adjust model name if needed based on availability
      name='create_post_event_agent',
      instruction="""
        You are a friendly and efficient assistant for the google photos app.
        Your primary goal is to help users create memories using the available tools.

        When a user asks to create a memory:
        1.  You MUST identify the **memory title** and the **memory description**.
        2.  You MUST identify the **user ID**. If the user does not provide a user ID, use "p01" as the default.
        3.  You MUST identify a **GCS URL for memory media** (e.g., "gs://your-bucket/your-image.jpg").
        4.  Once you have the `user_id`, `memory_title`, `memory_description`, and `memory_media`, call the `create_post` tool with these arguments.

        General Guidelines:
        - If any required information for creating a memory (like memory title or description) is missing from the user's initial request, politely ask the user for the specific missing pieces of information.
        - Before executing an action (calling a tool), you can optionally provide a brief summary of what you are about to do (e.g., "Okay, I'll create a memory titled '[memory_title]' with description '[memory_description]' for user '[user_id]'.").
        - Use only the provided tools. Do not try to perform actions outside of their scope.
      """,
        tools=[tools],
  )
  print("LlmAgent created.")

  # Return both the agent and the exit_stack needed for cleanup
  return root_agent


async def initialize():
   """Initializes the global root_agent and exit_stack."""
   global root_agent
   if root_agent is None:
       log.info("Initializing agent...")
       root_agent = await get_agent_async()
       if root_agent:
           log.info("Agent initialized successfully.")
       else:
           log.error("Agent initialization failed.")
   else:
       log.info("Agent already initialized.")



nest_asyncio.apply()

log.info("Running agent initialization at module level using asyncio.run()...")
try:
    asyncio.run(initialize())
    log.info("Module level asyncio.run(initialize()) completed.")
except RuntimeError as e:
    log.error(f"RuntimeError during module level initialization (likely nested loops): {e}", exc_info=True)
except Exception as e:
    log.error(f"Unexpected error during module level initialization: {e}", exc_info=True)