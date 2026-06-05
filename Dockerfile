# Pull the official Google MCP Toolbox image
FROM us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest

# Set the target BigQuery project directly via Environment Variable
ENV BIGQUERY_PROJECT=google-cloud-project-id

# Use the pre-built BigQuery tools and explicitly bind to port 8080 for Cloud Run
CMD ["--prebuilt", "bigquery", "--address", "0.0.0.0", "--port", "8080"]