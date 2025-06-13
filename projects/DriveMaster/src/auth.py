# auth.py
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging

# --- IMPORTANT ---
# The final tool needs to add, modify, and remove permissions,
# so we need a more permissive scope than just 'readonly'.
# This single 'drive' scope covers everything we need for Drive.
SCOPES = ['https://www.googleapis.com/auth/drive']

# Get the directory where this auth.py script is located
SCRIPT_DIR = os.path.dirname(__file__)
# Build a path to the project's root directory (one level up from src)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Build the full, correct paths to the credential files
TOKEN_FILE = os.path.join(PROJECT_ROOT, 'credentials', 'token.json')
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, 'credentials', 'credentials_DeskApp.json')

def authenticate_and_get_service():
    """
    Handles the OAuth 2.0 Installed Application flow.
    Returns an authenticated Google Drive API service object.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            logging.warning(f"Could not load token.json: {e}. Re-authenticating.")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing access token...")
            creds.refresh(Request())
        else:
            logging.info("No valid token found, starting new OAuth flow.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logging.info(f"Token saved to {TOKEN_FILE}")

    try:
        service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive service created successfully.")
        return service
    except Exception as e:
        logging.error(f"Failed to build Drive service: {e}")
        return None