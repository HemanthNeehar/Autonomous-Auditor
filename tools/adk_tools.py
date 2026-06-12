"""
adk_tools.py — Compliance Audit Tool Definitions
Registers pure-Python functions as ADK FunctionTools.

Pydantic schemas are applied *only* to tools that accept arguments so that
the ADK / Gemini function-calling layer receives a strongly-typed, validated
schema.  Zero-argument tools do not need a schema wrapper.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Annotated

from pydantic import BaseModel, Field, field_validator
from google.adk.tools import FunctionTool
from toolbox_core import ToolboxSyncClient
from google.adk.integrations.agent_registry import AgentRegistry
from google.adk.agents import Agent
from dotenv import load_dotenv
from pathlib import Path

from google.adk.tools import McpToolset
from google.cloud import discoveryengine_v1beta as discoveryengine

# --- Path Setup ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))
load_dotenv(SRC_DIR / ".env")

gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DATASET_ID = "retail_audit_db"
RAG_DATA_STORE_ID = "auditor-compliance-manual_1779853412403"


# Helper to fetch the Managed Toolset
def get_managed_bq_tools() -> McpToolset:
    """Returns the tools from the Google-managed BigQuery MCP server."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")
    region = "global"

    # Initialize the Registry
    registry = AgentRegistry(project_id=project_id, location=region)

    # Load the Managed BigQuery Toolset
    # This automatically includes: execute_sql, get_table_info, list_tables, etc.
    mcp_toolset = registry.get_mcp_toolset(
        f"projects/{project_id}/locations/{region}/mcpServers/agentregistry-00000000-0000-0000-329d-3e124456d70f"
    )

    return mcp_toolset


_COMPLIANCE_SECTIONS_CACHE = None


