Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

Install the latest PowerShell for new features and improvements! https://aka.ms/PSWindows

PS C:\WINDOWS\system32> cd E:\Gen_AI_RAG\Autonomous_Auditor\src_v2
PS E:\Gen_AI_RAG\Autonomous_Auditor\src_v2> .\agent_env\Scripts\activate
(agent_env) PS E:\Gen_AI_RAG\Autonomous_Auditor\src_v2> python .\eval\evaluate_agent.py
Starting agent evaluation...
--- Evaluating scenario: clean_data ---
Set AUDIT_CUSTOMER_TABLE=clean_data_customers, AUDIT_ORDER_TABLE=clean_data_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII anonymization orders_db masking'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Right to be Forgotten customer_id orders_db'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data retention 10 years anonymized customer_id'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'customer_id validation orders_db customer_db orphaned records'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data handling principles data minimization security breach 72 hours consent third party data sharing archives operational'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=0  , Agent=0  , Status=MATCH
    pii_integrity_failures   : Golden=0  , Agent=0  , Status=MATCH
    rtbf_violations          : Golden=0  , Agent=0  , Status=MATCH
    retention_failures       : Golden=0  , Agent=0  , Status=MATCH
    orphaned_records         : Golden=0  , Agent=0  , Status=MATCH
--- Evaluating scenario: extreme_edge_all_forgotten ---
Set AUDIT_CUSTOMER_TABLE=extreme_edge_all_forgotten_customers, AUDIT_ORDER_TABLE=extreme_edge_all_forgotten_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII handling, data masking, anonymization, integrity failure, [MASKED], NULL, N/A'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Right to be Forgotten (RTBF), forgotten customer status'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data retention, anonymization timelines, 3650 days, 10 years, ANONYMIZED'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data governance, data integrity, orphaned records'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=0  , Agent=0  , Status=MATCH
    pii_integrity_failures   : Golden=0  , Agent=0  , Status=MATCH
    rtbf_violations          : Golden=81 , Agent=81 , Status=MATCH
    retention_failures       : Golden=0  , Agent=0  , Status=MATCH
    orphaned_records         : Golden=0  , Agent=0  , Status=MATCH
--- Evaluating scenario: extreme_edge_all_old_not_anonymized ---
Set AUDIT_CUSTOMER_TABLE=extreme_edge_all_old_not_anonymized_customers, AUDIT_ORDER_TABLE=extreme_edge_all_old_not_anonymized_orders
  --- Violation Comparison ---
    pii_leaks                : Golden=0  , Agent=0  , Status=MATCH
    pii_integrity_failures   : Golden=0  , Agent=0  , Status=MATCH
    rtbf_violations          : Golden=0  , Agent=0  , Status=MATCH
    retention_failures       : Golden=19 , Agent=19 , Status=MATCH
    orphaned_records         : Golden=0  , Agent=0  , Status=MATCH
--- Evaluating scenario: extreme_edge_many_orphans ---
Set AUDIT_CUSTOMER_TABLE=extreme_edge_many_orphans_customers, AUDIT_ORDER_TABLE=extreme_edge_many_orphans_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII handling anonymization masking integrity'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Right to be Forgotten RTBF data deletion'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data retention archiving anonymization timelines'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data integrity governance orphaned records referential integrity'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
Failed to create cache: 400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'The cached content is of 955 tokens. The minimum token count to start caching is 1024.', 'status': 'INVALID_ARGUMENT'}}

[RAG TOOL] Calling query_compliance_manual with query: 'data breach notification data security measures'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
Failed to create cache: 400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'The cached content is of 955 tokens. The minimum token count to start caching is 1024.', 'status': 'INVALID_ARGUMENT'}}
  --- Violation Comparison ---
    pii_leaks                : Golden=0  , Agent=0  , Status=MATCH
    pii_integrity_failures   : Golden=0  , Agent=0  , Status=MATCH
    rtbf_violations          : Golden=0  , Agent=0  , Status=MATCH
    retention_failures       : Golden=0  , Agent=0  , Status=MATCH
    orphaned_records         : Golden=41 , Agent=41 , Status=MATCH
--- Evaluating scenario: mixed_violations_high ---
Set AUDIT_CUSTOMER_TABLE=mixed_violations_high_customers, AUDIT_ORDER_TABLE=mixed_violations_high_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII handling anonymization masking data best practices'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Right to be Forgotten RTBF procedures customer_id deletion'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data retention timelines anonymization old data policy'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data integrity orphaned records data governance policies'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=236, Agent=236, Status=MATCH
    pii_integrity_failures   : Golden=117, Agent=117, Status=MATCH
    rtbf_violations          : Golden=208, Agent=208, Status=MATCH
    retention_failures       : Golden=89 , Agent=89 , Status=MATCH
    orphaned_records         : Golden=102, Agent=102, Status=MATCH
--- Evaluating scenario: mixed_violations_low ---
Set AUDIT_CUSTOMER_TABLE=mixed_violations_low_customers, AUDIT_ORDER_TABLE=mixed_violations_low_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII Anonymization and Integrity, masked data, PII integrity failure'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Right to be Forgotten (RTBF) compliance for customer data'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data retention policy, 3650 days, 10 years, anonymized customer_id'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'customer_id validity, data governance'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'orphaned records, data governance'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=61 , Agent=61 , Status=MATCH
    pii_integrity_failures   : Golden=38 , Agent=38 , Status=MATCH
    rtbf_violations          : Golden=24 , Agent=24 , Status=MATCH
    retention_failures       : Golden=34 , Agent=34 , Status=MATCH
    orphaned_records         : Golden=38 , Agent=38 , Status=MATCH
--- Evaluating scenario: orphaned_only ---
Set AUDIT_CUSTOMER_TABLE=orphaned_only_customers, AUDIT_ORDER_TABLE=orphaned_only_orders

