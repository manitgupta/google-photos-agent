from a2a.server.apps import A2AStarletteApplication
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
import os
import logging
from dotenv import load_dotenv
from photos_mcp_client.agent_executor import PhotosAgentExecutor
import uvicorn
from photos_mcp_client import agent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

host=os.environ.get("A2A_HOST", "localhost")
port=int(os.environ.get("A2A_PORT",10002))
PUBLIC_URL=os.environ.get("PUBLIC_URL")

class PhotosAgent:
  """An agent that creates memories for Google Photos."""

  SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

  def __init__(self):
    self._agent = self._build_agent()
    self.runner = Runner(
        app_name=self._agent.name,
        agent=self._agent,
        artifact_service=InMemoryArtifactService(),
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
    )
    capabilities = AgentCapabilities(streaming=True)
    skill = AgentSkill(
            id="google_photos_memory_creation",
            name="Create Google Photos memories",
            description="""
            This "Google Photos" agent helps you create memories by identifying the memory title, description, user ID, and a GCS URL for memory media.
            It efficiently collects required information and utilizes dedicated tools to perform these actions on your behalf, ensuring a smooth sharing experience.
            """,
            tags=["google_photos"],
            examples=["Create a memory titled 'My Summer Vacation' with description 'Had a great time at the beach!' for user p01 and media gs://my-bucket/summer.jpg"],
        )
    self.agent_card = AgentCard(
            name="Google Photos Memory Agent",
            description="""
            This "Google Photos" agent helps you create memories by identifying the memory title, description, user ID, and a GCS URL for memory media.
            It efficiently collects required information and utilizes dedicated tools to perform these actions on your behalf, ensuring a smooth sharing experience.
            """,
            url=f"{PUBLIC_URL}",
            version="1.0.0",
            defaultInputModes=PhotosAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=PhotosAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )


  def get_processing_message(self) -> str:
      return "Processing the social post and event request..."

  def _build_agent(self) -> LlmAgent:
    """Builds the LLM agent for the Processing the social post and event request."""
    return agent.root_agent


if __name__ == '__main__':
    try:
        photosAgent = PhotosAgent()

        request_handler = DefaultRequestHandler(
            agent_executor=PhotosAgentExecutor(photosAgent.runner,photosAgent.agent_card),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=photosAgent.agent_card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)