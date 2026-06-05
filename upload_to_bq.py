from google.cloud import bigquery
import json

client = bigquery.Client(project="agent-ops-494011")

# Load your local JSON
with open("customer_db.json") as f:
    customers = json.load(f)

with open("orders_db.json") as f:
    orders = json.load(f)

# Upload directly to BigQuery
job = client.load_table_from_json(
    json_rows=customers,
    destination="agent-ops-494011.retail_audit_db.customers"
)
job.result() # Waits for the job to complete


job = client.load_table_from_json(
    json_rows=orders,
    destination="agent-ops-494011.retail_audit_db.orders"
)
job.result() # Waits for the job to complete

print("Customers and orders loaded into BigQuery!")
