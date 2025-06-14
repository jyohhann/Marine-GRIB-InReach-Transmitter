import os
import pickle
import base64
import logging
import json
from typing import Optional, Tuple, Any, List, Set
from email.mime.text import MIMEText
from base64 import urlsafe_b64decode
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from src.configs import Config
from src import saildoc_functions as saildoc_func
from src import inreach_functions as inreach_func

logger = logging.getLogger(__name__)
GMAIL_USER = "me"

def gmail_authenticate() -> Any:
    """Authenticate and return the Gmail API service."""
    creds = None
    if os.path.exists(Config.TOKEN_PATH):
        with open(Config.TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(Config.CREDENTIALS_PATH, Config.SCOPES)
            creds = flow.run_local_server(port=0)
        with open(Config.TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def load_processed_message_ids() -> Set[str]:
    """Load processed message IDs from file."""
    if not os.path.exists(Config.LIST_OF_PROCESSED_MESSAGES_FILE_LOCATION):
        return set()
    try:
        with open(Config.LIST_OF_PROCESSED_MESSAGES_FILE_LOCATION, "r") as f:
            return set(json.load(f))
    except Exception as e:
        logger.warning("Failed to load processed message IDs: %s", e)
        return set()

def save_processed_message_ids(processed_ids: Set[str]) -> None:
    """Save processed message IDs to file."""
    with open(Config.LIST_OF_PROCESSED_MESSAGES_FILE_LOCATION, "w") as f:
        json.dump(list(processed_ids), f)

def _extract_subject(msg: dict) -> str:
    """Extract the subject from a Gmail message."""
    headers = msg.get('payload', {}).get('headers', [])
    for header in headers:
        if header.get('name', '').lower() == 'subject':
            return header.get('value', '')
    return ''

def process_new_inreach_message(auth_service: Any, processed_ids: Set[str]) -> Optional[Tuple[str, str, str]]:
    """
    Checks for new unread messages and returns (msg_text, msg_id, garmin_reply_url)
    for the first unprocessed InReach message. Returns None if not found.
    """
    results = auth_service.users().messages().list(userId=GMAIL_USER, q='is:unread').execute()
    messages = results.get('messages', [])
    for m in messages:
        msg_id = m['id']
        if msg_id in processed_ids:
            continue
        msg = auth_service.users().messages().get(
            userId=GMAIL_USER, id=msg_id, format='metadata', metadataHeaders=['Subject']
        ).execute()
        subject = _extract_subject(msg)
        if "inreach" in subject.lower():
            msg_text, garmin_reply_url = fetch_message_text_and_url(msg_id, auth_service)
            return msg_text, msg_id, garmin_reply_url
    return None

def fetch_message_text_and_url(message_id: str, auth_service: Any) -> Tuple[str, Optional[str]]:
    """Fetch the message text and Garmin reply URL from a Gmail message."""
    msg = auth_service.users().messages().get(userId=GMAIL_USER, id=message_id).execute()
    payload = msg.get('payload', {})
    msg_data = payload.get('body', {}).get('data', '')

    if not msg_data and 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType', '').startswith('text/plain'):
                part_data = part.get('body', {}).get('data', '')
                if part_data:
                    msg_data = part_data
                    break
        if not msg_data:
            for part in payload['parts']:
                part_data = part.get('body', {}).get('data', '')
                if part_data:
                    msg_data = part_data
                    break

    if not msg_data:
        raise ValueError("No message data found.")

    decoded = urlsafe_b64decode(msg_data).decode(errors="replace")
    msg_text = next((line.strip() for line in decoded.splitlines() if line.strip().lower().startswith("mistral")), None)
    if not msg_text:
        msg_text = next((line.strip() for line in decoded.splitlines() if line.strip()), None)
    garmin_reply_url = next(
        (x.replace('\r', '') for x in decoded.split('\n') if Config.BASE_GARMIN_REPLY_URL in x), None
    )
    return msg_text, garmin_reply_url

def is_inreach_message(message_id: str, auth_service: Any) -> bool:
    """Return True if the message subject contains 'inreach' (case-insensitive)."""
    msg = auth_service.users().messages().get(
        userId=GMAIL_USER, id=message_id, format="metadata", metadataHeaders=["Subject"]
    ).execute()
    subject = _extract_subject(msg)
    return "inreach" in subject.lower()

def request_and_process_saildocs_grib(message_id: str, auth_service: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Processes a GRIB request by validating the request format, sending it to Saildocs if valid,
    and handling the Saildocs response and grib file retrieval.
    """
    msg_text, garmin_reply_url = fetch_message_text_and_url(message_id, auth_service)
    if not saildoc_func.is_valid_grib_request(msg_text):
        logger.info(f"Ignored: invalid GRIB request format: {msg_text}")
        inreach_func.send_messages_to_inreach(garmin_reply_url, "Invalid GRIB request format.")
        return None, garmin_reply_url

    _send_gmail_message(auth_service, Config.SAILDOCS_EMAIL_QUERY, "", "send " + msg_text)
    time_sent = datetime.utcnow()
    last_response = saildoc_func.wait_for_saildocs_response(auth_service, time_sent)

    if not last_response:
        inreach_func.send_messages_to_inreach(garmin_reply_url, "Saildocs timeout")
        return None, garmin_reply_url

    try:
        grib_path = _get_grib_attachment(auth_service, last_response['id'])
        if not grib_path:
            inreach_func.send_messages_to_inreach(garmin_reply_url, "Could not download grib attachment")
            return None, garmin_reply_url
    except Exception as e:
        logger.error("Failed to download GRIB: %s", e)
        inreach_func.send_messages_to_inreach(garmin_reply_url, "Could not download grib attachment")
        return None, garmin_reply_url

    return grib_path, garmin_reply_url

def _search_gmail_messages(service: Any, query: str) -> List[dict]:
    """Search for Gmail messages that match a query."""
    page_token = None
    messages = []
    while True:
        result = service.users().messages().list(userId=GMAIL_USER, q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
        page_token = result.get('nextPageToken')
        if not page_token:
            break
    return messages

def _build_gmail_message(destination: str, subject: str, body: str) -> dict:
    """Build a Gmail message for sending."""
    message = MIMEText(body)
    message['to'] = destination
    message['from'] = Config.GMAIL_ADDRESS
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

def _send_gmail_message(service: Any, destination: str, subject: str, body: str) -> dict:
    """Send a Gmail message."""
    return service.users().messages().send(
        userId=GMAIL_USER,
        body=_build_gmail_message(destination, subject, body)
    ).execute()

def _get_grib_attachment(service: Any, msg_id: str, user_id: str = GMAIL_USER) -> Optional[str]:
    """Download the GRIB attachment from a Gmail message."""
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id).execute()
        parts = message.get('payload', {}).get('parts', [])
        for part in parts:
            filename = part.get('filename')
            if filename and filename.endswith('.grb') and 'attachmentId' in part['body']:
                return _download_gmail_attachment(service, user_id, msg_id, part['body']['attachmentId'], filename)
        logger.warning("No GRIB attachment found in message %s.", msg_id)
        return None
    except Exception as error:
        logger.error('An error occurred: %s', error)
        return None

def _download_gmail_attachment(service: Any, user_id: str, msg_id: str, att_id: str, filename: str) -> str:
    """Download an attachment from Gmail and save it to disk."""
    att = service.users().messages().attachments().get(userId=user_id, messageId=msg_id, id=att_id).execute()
    data = att['data']
    file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
    path = os.path.join(Config.FILE_PATH, filename)
    with open(path, 'wb') as f:
        f.write(file_data)
    return path
