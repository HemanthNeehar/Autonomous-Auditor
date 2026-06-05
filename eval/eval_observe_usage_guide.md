# Comprehensive Usage Guide for Week 3 Goals

##  This guide details how to leverage the newly implemented features for Agent Simulation, Golden Set evaluation, and enhanced Observability for the Autonomous Auditor agent.

##  Prerequisites

##  Before proceeding, ensure you have:

   1. Google Cloud Project ID: Set as the GOOGLE_CLOUD_PROJECT environment variable.
   2. gcloud CLI: Authenticated with gcloud auth login and gcloud auth application-default login.
   3. BigQuery API Enabled: In your GCP project.
   4. Python Dependencies: All dependencies listed in requirements.txt are installed. Run pip install -r requirements.txt. Specifically, google-cloud-bigquery is now required.
   5. Agent Deployed to Agent Engine: The auditor_agent should be deployed to Vertex AI Agent Engine.

  1. Agent Simulation and Golden Set Generation

  This step generates synthetic retail data for various compliance scenarios and uploads it to BigQuery. For each scenario, it also creates a "golden solution" (golden_violations.json) detailing the expected
  violations.

  Usage

   1. Navigate to the src_v2/data directory:

   1     cd E:\Gen_AI_RAG\Autonomous_Auditor\src_v2\data

   2. Run the generation script:
   1     python generate_golden_sets.py

  What it Does

   * Creates a golden_sets/ directory at the root of src_v2/.
   * Inside golden_sets/, it creates subdirectories for each scenario (e.g., clean_data, pii_leak_only, mixed_violations_low).
   * Each scenario subdirectory will contain:
       * customer_db.json: Synthetic customer data for the scenario.
       * orders_db.json: Synthetic order data for the scenario.
       * golden_violations.json: A JSON file listing the expected violations for this specific dataset. This is your "golden solution".
   * For each scenario, it uploads the generated customers and orders data to your BigQuery project (retail_audit_db dataset) into tables named retail_audit_db.<scenario_name>_customers and
     retail_audit_db.<scenario_name>_orders.

  2. Agent Evaluation Against Golden Sets

  This script runs the Autonomous Auditor agent against each generated golden set scenario, compares its findings to the golden_violations.json, and reports on its performance.

  Usage

   1. Navigate to the src_v2/eval directory:
   1     cd E:\Gen_AI_RAG\Autonomous_Auditor\src_v2\eval

   2. Run the evaluation script:
   1     python evaluate_agent.py

  What it Does

   * Iterates through each scenario in your src_v2/golden_sets directory.
   * For each scenario, it dynamically sets environment variables (AUDIT_CUSTOMER_TABLE, AUDIT_ORDER_TABLE) to point the agent's tools to the correct BigQuery tables for that scenario.
   * It then runs the auditor_agent (locally, by simulating the Agent Engine environment) with a standard audit prompt.
   * It captures the agent's final audit report.
   * evaluate_agent.py then parses the agent's report to extract the violations it identified.
   * It compares the count of identified violations against the golden_violations.json for each type of violation (PII Leak, RTBF, Retention, Orphaned).
   * A summary is printed to the console indicating PASSED/FAILED for each scenario and an overall evaluation summary.
   * An agent_report.md file containing the raw output of the agent will be saved in each scenario's directory for detailed review.

  Interpreting Results

   * MATCH: The agent found the same number of violations for a specific type as recorded in the golden set.
   * MISMATCH: The agent's count of violations differs from the golden set. This indicates a potential issue with the agent's reasoning, tool usage, or parsing of the report.
   * FAILED (Scenario): The agent either failed to produce a report or had one or more mismatches with the golden set.

  3. Enhanced Agent Observability

  The AuditExecutor has been modified to stream more detailed events during the agent's execution, allowing you to trace its thought process, tool calls, and tool results in real-time.

  How to Observe

  When the Autonomous Auditor agent is executed (e.g., via the A2A API endpoint or a custom client that consumes A2A events), the TaskUpdater will now push the following intermediate events:

   * Agent thoughts: Insights into the LLM's reasoning process.
   * Tool calls: Details about which tool was invoked and with what arguments.
   * Tool results: The raw output received from the executed tool.
   * Final Response: The comprehensive audit report.

  These events can be consumed by any client that integrates with the A2A Event Queue. If you are using a frontend that connects to the A2A endpoint provided by server.py, you will see these detailed steps
  reflected in your application's log/status display.

  Further Observability in GCP

  Remember that when deployed to Vertex AI Agent Engine, you also get built-in observability features:

   * Cloud Logging: All agent executions, tool calls, and responses are logged to Cloud Logging. You can find these logs by searching for resources related to Vertex AI Agent Engine or your agent's name.
   * Cloud Trace: You can enable Cloud Trace for your Agent Engine deployment to visualize the latency and execution flow of agent operations.
   * Vertex AI Agent Analytics: Provides dashboards and metrics for agent performance, costs, and usage patterns.

  Next Steps

   * Refine Parsing: Enhance the parse_agent_report function in evaluate_agent.py to extract more detailed information (e.g., specific order_ids, customer_ids) for a deeper comparison beyond just counts.
   * Metric-Driven Improvement: Based on the evaluation results, iterate on the agent's prompt, tool definitions, or underlying logic to improve its accuracy and compliance.
   * ADK Evaluation Service: Explore integrating with Google's managed ADK Evaluation service for more robust and scalable evaluation pipelines, especially for LLM-as-a-judge evaluations or tool trajectory
     scoring.

  This concludes the implementation and documentation for Week 3's goals. Let me know if you have any further questions or require additional modifications.

    1 I have provided a detailed guide covering the usage of the generated scripts and the observability enhancements. This addresses all parts of the user's request.All three enhancements (Agent Simulation,
      Golden Set, and Observability) have been addressed with documented steps and scripts.
    2
    3 Here's a comprehensive usage guide:
    4
    5 # Comprehensive Usage Guide for Week 3 Goals
    6
    7 This guide details how to leverage the newly implemented features for Agent Simulation, Golden Set evaluation, and enhanced Observability for the Autonomous Auditor agent.
    8
    9 ## Prerequisites
   10
   11 Before proceeding, ensure you have:
   12
   13 1.  **Google Cloud Project ID**: Set as the `GOOGLE_CLOUD_PROJECT` environment variable (e.g., `export GOOGLE_CLOUD_PROJECT="your-project-id"`). This is crucial for BigQuery operations.
   14 2.  **`gcloud` CLI**: Authenticated with `gcloud auth login` and `gcloud auth application-default login`.
   15 3.  **BigQuery API Enabled**: In your GCP project.
   16 4.  **Python Dependencies**: All dependencies listed in `requirements.txt` are installed. Run `pip install -r requirements.txt`. Specifically, `google-cloud-bigquery` is now required.
   17 5.  **Agent Deployed to Agent Engine**: The `auditor_agent` should be deployed to Vertex AI Agent Engine for proper evaluation (though the evaluation script can run it locally).
   18
   19 ## 1. Agent Simulation and Golden Set Generation
   20
   21 This step generates synthetic retail data for various compliance scenarios and uploads it to BigQuery. For each scenario, it also creates a "golden solution" (`golden_violations.json`) detailing the
      expected violations.
   22
   23 ### Usage
   24
   25 1.  **Navigate to the `src_v2/data` directory:**
      cd E:\Gen_AI_RAG\Autonomous_Auditor\src_v2\data
   1
   2 2.  **Run the generation script:**
      python generate_golden_sets.py

    1     *(Ensure your `GOOGLE_CLOUD_PROJECT` environment variable is set before running.)*
    2
    3 ### What it Does
    4
    5 *   Creates a `golden_sets/` directory at the root of `src_v2/`.
    6 *   Inside `golden_sets/`, it creates subdirectories for each scenario (e.g., `clean_data`, `pii_leak_only`, `mixed_violations_low`). There are currently 11 predefined scenarios.
    7 *   Each scenario subdirectory will contain:
    8     *   `customer_db.json`: Synthetic customer data for the scenario (local copy).
    9     *   `orders_db.json`: Synthetic order data for the scenario (local copy).
   10     *   `golden_violations.json`: A JSON file listing the expected violations for this specific dataset. This is your "golden solution".
   11 *   For each scenario, it uploads the generated `customers` and `orders` data to your BigQuery project (`retail_audit_db` dataset) into tables named `retail_audit_db.<scenario_name>_customers` and
      `retail_audit_db.<scenario_name>_orders`. This allows the agent to query this specific data during evaluation.
   12
   13 ## 2. Agent Evaluation Against Golden Sets
   14
   15 This script runs the Autonomous Auditor agent against each generated golden set scenario, compares its findings to the `golden_violations.json`, and reports on its performance.
   16
   17 ### Usage
   18
   19 1.  **Navigate to the `src_v2/eval` directory:**
      cd E:\Gen_AI_RAG\Autonomous_Auditor\src_v2\eval

   1
   2 2.  **Run the evaluation script:**
      python evaluate_agent.py

    1     *(Ensure your `GOOGLE_CLOUD_PROJECT` environment variable is set before running.)*
    2
    3 ### What it Does
    4
    5 *   Iterates through each scenario in your `src_v2/golden_sets` directory.
    6 *   For each scenario, it dynamically sets environment variables (`AUDIT_CUSTOMER_TABLE`, `AUDIT_ORDER_TABLE`) to point the agent's BigQuery tools to the specific tables generated for that scenario.
    7 *   It then initializes and runs the `auditor_agent` (using the ADK `Runner` locally, which interacts with Vertex AI services as configured in your environment) with a standard audit prompt.
    8 *   It captures the agent's final audit report.
    9 *   `evaluate_agent.py` then parses the agent's report (based on the `merger_agent`'s instruction format) to extract the violations it identified.
   10 *   It compares the count of identified violations against the `golden_violations.json` for each type of violation (PII Leak, PII Integrity Failure, RTBF, Retention, Orphaned).
   11 *   A summary is printed to the console indicating PASSED/FAILED for each scenario and an overall evaluation summary.
   12 *   An `agent_report.md` file containing the raw output of the agent will be saved in each scenario's directory (e.g., `src_v2/golden_sets/<scenario_name>/agent_report.md`) for detailed review.
   13
   14 ### Interpreting Results
   15
   16 *   **MATCH**: The agent found the same number of violations for a specific type as recorded in the golden set.
   17 *   **MISMATCH**: The agent's count of violations differs from the golden set. This indicates a potential issue with the agent's reasoning, tool usage, or the parsing of its report.
   18 *   **FAILED (Scenario)**: The agent either failed to produce a final report or had one or more mismatches with the golden set. The summary will indicate the reason or the specific violation types that
      mismatched.
   19
   20 ## 3. Enhanced Agent Observability
   21
   22 The `AuditExecutor` in `src_v2/runtime/agent_executor.py` has been modified to stream more detailed events during the agent's execution, allowing you to trace its thought process, tool calls, and tool
      results in real-time.
   23
   24 ### How to Observe
   25
   26 When the Autonomous Auditor agent is executed (e.g., via the A2A API endpoint `/` that `server.py` exposes, or directly using the `AuditExecutor` if you have a custom client):
   27
   28 *   The `TaskUpdater` will now push the following intermediate events to the `EventQueue`:
   29     *   **Agent thoughts**: Insights into the LLM's reasoning process.
   30     *   **Tool calls**: Details about which tool was invoked and with what arguments.
   31     *   **Tool results**: The raw output received from the executed tool (truncated to 500 characters for brevity in status messages).
   32     *   **Final Response**: The comprehensive audit report.
   33
   34 Any client application designed to consume these A2A events will now display a much richer, step-by-step log of the agent's activity. This is particularly useful for debugging and understanding
      decision-making bottlenecks.
   35
   36 ### Further Observability in GCP
   37
   38 When your agent is deployed and running on Vertex AI Agent Engine, you also benefit from built-in GCP observability features:
   39
   40 *   **Cloud Logging**: All agent executions, tool calls, and responses are automatically logged to Cloud Logging. You can find these logs by searching for resources related to Vertex AI Agent Engine or
      your agent's name.
   41 *   **Cloud Trace**: If enabled for your Agent Engine deployment, Cloud Trace provides detailed insights into the latency and execution flow of agent operations, helping identify performance bottlenecks.
   42 *   **Vertex AI Agent Analytics**: Provides dashboards and metrics for agent performance, costs, and usage patterns.
   43
   44 ### Next Steps and Recommendations
   45
   46 *   **Refine Report Parsing**: The `parse_agent_report` function in `evaluate_agent.py` currently performs a count-based comparison. For more robust evaluation, consider enhancing it to perform a deep
      comparison of individual violation details (e.g., matching `order_id`s, `customer_id`s, and `violation_type`s).
   47 *   **Expand Golden Sets**: Create more diverse golden set scenarios, including complex edge cases and conflicting rules, to thoroughly test the agent's reasoning. The current script provides a solid
      foundation to generate many more scenarios.
   48 *   **Integrate with ADK Evaluation Service**: For a production-grade evaluation pipeline, explore using Google's managed ADK Evaluation service. This can automate running evaluations, managing datasets,
      and providing advanced metrics like LLM-as-a-judge feedback and tool trajectory scoring.
   49 *   **Metric-Driven Improvement**: Use the evaluation results as a feedback loop to iterate on the agent's prompt instructions, tool definitions, or sub-agent logic to improve its accuracy, reliability,
      and compliance with regulations.
   50
   51 This concludes the implementation and documentation for Week 3's goals. Please let me know if you have any further questions or require additional modifications.


I cannot directly "save the session" in the way a traditional application might. My environment and state are managed by the Gemini CLI.

  However, all the changes I've made (like modifying src_v2/runtime/agent_executor.py and creating src_v2/data/generate_golden_sets.py and src_v2/eval/evaluate_agent.py) are persistent on your local filesystem
  within the E:\Gen_AI_RAG\Autonomous_Auditor\src_v2 directory.

  You can continue working from this directory in a new session, and all these files will remain as they are.

│  To resume this session: gemini --resume '245a7b4a-1b3e-498d-b44d-18573d3ff100'

gemini --resume "245a7b4a-1b3e-498d-b44d-18573d3ff100"