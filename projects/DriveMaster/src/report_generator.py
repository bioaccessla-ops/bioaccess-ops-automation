# report_generator.py

import logging
import time
import random
from googleapiclient.errors import HttpError
from src.config import ROLE_MAP


def get_file_permissions(drive_service, file_id, max_retries=5):
    """
    Fetches all permissions for a given file ID with retry logic.
    Adapted from fetch_permissions in the original scripts.
    """
    retries = 0
    while retries < max_retries:
        try:
            # Request all relevant fields for the report.
            fields = 'permissions(id,type,emailAddress,domain,role,allowFileDiscovery,expirationTime)'
            response = drive_service.permissions().list(
                fileId=file_id,
                fields=fields
            ).execute()
            return response.get('permissions', [])
        except HttpError as e:
            if e.resp.status in [403, 429, 500, 502, 503, 504]:
                wait = (2 ** retries) + random.random()
                logging.warning(
                    f"Permissions fetch for {file_id} failed with status {e.resp.status}. "
                    f"Retrying in {wait:.1f}s... ({retries + 1}/{max_retries})"
                )
                time.sleep(wait)
                retries += 1
            else:
                logging.error(f"Failed to get permissions for {file_id}: {e}")
                return [] # Return empty list on unrecoverable error
    logging.error(f"Giving up on getting permissions for {file_id} after {max_retries} retries.")
    return []

def list_files_recursively(drive_service, folder_id, current_path="", max_retries=5):
    """
    Recursively lists all files and folders under a folder ID, building their full path.
    Adapted from list_all_folders_and_files and list_all_items.
    """
    all_items = []
    page_token = None
    retries = 0
    
    # Get the name of the current folder to build the path
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
            response = drive_service.files().list(
                q=query,
                fields=fields,
                pageSize=1000,
                pageToken=page_token
            ).execute()

            files = response.get('files', [])
            for item in files:
                # Add the constructed path to the item dictionary
                item['path'] = f"{current_path}/{item.get('name', 'Untitled')}"
                all_items.append(item)
                
                # If the item is a folder, recurse into it
                if item.get('mimeType') == 'application/vnd.google-apps.folder':
                    all_items.extend(list_files_recursively(drive_service, item['id'], current_path=current_path))

            page_token = response.get('nextPageToken')
            if not page_token:
                break
            retries = 0 # Reset retries on successful call
        except HttpError as e:
            if e.resp.status in [403, 429, 500, 502, 503, 504] and retries < max_retries:
                wait = (2 ** retries) + random.random()
                logging.warning(
                    f"File list for {folder_id} failed with status {e.resp.status}. "
                    f"Retrying in {wait:.1f}s... ({retries + 1}/{max_retries})"
                )
                time.sleep(wait)
                retries += 1
            else:
                logging.error(f"Failed to list files for folder {folder_id}: {e}")
                break # Exit loop on unrecoverable error
    return all_items

def generate_permission_report(drive_service, folder_id, user_email=None):
    """
    Generates a detailed permission report for all items under a folder.
    """
    logging.info(f"Starting report generation for folder ID: {folder_id}")
    all_items = list_files_recursively(drive_service, folder_id)
    logging.info(f"Found {len(all_items)} total items to process.")
    
    report_data = []
    for i, item in enumerate(all_items):
        item_id = item.get('id')
        logging.info(f"Processing item {i+1}/{len(all_items)}: '{item.get('name')}' ({item_id})")

        permissions = get_file_permissions(drive_service, item_id)
        if not permissions:
            continue

        # If a specific user_email is provided, check if they have access
        # before adding any permissions from this item to the report.
        if user_email:
            has_user_access = any(
                p.get('emailAddress', '').lower() == user_email.lower() for p in permissions
            )
            if not has_user_access:
                continue

        # If we are generating a full report or the user has access, process all permissions.
        owner = item.get('owners', [{}])[0].get('emailAddress', 'N/A')
        for p in permissions:
            report_data.append({
                'Item Name': item.get('name'),
                'Item ID': item_id,
                'Full Path': item.get('path'),
                'Owner': owner,
                'Principal Type': p.get('type'),
                'Email Address': p.get('emailAddress') or p.get('domain') or ('anyoneWithLink' if p.get('type') == 'anyone' else 'N/A'),
                 'Role': ROLE_MAP.get(p.get('role'), str(p.get('role')).capitalize()),
                'Allow Discovery': p.get('allowFileDiscovery', 'N/A'),
                'Expiration Time': p.get('expirationTime', 'N/A'),
                'Google Drive URL': item.get('webViewLink'),
            })
            
    logging.info(f"Generated {len(report_data)} permission entries for the final report.")
    return report_data