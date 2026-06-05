import vertexai
import os
import sys
import json
import logging
from pathlib import Path
from typing import Any
from google.protobuf import json_format
from dotenv import load_dotenv

# Ensure parent directory is in path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.getenv("STAGING_BUCKET")
SERVICE_ACCOUNT = os.getenv("SERVICE_ACCOUNT")
MCP_TOOLBOX_URL = os.getenv("MCP_TOOLBOX_URL")

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

def _a2a_agent_card_json_for_deploy(agent: Any) -> str:
    """Serialize A2aAgent.agent_card for class_methods/ Agent Registry.

    vertexai._genai._agent_engines_utils._generate_class_methods_spec_or_raise uses
    json_format.MessageToJson(agent.agent_card), which only accepts protobuf messages.
    A2aAgent stores the A2A SDK Pydantic AgentCard, so we JSON-encode it here.
    """
    card = getattr(agent, "agent_card", None)
    if card is None:
        return "{}"

    model_dump = getattr(card, "model_dump", None)
    if callable(model_dump):
        return json.dumps(model_dump(mode="json", exclude_none=True), default=str)

    dict_fn = getattr(card, "dict", None)
    if callable(dict_fn):
        try:
            return json.dumps(dict_fn(exclude_none=True))
        except Exception:
            return json.dumps(dict_fn())

    return json_format.MessageToJson(card)

def _class_methods_for_auditor_a2a() -> list[dict[str, Any]]:
    """Mirror _generate_class_methods_spec_or_raise with Pydantic safe a2a_agent_card."""
    from runtime.agent_engine_entry import a2a_agent
    from vertexai._genai import _agent_engines_utils as u
    from vertexai._genai._agent_engines_utils import (
        _A2A_AGENT_CARD,
        _MODE_KEY_IN_SCHEMA,
    )

    agent = a2a_agent
    operations = u._get_registered_operations(agent=agent)

    if isinstance(agent, u.ModuleAgent):
        agent = agent.clone()
        try:
            agent.set_up()
        except Exception as e:
            raise ValueError(f"Failed to set up agent {agent}: {e}") from e

    _log = logging.getLogger("vertexai_genai.agentengines")
    class_methods_spec: list[Any] = []

    for mode, method_names in operations.items():
        for method_name in method_names:
            if not hasattr(agent, method_name):
                raise ValueError(
                    f"Method `{method_name}` defined in `register_operations` not found on agent."
                )

            method = getattr(agent, method_name)
            try:
                schema_dict = u._generate_schema(method, schema_name=method_name)
            except Exception as e:
                _log.warning("failed to generate schema for %s: %s", method_name, e)
                continue

            class_method = u._to_proto(schema_dict)
            class_method[_MODE_KEY_IN_SCHEMA] = mode
            if hasattr(agent, "agent_card"):
                class_method[_A2A_AGENT_CARD] = _a2a_agent_card_json_for_deploy(agent)
            class_methods_spec.append(class_method)

    return [u._to_dict(s) for s in class_methods_spec]

# Create temporary requirements file inside runtime/ package so it gets uploaded
reqs = [
    "google-cloud-aiplatform[agent_engines,evaluation]>=1.112.0",
    "toolbox-core",
    "toolbox-adk",
    "mcp",
    "pypdf",
    "google-cloud-discoveryengine",
    "python-dotenv",
    "google-adk[a2a,agent-identity]==2.1.0",
    "google-genai>=1.70.0",
    "google-cloud-bigquery",
    "google-cloud-firestore",
    "a2a-sdk[http-server]==0.3.26"
]
reqs_path = Path("runtime/requirements_deploy.txt")
reqs_path.write_text("\n".join(reqs))

# Prepare the deployment configuration dictionary
config: dict[str, Any] = {
    "source_packages": ["agents", "ai_agents_adk", "tools", "eval", "services", "runtime", "A2A", "regulation.txt", "customer_db.json", "orders_db.json", "data/data_manager.py", "data/compliance_manual.txt", "data/__init__.py"],
    "entrypoint_module": "runtime.agent_engine_entry",
    "entrypoint_object": "a2a_agent",
    "requirements_file": "runtime/requirements_deploy.txt",
    "class_methods": _class_methods_for_auditor_a2a(),
    "display_name": "Autonomous Auditor",
    "agent_framework": "google-adk",
    "env_vars": {
        "MCP_TOOLBOX_URL": MCP_TOOLBOX_URL,
        "GOOGLE_CLOUD_LOCATION": LOCATION,
        "GEMINI_MODEL": "gemini-2.5-flash",
        "FIRESTORE_DATABASE_ID": os.getenv("FIRESTORE_DATABASE_ID", "ai-studio-c65c8c94-4557-4ed7-87bc-594554053988"),
    }
}

if SERVICE_ACCOUNT:
    config["service_account"] = SERVICE_ACCOUNT

print(f"[deploy] Deploying A2A Agent to Vertex Agent Engine...")
print(f"[deploy] Project: {PROJECT_ID} | Location: {LOCATION}")

try:
    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
    deployed_agent = client.agent_engines.create(config=config)

    resource_name = (
        getattr(deployed_agent, "resource_name", None)
        or getattr(getattr(deployed_agent, "api_resource", None), "name", None)
        or ""
    )
    print(f"Agent successfully deployed as A2A! ID: {resource_name}")
    if resource_name:
        engine_id = resource_name.split("/")[-1]
        env_path = Path(".env")
        if env_path.exists():
            env_content = env_path.read_text()
            new_lines = []
            for line in env_content.splitlines():
                if line.startswith("AGENT_RESOURCE_NAME="):
                    new_lines.append(f"AGENT_RESOURCE_NAME={resource_name}")
                elif line.startswith("AGENT_ENGINE_ID="):
                    new_lines.append(f"AGENT_ENGINE_ID={engine_id}")
                else:
                    new_lines.append(line)
            env_updated = "\n".join(new_lines) + "\n"
            env_path.write_text(env_updated)
            print("[deploy] Successfully updated local .env file with new deployment IDs.")
except Exception as e:
    print(f"Deployment failed: {e}", file=sys.stderr)
finally:
    if reqs_path.exists():
        reqs_path.unlink()
