"""
a2a_server.py — FastAPI Application exposing Autonomous Auditor as an A2A Remote Agent
"""

import os
import sys
import uuid
import json
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup paths and environment
load_dotenv()

# Logger configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("A2AServer")

# Monkeypatch tools.adk_tools.datetime to freeze the baseline date to May 24, 2026
import tools.adk_tools
from datetime import datetime as original_datetime


class MockDatetime(original_datetime):
    @classmethod
    def now(cls, tz=None):
        return original_datetime(2026, 5, 24, 12, 0, 0)


tools.adk_tools.datetime = MockDatetime

# Import A2A SDK and Fast API components
import uvicorn
from fastapi import FastAPI
from a2a.types import (
    AgentCard,
    Message,
    Role,
    Part,
    TextPart,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
)
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.apps.jsonrpc.fastapi_app import A2AFastAPIApplication

# Import ADK core components and existing agent
import vertexai
from agents.agent import auditor_agent
from google.adk import Runner
from google.adk.apps import App
from google.adk.agents.context_cache_config import ContextCacheConfig
from services.session_manager import create_session_service
from services.memory_manager import create_memory_service
from google.genai import types


from runtime.agent_executor import AuditExecutor

# Load metadata card
card_path = Path(__file__).resolve().parent / "A2A" / "agent_card.json"
with open(card_path, "r") as f:
    card_dict = json.load(f)
agent_card = AgentCard.model_validate(card_dict)

# Configure A2A Request Handler & Fast API App
executor = AuditExecutor()
task_store = InMemoryTaskStore()
http_handler = DefaultRequestHandler(agent_executor=executor, task_store=task_store)

a2a_app = A2AFastAPIApplication(agent_card=agent_card, http_handler=http_handler)

app = a2a_app.build()

from fastapi.responses import Response

# Remove the default compact agent card route so we can serve a pretty-printed version
for route in list(app.routes):
    if getattr(route, "path", None) == "/.well-known/agent-card.json":
        app.routes.remove(route)
        break

@app.get("/.well-known/agent-card.json")
def get_pretty_agent_card():
    return Response(
        content=json.dumps(agent_card.model_dump(mode="json", exclude_none=True), indent=2),
        media_type="application/json"
    )


@app.get("/")
def home():
    return {
        "status": "online",
        "agent": "Autonomous Auditor",
        "protocol": "A2A Remote Agent",
        "card_endpoint": "/.well-known/agent-card.json",
        "rpc_endpoint": "/rpc",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Start A2A Remote Agent Server")
    parser.add_argument("--port", type=int, default=None, help="Port to run the server on")
    args = parser.parse_known_args()[0]

    # Prioritize CLI argument, then environment variable, then default to 8000
    port = args.port
    if port is None:
        port = int(os.getenv("A2A_PORT", "8000"))

    logger.info(f"Starting A2A Remote Agent Server on port {port}...")
    uvicorn.run("a2a_server:app", host="0.0.0.0", port=port, reload=False)
