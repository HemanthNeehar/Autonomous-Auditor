import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from google.cloud import bigquery
import uuid
from dotenv import load_dotenv

# --- Path Setup ---
SRC_DIR = Path(__file__).resolve().parent.parent
load_dotenv(SRC_DIR / ".env")

GOLDEN_SETS_DIR = SRC_DIR / "golden_sets"
GOLDEN_SETS_DIR.mkdir(exist_ok=True)

# Configuration for data generation
NUM_CUSTOMERS = 100
NUM_ORDERS_PER_CUSTOMER = 5
PII_LEAK_PROBABILITY = 0.1
RTBF_PROBABILITY = 0.05
RETENTION_VIOLATION_PROBABILITY = 0.1
ORPHANED_RECORD_PROBABILITY = 0.05
MAX_ORDER_AGE_DAYS = 3650  # 10 years for retention rule
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "google-cloud-project-id")
DATASET_ID = "retail_audit_db"


def generate_customer_data(num_customers: int) -> list[dict]:
    customers = []
    for i in range(num_customers):
        customers.append(
            {
                "customer_id": f"cust_{i + 1:04d}",
                "name": f"Customer {i + 1}",
                "email": f"customer{i + 1}@example.com",
                "status": "active",
            }
        )
    return customers


def generate_order_data(customers: list[dict], num_orders_per_customer: int) -> list[dict]:
    orders = []
    order_id_counter = 1
    for customer in customers:
        for _ in range(num_orders_per_customer):
            order_date = (
                datetime.now() - timedelta(days=random.randint(1, MAX_ORDER_AGE_DAYS + 1000))
            ).strftime("%Y-%m-%d")  # Max age + 1000 to ensure some old orders
            orders.append(
                {
                    "order_id": f"ord_{order_id_counter:05d}",
                    "customer_id": customer["customer_id"],
                    "order_date": order_date,
                    "customer_email": "[MASKED]",
                    "customer_phone": "[MASKED]",
                    "product": f"Product {random.randint(1, 10)}",
                    "amount": round(random.uniform(10.0, 500.0), 2),
                }
            )
            order_id_counter += 1
    return orders


def introduce_pii_leak(
    orders: list[dict], customer_data: list[dict], probability: float
) -> list[dict]:
    pii_violations = []
    for order in orders:
        if random.random() < probability:
            customer = next(
                (c for c in customer_data if c["customer_id"] == order["customer_id"]), None
            )
            if customer:
                field_to_leak = random.choice(["customer_email", "customer_phone"])
                if field_to_leak == "customer_email":
                    order["customer_email"] = customer["email"]
                else:  # customer_phone
                    order["customer_phone"] = (
                        f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
                    )
                pii_violations.append(
                    {
                        "order_id": order["order_id"],
                        "field": field_to_leak,
                        "value": order[field_to_leak],
                        "violation_type": "PII Leak (Unmasked)",
                    }
                )
    return pii_violations


def introduce_pii_integrity_failure(
    orders: list[dict], probability: float, leaked_order_ids: set[str] = None
) -> list[dict]:
    integrity_violations = []
    invalid_states = ["NULL", "N/A", "ERROR"]
    if leaked_order_ids is None:
        leaked_order_ids = set()
    for order in orders:
        if order["order_id"] in leaked_order_ids:
            continue
        if random.random() < probability:
            field_to_fail = random.choice(["customer_email", "customer_phone"])
            order[field_to_fail] = random.choice(invalid_states)
            integrity_violations.append(
                {
                    "order_id": order["order_id"],
                    "field": field_to_fail,
                    "value": order[field_to_fail],
                    "violation_type": "PII Integrity Failure",
                }
            )
    return integrity_violations


def introduce_rtbf_violation(
    customers: list[dict], orders: list[dict], probability: float
) -> list[dict]:
    rtbf_violations = []
    forgotten_customer_ids = set()
    for customer in customers:
        if random.random() < probability:
            customer["status"] = "forgotten"
            forgotten_customer_ids.add(customer["customer_id"])

    for customer_id in forgotten_customer_ids:
        for order in orders:
            if order["customer_id"] == customer_id:
                rtbf_violations.append(
                    {
                        "customer_id": customer_id,
                        "order_id": order["order_id"],
                        "violation_type": "RTBF Violation",
                    }
                )
    return rtbf_violations


def introduce_retention_violation(orders: list[dict], probability: float) -> list[dict]:
    retention_violations = []
    today_midnight = datetime.combine(datetime.now().date(), datetime.min.time())
    cutoff = today_midnight - timedelta(days=MAX_ORDER_AGE_DAYS)
    for order in orders:
        order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
        if order_date < cutoff and random.random() < probability:
            # Ensure it's not anonymized by not changing customer_id if it's already ANONYMIZED
            if order["customer_id"] != "ANONYMIZED":
                retention_violations.append(
                    {
                        "order_id": order["order_id"],
                        "customer_id": order["customer_id"],
                        "order_date": order["order_date"],
                        "violation_type": "Data Retention Failure",
                    }
                )
    return retention_violations


