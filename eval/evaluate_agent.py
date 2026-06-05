import os
import json
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv
from typing import Any
import vertexai
import sys
import warnings

# Suppress all UserWarnings and library noise
warnings.filterwarnings("ignore")

# Force stdout to flush immediately for real-time progress logging
sys.stdout.reconfigure(line_buffering=True)

# --- Path Setup ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))
load_dotenv(SRC_DIR / ".env")  # Load environment variables from .env

# Import agent and runner components
from agents.agent import auditor_agent  # The main agent
from google.adk import Runner
from google.adk.apps import App
from google.adk.agents.context_cache_config import ContextCacheConfig
from services.session_manager import create_session_service
from services.memory_manager import create_memory_service

# Monkeypatch tools.adk_tools.datetime to freeze the baseline date to May 24, 2026
import tools.adk_tools
from datetime import datetime as original_datetime


class MockDatetime(original_datetime):
    @classmethod
    def now(cls, tz=None):
        return original_datetime(2026, 5, 24, 12, 0, 0)


tools.adk_tools.datetime = MockDatetime

from google.genai import types

GOLDEN_SETS_DIR = SRC_DIR / "golden_sets"
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "google-cloud-project-id")
DATASET_ID = "retail_audit_db"


# --- Helper to parse agent's final report ---
def parse_agent_report(report_text: str) -> dict:
    # This function will need to parse the agent's structured report
    # and extract the identified violations.
    # The agent's report format is defined in agents/agent.py (merger_agent instruction)

    parsed_violations = {
        "pii_leaks": [],
        "pii_integrity_failures": [],
        "rtbf_violations": [],
        "retention_failures": [],
        "orphaned_records": [],
    }

    # Helper to extract violations from a section
    def extract_section_violations(section_name: str, text: str, violation_keyword: str):
        violations = []
        # Find the start of the section and the start of the next section or end of text
        start_tag = f"### {section_name}"
        end_tags = [
            f"### {s}"
            for s in [
                "RTBF Violations",
                "Data Retention Policy Violations",
                "Orphaned Records Findings",
                "Overall Conclusion",
            ]
        ]
        end_tag_regex = "|".join(re.escape(tag) for tag in end_tags)

        section_match = re.search(
            rf"{re.escape(start_tag)}\s*([\s\S]*?)(?={end_tag_regex}|$)", text
        )

        if section_match:
            section_content = section_match.group(1).strip()
            # Split by lines and filter for lines indicating a violation
            for line in section_content.splitlines():
                # Heuristic: look for the keyword or any non-empty line that isn't a heading/sub-heading
                if violation_keyword in line or (
                    line.strip() and not line.strip().startswith(("(", "["))
                ):
                    violations.append(line.strip())
        return violations

    # PII Violations (combines PII Leak and Integrity failures)
    pii_violations_raw = extract_section_violations("PII Violations", report_text, "PII")
    for v in pii_violations_raw:
        if "PII Leak (Unmasked)" in v:
            parsed_violations["pii_leaks"].append(v)
        elif "PII Integrity Failure" in v:
            parsed_violations["pii_integrity_failures"].append(v)
        elif (
            "No PII violations found" not in v and v
        ):  # Capture general PII issues if keyword is not specific
            parsed_violations["pii_leaks"].append(v)  # Default to leak if not specific integrity

    # RTBF Violations
    parsed_violations["rtbf_violations"] = extract_section_violations(
        "RTBF Violations", report_text, "RTBF Violation"
    )
    # Filter out 'No RTBF violations found' explicitly
    parsed_violations["rtbf_violations"] = [
        v for v in parsed_violations["rtbf_violations"] if "No RTBF violations found" not in v
    ]

    # Data Retention Policy Violations
    parsed_violations["retention_failures"] = extract_section_violations(
        "Data Retention Policy Violations", report_text, "Data Retention Failure"
    )
    parsed_violations["retention_failures"] = [
        v
        for v in parsed_violations["retention_failures"]
        if "No data retention policy violations found" not in v
    ]

    # Orphaned Records Findings
    parsed_violations["orphaned_records"] = extract_section_violations(
        "Orphaned Records Findings", report_text, "Orphaned Record"
    )
    parsed_violations["orphaned_records"] = [
        v for v in parsed_violations["orphaned_records"] if "No orphaned records found" not in v
    ]

    return parsed_violations


