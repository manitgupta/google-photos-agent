import os
import logging
from dotenv import load_dotenv

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService

# Import the local agent and executor definitions
from agents.social_profiling_agent import agent
from agents.social_profiling_agent.agent_executor import SocialAgentExecutor

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
# CRITICAL: Cloud Run provides the PORT environment variable that the server must listen on.
host=os.environ.get("A2A_HOST", "localhost")
port=int(os.environ.get("A2A_PORT",10001))
PUBLIC_URL=os.environ.get("PUBLIC_URL")

class SocialAgent:
    """A wrapper class for the Social Profiling Agent to be exposed via A2A."""
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        self._agent = agent.root_agent
        self.runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id="social_profile_analysis",
            name="Analyze Photo Library Profile",
            description="""
            Using a provided user name and a natural language query, this agent synthesizes a user's photo library to find photos.
            It can find photos based on who is in them (including relationships like 'family' or 'friends'), where they were taken,
            and within a specific time range. It delivers a structured list of photo details as its result.
            """,
            tags=["photos", "social", "spanner"],
            examples=[
                "The logged in user is Rohan. Find photos of my family in Goa.",
                "The logged in user is Priya. Show me pictures of Vikram from last year."
            ],
        )
        self.agent_card = AgentCard(
            name="Social Profiling Agent",
            description="An agent that can find a user's photos based on people, relationships, locations, and dates.",
            url=f"{PUBLIC_URL}",
            version="1.0.0",
            defaultInputModes=self.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=self.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

    def get_processing_message(self) -> str:
        return "Analyzing photo library to find your memories..."

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the social profile analysis agent."""
        return agent.root_agent


if __name__ == '__main__':
    try:
        social_agent = SocialAgent()

        request_handler = DefaultRequestHandler(
            agent_executor=SocialAgentExecutor(social_agent.runner, social_agent.agent_card),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=social_agent.agent_card,
            http_handler=request_handler,
        )
        logger.info(f"Starting server for Agent: {social_agent.agent_card.name}")
        uvicorn.run(server.build(), host='0.0.0.0', port=port)

    except Exception as e:
        logger.error(f"FATAL: An error occurred during server startup: {e}", exc_info=True)
        exit(1)