def introduce_orphaned_record(
    orders: list[dict], customers: list[dict], probability: float, rtbf_order_ids: set[str] = None
) -> list[dict]:
    orphaned_violations = []
    # Create a temporary set of valid customer IDs based on the current customer list
    valid_customer_ids = {c["customer_id"] for c in customers}
    if rtbf_order_ids is None:
        rtbf_order_ids = set()

    for order in orders:
        if order["order_id"] in rtbf_order_ids:
            continue
        if random.random() < probability and order["customer_id"] in valid_customer_ids:
            original_customer_id = order["customer_id"]
            # Create a truly non-existent ID
            new_orphan_id = f"non_existent_{uuid.uuid4().hex[:8]}"
            order["customer_id"] = new_orphan_id
            orphaned_violations.append(
                {
                    "order_id": order["order_id"],
                    "customer_id": new_orphan_id,
                    "original_customer_id": original_customer_id,
                    "violation_type": "Orphaned Record",
                }
            )
    return orphaned_violations


def anonymize_old_orders(orders: list[dict], retention_violations: list[dict]):
    """Anonymizes orders older than MAX_ORDER_AGE_DAYS by setting customer_id to ANONYMIZED, except those in retention_violations."""
    retention_violation_ids = {v["order_id"] for v in retention_violations}
    today_midnight = datetime.combine(datetime.now().date(), datetime.min.time())
    cutoff = today_midnight - timedelta(days=MAX_ORDER_AGE_DAYS)
    for order in orders:
        order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
        if order_date < cutoff:
            if order["order_id"] not in retention_violation_ids:
                order["customer_id"] = "ANONYMIZED"


def upload_to_bigquery(
    json_data: list[dict], table_id: str, project_id: str = PROJECT_ID, dataset_id: str = DATASET_ID
):
    client = bigquery.Client(project=project_id)
    table_ref = client.dataset(dataset_id).table(table_id)

    # Delete existing table if it exists
    try:
        client.delete_table(table_ref)
        print(f"Deleted existing table {table_id}.")
    except Exception as e:
        print(f"Table {table_id} did not exist or could not be deleted: {e}")

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,  # Auto-detect schema
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Overwrite table if it exists
    )

    # BigQuery expects Newline Delimited JSON
    ndjson_data = "".join(json.dumps(row) for row in json_data)

    job = client.load_table_from_json(
        json_rows=json_data, destination=table_ref, job_config=job_config
    )
    job.result()
    print(f"Uploaded {len(json_data)} rows to BigQuery table {dataset_id}.{table_id}")


def generate_golden_set(scenario_name: str, config: dict):
    print(f"--- Generating scenario: {scenario_name} ---")
    scenario_path = GOLDEN_SETS_DIR / scenario_name
    scenario_path.mkdir(exist_ok=True)

    # Generate base data
    customers = generate_customer_data(config.get("num_customers", NUM_CUSTOMERS))
    orders = generate_order_data(
        customers, config.get("num_orders_per_customer", NUM_ORDERS_PER_CUSTOMER)
    )

    golden_violations = {
        "pii_leaks": [],
        "pii_integrity_failures": [],
        "rtbf_violations": [],
        "retention_failures": [],
        "orphaned_records": [],
    }

    # 1. Retention violations - identifies old orders that should be anonymized but are not
    retention_violations_found = introduce_retention_violation(
        orders, config.get("retention_violation_probability", 0)
    )
    golden_violations["retention_failures"].extend(retention_violations_found)

    # 2. Anonymize orders that *should* be anonymized by rule 3.1 (except retention violations)
    anonymize_old_orders(orders, retention_violations_found)

    # Introduce violations based on config
    pii_leaks = introduce_pii_leak(orders, customers, config.get("pii_leak_probability", 0))
    golden_violations["pii_leaks"].extend(pii_leaks)
    leaked_order_ids = {v["order_id"] for v in pii_leaks}

    pii_integrity_failures = introduce_pii_integrity_failure(
        orders, config.get("pii_integrity_failure_probability", 0), leaked_order_ids
    )
    golden_violations["pii_integrity_failures"].extend(pii_integrity_failures)

    # RTBF violations - modifies customer status and identifies orders that should be removed
    rtbf_violations_found = introduce_rtbf_violation(
        customers, orders, config.get("rtbf_probability", 0)
    )
    golden_violations["rtbf_violations"].extend(rtbf_violations_found)
    rtbf_order_ids = {v["order_id"] for v in rtbf_violations_found}

    # Orphaned records - introduces non-existent customer IDs in orders
    orphaned_records_found = introduce_orphaned_record(
        orders, customers, config.get("orphaned_record_probability", 0), rtbf_order_ids
    )
    golden_violations["orphaned_records"].extend(orphaned_records_found)

    # Save data locally
    with open(scenario_path / "customer_db.json", "w") as f:
        json.dump(customers, f, indent=2)
    with open(scenario_path / "orders_db.json", "w") as f:
        json.dump(orders, f, indent=2)

    # Save golden violations
    with open(scenario_path / "golden_violations.json", "w") as f:
        json.dump(golden_violations, f, indent=2)

    print(f"Saved synthetic data and golden violations for {scenario_name} to {scenario_path}")

    # Upload to BigQuery (dynamic table names for each scenario)
    bq_customer_table_id = f"{scenario_name.replace('-', '_')}_customers"
    bq_order_table_id = f"{scenario_name.replace('-', '_')}_orders"

    # Ensure the BigQuery dataset exists
    client = bigquery.Client(project=PROJECT_ID)
    try:
        client.get_dataset(DATASET_ID)
    except Exception:
        client.create_dataset(DATASET_ID)
        print(f"Created BigQuery dataset: {DATASET_ID}")

    upload_to_bigquery(customers, bq_customer_table_id)
    upload_to_bigquery(orders, bq_order_table_id)
    print(
        f"Uploaded data for {scenario_name} to BigQuery tables: {bq_customer_table_id}, {bq_order_table_id}"
    )


