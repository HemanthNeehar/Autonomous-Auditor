#!/usr/bin/env python3
"""
ingest_compliance_docs.py — CLI Utility for RAG Knowledge Expansion

Downloads official GDPR (HTML) and CCPA Regulations (PDF) files and uploads
them to the agent's GCS bucket to trigger automatic Discovery Engine indexing.
"""

import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Path setup
SRC_DIR = Path(__file__).resolve().parent.parent
load_dotenv(SRC_DIR / ".env")

BUCKET_NAME = os.getenv("STAGING_BUCKET")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "your-google-cloud-project-id")

# Authoritative Compliance URLs
GDPR_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679"
CCPA_DROP = "https://cppa.ca.gov/regulations/pdf/drop_ftr.pdf"
CCPA_COI_FTA = "https://cppa.ca.gov/regulations/pdf/coi_fta.pdf"
CCPA_DROP_AUDITS = "https://cppa.ca.gov/regulations/pdf/drop_audits.pdf"
CCPA_NOTICES_DISCLOSURES = (
    "https://cppa.ca.gov/regulations/pdf/notices_disclosures_employee_data.pdf"
)
CCPA_PRE_COMMENTS_REDUCING_FRICTION = (
    "https://cppa.ca.gov/regulations/pdf/pre_comments_reducing_friction_oops.pdf"
)
CCPA_STATUTE_EFF_20260101 = "https://cppa.ca.gov/regulations/pdf/ccpa_statute_eff_20260101.pdf"
CCPA_20230329_FINAL_REGS_TEXT = "https://cppa.ca.gov/regulations/pdf/20230329_final_regs_text.pdf"
CCPA_2022032_02NR_APPROVAL = "https://cppa.ca.gov/regulations/pdf/2022032_02nr_approval.pdf"
CCPA_20241227_DBFEE_FINALTEXT = "https://cppa.ca.gov/regulations/pdf/20241227_dbfee_finaltext.pdf"
CCPA_UPDATES_CYBER_RISK_ADMT_APPR_TEXT = (
    "https://cppa.ca.gov/regulations/pdf/ccpa_updates_cyber_risk_admt_appr_text.pdf"
)
CCPA_DATA_BROKER_REG_FEE_FRT = "https://cppa.ca.gov/regulations/pdf/data_broker_reg_fee_frt.pdf"
CCPA_20241226_DBR_FINAL = "https://cppa.ca.gov/regulations/pdf/20241226_dbr_final.pdf"