def _local_compliance_manual_search(query: str) -> str:
    """Fallback to search all compliance documents downloaded locally or in GCS bucket."""
    global _COMPLIANCE_SECTIONS_CACHE
    import re
    import glob
    import io

    bucket_name = os.getenv("STAGING_BUCKET")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")

    if _COMPLIANCE_SECTIONS_CACHE is not None:
        sections = _COMPLIANCE_SECTIONS_CACHE
    else:
        sections = []

        # 1. Load local compliance files first
        local_paths = []

        # Main local compliance_manual.txt
        manual_path = (
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            + "/data/compliance_manual.txt"
        )
        if os.path.exists(manual_path):
            local_paths.append(manual_path)

        # Files in data/compliance_downloads/
        downloads_dir = (
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            + "/data/compliance_downloads"
        )
        if os.path.exists(downloads_dir):
            local_paths.extend(glob.glob(os.path.join(downloads_dir, "*")))

        for path in local_paths:
            filename = os.path.basename(path)
            if not os.path.isfile(path):
                continue
            try:
                content = ""
                if path.endswith(".pdf"):
                    try:
                        import pypdf

                        reader = pypdf.PdfReader(path)
                        pages_text = []
                        for page in reader.pages:
                            t = page.extract_text()
                            if t:
                                pages_text.append(t)
                        content = "\n".join(pages_text)
                    except ImportError:
                        continue
                elif path.endswith((".html", ".htm")):
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        html_content = f.read()
                        content = re.sub(r"<[^>]+>", " ", html_content)
                elif path.endswith((".txt", ".json", ".xml")):
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                if content:
                    content = content.replace("\r\n", "\n")
                    if filename.endswith(".txt") or filename == "compliance_manual.txt":
                        paragraphs = content.split("\n\n")
                    else:
                        paragraphs = []
                        lines = content.split("\n")
                        current_chunk = []
                        current_len = 0
                        for line in lines:
                            line_clean = line.strip()
                            if not line_clean:
                                continue
                            if current_len + len(line_clean) > 1000 and current_chunk:
                                paragraphs.append(" ".join(current_chunk))
                                current_chunk = [line_clean]
                                current_len = len(line_clean)
                            else:
                                current_chunk.append(line_clean)
                                current_len += len(line_clean) + 1
                        if current_chunk:
                            paragraphs.append(" ".join(current_chunk))

                    for p in paragraphs:
                        cleaned_p = p.strip()
                        cleaned_p = re.sub(r"\s+", " ", cleaned_p)
                        if len(cleaned_p) > 40:
                            sections.append((cleaned_p, filename))
            except Exception as file_err:
                print(f"[RAG LOCAL] Error reading local file {filename}: {file_err}", flush=True)

        # 2. Try listing and downloading from GCS only if no local sections were loaded
        if not sections:
            try:
                from google.cloud import storage

                storage_client = storage.Client(project=project_id)
                bucket = storage_client.bucket(bucket_name)

                # Download compliance_manual.txt first
                try:
                    blob = bucket.blob("compliance_manual.txt")
                    text = blob.download_as_text(encoding="utf-8")
                    if text:
                        text = text.replace("\r\n", "\n")
                        paragraphs = text.split("\n\n")
                        for p in paragraphs:
                            if p.strip():
                                sections.append((p.strip(), "compliance_manual.txt"))
                except Exception:
                    pass

                # List all documents under compliance_docs/ folder
                try:
                    blobs = bucket.list_blobs(prefix="compliance_docs/")
                    for blob in blobs:
                        filename = os.path.basename(blob.name)
                        if not filename:
                            continue
                        content = ""
                        if filename.endswith(".pdf"):
                            try:
                                pdf_data = blob.download_as_bytes()
                                pdf_file = io.BytesIO(pdf_data)
                                reader = pypdf.PdfReader(pdf_file)
                                pages_text = []
                                for page in reader.pages:
                                    t = page.extract_text()
                                    if t:
                                        pages_text.append(t)
                                content = "\n".join(pages_text)
                            except Exception as pdf_err:
                                print(
                                    f"[RAG GCS FALLBACK] Error parsing PDF {filename} from GCS: {pdf_err}",
                                    flush=True,
                                )
                        elif filename.endswith((".html", ".htm")):
                            try:
                                html_content = blob.download_as_text(
                                    encoding="utf-8", errors="ignore"
                                )
                                content = re.sub(r"<[^>]+>", " ", html_content)
                            except Exception:
                                pass
                        elif filename.endswith((".txt", ".json", ".xml")):
                            try:
                                content = blob.download_as_text(encoding="utf-8", errors="ignore")
                            except Exception:
                                pass

                        if content:
                            content = content.replace("\r\n", "\n")
                            if filename.endswith(".txt") or filename == "compliance_manual.txt":
                                paragraphs = content.split("\n\n")
                            else:
                                paragraphs = []
                                lines = content.split("\n")
                                current_chunk = []
                                current_len = 0
                                for line in lines:
                                    line_clean = line.strip()
                                    if not line_clean:
                                        continue
                                    if current_len + len(line_clean) > 1000 and current_chunk:
                                        paragraphs.append(" ".join(current_chunk))
                                        current_chunk = [line_clean]
                                        current_len = len(line_clean)
                                    else:
                                        current_chunk.append(line_clean)
                                        current_len += len(line_clean) + 1
                                if current_chunk:
                                    paragraphs.append(" ".join(current_chunk))

                            for p in paragraphs:
                                cleaned_p = p.strip()
                                cleaned_p = re.sub(r"\s+", " ", cleaned_p)
                                if len(cleaned_p) > 40:
                                    # Prevent duplicate sections
                                    if not any(filename == src for _, src in sections):
                                        sections.append((cleaned_p, filename))
                except Exception as list_err:
                    print(
                        f"[RAG GCS FALLBACK] Error listing compliance_docs/ from GCS: {list_err}",
                        flush=True,
                    )

            except Exception as gcs_err:
                print(f"[RAG GCS FALLBACK] GCS Storage client error: {gcs_err}", flush=True)

        # Cache the parsed sections globally if any were found
        if sections:
            _COMPLIANCE_SECTIONS_CACHE = sections

    if not sections:
        return "No compliance documents found locally or in GCS."

    # Score each section based on word matches with the query
    query_words = set(re.findall(r"\w+", query.lower()))
    scored_sections = []
    for sec, source in sections:
        sec_words = set(re.findall(r"\w+", sec.lower()))
        common_words = query_words.intersection(sec_words)
        important_matches = {w for w in common_words if len(w) > 3}
        score = len(important_matches)
        if score > 0 and source == "compliance_manual.txt":
            score += 3  # Balanced boost to prioritize primary internal policy manual while allowing highly relevant CCPA/GDPR matches
        scored_sections.append((score, sec, source))

    scored_sections.sort(key=lambda x: x[0], reverse=True)
    top_sections = [(sec, source) for score, sec, source in scored_sections if score > 0]

    if not top_sections:
        top_sections = [(sec, source) for sec, source in sections[:3]]

    result_snippets = []
    for sec, source in top_sections[:3]:
        result_snippets.append(f"[Source: {source}]\n{sec}")

    return "\n\n---\n\n".join(result_snippets)


