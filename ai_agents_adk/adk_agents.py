from google.adk.agents import Agent
from pathlib import Path
import sys

# --- Path Setup ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

from tools.adk_tools import gemini_model, read_regulation_file_tool, find_pii_compliance_violations_tool, find_retention_policy_violations_tool, find_orphaned_orders_tool, find_customers_by_status_tool, get_orders_by_customer_id_tool, query_compliance_manual_tool
from services.memory_manager import auto_save_memories

# =========================================================================
#  REGISTER AS ADK SPECIALIST AGENTS
# =========================================================================

policy_analyst = Agent(
    name="policy_analyst",
    model=gemini_model,
    description="Provides deep policy context and interpretations from the unstructured compliance manual using RAG.",
    tools=[query_compliance_manual_tool],
    instruction="""
    You are a Senior Compliance Policy Analyst.
    Your job is to provide deep contextual insights and interpretations from the 'Retail Data Handling Policy' manual.
    Analyze the user's query carefully to identify all key regulatory topics requested (e.g. data anonymization, archives versus operational, Right to be Forgotten, data sharing, third-party rules, data breaches, 72 hours, consent, retention timelines).
    For EACH identified topic, use the `query_compliance_manual_tool` to search for relevant sections in the manual.
    Summarize all retrieved policy contexts, best practices, and nuances comprehensively for the Synthesis Agent.
    **Crucially, you must explicitly capture and preserve all specific numbers, timelines, durations, and legal exceptions (e.g., '30 days', '7 years', '72 hours', 'tax records', 'differential privacy', 'k-anonymity', 'discovery', 'third party', 'consent', 'anonymized') exactly as written in the retrieved compliance manual text in your output summary.**
    """,
    output_key="policy_context"
)

regulation_file_reader = Agent(
    name="regulation_file_reader",
    model=gemini_model,
    description="Reads the regulation.txt file to understand the compliance rules.",
    tools=[read_regulation_file_tool],
    instruction="""
    You are a compliance assistant. Your only job is to read the regulation file and return its content.
    Use read_regulation_file_tool for reading regulation file.
    """,
    output_key="regulation_file_content",
    after_agent_callback=auto_save_memories,
)

pii_specialist = Agent(
    name="pii_specialist",
    model=gemini_model,
    description="Scans the entire orders database for records that violate PII rules (Rules 1.1, 1.3 from REGULATION_TEXT). Checks for both unmasked PII (e.g. a real email) AND invalid PII states (like 'NULL' or 'N/A'). A compliant field must be exactly '[MASKED]'.",
    tools=[find_pii_compliance_violations_tool],
    instruction="""
    You are a PII compliance assistant. Your only job is to find violations of PII rules in the orders database.
    Use find_pii_compliance_violations_tool for performing audit checks.
    Do not ask for confirmation, permission, or additional inputs. Run the tool immediately.

    CRITICAL: In your final response, you MUST:
    1. Count the exact total number of violations returned by your tool.
    2. Explicitly output a line stating the count in this exact format: "Total PII Violations: <count>" where <count> is the integer number of violations found (e.g., "Total PII Violations: 34"). If there are none, output "Total PII Violations: 0".
    3. List EVERY single violation returned by the tool in a markdown table with all details (order_id, customer_id, field, value, violation_type). Do not truncate, summarize, or omit any rows.
    """,
    output_key="pii_violations"
)

rtbf_expert = Agent(
    name="rtbf_expert",
    model=gemini_model,
    description="Scans BigQuery to find orders that violate the RTBF policy (Rule 2.1 & 2.2).",
    tools=[find_customers_by_status_tool, get_orders_by_customer_id_tool],
    instruction="""
    You are a RTBF compliance assistant. Your only job is to find violations of RTBF policy in the orders database.
    **RTBF (Rule 2):** Check for "Right to be Forgotten" violations. First, use `find_customers_by_status_tool` to get all 'forgotten' customers. Then, batch all of their customer IDs together into a single comma-separated string (e.g., "id1,id2,id3") and call the `get_orders_by_customer_id_tool` ONCE with this comma-separated string to retrieve all their orders in a single batch query. This is highly preferred over looping one-by-one.
    Do not ask for confirmation, permission, or additional inputs. Run the tools immediately.

    CRITICAL: In your final response, you MUST:
    1. Count the exact total number of orders (violations) retrieved for the 'forgotten' customers.
    2. Explicitly output a line stating the count in this exact format: "Total RTBF Violations: <count>" where <count> is the integer number of violations found (e.g., "Total RTBF Violations: 1"). If there are none, output "Total RTBF Violations: 0".
    3. List EVERY single violation/order found in a markdown table with all details (customer_id, order_id, violation_type). Do not truncate, summarize, or omit any rows.
    """,
    output_key="rtbf_violations"
)

retention_policy_checker = Agent(
    name="retention_policy_checker",
    model=gemini_model,
    description="Scans the entire orders database for records that violate the data retention policy (Rule 3.1 from REGULATION_TEXT). Returns orders older than 'max_age_days' that have NOT been anonymised.",
    #mode="task",  # returns control automatically when done
    tools=[find_retention_policy_violations_tool],
    instruction="""
    You are a data retention compliance assistant. Your only job is to find violations of data retention policy in the orders database.
    Rule 3.1 specifies that order records older than 3650 days (10 years) must be anonymized.
    Always execute the find_retention_policy_violations_tool with max_age_days=3650.
    Do not ask for confirmation, permission, or additional inputs. Run the tool immediately.

    CRITICAL: In your final response, you MUST:
    1. Count the exact total number of violations returned by your tool.
    2. Explicitly output a line stating the count in this exact format: "Total Data Retention Violations: <count>" where <count> is the integer number of violations found (e.g., "Total Data Retention Violations: 5"). If there are none, output "Total Data Retention Violations: 0".
    3. List EVERY single violation returned by the tool in a markdown table with all details (order_id, customer_id, order_date, violation_type). Do not truncate, summarize, or omit any rows.
    """,
    output_key="retention_policy_violations"
)

orphaned_orders_finder = Agent(
    name="orphaned_orders_finder",
    model=gemini_model,
    description="Scans BigQuery to find orders with invalid customer IDs (Rules 4.1 and 4.2 from REGULATION_TEXT).",
    #mode="task",  # returns control automatically when done
    tools=[find_orphaned_orders_tool],
    instruction="""
    You are an orphaned records compliance assistant. Your only job is to find violations of orphaned records policy in the orders database.
    Use find_orphaned_orders_tool for performing audit checks.    
    Do not ask for confirmation, permission, or additional inputs. Run the tool immediately.

    CRITICAL: In your final response, you MUST:
    1. Count the exact total number of violations returned by your tool.
    2. Explicitly output a line stating the count in this exact format: "Total Orphaned Record Violations: <count>" where <count> is the integer number of violations found (e.g., "Total Orphaned Record Violations: 2"). If there are none, output "Total Orphaned Record Violations: 0".
    3. List EVERY single violation returned by the tool in a markdown table with all details (order_id, customer_id, violation_type). Do not truncate, summarize, or omit any rows.
    """,
    output_key="orphaned_orders"
)
