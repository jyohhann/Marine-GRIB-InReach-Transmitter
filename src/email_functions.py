import os
import pickle
import base64
import logging
from typing import Optional, Tuple, Set, Any
from email.mime.text import MIMEText
from base64 import urlsafe_b64decode
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import sys
sys.path.append(".")
from src import configs
from src import saildoc_functions as saildoc_func
from src import inreach_functions as inreach_func

# Constants
GMAIL_USER = "me"

# Setup logging
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def gmail_authenticate():
    """
    Authenticates the Gmail API using google-auth, not oauth2client.
    Stores and reuses the user's credentials.
    """
    creds = None
    # The token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If credentials are not available or are invalid, log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save credentials for next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service

def process_new_inreach_message(auth_service: Any) -> Optional[Tuple[str, str]]:
    """
    Check for new messages, process them, and record their IDs.
    Returns:
        tuple: (path to GRIB attachment, Garmin reply URL) if successful, else None.
    """
    previous_messages = _load_previous_messages()
    unanswered_messages = _get_new_message_ID(auth_service, previous_messages)

    if not unanswered_messages:
        logger.info("No new messages found.")
        return None

    for message_id in unanswered_messages:
        logger.info("New message received: %s", message_id)
        try:
            grib_path, garmin_reply_url = _request_and_process_saildocs_grib(message_id, auth_service)
            logger.info(f"Answered message {message_id}")
            _append_to_previous_messages(message_id)
            if grib_path and garmin_reply_url:
                return grib_path, garmin_reply_url
        except Exception as e:
            logger.error(f"Error answering message {message_id}: {e}")
            _append_to_previous_messages(message_id)

    return None

######## HELPERS ########

def _build_gmail_message(destination: str, subject: str, body: str) -> dict:
    """Construct a MIMEText message for Gmail API."""
    message = MIMEText(body)
    message['to'] = destination
    message['from'] = configs.GMAIL_ADDRESS
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

def _send_gmail_message(service: Any, destination: str, subject: str, body: str) -> dict:
    """Send an email message through Gmail API."""
    return service.users().messages().send(
        userId=GMAIL_USER,
        body=_build_gmail_message(destination, subject, body)
    ).execute()

def _search_gmail_messages(service: Any, query: str) -> list:
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

def _get_grib_attachment(service: Any, msg_id: str, user_id: str = GMAIL_USER) -> Optional[str]:
    """Retrieve and save the first GRIB attachment from a Gmail message."""
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

def _request_and_process_saildocs_grib(message_id: str, auth_service: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Request Saildocs GRIB data, process response, and return (GRIB path, Garmin reply URL).
    """
    msg_text, garmin_reply_url = _fetch_message_text_and_url(message_id, auth_service)
    _send_gmail_message(auth_service, configs.SAILDOCS_EMAIL_QUERY, "", "send " + msg_text)
    time_sent = datetime.utcnow()
    last_response = saildoc_func.wait_for_saildocs_response(auth_service, time_sent)

    if not last_response:
        inreach_func.send_reply_to_inreach(garmin_reply_url, "Saildocs timeout")
        return None, garmin_reply_url

    try:
        grib_path = _get_grib_attachment(auth_service, last_response['id'])
        if not grib_path:
            inreach_func.send_reply_to_inreach(garmin_reply_url, "Could not download grib attachment")
            return None, garmin_reply_url
    except Exception as e:
        logger.error("Failed to download GRIB: %s", e)
        inreach_func.send_reply_to_inreach(garmin_reply_url, "Could not download grib attachment")
        return None, garmin_reply_url

    return grib_path, garmin_reply_url

def _get_new_or_refreshed_credentials(creds: Any) -> Any:
    """Helper to obtain new credentials or refresh expired ones."""
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(configs.CREDENTIALS_PATH, configs.SCOPES)
        creds = flow.run_local_server(port=0)
    return creds

def _download_gmail_attachment(service: Any, user_id: str, msg_id: str, att_id: str, filename: str) -> str:
    """Download and save an attachment from a Gmail message."""
    att = service.users().messages().attachments().get(userId=user_id, messageId=msg_id, id=att_id).execute()
    data = att['data']
    file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
    path = os.path.join(configs.FILE_PATH, filename)
    with open(path, 'wb') as f:
        f.write(file_data)
    return path

def _load_previous_messages() -> Set[str]:
    """Load previously processed messages from file."""
    if not os.path.exists(configs.LIST_OF_PREVIOUS_MESSAGES_FILE_LOCATION):
        return set()
    with open(configs.LIST_OF_PREVIOUS_MESSAGES_FILE_LOCATION, 'r') as f:
        return set(f.read().splitlines())

def _append_to_previous_messages(message_id: str) -> None:
    """Append a new message ID to the file."""
    with open(configs.LIST_OF_PREVIOUS_MESSAGES_FILE_LOCATION, 'a') as f:
        f.write(f'{message_id}\n')

def _get_new_message_ID(auth_service: Any, previous_messages: Set[str]) -> Set[str]:
    """Retrieve new InReach messages that haven't been processed."""
    inreach_msgs = _search_gmail_messages(auth_service, configs.SERVICE_EMAIL)
    inreach_msgs_ids = {msg['id'] for msg in inreach_msgs}
    return inreach_msgs_ids.difference(previous_messages)

def _fetch_message_text_and_url(message_id: str, auth_service: Any) -> Tuple[str, Optional[str]]:
    """Retrieve message content and extract the text and reply URL."""
    msg = auth_service.users().messages().get(userId=GMAIL_USER, id=message_id).execute()
    msg_data = msg['payload']['body'].get('data', '')
    if not msg_data:
        raise ValueError("No message data found.")
    decoded = urlsafe_b64decode(msg_data).decode()
    msg_text = decoded.split('\r')[0].lower()
    garmin_reply_url = next((x.replace('\r', '') for x in decoded.split('\n') if configs.BASE_GARMIN_REPLY_URL in x), None)

    return msg_text, garmin_reply_url