def query_compliance_manual(query: str) -> str:
    """
    Queries the 'Retail Data Handling Policy' manual for detailed guidelines and interpretations.
    Use this tool when you need clarification on data handling standards, anonymization techniques,
    RTBF procedures, or any policy-level detail not found in the core regulation file.
    """
    import re
    import html

    def _clean_text(val: str) -> str:
        # Strip HTML tags like <b> and </b>
        val = re.sub(r"<[^>]+>", "", val)
        # Decode HTML entities like &nbsp; or &amp;
        val = html.unescape(val)
        # Normalize whitespace
        val = re.sub(r"\s+", " ", val).strip()
        return val

    # Validate using Pydantic schema
    validated = ComplianceQueryInput(query=query)
    query_str = validated.query
    print(f"\n[RAG TOOL] Calling query_compliance_manual with query: {query_str!r}", flush=True)

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")
    location = "global"  # Vertex AI Search location

    # Check if we should skip cloud search and run purely local RAG (highly recommended for offline/local eval!)
    if os.getenv("RAG_LOCAL_ONLY", "false").lower() == "true":
        print(
            f"[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.", flush=True
        )
        return _local_compliance_manual_search(query_str)

    try:
        client = discoveryengine.SearchServiceClient()

        # Define the serving configuration resource name
        serving_config = client.serving_config_path(
            project=project_id,
            location=location,
            data_store=RAG_DATA_STORE_ID,
            serving_config="default_config",
        )

        content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
            snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True,
                max_snippet_count=3,
            )
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query_str,
            page_size=3,  # Retrieve top 3 relevant snippets
            content_search_spec=content_search_spec,
        )

        response = client.search(request)
        snippets = []
        for result in response.results:
            print(f"[RAG TOOL] Discovery Engine raw result: {result}", flush=True)
            # Extract relevant text from the result
            data = result.document.derived_struct_data
            if not data:
                continue

            # Support multiple Discovery Engine result structures
            # 1. Standard search snippets (MapComposite / dict)
            if "snippets" in data:
                for snippet_obj in data["snippets"]:
                    try:
                        raw_text = None
                        if hasattr(snippet_obj, "get") and "snippet" in snippet_obj:
                            raw_text = snippet_obj["snippet"]
                        elif "snippet" in snippet_obj:
                            raw_text = snippet_obj["snippet"]
                        if raw_text:
                            snippets.append(_clean_text(raw_text))
                    except Exception:
                        pass

            # 2. Extractive answers
            if "extractive_answers" in data:
                for answer in data["extractive_answers"]:
                    try:
                        raw_text = None
                        if hasattr(answer, "get") and "content" in answer:
                            raw_text = answer["content"]
                        elif "content" in answer:
                            raw_text = answer["content"]
                        if raw_text:
                            snippets.append(_clean_text(raw_text))
                    except Exception:
                        pass

            # 3. Extractive segments
            if "extractive_segments" in data:
                for segment in data["extractive_segments"]:
                    try:
                        raw_text = None
                        if hasattr(segment, "get") and "content" in segment:
                            raw_text = segment["content"]
                        elif "content" in segment:
                            raw_text = segment["content"]
                        if raw_text:
                            snippets.append(_clean_text(raw_text))
                    except Exception:
                        pass

        # Always run local search as well, to ensure un-truncated compliance_manual.txt paragraphs are loaded!
        local_res = _local_compliance_manual_search(query_str)
        local_snippets = local_res.split("\n\n---\n\n") if local_res else []

        combined_snippets = []
        # 1. Add all local snippets first (they are un-truncated and prioritized for compliance_manual.txt)
        for s in local_snippets:
            s_stripped = s.strip()
            if s_stripped:
                combined_snippets.append(s_stripped)

        # 2. Add cloud search snippets (avoiding duplicates based on a prefix match)
        for snip in snippets:
            snip_clean = snip.strip()
            if snip_clean:
                # Deduplicate: check if this snippet prefix already exists in combined_snippets
                snippet_prefix = snip_clean[:40].lower()
                is_duplicate = False
                for existing in combined_snippets:
                    if snippet_prefix in existing.lower():
                        is_duplicate = True
                        break
                if not is_duplicate:
                    combined_snippets.append(f"[Source: Cloud Search]\n{snip_clean}")

        # Keep top 4 distinct snippets
        final_snippets = combined_snippets[:4]
        res = "\n\n---\n\n".join(final_snippets)
        print(f"[RAG TOOL] Combined local & cloud search results: {res[:120]}...", flush=True)
        return res
    except Exception as e:
        # Fallback to local search if API call fails (e.g. offline, missing credentials, resource not found)
        res = _local_compliance_manual_search(query_str)
        print(f"[RAG TOOL] Exception {e!r}, returned local search: {res[:120]}...", flush=True)
        return res


