# src/report_generator.py

import logging
import time
import random
from googleapiclient.errors import HttpError
from src.config import ROLE_MAP

def get_file_permissions(drive_service, file_id, max_retries=5):
    """Fetches all permissions for a given file ID with retry logic."""
    # ... (This function is correct and remains unchanged)
    retries = 0
    while retries < max_retries:
        try:
            fields = 'permissions(id,type,emailAddress,domain,role)'
            response = drive_service.permissions().list(
                fileId=file_id, fields=fields
            ).execute()
            return response.get('permissions', [])
        except HttpError as e:
            if e.resp.status in [403, 429, 500, 502, 503, 504]:
                wait = (2 ** retries) + random.random()
                logging.warning(f"Permissions fetch for {file_id} failed with status {e.resp.status}. Retrying in {wait:.1f}s... ({retries + 1}/{max_retries})")
                time.sleep(wait)
                retries += 1
            else:
                logging.error(f"Failed to get permissions for {file_id}: {e}")
                return []
    logging.error(f"Giving up on getting permissions for {file_id} after {max_retries} retries.")
    return []


def list_files_recursively(drive_service, folder_id, current_path="", max_retries=5):
    """Recursively lists all files and folders under a folder ID, building their full path."""
    # ... (This function is correct and remains unchanged)
    all_items = []
    page_token = None
    retries = 0
    try:
        root_folder = drive_service.files().get(fileId=folder_id, fields='name').execute()
        current_path = f"{current_path}/{root_folder.get('name', 'Unknown')}"
    except HttpError as e:
        logging.error(f"Could not retrieve metadata for folder ID {folder_id}: {e}")
        return []
    while True:
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            fields = 'nextPageToken, files(id,name,mimeType,owners,webViewLink)'
            response = drive_service.files().list(q=query, fields=fields, pageSize=1000, pageToken=page_token).execute()
            files = response.get('files', [])
            for item in files:
                item['path'] = f"{current_path}/{item.get('name', 'Untitled')}"
                all_items.append(item)
                if item.get('mimeType') == 'application/vnd.google-apps.folder':
                    all_items.extend(list_files_recursively(drive_service, item['id'], current_path=current_path))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
            retries = 0
        except HttpError as e:
            if e.resp.status in [403, 429, 500, 502, 503, 504] and retries < max_retries:
                wait = (2 ** retries) + random.random()
                logging.warning(f"File list for {folder_id} failed with status {e.resp.status}. Retrying in {wait:.1f}s... ({retries + 1}/{max_retries})")
                time.sleep(wait)
                retries += 1
            else:
                logging.error(f"Failed to list files for folder {folder_id}: {e}")
                break
    return all_items


def generate_permission_report(drive_service, folder_id, user_email=None):
    """
    Generates a detailed permission report for all items under a folder.
    """
    logging.info(f"Starting report generation for folder ID: {folder_id}")
    if user_email:
        logging.info(f"Filtering report to only include permissions for: {user_email}")

    all_items = list_files_recursively(drive_service, folder_id)
    logging.info(f"Found {len(all_items)} total items to scan for permissions.")
    
    report_data = []
    for i, item in enumerate(all_items):
        item_id = item.get('id')
        logging.info(f"Processing item {i+1}/{len(all_items)}: '{item.get('name')}' ({item_id})")

        # *** MODIFIED: Using the correct API field 'copyRequiresWriterPermission' ***
        try:
            # Note: Folders do not have this property and will throw an error, which we can safely ignore.
            if item.get('mimeType') == 'application/vnd.google-apps.folder':
                is_restricted = "N/A"
            else:
                file_metadata = drive_service.files().get(fileId=item_id, fields='copyRequiresWriterPermission').execute()
                # This mapping is now direct. If the property is True, the file is restricted.
                is_restricted = file_metadata.get('copyRequiresWriterPermission', False)
        except HttpError as e:
            logging.warning(f"Could not get metadata for '{item.get('name')}' ({item_id}). This is expected for folders. Error: {e}")
            is_restricted = "N/A" # Default for items where it can't be fetched

        permissions = get_file_permissions(drive_service, item_id)
        if not permissions and is_restricted == "N/A":
            continue

        owner = item.get('owners', [{}])[0].get('emailAddress', 'N/A')
        for p in permissions:
            if user_email:
                permission_email = p.get('emailAddress', '').lower()
                if permission_email != user_email.lower():
                    continue
            
            ui_role = ROLE_MAP.get(p.get('role'), str(p.get('role')).capitalize())
            ui_principal_type = ROLE_MAP.get(p.get('type'), str(p.get('type')).capitalize())

            report_data.append({
                'Full Path': item.get('path'),
                'Item Name': item.get('name'),
                'Item ID': item_id,
                'Restrict Download': str(is_restricted).upper(),
                'Role': ui_role,
                'Principal Type': ui_principal_type,
                'Email Address': p.get('emailAddress') or p.get('domain') or ('anyoneWithLink' if p.get('type') == 'anyone' else 'N/A'),
                'Owner': owner,
                'Google Drive URL': item.get('webViewLink'),
                'Root Folder ID': folder_id,
            })
            
    logging.info(f"Generated {len(report_data)} permission entries for the final report.")
    return report_data