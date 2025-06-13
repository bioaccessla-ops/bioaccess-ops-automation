from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

import httplib2
import logging
import time
import random
import csv
import argparse

# ---- CONFIG ----
httplib2.debuglevel = 4
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]

logging.basicConfig(
    filename='single_email_permissions.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def get_credentials():
    """
    Authenticate and return OAuth credentials for Google APIs.
    """
    creds = None
    try:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    except (FileNotFoundError, ValueError):
        logging.info("No valid token.json, starting OAuth flow.")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing access token…")
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials_DeskApp.json', SCOPES)
            creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
        with open('token.json', 'w', encoding='utf-8') as token_file:
            token_file.write(creds.to_json())
            logging.info("token.json updated.")
    return creds


def list_all_items(service, parent_id, max_retries=5):
    """
    Recursively list all files and folders under a parent folder.
    """
    query = "'{0}' in parents".format(parent_id)
    all_items = []
    page_token = None
    retries = 0
    while True:
        try:
            response = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, parents)",
                pageSize=1000,
                pageToken=page_token
            ).execute()
            files = response.get('files', [])
            for f in files:
                all_items.append(f)
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    all_items.extend(list_all_items(service, f['id']))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            if e.resp.status in [429, 500, 502, 503, 504] and retries < max_retries:
                wait = (2 ** retries) + random.random()
                logging.info(f"Retry {retries+1} after {wait:.1f}s")
                time.sleep(wait)
                retries += 1
            else:
                logging.error(f"Error listing items: {e}")
                break
    return all_items


def fetch_permissions(service, file_id, max_retries=5):
    """
    Fetch permissions for a given file/folder.
    """
    retries = 0
    while True:
        try:
            resp = service.permissions().list(
                fileId=file_id,
                fields="permissions(emailAddress, role, type)"
            ).execute()
            return resp.get('permissions', [])
        except HttpError as e:
            if e.resp.status in [429, 500, 502, 503, 504] and retries < max_retries:
                wait = (2 ** retries) + random.random()
                logging.info(f"Retry permissions {retries+1} for {file_id}")
                time.sleep(wait)
                retries += 1
            else:
                logging.error(f"Failed permissions fetch for {file_id}: {e}")
                return []


def has_general_access(perms):
    """
    Determine if item is shared broadly.
    """
    for p in perms:
        if p.get('type') in ['anyone', 'anyoneWithLink', 'domain', 'group']:
            return 'Yes'
    return 'No'


def write_csv(rows, headers, filename):
    """
    Write rows to CSV.
    """
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        logging.info(f"CSV written to {filename}")
    except Exception as e:
        logging.error(f"Error writing CSV {filename}: {e}")


def main():
    parser = argparse.ArgumentParser(description='Fetch Drive permissions for one email')
    parser.add_argument('--email', required=True, help='Target email address')
    parser.add_argument('--output', default='single_email_permissions.csv', help='Output CSV file')
    parser.add_argument('--root', required=True, help='Root folder ID to scan')
    args = parser.parse_args()
    target = args.email.strip().lower()

    creds = get_credentials()
    drive_service = build('drive', 'v3', credentials=creds)
    logging.info("Google Drive service initialized.")

    # Retrieve all items under the specified root
    items = list_all_items(drive_service, args.root)
    logging.info(f"Total items found: {len(items)}")

    # Fetch and include root folder metadata so we can reconstruct its path
    root_meta = drive_service.files().get(fileId=args.root, fields="id,name").execute()

    # Build ID->item map (including root)
    items_by_id = {i['id']: i for i in items}
    items_by_id[args.root] = root_meta

    # Build parent->children map
    parent_map = {}
    for it in items:
        for p in it.get('parents', []):
            parent_map.setdefault(p, []).append(it)

    # Flatten hierarchy starting at root_meta
    def recurse(item, current_path=None):
        path = (current_path or []) + [(item['id'], item['name'])]
        rows = [path]
        for child in parent_map.get(item['id'], []):
            rows.extend(recurse(child, path))
        return rows

    flattened = recurse(root_meta)

    # Prepare CSV rows
    rows = []
    headers = ['Item Path', 'Item ID', f'Role for {target}', 'General Access']
    for path in flattened:
        item_id, item_name = path[-1]
        full_path = '/' + '/'.join([n for _, n in path])
        perms = fetch_permissions(drive_service, item_id)
        role = next((p['role'] for p in perms if p.get('emailAddress', '').lower() == target), 'No Access')
        general = has_general_access(perms)
        rows.append([full_path, item_id, role, general])

    write_csv(rows, headers, args.output)
    print(f"Done: {args.output} created for email {target}")

if __name__ == '__main__':
    main()
