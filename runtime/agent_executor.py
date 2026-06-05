import uuid
import vertexai
import os
import sys
import json
from dotenv import load_dotenv
from pathlib import Path
from services.session_manager import create_session_service, SessionManager
from services.memory_manager import create_memory_service
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, UnsupportedOperationError, Part
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError
from google.genai import types
from google.adk import Runner

# --- Path Setup ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))
load_dotenv(SRC_DIR / ".env")
from agents.agent import auditor_agent

APP_NAME: str = "AUTONOMOUS_AUDITOR"
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

# =========================================================================
#  LEGACY RUNNER FACTORY  (used by FastAPI; NOT needed for Agent Engine)
# =========================================================================


async def create_runner():
    """
    Create a fresh InMemoryRunner bound to a new session.

    Each audit invocation should call this factory so sessions are isolated.
    """
    from google.adk.sessions import InMemorySessionService

    session_service = InMemorySessionService()
    runner = Runner(
        node=auditor_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    session_id = str(uuid.uuid4())
    await session_service.create_session(app_name=APP_NAME, user_id="system", session_id=session_id)
    return runner, session_id


class AuditExecutor(AgentExecutor):
    def __init__(self):
        self.agent = None
        self.runner = None
        self.session_manager = None

    def _init_agent(self):
        if self.agent is None:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            vertexai.init(project=project_id, location=location)
            self.agent = auditor_agent

        if self.runner is None:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            session_service = create_session_service(project=project_id, location=location)
            memory_service = create_memory_service(project=project_id, location=location)

            from google.adk.apps import App
            from google.adk.agents.context_cache_config import ContextCacheConfig

            app = App(
                name=self.agent.name,
                root_agent=self.agent,
                context_cache_config=ContextCacheConfig(
                    cache_intervals=10, ttl_seconds=3600, min_tokens=4096
                ),
            )
            self.runner = Runner(
                app=app, session_service=session_service, memory_service=memory_service
            )

        if self.session_manager is None:
            self.session_manager = SessionManager(session_service=self.runner.session_service)

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        if self.agent is None:
            self._init_agent()
        user_id = (
            context.message.metadata.get("user_id")
            if context.message and context.message.metadata
            else "auditor_agent"
        )
        if not context.task_id or not context.context_id:
            raise ValueError("task_id and context_id must not be None")
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not hasattr(context, "current_task") or not context.current_task:
            await updater.submit()
        await updater.start_work()
        audit_data = context.get_user_input()
        if not audit_data:
            audit_data = (
                "Please perform a comprehensive 5-point compliance audit of the retail database."
            )
        try:
            # Force local-only RAG for consistency/speed in standard A2A requests
            os.environ["RAG_LOCAL_ONLY"] = "true"
            await updater.update_status(
                TaskState.working, message=new_agent_text_message("Reviewing audit...")
            )
            if self.runner is not None:
                if self.session_manager is not None:
                    session_id = await self.session_manager.get_or_create_session(
                        context_id=context.context_id,
                        app_name=self.runner.app_name,
                        user_id=user_id,
                    )
                else:
                    # Create new session for each audit
                    session_id = (
                        await self.runner.session_service.create_session(
                            app_name=self.runner.app_name, user_id=user_id
                        )
                    ).id
                content = types.Content(role="user", parts=[types.Part(text=audit_data)])
                final_event = None
                async for event in self.runner.run_async(
                    session_id=session_id, user_id=user_id, new_message=content
                ):
                    # Emit intermediate events for observability
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.function_call:
                                fc = part.function_call
                                await updater.update_status(
                                    TaskState.working,
                                    message=new_agent_text_message(
                                        f"Calling tool: {fc.name} with args: {dict(fc.args) if fc.args else {}}"
                                    ),
                                )
                            elif part.function_response:
                                fr = part.function_response
                                raw = json.dumps(fr.response) if fr.response else ""
                                await updater.update_status(
                                    TaskState.working,
                                    message=new_agent_text_message(
                                        f"Tool {fr.name} returned: {raw[:500]}..."
                                    ),
                                )
                            elif part.text and part.text.strip():
                                text = part.text.strip()
                                if event.content.role == "model":
                                    await updater.update_status(
                                        TaskState.working,
                                        message=new_agent_text_message(
                                            f"Agent thought: {text[:500]}..."
                                        ),
                                    )
                    if event.is_final_response():
                        final_event = event
                        await updater.update_status(
                            TaskState.working,
                            message=new_agent_text_message(
                                "Audit completed. Preparing final report..."
                            ),
                        )
            else:
                await updater.update_status(
                    TaskState.failed,
                    message=new_agent_text_message("Agent runner is not initialized"),
                    final=True,
                )

            if final_event and final_event.content and final_event.content.parts:
                text = "".join(
                    p.text for p in final_event.content.parts if hasattr(p, "text") and p.text
                )
                if text:
                    await updater.add_artifact([Part(TextPart(text=text))], name="result")
                    await updater.complete()
                    return
            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message("Failed to get a final audit report."),
                final=True,
            )
        except Exception as e:
            # Added more specific error logging
            print(f"ERROR during audit execution: {e}", file=sys.stderr)
            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message(f"Audit failed: {type(e).__name__} - {e}"),
                final=True,
            )

    async def cancel(self, context, event_queue):
        raise ServerError(error=UnsupportedOperationError())
