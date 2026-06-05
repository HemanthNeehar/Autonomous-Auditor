"""Local A2A server for the Autonomous Auditor Agent.

Usage: uv run python -m runtime.server
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv

# --- Path Setup ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))
load_dotenv(SRC_DIR / ".env")
from agents.agent import auditor_agent

AGENT_PORT = 8089


async def run_server():
    from .agent_card import create_auditor_card
    from .agent_executor import AuditExecutor

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise ValueError("GOOGLE_CLOUD_PROJECT must be set.")

    print("=" * 60)
    print("Starting Auditor Agent Local A2A Server")
    print("=" * 60)

    agent_card = create_auditor_card()
    executor = AuditExecutor()
    handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())

    # Import the FastAPI app from ui.app
    from ui.app import app as fastapi_app
    
    a2a_app = A2AStarletteApplication(agent_card=agent_card, http_handler=handler)
    
    # Mount the A2A endpoints onto the existing FastAPI app
    a2a_app.add_routes_to_app(fastapi_app, agent_card_url='/.well-known/agent.json', rpc_url='/')
    
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=AGENT_PORT, log_level="info", loop="none")

    print(f"Auditor A2A server: http://127.0.0.1:{AGENT_PORT}")
    print(f"Agent card: http://127.0.0.1:{AGENT_PORT}/.well-known/agent.json")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(run_server())