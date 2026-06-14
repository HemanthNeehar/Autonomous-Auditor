import re
import os
from typing import Any, Union, Dict, List

# Local Regex Patterns for sensitive data
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
PHONE_PATTERN = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?:\s*(?:ext|x|ext\.)\s*\d+)?\b', re.IGNORECASE)

def redact_text_regex(text: str) -> str:
    """Fallback local regex redaction for email and phone numbers."""
    if not isinstance(text, str):
        return text
    # Mask emails
    text = EMAIL_PATTERN.sub("[EMAIL_ADDRESS]", text)
    # Mask phones
    text = PHONE_PATTERN.sub("[PHONE_NUMBER]", text)
    return text

def redact_text_dlp(text: str, project_id: str) -> str:
    """Uses GCP Cloud Data Loss Prevention (DLP) API to identify and redact PII."""
    try:
        from google.cloud import dlp_v2
        
        dlp_client = dlp_v2.DlpServiceClient()
        parent = f"projects/{project_id}"
        
        # Define info types we want to identify
        info_types = [
            {"name": "EMAIL_ADDRESS"},
            {"name": "PHONE_NUMBER"},
            {"name": "PERSON_NAME"},
        ]
        
        inspect_config = {"info_types": info_types}
        
        # We will replace found info types with their type label (e.g. [PERSON_NAME])
        deidentify_config = {
            "info_type_transformations": {
                "transformations": [
                    {
                        "info_types": [],  # Apply to all configured info types
                        "primitive_transformation": {
                            "replace_with_info_type_value": {}
                        }
                    }
                ]
            }
        }
        
        response = dlp_client.deidentify_content(
            request={
                "parent": parent,
                "deidentify_config": deidentify_config,
                "inspect_config": inspect_config,
                "item": {"value": text},
            }
        )
        return response.item.value
    except Exception as e:
        # Fallback gracefully
        print(f"[REDACTION] Cloud DLP failed: {e}. Falling back to Regex redaction.", flush=True)
        return redact_text_regex(text)

def redact_text(text: str) -> str:
    """Main text redaction router."""
    if not isinstance(text, str):
        return text
        
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    enable_dlp = os.getenv("ENABLE_CLOUD_DLP", "false").lower() == "true"
    
    if enable_dlp and project_id:
        return redact_text_dlp(text, project_id)
    return redact_text_regex(text)

def redact_value(key: str, value: Any) -> Any:
    """Mask specific database fields directly or runs string redaction."""
    if not isinstance(value, str):
        return value
        
    # Check if value is already a standard mask placeholder
    if value in ("[MASKED]", "ANONYMIZED", "ANONYMISED"):
        return value
        
    key_lower = key.lower()
    # Mask specific known PII keys directly to save api costs and be robust
    if "email" in key_lower:
        return "[EMAIL_ADDRESS]"
    if "phone" in key_lower:
        return "[PHONE_NUMBER]"
    if "name" in key_lower:
        return "[PERSON_NAME]"
        
    # Otherwise run general string PII checks on the value
    return redact_text(value)

def redact_records(records: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Traverses records and redacts any customer PII details in values."""
    if isinstance(records, list):
        return [redact_records(r) for r in records]
    elif isinstance(records, dict):
        redacted = {}
        for k, v in records.items():
            if k in ("customer_id", "order_id", "order_date", "product", "amount", "status", "original_customer_id", "violation_type", "field"):
                # Preserve structural tracking metadata intact
                redacted[k] = v
            else:
                redacted[k] = redact_value(k, v)
        return redacted
    return records