def _run_bq_query(query: str) -> list[dict]:
    """Helper to run a BigQuery SQL query directly using BigQuery client."""
    from google.cloud import bigquery
    from datetime import date, datetime

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")
    try:
        client = bigquery.Client(project=project_id)
        query_job = client.query(query)
        results = query_job.result()

        serialized_results = []
        for row in results:
            row_dict = dict(row)
            for k, v in row_dict.items():
                if isinstance(v, (datetime, date)):
                    row_dict[k] = v.isoformat()
            serialized_results.append(row_dict)
        return serialized_results
    except Exception as e:
        print(f"Error executing BigQuery query: {e}", flush=True)
        return []


# Global method to get results from Orders table
def _fetch_orders_from_bigquery() -> list[dict]:
    if os.getenv("DB_MODE", "local") == "local":
        import data.data_manager as dm
        return dm.ORDER_DB
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")
    dataset_id = DATASET_ID  # Use constant
    order_table_name = os.getenv("AUDIT_ORDER_TABLE", "orders")
    query = f"SELECT * FROM `{project_id}.{dataset_id}.{order_table_name}`"
    return _run_bq_query(query)


# Global method to get results from Customers table
def _fetch_customers_from_bigquery() -> list[dict]:
    if os.getenv("DB_MODE", "local") == "local":
        import data.data_manager as dm
        return dm.CUSTOMER_DB
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")
    dataset_id = DATASET_ID  # Use constant
    customer_table_name = os.getenv("AUDIT_CUSTOMER_TABLE", "customers")
    query = f"SELECT * FROM `{project_id}.{dataset_id}.{customer_table_name}`"
    return _run_bq_query(query)


