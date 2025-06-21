# src/auth.py

import os
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError
# NOTE: We are intentionally NOT importing FlowTimeoutError to work around the environment issue.

SCOPES = ['https://www.googleapis.com/auth/drive']
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TOKEN_FILE = os.path.join(PROJECT_ROOT, 'credentials', 'token.json')
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, 'credentials', 'credentials_DeskApp.json')

def authenticate_and_get_service():
    """ Handles the OAuth 2.0 Installed Application flow. """
    if not os.path.exists(CREDENTIALS_FILE):
        logging.critical(f"FATAL: Client secrets file not found at '{CREDENTIALS_FILE}'. Please set it up."); return None

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            logging.warning(f"Corrupted token file at '{TOKEN_FILE}'. Deleting it."); os.remove(TOKEN_FILE)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired access token...")
            try:
                creds.refresh(Request())
            except RefreshError:
                logging.warning(f"Failed to refresh token. Deleting invalid token and re-authenticating."); os.remove(TOKEN_FILE); creds = None
            except Exception as e:
                logging.error(f"Unexpected error during token refresh: {e}"); creds = None
        
        if not creds:
            logging.info("No valid token found, starting new OAuth flow...")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0, timeout_seconds=120, prompt='select_account')
                with open(TOKEN_FILE, 'w') as token: token.write(creds.to_json())
                logging.info(f"Token saved to {TOKEN_FILE}")
            except Exception as e:
                logging.error("\n---"); logging.error(f"Authentication flow failed or timed out. (Error: {e})"); logging.error("Please re-run and authenticate with an authorized account."); logging.error("---\n"); return None

    try:
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        logging.info("Google Drive service created successfully (caching disabled).")
        return service
    except Exception as e:
        logging.error(f"Failed to build Drive service: {e}"); return None