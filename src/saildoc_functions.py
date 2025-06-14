import time
import base64
import zlib
import logging
import re
from typing import Optional, Any
from datetime import datetime
from pathlib import Path

import sys
sys.path.append(".")
from src import configs
from src import email_functions as email_func

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 60
SLEEP_SECONDS = 10

def encode_saildocs_grib_file(file_path: str) -> str:
    """Compress and base64-encode a GRIB file for SailDocs."""
    try:
        path = Path(file_path)
        with path.open('rb') as file:
            grib_binary = file.read()
        compressed_grib = zlib.compress(grib_binary)
        encoded_data = base64.b64encode(compressed_grib).decode('utf-8')
        return encoded_data
    except Exception as e:
        logger.error(f"Failed to encode file {file_path}: {e}")
        raise

def is_valid_grib_request(msg: str) -> bool:
    """Validate GRIB request format for SailDocs."""
    pattern = (
        r'^[a-zA-Z0-9_]+:'
        r'(\d{1,2}[ns]),(\d{1,2}[ns]),'
        r'(\d{1,3}[ew]),(\d{1,3}[ew])\|'
        r'(\d{1,2}),(\d{1,2})\|'
        r'(\d{1,3}),(\d{1,3})\|'
        r'([a-zA-Z0-9_,]+)$'
    )
    return re.match(pattern, msg.strip(), re.IGNORECASE) is not None

def handle_grib_request(msg: str) -> None:
    """
    Handle GRIB requests, only passing valid requests to SailDocs.
    This is the ONLY function that should ever send to SailDocs.
    """
    if not is_valid_grib_request(msg):
        logger.info(f"Ignored: invalid GRIB request format: {msg}")
        return
    _send_to_saildocs(msg)

def _send_to_saildocs(msg: str) -> None:
    """Send a GRIB request to SailDocs (implementation placeholder)."""
    logger.info(f"Sending to SailDocs: {msg}")

def wait_for_saildocs_response(auth_service: Any, time_sent: datetime) -> Optional[dict]:
    """
    Wait for a Saildocs response email after a GRIB request.
    Returns the response dict if received, else None.
    """
    for attempt in range(MAX_ATTEMPTS):
        time.sleep(SLEEP_SECONDS)
        try:
            responses = email_func._search_gmail_messages(auth_service, configs.SAILDOCS_RESPONSE_EMAIL)
            if not responses:
                continue
            last_response = responses[0]
            msg = auth_service.users().messages().get(userId='me', id=last_response['id']).execute()
            headers = msg.get('payload', {}).get('headers', [])
            date_header = next((h for h in headers if h['name'].lower() == 'date'), None)
            if not date_header:
                continue
            from email.utils import parsedate_to_datetime
            time_received = parsedate_to_datetime(date_header['value'])
            if time_received > time_sent:
                return last_response
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}: Could not check SailDocs response: {e}")
    logger.error("Timed out waiting for SailDocs response.")
    return None