# =========================================================================
#  INPUT SCHEMAS  (only for tools that take parameters)
# =========================================================================


class CustomerStatusInput(BaseModel):
    """Input schema for find_customers_by_status."""

    status: Annotated[
        str,
        Field(
            description="Customer status to filter by. Valid values: 'active' or 'forgotten'.",
            pattern=r"^(active|forgotten)$",
        ),
    ]

    @field_validator("status", mode="before")
    @classmethod
    def normalise_status(cls, v: str) -> str:
        return v.strip().lower()


class CustomerIdInput(BaseModel):
    """Input schema for get_orders_by_customer_id."""

    customer_id: Annotated[
        str,
        Field(
            description="The unique customer ID or a comma-separated list of customer IDs whose orders should be retrieved.",
            min_length=1,
        ),
    ]

    @field_validator("customer_id", mode="before")
    @classmethod
    def normalise_id(cls, v: str) -> str:
        return v.strip()


class RetentionPolicyInput(BaseModel):
    """Input schema for find_retention_policy_violations."""

    max_age_days: Annotated[
        int,
        Field(
            description=(
                "Maximum allowed age (in days) for un-anonymised order records. "
                "Records older than this are considered violations. "
                "Regulation Rule 3.1 requires 3650 days (10 years)."
            ),
            ge=1,
            le=36500,
        ),
    ]


class ComplianceQueryInput(BaseModel):
    """Input schema for query_compliance_manual."""

    query: Annotated[
        str,
        Field(
            description="The search query or question about compliance policy.",
            min_length=3,
        ),
    ]


# =========================================================================
#  TOOL FUNCTIONS
# =========================================================================


def read_regulation_file() -> str:
    """
    Reads the 'regulation.txt' file to understand the compliance rules.
    This should be the first step in any audit.
    """
    file_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/regulation.txt"
    with open(file_path, "r") as f:
        return f.read()


def find_customers_by_status(status: str) -> list[dict]:
    """
    Searches the customer database and returns a list of all customers
    matching a given status ('active' or 'forgotten').
    """
    validated = CustomerStatusInput(status=status)
    if os.getenv("DB_MODE", "local") == "local":
        import data.data_manager as dm
        return [c for c in dm.CUSTOMER_DB if c.get("status") == validated.status]

    customer_table_name = os.getenv("AUDIT_CUSTOMER_TABLE", "customers")

    query = f"""
        SELECT * FROM `{os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")}.retail_audit_db.{customer_table_name}` 
        WHERE status = '{validated.status}'
    """

    return _run_bq_query(query)


def get_orders_by_customer_id(customer_id: str) -> list[dict]:
    """Retrieves orders for a specific customer or a comma-separated list of customer IDs from BigQuery."""

    validated = CustomerIdInput(customer_id=customer_id)
    if os.getenv("DB_MODE", "local") == "local":
        import data.data_manager as dm
        ids = [i.strip() for i in validated.customer_id.split(",") if i.strip()]
        return [o for o in dm.ORDER_DB if o.get("customer_id") in ids]

    order_table_name = os.getenv("AUDIT_ORDER_TABLE", "orders")

    ids = [i.strip() for i in validated.customer_id.split(",") if i.strip()]
    if len(ids) > 1:
        ids_str = ", ".join(f"'{i}'" for i in ids)
        query = f"""
            SELECT * 
            FROM `{os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")}.retail_audit_db.{order_table_name}`
            WHERE customer_id IN ({ids_str})
        """
    else:
        query = f"""
            SELECT * 
            FROM `{os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")}.retail_audit_db.{order_table_name}`
            WHERE customer_id = '{validated.customer_id}'
        """

    return _run_bq_query(query)


