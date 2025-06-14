import time
import base64
import zlib
import logging
from typing import Optional, Any
from datetime import datetime

import sys
sys.path.append(".")
from src import configs
from src import email_functions as email_func

logger = logging.getLogger(__name__)
"""logging.basicConfig(level=logging.INFO)"""

def encode_saildocs_grib_file(file_path: str) -> str:
    """
    Reads the content of a GRIB file, compresses it using zlib, then encodes the compressed data into a base64 string.

    Args:
        file_path (str): Path to the GRIB file to encode.

    Returns:
        str: Base64 encoded string of the compressed GRIB file.
    """
    try:
        with open(file_path, 'rb') as file:
            grib_binary = file.read()
        compressed_grib = zlib.compress(grib_binary)
        encoded_data = base64.b64encode(compressed_grib).decode('utf-8')
        return encoded_data
    except Exception as e:
        logger.error(f"Failed to encode file {file_path}: {e}")
        raise

def wait_for_saildocs_response(auth_service: Any, time_sent: datetime) -> Optional[dict]:
    """
    Wait for a SailDocs response and verify if the response matches the request timestamp.

    Args:
        auth_service: Authenticated Gmail API service instance.
        time_sent (datetime): Timestamp of the SailDocs request.

    Returns:
        dict or None: The latest email response dict, or None if no valid response within the timeout.
    """
    max_attempts = 60
    sleep_seconds = 10

    for attempt in range(max_attempts):
        time.sleep(sleep_seconds)
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
            # Parse date using standard library for better portability
            from email.utils import parsedate_to_datetime
            time_received = parsedate_to_datetime(date_header['value'])
            if time_received > time_sent:
                return last_response
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}: Could not check SailDocs response: {e}")
            continue
    logger.error("Timed out waiting for SailDocs response.")

    return None