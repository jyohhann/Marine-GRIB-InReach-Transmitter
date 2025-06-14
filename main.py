import time
import sys
import logging
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

sys.path.append(".")
from src import email_functions as email_func
from src import saildoc_functions as saildoc_func
from src import inreach_functions as inreach_func

POLL_INTERVAL = 60  # seconds

def main():
    """
    Main loop for checking new InReach messages, processing GRIB files, and sending replies.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    try:
        # Authenticate Gmail API
        auth_service = email_func.gmail_authenticate()
        """logging.info("Authenticated with Gmail API.")"""

        while True:
            logging.info("Checking for new InReach messages...")

            try:
                # Check for new messages and retrieve GRIB path and Garmin reply URL
                result = email_func.process_new_inreach_message(auth_service)

                if result is not None:
                    grib_path, garmin_reply_url = result

                    # Encode GRIB to binary
                    encoded_grib = saildoc_func.encode_saildocs_grib_file(grib_path)
                    logging.info(f"Encoded GRIB file: {grib_path}")

                    # Send the encoded GRIB to InReach
                    inreach_func.send_messages_to_inreach(garmin_reply_url, encoded_grib)
                    logging.info("Sent GRIB to InReach.")

            except Exception as e:
                logging.exception("Error during message processing loop:")

            # Wait before next check
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logging.info("Shutting down gracefully.")
    except Exception as e:
        logging.exception("Fatal error in main loop.")

if __name__ == "__main__":
    main()