def find_pii_compliance_violations() -> list[dict]:
    """
    Scans the entire orders database for records that violate PII rules
    (Rules 1.1, 1.3 from REGULATION_TEXT).
    Checks for both unmasked PII (e.g. a real email) AND invalid PII states
    (like 'NULL' or 'N/A').  A compliant field must be exactly '[MASKED]'.
    """
    violations: list[dict] = []
    compliant_state = "[MASKED]"
    invalid_states = {"NULL", "N/A", "ERROR", "NONE"}

    results = _fetch_orders_from_bigquery()

    for order in results:
        for field_name in ("customer_email", "customer_phone"):
            field_value = order.get(field_name)
            if field_value is not None and field_value != compliant_state:
                vtype = (
                    "PII Integrity Failure"
                    if str(field_value).upper() in invalid_states
                    else "PII Leak (Unmasked)"
                )
                violations.append(
                    {
                        "order_id": order.get("order_id"),
                        "field": field_name,
                        "value": field_value,
                        "violation_type": vtype,
                    }
                )
    return violations


def find_retention_policy_violations(max_age_days: int) -> list[dict]:
    """
    Scans all orders to find records that violate the data retention policy
    (Rule 3.1 from REGULATION_TEXT).
    Returns orders older than 'max_age_days' that have NOT been anonymised.
    """
    validated = RetentionPolicyInput(max_age_days=max_age_days)
    today_midnight = datetime.combine(datetime.now().date(), datetime.min.time())
    cutoff = today_midnight - timedelta(days=validated.max_age_days)
    violations: list[dict] = []

    results = _fetch_orders_from_bigquery()

    for order in results:
        try:
            order_date = datetime.strptime(order.get("order_date", ""), "%Y-%m-%d")
        except (ValueError, TypeError):
            continue

        if order_date < cutoff and order.get("customer_id") != "ANONYMIZED":
            violations.append(
                {
                    "order_id": order.get("order_id"),
                    "customer_id": order.get("customer_id"),
                    "order_date": order.get("order_date"),
                    "violation_type": "Data Retention Failure",
                }
            )
    return violations


def find_orphaned_orders() -> list[dict]:
    """Scans BigQuery to find orders with invalid customer IDs."""
    if os.getenv("DB_MODE", "local") == "local":
        import data.data_manager as dm
        valid_cust_ids = {c["customer_id"] for c in dm.CUSTOMER_DB}
        violations = []
        for o in dm.ORDER_DB:
            cid = o.get("customer_id")
            if cid not in valid_cust_ids and cid not in ("ANONYMIZED", "ANONYMISED"):
                violations.append(
                    {
                        "order_id": o.get("order_id"),
                        "customer_id": cid,
                        "violation_type": "Orphaned Record",
                    }
                )
        return violations

    order_table_name = os.getenv("AUDIT_ORDER_TABLE", "orders")
    customer_table_name = os.getenv("AUDIT_CUSTOMER_TABLE", "customers")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")

    query = f"""
        SELECT order_id, customer_id 
        FROM `{project_id}.retail_audit_db.{order_table_name}`
        WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM `{project_id}.retail_audit_db.{customer_table_name}`)
          AND customer_id NOT IN ('ANONYMIZED', 'ANONYMISED')
    """

    results = _run_bq_query(query)

    violations = []
    for row in results:
        violations.append(
            {
                "order_id": row.get("order_id"),
                "customer_id": row.get("customer_id"),
                "violation_type": "Orphaned Record",
            }
        )
    return violations


# =========================================================================
#  REGISTER AS ADK FUNCTION TOOLS
# =========================================================================

read_regulation_file_tool = FunctionTool(read_regulation_file)
find_customers_by_status_tool = FunctionTool(find_customers_by_status)
get_orders_by_customer_id_tool = FunctionTool(get_orders_by_customer_id)
find_pii_compliance_violations_tool = FunctionTool(find_pii_compliance_violations)
find_retention_policy_violations_tool = FunctionTool(find_retention_policy_violations)
find_orphaned_orders_tool = FunctionTool(find_orphaned_orders)
query_compliance_manual_tool = FunctionTool(query_compliance_manual)
