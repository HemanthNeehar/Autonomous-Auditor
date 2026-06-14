"""
agents_with_tools.py — Autonomous Auditor ADK Agent

Exposes a single module-level `auditor_agent` (google.adk.agents.Agent).
"""

import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from typing import Optional
from google.adk import Agent, Workflow, Event
from google.adk.agents import ParallelAgent
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

# --- Path Setup ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))
load_dotenv(SRC_DIR / ".env")

# Import tools
from tools.adk_tools import (
    find_customers_by_status_tool,
    get_orders_by_customer_id_tool,
    get_managed_bq_tools
)

# Import Agents
from ai_agents_adk.adk_agents import ( 
    pii_specialist,
    retention_policy_checker,
    orphaned_orders_finder,
    regulation_file_reader,
    rtbf_expert,
    policy_analyst
)

from services.memory_manager import auto_save_memories, create_memory_service
from services.session_manager import SessionManager, create_session_service

# =========================================================================
#  CONFIGURATION
# =========================================================================

#gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
APP_NAME: str = "AUTONOMOUS_AUDITOR"
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

# =========================================================================
#  Hybrid Agent combined with Coordinator-Specialist
# =========================================================================

coordinator = ParallelAgent(
  name = "auditor_coordinator",
  description = "Coordinates the audit process by running multiple specialists in parallel to perform comprehensive audit based on the regulation file.",
  sub_agents = [
    pii_specialist,
    retention_policy_checker,
    orphaned_orders_finder,
    rtbf_expert,
    policy_analyst,
  ],
)

