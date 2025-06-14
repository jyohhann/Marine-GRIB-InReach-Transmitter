import os

class Config:
    """Configuration for the Marine GRIB and Mistral chat InReach Transmitter."""

    # Paths
    TOKEN_PATH = os.environ.get('TOKEN_PATH', './token.pickle')
    CREDENTIALS_PATH = os.environ.get('CREDENTIALS_PATH', './credentials.json')
    FILE_PATH = os.environ.get('FILE_PATH', './files/attachments')
    LIST_OF_PROCESSED_MESSAGES_FILE_LOCATION = os.environ.get('LIST_OF_PROCESSED_MESSAGES_FILE_LOCATION', './files/processed_messages.txt')

    # Gmail permissions
    SCOPES = ['https://mail.google.com/']

    # E-Mails and Links
    GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS', 'jyohhannes@gmail.com')
    SERVICE_EMAIL = os.environ.get('SERVICE_EMAIL', 'no.reply.inreach@garmin.com')
    BASE_GARMIN_REPLY_URL = os.environ.get('BASE_GARMIN_REPLY_URL', 'explore.garmin.com')
    SAILDOCS_EMAIL_QUERY = os.environ.get('SAILDOCS_EMAIL_QUERY', 'query@saildocs.com')
    SAILDOCS_RESPONSE_EMAIL = os.environ.get('SAILDOCS_RESPONSE_EMAIL', 'query-reply@saildocs.com')
    INREACH_BASE_URL_POST_REQUEST_EUR = os.environ.get('INREACH_BASE_URL_POST_REQUEST_EUR', 'https://eur.explore.garmin.com/TextMessage/TxtMsg')
    INREACH_BASE_URL_POST_REQUEST_DEFAULT = os.environ.get('INREACH_BASE_URL_POST_REQUEST_DEFAULT', 'https://explore.garmin.com/TextMessage/TxtMsg')

    # E-Mail Headers
    INREACH_HEADERS = {
        'authority': 'explore.garmin.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://explore.garmin.com',
        'sec-ch-ua': '"Chromium";v="106", "Not;A=Brand";v="99", "Google Chrome";v="106.0.5249.119"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    INREACH_COOKIES = {
        'BrowsingMode': 'Desktop',
    }

    # Mistral AI Configuration
    MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
    MISTRAL_API_URL = os.environ.get("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")

    # Others
    MESSAGE_SPLIT_LENGTH = int(os.environ.get('MESSAGE_SPLIT_LENGTH', 120))
    DELAY_BETWEEN_MESSAGES = int(os.environ.get('DELAY_BETWEEN_MESSAGES', 5))

# Module-level constants for convenience
TOKEN_PATH = Config.TOKEN_PATH
CREDENTIALS_PATH = Config.CREDENTIALS_PATH
FILE_PATH = Config.FILE_PATH
LIST_OF_PROCESSED_MESSAGES_FILE_LOCATION = Config.LIST_OF_PROCESSED_MESSAGES_FILE_LOCATION

SCOPES = Config.SCOPES

GMAIL_ADDRESS = Config.GMAIL_ADDRESS
SERVICE_EMAIL = Config.SERVICE_EMAIL
BASE_GARMIN_REPLY_URL = Config.BASE_GARMIN_REPLY_URL
SAILDOCS_EMAIL_QUERY = Config.SAILDOCS_EMAIL_QUERY
SAILDOCS_RESPONSE_EMAIL = Config.SAILDOCS_RESPONSE_EMAIL
INREACH_BASE_URL_POST_REQUEST_EUR = Config.INREACH_BASE_URL_POST_REQUEST_EUR
INREACH_BASE_URL_POST_REQUEST_DEFAULT = Config.INREACH_BASE_URL_POST_REQUEST_DEFAULT

INREACH_HEADERS = Config.INREACH_HEADERS
INREACH_COOKIES = Config.INREACH_COOKIES

MISTRAL_API_KEY = Config.MISTRAL_API_KEY
MISTRAL_API_URL = Config.MISTRAL_API_URL

MESSAGE_SPLIT_LENGTH = Config.MESSAGE_SPLIT_LENGTH
DELAY_BETWEEN_MESSAGES = Config.DELAY_BETWEEN_MESSAGES
