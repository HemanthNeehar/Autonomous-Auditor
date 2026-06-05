import os
import json
import sys
from pathlib import Path
from typing import Any

# Ensure parent directory is in path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from vertexai.preview.reasoning_engines import A2aAgent
from a2a.types import AgentCard

# Import components
from runtime.agent_executor import AuditExecutor
from runtime.firestore_task_store import FirestoreTaskStore

_vertex_a2a_task_store_singleton: list = []

def _singleton_task_store(**_kwargs: Any) -> FirestoreTaskStore:
    if not _vertex_a2a_task_store_singleton:
        _vertex_a2a_task_store_singleton.append(
            FirestoreTaskStore(collection_name="auditor_tasks")
        )
    return _vertex_a2a_task_store_singleton[0]

class PlaygroundCompatibleA2aAgent(A2aAgent):
    """Exposes standard A2A operations made compatible with the Google Cloud Console Playground."""

    def register_operations(self) -> dict[str, list[str]]:
        routes = super().register_operations()
        routes[""] = ["query"]
        return routes

    async def query(
        self, input: str = "", text: str = "", query: str = "", **kwargs: Any
    ) -> str:
        """Standard query interface for testing in the GCP Console Playground.

        CRITICAL: Returns a raw string directly so the front-end chat interface
        can seamlessly render the text bubble response.
        """
        user_query = input or text or query or ""
        if not user_query:
            return "No query provided."

        executor_builder = self._tmpl_attrs.get("agent_executor_builder")
        if not executor_builder:
            return "Executor not configured."

        executor = executor_builder(**self._tmpl_attrs.get("agent_executor_kwargs"))
        executor._init_agent()

        user_id = "playground_user"
        session_id = "playground_session"

        from google.genai import types

        content = types.Content(role="user", parts=[types.Part(text=user_query)])

        try:
            session = await executor.runner.session_service.get_session(
                app_name=executor.runner.app_name,
                user_id=user_id,
                session_id=session_id,
            ) or await executor.runner.session_service.create_session(
                app_name=executor.runner.app_name,
                user_id=user_id,
                session_id=session_id,
            )

            final_event = None
            async for event in executor.runner.run_async(
                session_id=session.id,
                user_id=user_id,
                new_message=content,
            ):
                if event.is_final_response():
                    final_event = event

            if final_event and final_event.content and final_event.content.parts:
                response_text = "".join(
                    part.text
                    for part in final_event.content.parts
                    if hasattr(part, "text") and part.text
                )
                if response_text:
                    return response_text

            return "No response text generated."
        except Exception as e:
            return f"Error running query: {str(e)}"

# Load the pydantic AgentCard from agent_card.json
card_path = Path(__file__).resolve().parent.parent / "A2A" / "agent_card.json"
with open(card_path, "r") as f:
    card_dict = json.load(f)
agent_card = AgentCard.model_validate(card_dict)

# Force preferred transport to HTTP+JSON for Vertex A2A compliance
from a2a.types import TransportProtocol
agent_card.preferred_transport = TransportProtocol.http_json

# Instantiate the A2aAgent for Vertex deployment
a2a_agent = PlaygroundCompatibleA2aAgent(
    agent_card=agent_card,
    agent_executor_builder=AuditExecutor,
    task_store_builder=_singleton_task_store,
)
