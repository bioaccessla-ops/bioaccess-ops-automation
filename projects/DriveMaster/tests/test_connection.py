# test_connection.py
import logging
from google_auth import get_drive_service
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    logging.info("Attempting to get Drive service...")
    service = get_drive_service()
    logging.info("Successfully created Drive service object.")

    logging.info("Checking service account identity...")
    about = service.about().get(fields='user').execute()
    email = about['user']['emailAddress']

    logging.info(f"Service is authenticated and acting as: {email}")
    print("\n✅ Authentication test PASSED.")

except HttpError as e:
    logging.error(f"An API error occurred: {e}")
    print("\n❌ Authentication test FAILED.")
except Exception as e:
    logging.error(f"An unexpected error occurred: {e}")
    print("\n❌ Authentication test FAILED.")