# Define golden set scenarios (20-50 cases in total, this is a good start)
golden_set_scenarios = {
    "clean_data": {
        "num_customers": 50,
        "num_orders_per_customer": 10,
        "pii_leak_probability": 0,
        "pii_integrity_failure_probability": 0,
        "rtbf_probability": 0,
        "retention_violation_probability": 0,
        "orphaned_record_probability": 0,
    },
    "pii_leak_only": {
        "num_customers": 50,
        "num_orders_per_customer": 10,
        "pii_leak_probability": 0.2,
        "pii_integrity_failure_probability": 0,
        "rtbf_probability": 0,
        "retention_violation_probability": 0,
        "orphaned_record_probability": 0,
    },
    "pii_integrity_only": {
        "num_customers": 50,
        "num_orders_per_customer": 10,
        "pii_leak_probability": 0,
        "pii_integrity_failure_probability": 0.1,
        "rtbf_probability": 0,
        "retention_violation_probability": 0,
        "orphaned_record_probability": 0,
    },
    "rtbf_only": {
        "num_customers": 50,
        "num_orders_per_customer": 10,
        "pii_leak_probability": 0,
        "pii_integrity_failure_probability": 0,
        "rtbf_probability": 0.1,  # 10% of customers forgotten
        "retention_violation_probability": 0,
        "orphaned_record_probability": 0,
    },
    "retention_only": {
        "num_customers": 50,
        "num_orders_per_customer": 10,
        "pii_leak_probability": 0,
        "pii_integrity_failure_probability": 0,
        "rtbf_probability": 0,
        "retention_violation_probability": 0.3,  # Higher probability for old orders violating retention
        "orphaned_record_probability": 0,
    },
    "orphaned_only": {
        "num_customers": 50,
        "num_orders_per_customer": 10,
        "pii_leak_probability": 0,
        "pii_integrity_failure_probability": 0,
        "rtbf_probability": 0,
        "retention_violation_probability": 0,
        "orphaned_record_probability": 0.1,
    },
    "mixed_violations_low": {
        "num_customers": 100,
        "num_orders_per_customer": 15,
        "pii_leak_probability": 0.05,
        "pii_integrity_failure_probability": 0.02,
        "rtbf_probability": 0.03,
        "retention_violation_probability": 0.1,
        "orphaned_record_probability": 0.03,
    },
    "mixed_violations_high": {
        "num_customers": 100,
        "num_orders_per_customer": 20,
        "pii_leak_probability": 0.15,
        "pii_integrity_failure_probability": 0.07,
        "rtbf_probability": 0.07,
        "retention_violation_probability": 0.2,
        "orphaned_record_probability": 0.07,
    },
    "extreme_edge_all_forgotten": {
        "num_customers": 20,
        "num_orders_per_customer": 5,
        "pii_leak_probability": 0.0,
        "pii_integrity_failure_probability": 0.0,
        "rtbf_probability": 1.0,  # All customers forgotten
        "retention_violation_probability": 0.0,
        "orphaned_record_probability": 0.0,
    },
    "extreme_edge_all_old_not_anonymized": {
        "num_customers": 20,
        "num_orders_per_customer": 5,
        "pii_leak_probability": 0.0,
        "pii_integrity_failure_probability": 0.0,
        "rtbf_probability": 0.0,
        "retention_violation_probability": 1.0,  # All old orders are retention violations
        "orphaned_record_probability": 0.0,
    },
    "extreme_edge_many_orphans": {
        "num_customers": 20,
        "num_orders_per_customer": 5,
        "pii_leak_probability": 0.0,
        "pii_integrity_failure_probability": 0.0,
        "rtbf_probability": 0.0,
        "retention_violation_probability": 0.0,
        "orphaned_record_probability": 0.5,  # Half of orders are orphaned
    },
}

if __name__ == "__main__":
    # Ensure GOOGLE_CLOUD_PROJECT is set before running
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        print(
            "ERROR: GOOGLE_CLOUD_PROJECT environment variable is not set. Please set it to your GCP Project ID."
        )
        exit(1)

    for name, config in golden_set_scenarios.items():
        generate_golden_set(name, config)

    print("--- Golden set generation complete ---")
