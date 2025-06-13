#!/usr/bin/env python3
"""
remove_permissions.py

Recursively remove all Viewer/Editor permissions for a given list of emails
from every file and subfolder under a specified root folder ID.

At the end, it prints a summary of exactly which items lost which email’s access.
"""

import os
import pickle
import sys
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If you modify these scopes, delete token.pickle/token.json
SCOPES = ['https://www.googleapis.com/auth/drive']

# ─── CONFIGURE THESE ─────────────────────────────────────────────────────────────
# The ID of the folder under which you want to strip permissions.
# You can find this by going into Drive → Right-click folder → Get link → copy the ID.
ROOT_FOLDER_ID = '166gOxE118LBoozqLdeHLdPzCGE2Wd_95'

# A list of emails whose access you want to remove from everything under ROOT_FOLDER_ID.
TARGET_EMAILS = [
    'aagree@medinstitute.com',
    'lhoard@medinstitute.com',
    'jkrieger@medinstitute.com',
    'vlinares@bioaccessla.com',
    'jespinosa@bioaccessla.com',
    'betoven404@gmail.com',
    'manueld1975@gmail.com',
    'danielvegamejia@gmail.com',
    'cadenabonfanti@gmail.com',
    'mariel@reachbeacon.com',
    'myra@reachbeacon.com',
    'myra.fabro@gmail.com',
    'durley.fernandez@ocasa.com',
    'earalfa@hotmail.com',
    'jlopezgo0215@gmail.com',
    'julio.naranjo@urosario.edu.co',
    'nkoto@avantecvascular.com',
    'nohe3112@hotmail.com',
    'jd.ruiz122@gmail.com',
    'jiguerra0411@gmail.com',
    'ybolivar@clinicadelacosta.co',
    'ypulido@clinicadelacosta.co',
    'yrojas@clinicadelacosta.co',
    'talentohumano@clinicadelacosta.co',
    'lgomez@clinicadelacosta.co',
    'johndiaz@anicamenterprises.com',
    'jmartinez@clinicadelacosta.co',
    'ebenavidez@clinicadelacosta.co',
    'citasmedicas@garpermedica.com',
    'theoheise@gmail.com',
    'sconverse@medinstitute.com',
    'sala_dmrdi@invima.gov.co',
    'motlewski@medinstitute.com',
    'kduran@clinicadelacosta.co',
    'kdelahoz@clinicadelacosta.co',
    'jmclark@latammarketaccess.com',
    'hcastilla@clinicadelacosta.co',
    'gestor.radicacion@foscal.com.co',
    'gestiondelconocimientofhsjb@gmail.com',
    'fhsjbcalidad@gmail.com',
    'claudia.caicedo@foscal.com.co',
    'ccruzf@invima.gov.co',
    'asistente.etica@foscal.com.co',
    # add more addresses here...
]
# ──────────────────────────────────────────────────────────────────────────────────