# --- Main Evaluation Function ---
async def evaluate_agent():
    print("Starting agent evaluation...")
    os.environ["RAG_LOCAL_ONLY"] = "true"
    vertexai.init(project=PROJECT_ID, location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"))

    # Initialize ADK Runner once for all evaluations
    session_service = create_session_service(
        project=PROJECT_ID,
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        use_vertex=False,
    )
    memory_service = create_memory_service(
        project=PROJECT_ID, location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    )

    app_instance = App(
        name=auditor_agent.name,
        root_agent=auditor_agent,
        context_cache_config=ContextCacheConfig(
            cache_intervals=10, ttl_seconds=3600, min_tokens=4096
        ),
    )
    runner = Runner(
        app=app_instance, session_service=session_service, memory_service=memory_service
    )

    evaluation_results: dict[str, Any] = {}

    for scenario_path in GOLDEN_SETS_DIR.iterdir():
        if scenario_path.is_dir():
            scenario_name = scenario_path.name
            print(f"--- Evaluating scenario: {scenario_name} ---")
            await asyncio.sleep(
                12
            )  # Pace requests to prevent Vertex AI quota exhaustion (RESOURCE_EXHAUSTED)

            # Load golden violations
            golden_violations_file = scenario_path / "golden_violations.json"
            if not golden_violations_file.exists():
                print(f"Skipping {scenario_name}: golden_violations.json not found.")
                continue
            with open(golden_violations_file, "r") as f:
                golden_violations = json.load(f)

            # Set environment variables for BigQuery tables for this scenario
            # RAG-only scenarios query policy and do not have database violations, so we use clean data as fallback
            if scenario_name.startswith("rag_"):
                os.environ["AUDIT_CUSTOMER_TABLE"] = "clean_data_customers"
                os.environ["AUDIT_ORDER_TABLE"] = "clean_data_orders"
            else:
                os.environ["AUDIT_CUSTOMER_TABLE"] = f"{scenario_name.replace('-', '_')}_customers"
                os.environ["AUDIT_ORDER_TABLE"] = f"{scenario_name.replace('-', '_')}_orders"
            print(
                f"Set AUDIT_CUSTOMER_TABLE={os.environ['AUDIT_CUSTOMER_TABLE']}, AUDIT_ORDER_TABLE={os.environ['AUDIT_ORDER_TABLE']}"
            )

            # Run the agent with robust retry logic for transient connection/token errors
            user_id = "evaluator"
            session_id = f"eval_session_{scenario_name}"

            # Use custom scenario prompt if provided, otherwise fallback to standard prompt
            custom_prompt_file = scenario_path / "prompt.txt"
            if custom_prompt_file.exists():
                with open(custom_prompt_file, "r") as f:
                    audit_prompt = f.read().strip()
            else:
                audit_prompt = "Please perform a comprehensive 5-point compliance audit of the retail database."

            content = types.Content(role="user", parts=[types.Part(text=audit_prompt)])

            agent_output = ""
            tool_violations = {
                "pii_leaks": [],
                "pii_integrity_failures": [],
                "rtbf_violations": [],
                "retention_failures": [],
                "orphaned_records": [],
            }
            database_tools_executed = False

            attempts = 5
            for attempt in range(attempts):
                try:
                    # Ensure a fresh session for each evaluation attempt
                    try:
                        await session_service.delete_session(
                            app_name=app_instance.name, user_id=user_id, session_id=session_id
                        )
                    except Exception:
                        pass
                    await session_service.create_session(
                        app_name=app_instance.name, user_id=user_id, session_id=session_id
                    )

                    # Clear violations list for a fresh attempt
                    tool_violations = {
                        "pii_leaks": [],
                        "pii_integrity_failures": [],
                        "rtbf_violations": [],
                        "retention_failures": [],
                        "orphaned_records": [],
                    }
                    database_tools_executed = False
                    agent_output = ""

                    async for event in runner.run_async(
                        session_id=session_id, user_id=user_id, new_message=content
                    ):
                        # Intercept intermediate tool calls/results
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.function_response:
                                    fr = part.function_response
                                    tool_name = fr.name
                                    response_data = fr.response

                                    if tool_name in [
                                        "find_pii_compliance_violations",
                                        "find_customers_by_status",
                                        "get_orders_by_customer_id",
                                        "find_retention_policy_violations",
                                        "find_orphaned_orders",
                                    ]:
                                        database_tools_executed = True

                                    # Parse standard lists returned by tools
                                    results_list = []
                                    if isinstance(response_data, list):
                                        results_list = response_data
                                    elif (
                                        isinstance(response_data, dict)
                                        and "result" in response_data
                                    ):
                                        results_list = response_data["result"]

                                    if isinstance(results_list, list):
                                        for item in results_list:
                                            if not isinstance(item, dict):
                                                continue
                                            if tool_name == "find_pii_compliance_violations":
                                                vtype = item.get("violation_type")
                                                if vtype == "PII Leak (Unmasked)":
                                                    tool_violations["pii_leaks"].append(item)
                                                elif vtype == "PII Integrity Failure":
                                                    tool_violations[
                                                        "pii_integrity_failures"
                                                    ].append(item)
                                            elif tool_name == "get_orders_by_customer_id":
                                                item["violation_type"] = "RTBF Violation"
                                                tool_violations["rtbf_violations"].append(item)
                                            elif tool_name == "find_retention_policy_violations":
                                                tool_violations["retention_failures"].append(item)
                                            elif tool_name == "find_orphaned_orders":
                                                tool_violations["orphaned_records"].append(item)

                        if event.is_final_response() and event.content and event.content.parts:
                            agent_output = "".join(
                                p.text for p in event.content.parts if hasattr(p, "text") and p.text
                            )

                    if not agent_output:
                        raise ValueError("Agent did not produce a final report.")
                    break  # Success, exit the retry loop!
                except Exception as run_err:
                    print(
                        f"  [Attempt {attempt + 1}/{attempts}] Scenario execution failed: {run_err!r}",
                        flush=True,
                    )
                    if attempt < attempts - 1:
                        await asyncio.sleep(15)  # Wait 15 seconds before retrying
                    else:
                        print(
                            f"  [Error] Failed all {attempts} attempts for scenario {scenario_name}.",
                            flush=True,
                        )
                        agent_output = ""

            if not agent_output:
                print(
                    f"Agent did not produce a final report for {scenario_name}. Skipping evaluation."
                )
                evaluation_results[scenario_name] = {
                    "status": "FAILED",
                    "reason": "No final report from agent",
                }
                continue

            # Save agent's raw report for debugging
            with open(scenario_path / "agent_report.md", "w") as f:
                f.write(agent_output)

            # Prioritize structural tool-level violations for comparison, falling back to text parsing if no tools were executed
            agent_found_violations = tool_violations
            if not database_tools_executed and not any(agent_found_violations.values()):
                agent_found_violations = parse_agent_report(agent_output)

            # Compare and report
            scenario_evaluation: dict[str, Any] = {"status": "PASSED", "details": {}}
            all_passed = True

            print("  --- Violation Comparison ---")
            for violation_type in golden_violations.keys():
                if violation_type == "rag_expected_keywords":
                    expected_keywords = golden_violations["rag_expected_keywords"]
                    found_keywords = []
                    missing_keywords = []
                    for kw in expected_keywords:
                        # Allow optional hyphens, spaces, and plurals for robust matching
                        normalized_kw = kw.strip().lower()
                        if normalized_kw.endswith("s"):
                            base_kw = normalized_kw[:-1]
                            suffix = "s?"
                        else:
                            base_kw = normalized_kw
                            suffix = ""
                        escaped_base = re.escape(base_kw)
                        pattern = (
                            escaped_base.replace(r"\ ", r"[\s-]?").replace(" ", r"[\s-]?") + suffix
                        )
                        if re.search(pattern, agent_output, re.IGNORECASE):
                            found_keywords.append(kw)
                        else:
                            missing_keywords.append(kw)

                    status = "MATCH" if not missing_keywords else "MISMATCH"
                    if missing_keywords:
                        all_passed = False

                    scenario_evaluation["details"]["rag_expected_keywords"] = {
                        "golden_count": len(expected_keywords),
                        "agent_count": len(found_keywords),
                        "status": status,
                        "golden_violations": expected_keywords,
                        "agent_violations": found_keywords,
                        "missing_keywords": missing_keywords,
                    }
                    print(
                        f"    rag_expected_keywords    : Golden={len(expected_keywords):<3}, Agent={len(found_keywords):<3}, Status={status}"
                    )
                    if missing_keywords:
                        print(f"      Missing keywords: {missing_keywords}")
                else:
                    golden_count = len(golden_violations[violation_type])
                    agent_count = len(
                        agent_found_violations.get(violation_type, [])
                    )  # Use .get for robustness

                    # For now, a simplified comparison: check if the count matches.
                    if golden_count == agent_count:
                        status = "MATCH"
                    else:
                        status = "MISMATCH"
                        all_passed = False

                    scenario_evaluation["details"][violation_type] = {
                        "golden_count": golden_count,
                        "agent_count": agent_count,
                        "status": status,
                        "golden_violations": golden_violations[
                            violation_type
                        ],  # Include for inspection
                        "agent_violations": agent_found_violations.get(violation_type, []),
                    }
                    print(
                        f"    {violation_type:<25}: Golden={golden_count:<3}, Agent={agent_count:<3}, Status={status}"
                    )

            if not all_passed:
                scenario_evaluation["status"] = "FAILED"
            evaluation_results[scenario_name] = scenario_evaluation

            # Clean up environment variables
            if "AUDIT_CUSTOMER_TABLE" in os.environ:
                del os.environ["AUDIT_CUSTOMER_TABLE"]
            if "AUDIT_ORDER_TABLE" in os.environ:
                del os.environ["AUDIT_ORDER_TABLE"]

    print("--- Evaluation Summary ---")
    total_scenarios = len(evaluation_results)
    passed_scenarios = sum(1 for r in evaluation_results.values() if r["status"] == "PASSED")

    print(f"Total Scenarios: {total_scenarios}")
    print(f"Passed: {passed_scenarios}")
    print(f"Failed: {total_scenarios - passed_scenarios}\n")

    for scenario, result in evaluation_results.items():
        print(f"Scenario: {scenario}, Overall Status: {result['status']}")
        if result["status"] == "FAILED":
            if "reason" in result:
                print(f"  Reason: {result['reason']}")
            else:
                for vt, detail in result["details"].items():
                    if detail["status"] == "MISMATCH":
                        print(
                            f"  - {vt}: Mismatch (Golden: {detail['golden_count']}, Agent: {detail['agent_count']})"
                        )
                        print(f"    Golden: {detail['golden_violations']}")
                        print(f"    Agent : {detail['agent_violations']}\n\n")


if __name__ == "__main__":
    if not PROJECT_ID or PROJECT_ID == "google-cloud-project-id":
        print(
            "ERROR: GOOGLE_CLOUD_PROJECT environment variable is not set or is default. Please set it to your GCP Project ID."
        )
        exit(1)

    asyncio.run(evaluate_agent())
