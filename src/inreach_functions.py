import requests
import time
import random
import logging
from typing import List, Optional
from src import configs
from src.mistralchat_functions import clean_llm_output, is_valid_for_inreach

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 120

def split_message_for_inreach(gribmessage: str, max_len: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Split and format a message for InReach, with each part up to max_len characters."""
    chunks = [gribmessage[i:i + max_len] for i in range(0, len(gribmessage), max_len)]
    total = len(chunks)
    return [
        f"msg {idx + 1}/{total}:\n{chunk}{'\nend' if idx == total - 1 else ''}"
        for idx, chunk in enumerate(chunks)
    ]

def send_messages_to_inreach(
    url: str,
    gribmessage: str,
    sanitize_for_mistral: bool = False,
    max_message_length: Optional[int] = None
) -> List[Optional[requests.Response]]:
    """
    Split gribmessage and send each part to InReach.
    If sanitize_for_mistral: clean and validate the message and split to 120 chars.
    Else: use configs.MESSAGE_SPLIT_LENGTH.
    """
    max_len = max_message_length or (MAX_MESSAGE_LENGTH if sanitize_for_mistral else configs.MESSAGE_SPLIT_LENGTH)
    if sanitize_for_mistral:
        gribmessage = clean_llm_output(gribmessage)
        if not is_valid_for_inreach(gribmessage):
            logger.error("Refusing to send message containing internal LLM/system markers!")
            return []
    message_parts = split_message_for_inreach(gribmessage, max_len)

    responses = []
    for idx, part in enumerate(message_parts):
        logger.info(
            f"Sending part {idx+1}/{len(message_parts)}: length={len(part)} code=200"
        )
        response = _post_request_to_inreach(url, part)
        logger.info(
            f"Status Code: {getattr(response, 'status_code', None)} length={len(part)} code=200"
        )
        responses.append(response)
        time.sleep(configs.DELAY_BETWEEN_MESSAGES)
    return responses

def _post_request_to_inreach(url: str, message_str: str) -> Optional[requests.Response]:
    """Send a single message part to InReach."""
    try:
        guid = _extract_guid_from_url(url)
    except Exception as e:
        logger.error(f"Failed to extract GUID from URL: {e}")
        raise

    data = {
        'ReplyMessage': message_str,
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
        logger.info(
            f"Reply to InReach sent successfully. Status={response.status_code} length={len(message_str)} code=200"
        )
        return response
    except requests.RequestException as e:
        logger.error(
            f'Error sending part: {message_str}\nException: {e}\n'
            f'Response: {getattr(e.response, "content", None)} length={len(message_str)} code=200'
        )
        return getattr(e, 'response', None)

def _extract_guid_from_url(url: str) -> str:
    """Extract the GUID (extId) from the InReach URL."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    guid_list = parse_qs(parsed.query).get('extId')
    if not guid_list:
        raise ValueError("Guid (extId) not found in URL.")
    return guid_list[0]