def authenticate():
    """
    Authenticates via OAuth2, using 'credentials.json'. Saves/reads 'token.json'.
    Returns an authorized Drive API service instance.
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If no valid credentials, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save for next run
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Error building Drive service: {e}")
        sys.exit(1)


def list_permissions(service, file_id):
    """
    Returns a list of all permissions on the given file/folder.
    Each element is a dict containing at least 'id' and 'emailAddress' (if it's a user permission).
    """
    perms = []
    page_token = None
    while True:
        try:
            response = service.permissions().list(
                fileId=file_id,
                fields='permissions(id,emailAddress,role)',
                pageToken=page_token
            ).execute()
        except HttpError as e:
            print(f"  [!] Error listing permissions for {file_id}: {e}")
            return []
        perms.extend(response.get('permissions', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    return perms


def delete_permission(service, file_id, permission_id):
    """
    Deletes a single permission (by its permissionId) on a file/folder.
    Uses exponential backoff for 403/429 errors.
    """
    for attempt in range(5):
        try:
            service.permissions().delete(fileId=file_id, permissionId=permission_id).execute()
            return True
        except HttpError as e:
            status = e.resp.status if hasattr(e, 'resp') else None
            # If rate-limited or temporarily forbidden, wait and retry
            if status in (403, 429):
                sleep_time = (2 ** attempt) + (0.2 * attempt)
                print(f"    → Rate‐limited or forbidden ({status}), sleeping {sleep_time:.1f}s then retrying...")
                time.sleep(sleep_time)
                continue
            else:
                print(f"    [!] Failed to delete permission {permission_id} on {file_id}: {e}")
                return False
    print(f"    [!] Giving up on deleting permission {permission_id} for {file_id} after multiple retries.")
    return False


def traverse_and_strip(service, folder_id, target_emails, removed_log):
    """
    Recursively traverse every item under folder_id (including that folder itself),
    remove any permissions belonging to any email in target_emails, and record
    what was removed into removed_log (a list of dicts).
    
    removed_log entries will look like:
      {
        'item_id': '1A2B3C4D...',
        'item_name': 'Report.pdf',
        'item_type': 'file' or 'folder',
        'removed_permission_id': '0172ABCDEF...',
        'removed_email': 'alice@example.com',
        'role': 'reader' or 'writer'
      }
    """
    # 1) Remove permissions on THIS folder itself
    perms = list_permissions(service, folder_id)
    for p in perms:
        email = p.get('emailAddress')
        perm_id = p.get('id')
        role = p.get('role')
        if email and email.lower() in [e.lower() for e in target_emails]:
            success = delete_permission(service, folder_id, perm_id)
            if success:
                removed_log.append({
                    'item_id': folder_id,
                    'item_name': service.files().get(fileId=folder_id, fields='name').execute().get('name'),
                    'item_type': 'folder',
                    'removed_permission_id': perm_id,
                    'removed_email': email,
                    'role': role
                })
                print(f"  • Removed {email} ({role}) from folder '{removed_log[-1]['item_name']}' (ID: {folder_id})")

    # 2) List all direct children (files and folders) of this folder
    page_token = None
    while True:
        try:
            response = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields='nextPageToken, files(id, name, mimeType)',
                pageToken=page_token
            ).execute()
        except HttpError as e:
            print(f"[!] Error listing children of {folder_id}: {e}")
            return

        for item in response.get('files', []):
            item_id = item['id']
            item_name = item['name']
            mime_type = item['mimeType']

            if mime_type == 'application/vnd.google-apps.folder':
                # It's a subfolder: recurse
                traverse_and_strip(service, item_id, target_emails, removed_log)
            else:
                # It's a file: remove perms if any match
                file_perms = list_permissions(service, item_id)
                for fp in file_perms:
                    email = fp.get('emailAddress')
                    perm_id = fp.get('id')
                    role = fp.get('role')
                    if email and email.lower() in [e.lower() for e in target_emails]:
                        success = delete_permission(service, item_id, perm_id)
                        if success:
                            removed_log.append({
                                'item_id': item_id,
                                'item_name': item_name,
                                'item_type': 'file',
                                'removed_permission_id': perm_id,
                                'removed_email': email,
                                'role': role
                            })
                            print(f"  • Removed {email} ({role}) from file '{item_name}' (ID: {item_id})")

        page_token = response.get('nextPageToken')
        if not page_token:
            break


def main():
    service = authenticate()
    print(f"\n→ Starting recursive permission-stripping under folder ID: {ROOT_FOLDER_ID}\n")

    removed_log = []  # will hold dicts describing each removal
    traverse_and_strip(service, ROOT_FOLDER_ID, TARGET_EMAILS, removed_log)

    # After traversal, print a summary
    print("\n=== PERMISSION REMOVAL SUMMARY ===")
    if not removed_log:
        print("No matching permissions were found or removed.")
    else:
        # Group by item_type for clarity
        folders_removed = [e for e in removed_log if e['item_type'] == 'folder']
        files_removed   = [e for e in removed_log if e['item_type'] == 'file']
        print(f"Total folders updated: {len(folders_removed)}")
        for entry in folders_removed:
            print(f"  • Folder: {entry['item_name']} (ID: {entry['item_id']})  → removed '{entry['removed_email']}' as {entry['role']}")
        print(f"\nTotal files updated:   {len(files_removed)}")
        for entry in files_removed:
            print(f"  • File:   {entry['item_name']} (ID: {entry['item_id']})  → removed '{entry['removed_email']}' as {entry['role']}")

    print("\nDone.")

if __name__ == '__main__':
    main()