merger_agent = Agent(
     name="SynthesisAgent",
     model=gemini_model,
     instruction="""You are an AI Assistant responsible for combining research findings into a structured compliance report.

Your primary task is to synthesize the provided research summaries into a comprehensive report, clearly attributing findings to their source areas. Structure your response using specific headings for each topic as outlined below. Ensure the report is coherent, integrates key points smoothly, and thoroughly adheres to all specified rules and details from the provided context.

**Crucially: Your entire response MUST be grounded *exclusively* on the information provided in the individual Audit Outputs and Policy Context from the specialist agents below. Do NOT add any external knowledge, facts, or details not present in these specific outputs.**

**Be extremely thorough and preserve all specific numbers, timelines, durations, exceptions, and key compliance terms (e.g., '30 days', '7 years', '72 hours', 'tax records', '3650 days', '10 years', 'k-anonymity', 'differential privacy', 'discovery', 'third party' [strictly in this exact singular form], 'consent', 'anonymized') exactly as written in the policy context and audit outputs in your final report.**

**Calculate and explicitly display the total counts of identified violations in each category (if any are present) by reading the "Total PII Violations: <count>", "Total RTBF Violations: <count>", "Total Data Retention Violations: <count>", and "Total Orphaned Record Violations: <count>" lines outputted by each specialist agent respectively. Do NOT guess or default to arbitrary numbers; you must use the exact total counts reported by the specialist agents. Present them as a Summary Scorecard at the very beginning of the findings.**

**When reporting violations, explicitly list all `order_id`, `customer_id`, `field`, `value`, `order_date`, `product_name`, `price`, and `violation_type` as they appear in the audit outputs. Render them in a clean Markdown Table format for each category to ensure a neat scrollable display in the UI, listing all reported rows.**

**If a specialist's function is limited and cannot perform a requested action (e.g., verify a "true orphan" status beyond initial identification, or speculate on root causes), you must explicitly state this limitation based on the specialist's defined role and capabilities, as indicated in the policy context or audit outputs.**

**Policy Context (RAG):**
This section contains extracted policy documents (`REGULATION DOCUMENT: RG-101 (Retail Data Compliance)` including its Sections and Rules, `compliance_manual.txt`, `gdpr_regulation.html`, `ccpa_2022032_02NR_APPROVAL.pdf`, and `Cloud Search`) that define the rules, standards, and best practices for data handling, PII, RTBF, data retention, and data governance.

**Audit Outputs:**
This section provides specific findings from specialized agents:
*   **PII and RTBF Compliance:** Details PII integrity failures (e.g., `NULL` values) and PII leaks (unmasked `customer_email`, `customer_phone`).
*   **Data Retention Policy:** Identifies order records violating retention policies, typically orders older than `3650 days (10 years)` that have not been anonymized.
*   **Orphaned Records:** Pinpoints records in `orders_db` without a corresponding valid parent `customer_id` in `customer_db`.
*   **RTBF:** Details specific instances where orders are found for customers whose status is 'forgotten', violating RTBF rules.

**Output Format:**

## Summary of Autonomous Auditor Agent Findings

### Compliance Scorecard (Violation Counts)
| Category | Violated Rules | Violation Count | Status |
| :--- | :--- | :--- | :--- |
| PII Security & Integrity | Rule 1.1, 1.3 | [Specify Count, or 0 if none] | [PASSED / FAILED] |
| Right to Be Forgotten (RTBF) | Rule 2.1, 2.2 | [Specify Count, or 0 if none] | [PASSED / FAILED] |
| Data Retention Limits | Rule 3.1, 3.2 | [Specify Count, or 0 if none] | [PASSED / FAILED] |
| Data Governance & Integrity | Rule 4.1, 4.2 | [Specify Count, or 0 if none] | [PASSED / FAILED] |

### Policy Interpretation & Best Practices (RAG Insights)
(Based on Senior Policy Analyst findings from the compliance manual)
[Synthesize the high-level policy context, standards, and best practices retrieved via RAG. Include specific rules, definitions, timelines (e.g., `30 days`, `7 years`, `3650 days`, `10 years`), exceptions (e.g., `tax records`), and anonymization techniques (e.g., `k-anonymity`, `differential privacy`). Explain what `[MASKED]` and `'ANONYMIZED'` status means for compliance, citing relevant rules (e.g., Rule 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2) and sections (e.g., Section 1: PII, Section 2: RTBF, Section 3: Data Retention, Section 4: Data Governance & Integrity) from `REGULATION DOCUMENT: RG-101 (Retail Data Compliance)`. Crucially, you must explicitly describe data breach notification requirements (notifying affected individuals and authorities within 72 hours of discovery) and third-party data sharing rules (requiring explicit consent and data protection agreements) from `compliance_manual.txt` in extensive detail, always preserving the terms 'discovery', 'third party' (strictly in this exact singular form), 'consent', '72 hours', and 'anonymized'.]

### PII Violations
(Based on PII Specialist findings)
[If no violations: State "No PII violations identified". Otherwise: List counts and present a markdown table with columns: `Order ID`, `Field`, `Redacted Value`, `Violation Type` (Integrity Failure/Leak), `Rule Violated` (Rule 1.1/1.3).]

### RTBF Violations
(Based on RTBF Expert findings)
[If no violations: State "No RTBF violations identified". Otherwise: Present a markdown table with columns: `Customer ID`, `Order ID`, `Violation Type`, `Rule Violated` (Rule 2.1/2.2).]

### Data Retention Policy Violations
(Based on Data Retention Policy Specialist findings)
[If no violations: State "No Data Retention violations identified". Otherwise: Present a markdown table with columns: `Order ID`, `Customer ID`, `Order Date`, `Violation Type`, `Rule Violated` (Rule 3.1/3.2).]

### Orphaned Records Findings
(Based on Orphaned Records Specialist findings)
[If no violations: State "No Orphaned Record violations identified". Otherwise: Present a markdown table with columns: `Order ID`, `Customer ID`, `Violation Type`, `Rule Violated` (Rule 4.1/4.2). Include any stated limitations on verifying true orphan status.]

### Overall Conclusion
[Provide a brief (1-2 sentence) concluding statement that connects the findings with the policy context presented above, highlighting the overall compliance status or key areas of concern.]

Output *only* the structured report following this format. Do not include introductory or concluding phrases outside this structure, and strictly adhere to using only the provided input summary content.
""",
     description="Combines research findings from parallel agents into a structured, cited report, strictly grounded on provided inputs and RAG context.",
     tools=[PreloadMemoryTool()],
     after_agent_callback=auto_save_memories,
 )

auditor_agent = Workflow(
    name = "auditor_agent",
    edges = [
        ("START", regulation_file_reader),
        (regulation_file_reader, coordinator),
        (coordinator, merger_agent),
    ],
)

# Metaprogramming layer to support GEPARootAgentPromptOptimizer (adk optimize)
# This dynamically maps the prompt optimization fields to merger_agent (SynthesisAgent)
import types

def workflow_clone(self, update=None):
    new_instruction = update.get("instruction", merger_agent.instruction) if update else merger_agent.instruction
    new_merger = merger_agent.clone(update={"instruction": new_instruction})
    
    from google.adk import Workflow
    new_workflow = Workflow(
        name=self.name,
        edges=[
            (edge[0], new_merger if edge[1] == merger_agent else edge[1])
            for edge in self.edges
        ]
    )
    new_workflow.__dict__["sub_agents"] = []
    new_workflow.__dict__["instruction"] = new_instruction
    new_workflow.__dict__["model"] = new_merger.model
    new_workflow.__dict__["description"] = new_merger.description
    new_workflow.__dict__["clone"] = types.MethodType(workflow_clone, new_workflow)
    return new_workflow

auditor_agent.__dict__["sub_agents"] = []
auditor_agent.__dict__["instruction"] = merger_agent.instruction
auditor_agent.__dict__["model"] = merger_agent.model
auditor_agent.__dict__["description"] = merger_agent.description
auditor_agent.__dict__["clone"] = types.MethodType(workflow_clone, auditor_agent)
