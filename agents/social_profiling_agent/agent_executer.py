import logging
from typing import TYPE_CHECKING

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    FilePart,
    FileWithBytes,
    Part,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils.errors import ServerError
from google.adk.runners import Runner
from google.genai import types

if TYPE_CHECKING:
    from google.adk.sessions.session import Session

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Constants
DEFAULT_USER_ID = 'self'

class SocialAgentExecutor(AgentExecutor):
    """Connects the A2A server to the ADK Runner for the Social Profiling Agent."""
    def __init__(self, runner: Runner, card: AgentCard):
        self.runner = runner
        self._card = card
        self._active_sessions: set[str] = set()

    async def _process_request(
            self,
            new_message: types.Content,
            session_id: str,
            task_updater: TaskUpdater,
    ) -> None:
        session_obj = await self._upsert_session(session_id)
        session_id = session_obj.id
        self._active_sessions.add(session_id)

        try:
            async for event in self.runner.run_async(
                    session_id=session_id,
                    user_id=DEFAULT_USER_ID,
                    new_message=new_message,
            ):
                if event.is_final_response():
                    parts = [
                        convert_genai_part_to_a2a(part)
                        for part in event.content.parts
                        if (part.text or part.file_data or part.inline_data)
                    ]
                    logger.debug('Yielding final response: %s', parts)
                    await task_updater.add_artifact(parts)
                    await task_updater.update_status(
                        TaskState.completed, final=True
                    )
                    break
                if not event.get_function_calls():
                    logger.debug('Yielding update response')
                    await task_updater.update_status(
                        TaskState.working,
                        message=task_updater.new_agent_message(
                            [
                                convert_genai_part_to_a2a(part)
                                for part in event.content.parts
                                if (part.text)
                            ],
                        ),
                    )
                else:
                    logger.debug('Skipping tool call event for now.')
        finally:
            self._active_sessions.discard(session_id)

    async def execute(
            self,
            context: RequestContext,
            event_queue: EventQueue,
    ):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.update_status(TaskState.submitted)
        await updater.update_status(TaskState.working)
        await self._process_request(
            types.Content(
                role="user",
                parts=[
                    convert_a2a_part_to_genai(part)
                    for part in context.message.parts
                ],
            ),
            context.context_id,
            updater,
        )
        logger.debug('[SocialAgentExecutor] execute exiting')

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        session_id = context.context_id
        if session_id in self._active_sessions:
            logger.info(f'Cancellation requested for active session: {session_id}')
            self._active_sessions.discard(session_id)
        else:
            logger.debug(f'Cancellation requested for inactive session: {session_id}')

        raise ServerError(error=UnsupportedOperationError())

    async def _upsert_session(self, session_id: str) -> 'Session':
        session = await self.runner.session_service.get_session(
            app_name=self.runner.app_name,
            user_id=DEFAULT_USER_ID,
            session_id=session_id,
        )
        if session is None:
            session = await self.runner.session_service.create_session(
                app_name=self.runner.app_name,
                user_id=DEFAULT_USER_ID,
                session_id=session_id,
            )
        return session

def convert_a2a_part_to_genai(part: Part) -> types.Part:
    part = part.root
    if isinstance(part, TextPart):
        return types.Part(text=part.text)
    raise ValueError(f'Unsupported part type: {type(part)}')

def convert_genai_part_to_a2a(part: types.Part) -> Part:
    if part.text:
        return Part(root=TextPart(text=part.text))
    if part.inline_data:
        return Part(
            root=FilePart(
                file=FileWithBytes(
                    bytes=part.inline_data.data,
                    mime_type=part.inline_data.mime_type,
                )
            )
        )
    raise ValueError(f'Unsupported part type: {part}')