[RAG TOOL] Calling query_compliance_manual with query: 'data anonymization techniques and policies'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=0  , Agent=0  , Status=MATCH
    pii_integrity_failures   : Golden=0  , Agent=0  , Status=MATCH
    rtbf_violations          : Golden=0  , Agent=0  , Status=MATCH
    retention_failures       : Golden=0  , Agent=0  , Status=MATCH
    orphaned_records         : Golden=51 , Agent=51 , Status=MATCH
--- Evaluating scenario: pii_integrity_only ---
Set AUDIT_CUSTOMER_TABLE=pii_integrity_only_customers, AUDIT_ORDER_TABLE=pii_integrity_only_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII masking orders_db anonymization retail database'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Right to be Forgotten retail database customer_id'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Data retention policy retail orders 10 years anonymization old records'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Data integrity customer_id orders_db customer_db orphaned records policy'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'compliance audit reporting guidelines remediation procedures policy'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=0  , Agent=0  , Status=MATCH
    pii_integrity_failures   : Golden=46 , Agent=46 , Status=MATCH
    rtbf_violations          : Golden=0  , Agent=0  , Status=MATCH
    retention_failures       : Golden=0  , Agent=0  , Status=MATCH
    orphaned_records         : Golden=0  , Agent=0  , Status=MATCH
--- Evaluating scenario: pii_leak_only ---
Set AUDIT_CUSTOMER_TABLE=pii_leak_only_customers, AUDIT_ORDER_TABLE=pii_leak_only_orders

[RAG TOOL] Calling query_compliance_manual with query: 'data anonymization techniques and policies'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data sharing policies third-party'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'data breach notification 72 hours'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=82 , Agent=82 , Status=MATCH
    pii_integrity_failures   : Golden=0  , Agent=0  , Status=MATCH
    rtbf_violations          : Golden=0  , Agent=0  , Status=MATCH
    retention_failures       : Golden=0  , Agent=0  , Status=MATCH
    orphaned_records         : Golden=0  , Agent=0  , Status=MATCH
--- Evaluating scenario: rag_anonymization_and_rtbf ---
Set AUDIT_CUSTOMER_TABLE=clean_data_customers, AUDIT_ORDER_TABLE=clean_data_orders

[RAG TOOL] Calling query_compliance_manual with query: 'data anonymization standards for archives versus operational systems'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    rag_expected_keywords    : Golden=5  , Agent=5  , Status=MATCH
--- Evaluating scenario: rag_data_breach_and_sharing ---
Set AUDIT_CUSTOMER_TABLE=clean_data_customers, AUDIT_ORDER_TABLE=clean_data_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII data breach notification requirements and timelines'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'rules for third-party data sharing'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    rag_expected_keywords    : Golden=5  , Agent=5  , Status=MATCH
--- Evaluating scenario: retention_only ---
Set AUDIT_CUSTOMER_TABLE=retention_only_customers, AUDIT_ORDER_TABLE=retention_only_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII handling, anonymization, and masking policies'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Right to be Forgotten procedures and rules'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Data Retention policies, timelines, and anonymization requirements'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Data Governance and Integrity requirements'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Data Breach Procedures and Reporting'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=0  , Agent=0  , Status=MATCH
    pii_integrity_failures   : Golden=0  , Agent=0  , Status=MATCH
    rtbf_violations          : Golden=0  , Agent=0  , Status=MATCH
    retention_failures       : Golden=32 , Agent=32 , Status=MATCH
    orphaned_records         : Golden=0  , Agent=0  , Status=MATCH
--- Evaluating scenario: rtbf_only ---
Set AUDIT_CUSTOMER_TABLE=rtbf_only_customers, AUDIT_ORDER_TABLE=rtbf_only_orders

[RAG TOOL] Calling query_compliance_manual with query: 'PII handling and anonymization in retail data'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Right to be Forgotten procedures and requirements'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Data retention policies and timelines'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Data governance and integrity standards'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.

[RAG TOOL] Calling query_compliance_manual with query: 'Data sharing with third parties'
[RAG TOOL] Purely local search enabled, skipping cloud Discovery Engine.
  --- Violation Comparison ---
    pii_leaks                : Golden=0  , Agent=0  , Status=MATCH
    pii_integrity_failures   : Golden=0  , Agent=0  , Status=MATCH
    rtbf_violations          : Golden=13 , Agent=13 , Status=MATCH
    retention_failures       : Golden=0  , Agent=0  , Status=MATCH
    orphaned_records         : Golden=0  , Agent=0  , Status=MATCH
--- Evaluation Summary ---
Total Scenarios: 13
Passed: 13
Failed: 0

Scenario: clean_data, Overall Status: PASSED
Scenario: extreme_edge_all_forgotten, Overall Status: PASSED
Scenario: extreme_edge_all_old_not_anonymized, Overall Status: PASSED
Scenario: extreme_edge_many_orphans, Overall Status: PASSED
Scenario: mixed_violations_high, Overall Status: PASSED
Scenario: mixed_violations_low, Overall Status: PASSED
Scenario: orphaned_only, Overall Status: PASSED
Scenario: pii_integrity_only, Overall Status: PASSED
Scenario: pii_leak_only, Overall Status: PASSED
Scenario: rag_anonymization_and_rtbf, Overall Status: PASSED
Scenario: rag_data_breach_and_sharing, Overall Status: PASSED
Scenario: retention_only, Overall Status: PASSED
Scenario: rtbf_only, Overall Status: PASSED
(agent_env) PS E:\Gen_AI_RAG\Autonomous_Auditor\src_v2>
(agent_env) PS E:\Gen_AI_RAG\Autonomous_Auditor\src_v2>