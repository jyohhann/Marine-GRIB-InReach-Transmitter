import requests
import time
import random
import logging
from typing import List, Any

import sys
sys.path.append(".")
from src import configs

logger = logging.getLogger(__name__)
"""logging.basicConfig(level=logging.INFO)"""

def send_messages_to_inreach(url: str, gribmessage: str) -> List[requests.Response]:
    """
    Splits the gribmessage and sends each part to InReach.

    Args:
        url (str): The target URL for the InReach API.
        gribmessage (str): The full message string to be split and sent.

    Returns:
        list: Response objects from the InReach API for each sent message.
    """
    message_parts = _split_message(gribmessage)
    responses = []

    for idx, part in enumerate(message_parts):
        logger.info(f"Sending part {idx+1}/{len(message_parts)}: length={len(part)}")
        response = _post_request_to_inreach(url, part)
        logger.info(f"Status Code: {getattr(response, 'status_code', None)}")
        responses.append(response)
        time.sleep(configs.DELAY_BETWEEN_MESSAGES)

    return responses

######## HELPERS ########

def _split_message(gribmessage: str) -> List[str]:
    """
    Splits a given grib message into chunks and formats each with its index.

    Args:
        gribmessage (str): The grib message to split.

    Returns:
        list: Formatted message chunks.
    """
    length = configs.MESSAGE_SPLIT_LENGTH
    chunks = [gribmessage[i:i + length] for i in range(0, len(gribmessage), length)]
    total = len(chunks)
    return [
        f"msg {idx + 1}/{total}:\n{chunk}\nend"
        for idx, chunk in enumerate(chunks)
    ]

def _post_request_to_inreach(url: str, message_str: str) -> requests.Response:
    """
    Sends a post request with the message to InReach.

    Args:
        url (str): The InReach endpoint URL.
        message_str (str): The message to send.

    Returns:
        Response: The server's response to the request.
    """
    try:
        guid = _extract_guid_from_url(url)
    except Exception as e:
        logger.error(f"Failed to extract GUID from URL: {e}")
        raise

    data = {
        'ReplyAddress': configs.GMAIL_ADDRESS,
        'ReplyMessage': message_str,
        'MessageId': str(random.randint(10000000, 99999999)),
        'Guid': guid,
    }

    try:
        response = requests.post(
            url,
            cookies=configs.INREACH_COOKIES,
            headers=configs.INREACH_HEADERS,
            data=data
        )
        response.raise_for_status()
        logger.info('Reply to InReach sent successfully.')
    except requests.RequestException as e:
        logger.error(f'Error sending part: {message_str}\nException: {e}\nResponse: {getattr(e.response, "content", None)}')
        return e.response if hasattr(e, 'response') else None

    return response

def _extract_guid_from_url(url: str) -> str:
    """
    Extracts the GUID from the InReach URL.

    Args:
        url (str): The InReach endpoint URL.

    Returns:
        str: The extracted GUID.
    """
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    guid_list = qs.get('extId')
    if not guid_list:
        raise ValueError("Guid (extId) not found in URL.")

    return guid_list[0]