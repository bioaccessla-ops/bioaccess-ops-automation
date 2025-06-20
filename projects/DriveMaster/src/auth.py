# src/auth.py

import os
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

SCOPES = ['https://www.googleapis.com/auth/drive']

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TOKEN_FILE = os.path.join(PROJECT_ROOT, 'credentials', 'token.json')
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, 'credentials', 'credentials_DeskApp.json')

def authenticate_and_get_service():
    """
    Handles the OAuth 2.0 Installed Application flow.
    Returns an authenticated Google Drive API service object.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        logging.critical(f"FATAL: Client secrets file not found at '{CREDENTIALS_FILE}'.")
        logging.critical("Please download your OAuth 2.0 Client ID JSON from Google Cloud Console")
        logging.critical("and place it in the 'credentials' directory with the name 'credentials_DeskApp.json'.")
        return None

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            logging.warning(f"Could not load token.json, it may be corrupted: {e}.")
            logging.warning(f"Deleting the invalid token file at '{TOKEN_FILE}'.")
            os.remove(TOKEN_FILE)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired access token...")
            try:
                creds.refresh(Request())
            except RefreshError as e:
                logging.warning(f"Failed to refresh token, it may have been revoked: {e}")
                logging.warning(f"Deleting invalid token '{TOKEN_FILE}' and requesting new user authentication.")
                os.remove(TOKEN_FILE)
                creds = None
            except Exception as e:
                logging.error(f"An unexpected error occurred during token refresh: {e}")
                creds = None

        if not creds:
            logging.info("No valid token found, starting new OAuth flow...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                
                # --- MODIFIED: Added 'prompt' parameter to force account selection ---
                # This ensures the user can choose a different account after a failed attempt,
                # bypassing the browser's session caching.
                creds = flow.run_local_server(port=0,
                                              timeout_seconds=60,
                                              prompt='select_account')
                
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                    logging.info(f"Token saved to {TOKEN_FILE}")

            except Exception as e:
                logging.error("\n---")
                logging.error(f"Authentication flow failed or timed out. (Error: {e})")
                logging.error("This can happen if you used an email from outside the allowed organization or did not complete the login within 2 minutes.")
                logging.error("Please re-run the command and authenticate with an authorized account.")
                logging.error("---\n")
                return None

    try:
        service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive service created successfully.")
        return service
    except Exception as e:
        logging.error(f"Failed to build Drive service: {e}")
        return None