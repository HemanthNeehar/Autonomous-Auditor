"""
Autonomous Auditor — FastAPI Backend (ADK Edition)
===================================================
Uses the Google ADK agentic system (Gemini + tool-calling) to perform
compliance audits.

Endpoints
---------
GET  /                   → serve index.html
GET  /styles.css         → serve stylesheet
GET  /api/stats          → database summary statistics
GET  /api/regulation     → raw regulation text
POST /api/reload         → hot-reload data files from disk
POST /api/audit/agent    → full 5-point agentic audit (SSE streaming)
POST /api/audit/pii      → standalone PII check (non-agentic, fast)
POST /api/audit/rtbf     → standalone RTBF check
POST /api/audit/retention→ standalone retention check
POST /api/audit/orphaned → standalone orphaned-records check
POST /api/audit/full     → all 4 checks, consolidated JSON response
"""

import asyncio
import concurrent.futures
import json
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel
from vertexai.agent_engines import AgentEngine
import os
import uuid

# ---------------------------------------------------------------------------
# Path bootstrap — make src_v2 importable regardless of cwd
# ---------------------------------------------------------------------------
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

from data.data_manager import load_data, CUSTOMER_DB, ORDER_DB, REGULATION_TEXT

# ADK tools (direct Python functions — used for the fast, non-agentic endpoints)
from tools.adk_tools import (
    find_customers_by_status,
    find_orphaned_orders,
    find_pii_compliance_violations,
    find_retention_policy_violations,
    get_orders_by_customer_id,
)

# ADK agent + per-request runner factory
from agents.agent import auditor_agent, APP_NAME
from runtime.agent_executor import create_runner

from google.genai import types as genai_types

# BigQuery project/dataset (read from env, defaulting to known values)
BQ_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")
BQ_DATASET = os.getenv("BQ_DATASET", "retail_audit_db")

# Thread-pool for running synchronous BigQuery / AgentEngine calls
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)

# =========================================================================
#  FASTAPI APP
# =========================================================================