TEMP_DIR = SRC_DIR / "data" / "compliance_downloads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest_path: Path):
    print(f"Downloading from {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    with httpx.Client(follow_redirects=True, headers=headers, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        dest_path.write_bytes(response.content)
    print(f"Saved local copy to: {dest_path}")


def upload_to_gcs(local_path: Path, bucket_name: str, destination_blob_name: str):
    try:
        from google.cloud import storage
    except ImportError:
        print("Error: 'google-cloud-storage' package is not installed. Install it with:")
        print("  pip install google-cloud-storage")
        sys.exit(1)

    print(f"Uploading {local_path.name} to gs://{bucket_name}/{destination_blob_name}...")
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(str(local_path))
    print(f"Successfully uploaded: gs://{bucket_name}/{destination_blob_name}")


def main():
    print("=== RAG Knowledge Expansion Ingestion ===")
    print(f"Target GCS Bucket: gs://{BUCKET_NAME}")
    print(f"Google Cloud Project: {PROJECT_ID}")
    print("------------------------------------------")

    gdpr_file = TEMP_DIR / "gdpr_regulation.html"
    ccpa_drop_file = TEMP_DIR / "ccpa_drop.pdf"
    ccpa_coi_fta_file = TEMP_DIR / "ccpa_coi_fta.pdf"
    ccpa_drop_audits_file = TEMP_DIR / "ccpa_drop_audits.pdf"
    ccpa_notices_disclosures_file = TEMP_DIR / "ccpa_notices_disclosures.pdf"
    ccpa_pre_comments_reducing_friction_file = TEMP_DIR / "ccpa_pre_comments_reducing_friction.pdf"
    ccpa_statute_eff_20260101_file = TEMP_DIR / "ccpa_statute_eff_20260101.pdf"
    ccpa_data_broker_reg_fee_frt_file = TEMP_DIR / "ccpa_data_broker_reg_fee_frt.pdf"
    ccpa_20230329_final_regs_text_file = TEMP_DIR / "ccpa_20230329_final_regs_text.pdf"
    ccpa_2022032_02NR_APPROVAL_file = TEMP_DIR / "ccpa_2022032_02NR_APPROVAL.pdf"
    ccpa_20241227_DBFEE_FINALTEXT_file = TEMP_DIR / "ccpa_20241227_dbfee_finaltext.pdf"
    ccpa_updates_cyber_risk_admt_appr_text_file = (
        TEMP_DIR / "ccpa_updates_cyber_risk_admt_appr_text.pdf"
    )
    ccpa_20241226_DBR_FINAL_file = TEMP_DIR / "ccpa_20241226_dbr_final.pdf"

    # Step 1: Download Documents
    try:
        download_file(GDPR_URL, gdpr_file)
        download_file(CCPA_DROP, ccpa_drop_file)
        download_file(CCPA_COI_FTA, ccpa_coi_fta_file)
        download_file(CCPA_DROP_AUDITS, ccpa_drop_audits_file)
        download_file(CCPA_NOTICES_DISCLOSURES, ccpa_notices_disclosures_file)
        download_file(CCPA_PRE_COMMENTS_REDUCING_FRICTION, ccpa_pre_comments_reducing_friction_file)
        download_file(CCPA_STATUTE_EFF_20260101, ccpa_statute_eff_20260101_file)
        download_file(CCPA_DATA_BROKER_REG_FEE_FRT, ccpa_data_broker_reg_fee_frt_file)
        download_file(CCPA_20230329_FINAL_REGS_TEXT, ccpa_20230329_final_regs_text_file)
        download_file(CCPA_2022032_02NR_APPROVAL, ccpa_2022032_02NR_APPROVAL_file)
        download_file(CCPA_20241227_DBFEE_FINALTEXT, ccpa_20241227_DBFEE_FINALTEXT_file)
        download_file(
            CCPA_UPDATES_CYBER_RISK_ADMT_APPR_TEXT, ccpa_updates_cyber_risk_admt_appr_text_file
        )
        download_file(CCPA_DATA_BROKER_REG_FEE_FRT, ccpa_data_broker_reg_fee_frt_file)
        download_file(CCPA_20241226_DBR_FINAL, ccpa_20241226_DBR_FINAL_file)
    except Exception as e:
        print(f"Error downloading compliance documents: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 2: Upload to GCS Bucket
    try:
        upload_to_gcs(gdpr_file, BUCKET_NAME, "compliance_docs/gdpr_regulation.html")
        upload_to_gcs(ccpa_drop_file, BUCKET_NAME, "compliance_docs/ccpa_drop.pdf")
        upload_to_gcs(ccpa_coi_fta_file, BUCKET_NAME, "compliance_docs/ccpa_coi_fta.pdf")
        upload_to_gcs(ccpa_drop_audits_file, BUCKET_NAME, "compliance_docs/ccpa_drop_audits.pdf")
        upload_to_gcs(
            ccpa_notices_disclosures_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_notices_disclosures.pdf",
        )
        upload_to_gcs(
            ccpa_pre_comments_reducing_friction_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_pre_comments_reducing_friction.pdf",
        )
        upload_to_gcs(
            ccpa_statute_eff_20260101_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_statute_eff_20260101.pdf",
        )
        upload_to_gcs(
            ccpa_data_broker_reg_fee_frt_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_data_broker_reg_fee_frt.pdf",
        )
        upload_to_gcs(
            ccpa_20230329_final_regs_text_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_20230329_final_regs_text.pdf",
        )
        upload_to_gcs(
            ccpa_2022032_02NR_APPROVAL_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_2022032_02NR_APPROVAL.pdf",
        )
        upload_to_gcs(
            ccpa_20241227_DBFEE_FINALTEXT_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_20241227_dbfee_finaltext.pdf",
        )
        upload_to_gcs(
            ccpa_updates_cyber_risk_admt_appr_text_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_updates_cyber_risk_admt_appr_text.pdf",
        )
        upload_to_gcs(
            ccpa_data_broker_reg_fee_frt_file,
            BUCKET_NAME,
            "compliance_docs/ccpa_data_broker_reg_fee_frt.pdf",
        )
        upload_to_gcs(
            ccpa_20241226_DBR_FINAL_file, BUCKET_NAME, "compliance_docs/ccpa_20241226_dbr_final.pdf"
        )
    except Exception as e:
        print(f"Error uploading to GCS: {e}", file=sys.stderr)
        print("\nNote: Make sure your GCP credentials are configured and that the bucket exists.")
        sys.exit(1)

    print("\nKnowledge Expansion complete!")
    print("==========================================")
    print("Discovery Engine (Vertex AI Search) will automatically index the new files.")
    print(
        "The Senior Policy Analyst agent will immediately have access to this expanded knowledge."
    )


if __name__ == "__main__":
    main()
