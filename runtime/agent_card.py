"""A2A Agent Card for Autonomous Auditor"""

from a2a.types import AgentCard, AgentSkill
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card


def create_auditor_card() -> AgentCard:
    skill = AgentSkill(
        id="audit_plans",
        name="Plans and Executes Audits",
        description="Plans and Executes Audits.",
        tags=["audit", "execute", "plan", "audit"],
    )
    return create_agent_card(
        agent_name="autonomous_auditor",
        description="Autonomous Auditor - Plans and Executes Audits.",
        skills=[skill],
    )