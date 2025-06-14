import time
import sys
import logging

logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
sys.path.append(".")

from src import email_functions as email_func
from src import saildoc_functions as saildoc_func
from src import inreach_functions as inreach_func
from src import mistralchat_functions as mistral_func

POLL_INTERVAL = 60  # seconds

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

def initialize_services():
    auth_service = email_func.gmail_authenticate()
    processed_ids = email_func.load_processed_message_ids()
    return auth_service, processed_ids

def handle_mistral_message(msg_text: str, garmin_reply_url: str) -> None:
    logging.info("InReach: Mistral chat request received.")
    encoded_reply = mistral_func.generate_mistral_response_from_inreach_message(msg_text)
    if encoded_reply:
        inreach_func.send_messages_to_inreach(garmin_reply_url, encoded_reply)
        logging.info("Sent Mistral response to InReach.")
    else:
        logging.warning("Failed to generate or encode Mistral response.")

def handle_grib_message(msg_id: str, msg_text: str, garmin_reply_url: str, auth_service) -> None:
    logging.info("InReach: GRIB file request received.")
    grib_result = email_func.request_and_process_saildocs_grib(msg_id, auth_service)
    if grib_result is not None:
        grib_path, _ = grib_result
        if grib_path:
            encoded_grib = saildoc_func.encode_saildocs_grib_file(grib_path)
            if encoded_grib:
                inreach_func.send_messages_to_inreach(garmin_reply_url, encoded_grib)
                logging.info("Sent GRIB to InReach.")
            else:
                logging.warning("Failed to encode GRIB file.")
        else:
            logging.warning("No GRIB file path returned.")
    else:
        logging.warning("Failed to process GRIB request.")

def process_new_message(result, auth_service, processed_ids):
    if result is None:
        return

    msg_text, msg_id, garmin_reply_url = result

    if not msg_text or not msg_text.strip():
        return

    if not email_func.is_inreach_message(msg_id, auth_service):
        return

    if msg_id in processed_ids:
        return

    if msg_text.strip().lower().startswith("mistral"):
        handle_mistral_message(msg_text, garmin_reply_url)
    else:
        handle_grib_message(msg_id, msg_text, garmin_reply_url, auth_service)

    processed_ids.add(msg_id)
    email_func.save_processed_message_ids(processed_ids)

def poll_messages(auth_service, processed_ids):
    while True:
        logging.info("Checking for new InReach messages...")
        try:
            result = email_func.process_new_inreach_message(auth_service, processed_ids)
            process_new_message(result, auth_service, processed_ids)
        except Exception as exc:
            logging.exception("Error during message processing loop: %s", exc)
        time.sleep(POLL_INTERVAL)

def main():
    setup_logging()
    try:
        auth_service, processed_ids = initialize_services()
        poll_messages(auth_service, processed_ids)
    except KeyboardInterrupt:
        logging.info("Shutting down gracefully.")
    except Exception as exc:
        logging.exception("Fatal error in main loop: %s", exc)

if __name__ == "__main__":
    main()