app = FastAPI(
    title="Autonomous Auditor API",
    description="Agentic compliance auditor powered by Google ADK + Gemini.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================================
#  PYDANTIC MODELS
# =========================================================================


class DatabaseStats(BaseModel):
    total_customers: int
    total_orders: int
    active_customers: int
    forgotten_customers: int
    oldest_order_date: str
    newest_order_date: str


# =========================================================================
#  STATIC FILE ROUTES
# =========================================================================


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend HTML page."""
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/styles.css")
async def serve_css():
    """Serve the CSS stylesheet."""
    return FileResponse(Path(__file__).parent / "styles.css", media_type="text/css")


# =========================================================================
#  DATA API ENDPOINTS
# =========================================================================


@app.get("/api/stats", response_model=DatabaseStats)
async def get_database_stats():
    """Return high-level statistics — queries BigQuery when available, falls back to local JSON."""

    def _query_bq() -> DatabaseStats:
        from toolbox_core import ToolboxSyncClient

        url = os.getenv("MCP_TOOLBOX_URL", "http://localhost:5000")

        stats_sql = f"""
            SELECT
              (SELECT COUNT(*) FROM `{BQ_PROJECT}.{BQ_DATASET}.customers`)            AS total_customers,
              (SELECT COUNT(*) FROM `{BQ_PROJECT}.{BQ_DATASET}.orders`)               AS total_orders,
              (SELECT COUNT(*) FROM `{BQ_PROJECT}.{BQ_DATASET}.customers` WHERE status='active')   AS active_customers,
              (SELECT COUNT(*) FROM `{BQ_PROJECT}.{BQ_DATASET}.customers` WHERE status='forgotten') AS forgotten_customers,
              (SELECT MIN(order_date) FROM `{BQ_PROJECT}.{BQ_DATASET}.orders`)        AS oldest_order_date,
              (SELECT MAX(order_date) FROM `{BQ_PROJECT}.{BQ_DATASET}.orders`)        AS newest_order_date
        """

        with ToolboxSyncClient(url) as toolbox:
            execute_sql = toolbox.load_tool("execute_sql")
            results = execute_sql(sql=stats_sql)
            # The MCP toolbox execute_sql usually returns a string (JSON/CSV) or a list of dicts.
            # The MCP toolbox returns results as a JSON string.
            import json

            try:
                parsed = json.loads(results) if isinstance(results, str) else results
                if isinstance(parsed, list) and len(parsed) > 0:
                    row = parsed[0]
                elif isinstance(parsed, dict):
                    row = parsed
                else:
                    row = {}
            except Exception:
                row = {}

        def _fmt(d) -> str:
            if d is None:
                return "N/A"
            return str(d)

        return DatabaseStats(
            total_customers=int(row.get("total_customers", 0)),
            total_orders=int(row.get("total_orders", 0)),
            active_customers=int(row.get("active_customers", 0)),
            forgotten_customers=int(row.get("forgotten_customers", 0)),
            oldest_order_date=_fmt(row.get("oldest_order_date")),
            newest_order_date=_fmt(row.get("newest_order_date")),
        )

    def _local_stats() -> DatabaseStats:
        order_dates = []
        for o in ORDER_DB:
            try:
                order_dates.append(datetime.strptime(o.get("order_date", ""), "%Y-%m-%d"))
            except (ValueError, TypeError):
                continue
        return DatabaseStats(
            total_customers=len(CUSTOMER_DB),
            total_orders=len(ORDER_DB),
            active_customers=sum(1 for c in CUSTOMER_DB if c.get("status") == "active"),
            forgotten_customers=sum(1 for c in CUSTOMER_DB if c.get("status") == "forgotten"),
            oldest_order_date=min(order_dates).strftime("%Y-%m-%d") if order_dates else "N/A",
            newest_order_date=max(order_dates).strftime("%Y-%m-%d") if order_dates else "N/A",
        )

    # Try BigQuery first; fall back to local files if BQ is unreachable
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _query_bq)
    except Exception as bq_err:
        print(f"[WARN] BigQuery stats unavailable ({bq_err}), falling back to local JSON")
        return _local_stats()


@app.get("/api/regulation")
async def get_regulation():
    """Return the regulation text."""
    return {"regulation": REGULATION_TEXT}


@app.post("/api/reload")
async def reload_data():
    """Reload data files from disk (e.g. after regenerating with generate_data.py)."""
    load_data()
    return {"status": "ok", "customers": len(CUSTOMER_DB), "orders": len(ORDER_DB)}


# =========================================================================
#  AGENTIC AUDIT ENDPOINT  (SSE streaming via ADK Runner)
# =========================================================================

AUDIT_PROMPT = "Please start the comprehensive 5-point compliance audit!"

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable Nginx buffering
}


def _sse(payload: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(payload)}\n\n"


@app.post("/api/audit/agent")
async def run_agent_audit():
    """
    Run the full agentic 5-point compliance audit using the ADK Runner.
    Supports local ADK Runner or Remote Agent Engine via AGENT_MODE env var.

    Streams agent reasoning steps as Server-Sent Events (SSE).
    Each event is a JSON object:
      { type: "thought"|"tool_call"|"tool_result"|"final_report"|"error", ... }
    """

    # Read configuration from environment
    AGENT_MODE = os.getenv("AGENT_MODE", "local")  # "local" or "remote"
    AGENT_RESOURCE_NAME = os.getenv("AGENT_RESOURCE_NAME")  # e.g. projects/.../agentEngines/...
    GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false")

    async def event_stream():
        final_text = ""
        try:
            if AGENT_MODE == "local":
                # --- LOCAL MODE ---
                runner, session_id = await create_runner()
                user_message = genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=AUDIT_PROMPT)],
                )

                # run_async yields Event objects as the agent works
                async for event in runner.run_async(
                    user_id="system",
                    session_id=session_id,
                    new_message=user_message,
                ):
                    # ── Agent text / reasoning ──────────────────────────────
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            # Function (tool) call the model is about to make
                            if part.function_call:
                                fc = part.function_call
                                yield _sse(
                                    {
                                        "type": "tool_call",
                                        "tool": fc.name,
                                        "args": dict(fc.args) if fc.args else {},
                                    }
                                )

                            # Function (tool) result returned from our Python fn
                            elif part.function_response:
                                fr = part.function_response
                                raw = json.dumps(fr.response) if fr.response else ""
                                display = (
                                    raw[:2000] + f"… [{len(raw)} chars total]"
                                    if len(raw) > 2000
                                    else raw
                                )
                                yield _sse(
                                    {
                                        "type": "tool_result",
                                        "tool": fr.name,
                                        "content": display,
                                    }
                                )
                                # Brief yield to keep the event loop responsive
                                await asyncio.sleep(5)

                            # Plain text — model reasoning or final narrative
                            elif part.text and part.text.strip():
                                text = part.text.strip()
                                yield _sse({"type": "thought", "content": text})
                                final_text = text

                    # ── Turn complete — mark final report ───────────────────
                    if event.is_final_response():
                        yield _sse({"type": "final_report", "content": final_text})

                yield "data: [DONE]\n\n"
            else:
                # --- REMOTE MODE (GCP Agent Engine) ---
                # AgentEngine.stream_query() is a *synchronous* generator.
                # We run it in a thread executor and push events into an async queue
                # so the SSE stream stays non-blocking.
                if not AGENT_RESOURCE_NAME:
                    raise ValueError("AGENT_RESOURCE_NAME must be set for remote mode")

                print("Running through Agent Engine using resource name: ", AGENT_RESOURCE_NAME)

                remote_agent = AgentEngine(AGENT_RESOURCE_NAME)
                session_id = str(uuid.uuid4())
                queue: asyncio.Queue = asyncio.Queue()
                loop = asyncio.get_event_loop()

                def _run_stream():
                    """Sync worker: pulls chunks from stream_query and puts them on the queue."""
                    try:
                        for chunk in remote_agent.stream_query(
                            message=AUDIT_PROMPT,
                            user_id="system",
                        ):
                            loop.call_soon_threadsafe(queue.put_nowait, chunk)
                    except Exception as stream_err:
                        loop.call_soon_threadsafe(queue.put_nowait, {"_error": str(stream_err)})
                    finally:
                        print("Stream finished")
                        loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

                loop.run_in_executor(_executor, _run_stream)

                while True:
                    chunk = await queue.get()
                    if chunk is None:  # sentinel → stream finished
                        break

                    # Handle error forwarded from the thread
                    if isinstance(chunk, dict) and "_error" in chunk:
                        yield _sse({"type": "error", "content": chunk["_error"]})
                        continue

                    # --- Extract text from the chunk ---
                    # stream_query() can return different shapes depending on
                    # the ADK / Agent Engine version.  We try them all.
                    extracted_text = ""
                    extracted_fc = None  # function call dict

                    if isinstance(chunk, str):
                        # Simplest case: chunk is just a string
                        extracted_text = chunk.strip()

                    elif isinstance(chunk, dict):
                        # Case A: {"content": {"parts": [{"text": "..."}]}}
                        content = chunk.get("content")
                        if isinstance(content, dict):
                            for part in content.get("parts", []):
                                if isinstance(part, dict):
                                    if "functionCall" in part:
                                        extracted_fc = part["functionCall"]
                                    elif "text" in part:
                                        extracted_text += part["text"]

                        # Case B: {"output": "some text"} (older Agent Engine)
                        if not extracted_text and not extracted_fc:
                            output = chunk.get("output")
                            if isinstance(output, str):
                                extracted_text = output.strip()

                        # Case C: top-level {"text": "..."} (some ADK versions)
                        if not extracted_text and not extracted_fc:
                            if "text" in chunk:
                                extracted_text = str(chunk["text"]).strip()

                    else:
                        # Protobuf or other object — try to convert
                        try:
                            chunk_dict = (
                                type(chunk).to_dict(chunk)
                                if hasattr(type(chunk), "to_dict")
                                else {}
                            )
                            content = chunk_dict.get("content", {})
                            for part in content.get("parts", []):
                                if "functionCall" in part:
                                    extracted_fc = part["functionCall"]
                                elif "text" in part:
                                    extracted_text += part["text"]
                        except Exception:
                            extracted_text = str(chunk).strip()

                    # --- Emit SSE events ---
                    if extracted_fc:
                        yield _sse(
                            {
                                "type": "tool_call",
                                "tool": extracted_fc.get("name", ""),
                                "args": extracted_fc.get("args", {}),
                            }
                        )
                    if extracted_text:
                        yield _sse({"type": "thought", "content": extracted_text})
                        final_text = extracted_text

                yield _sse({"type": "final_report", "content": final_text})
                yield "data: [DONE]\n\n"

        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "content": str(exc)})
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# =========================================================================
#  DIRECT (NON-AGENTIC) AUDIT ENDPOINTS  — fast, deterministic checks
# =========================================================================


@app.post("/api/audit/pii")
async def audit_pii():
    """Standalone PII compliance check (no LLM involved)."""
    violations = find_pii_compliance_violations()
    return {
        "rule_id": "Section 1",
        "rule_name": "PII (Personally Identifiable Information)",
        "status": "FAILED" if violations else "PASSED",
        "violation_count": len(violations),
        "violations": violations[:100],
        "description": "Checks PII fields in orders are properly masked as '[MASKED]'.",
    }


@app.post("/api/audit/rtbf")
async def audit_rtbf():
    """Standalone RTBF (Right to be Forgotten) check."""
    forgotten = find_customers_by_status(status="forgotten")
    violations = []
    for customer in forgotten:
        orders = get_orders_by_customer_id(customer_id=customer["customer_id"])
        for o in orders:
            violations.append(
                {
                    "order_id": o.get("order_id"),
                    "customer_id": customer["customer_id"],
                    "customer_name": customer.get("name"),
                    "violation_type": "RTBF - Orders Still Exist",
                }
            )
    return {
        "rule_id": "Section 2",
        "rule_name": "RTBF (Right to be Forgotten)",
        "status": "FAILED" if violations else "PASSED",
        "violation_count": len(violations),
        "violations": violations[:100],
        "description": "Verifies forgotten customers have zero associated orders.",
    }


@app.post("/api/audit/retention")
async def audit_retention():
    """Standalone data retention check (10-year rule)."""
    violations = find_retention_policy_violations(max_age_days=3650)
    return {
        "rule_id": "Section 3",
        "rule_name": "Data Retention",
        "status": "FAILED" if violations else "PASSED",
        "violation_count": len(violations),
        "violations": violations[:100],
        "description": "Ensures orders older than 10 years are anonymised.",
    }


@app.post("/api/audit/orphaned")
async def audit_orphaned():
    """Standalone orphaned-records check."""
    violations = find_orphaned_orders()
    return {
        "rule_id": "Section 4",
        "rule_name": "Data Governance & Integrity",
        "status": "FAILED" if violations else "PASSED",
        "violation_count": len(violations),
        "violations": violations[:100],
        "description": "Validates every customer_id in orders has a valid customer record.",
    }


@app.post("/api/audit/full")
async def audit_full():
    """Run all 4 compliance checks sequentially and return a consolidated report."""
    # Run concurrently — these are pure-Python, CPU-bound but tiny datasets
    pii_res, rtbf_res, retention_res, orphaned_res = await asyncio.gather(
        audit_pii(), audit_rtbf(), audit_retention(), audit_orphaned()
    )

    sections = [pii_res, rtbf_res, retention_res, orphaned_res]
    total_violations = sum(s["violation_count"] for s in sections)
    failed_count = sum(1 for s in sections if s["status"] == "FAILED")
    passed_count = len(sections) - failed_count

    summary = (
        "Comprehensive Audit Complete: All compliance checks passed successfully."
        if failed_count == 0
        else f"Comprehensive Audit Complete: {passed_count} checks passed, {failed_count} checks failed."
    )

    return {
        "sections": sections,
        "summary": summary,
        "total_violations": total_violations,
        "timestamp": datetime.now().isoformat(),
    }


# =========================================================================
#  ENTRY POINT
# =========================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
