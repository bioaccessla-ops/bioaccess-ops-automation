# src/permission_manager.py
import logging # <-- THIS LINE WAS MISSING
import pandas as pd
from googleapiclient.errors import HttpError
from src.config import REVERSE_ROLE_MAP

def _find_permission_id(drive_service, file_id, p_type, p_address, p_role_api):
    """
    Helper function to find the ID of a specific permission that matches
    the type, address (email/domain), and role. This is now case-insensitive.
    """
    try:
        permissions = drive_service.permissions().list(
            fileId=file_id, fields='permissions(id,type,emailAddress,domain,role)').execute()
        for p in permissions.get('permissions', []):
            address_key = 'emailAddress' if p.get('type') in ['user', 'group'] else 'domain'
            permission_address = p.get(address_key, '')
            if (p.get('type') == p_type and
                permission_address.lower() == p_address.lower() and
                p.get('role') == p_role_api):
                return p.get('id')
    except HttpError as e:
        logging.error(f"Could not list permissions for file {file_id}: {e}")
    return None

def process_changes(drive_service, input_excel_path, dry_run=True):
    """
    Reads an Excel file and processes actions based on the new Action Builder columns.
    """
    if not dry_run:
        logging.warning("--- Starting Live Mode: Changes WILL be applied to Google Drive. ---")

    try:
        df = pd.read_excel(input_excel_path).fillna('') # Use fillna to treat blank cells as empty strings
    except Exception as e:
        logging.error(f"Failed to read Excel file {input_excel_path}: {e}")
        return

    # Filter for rows where an 'Action_Type' has been selected
    action_df = df[df['Action_Type'] != ''].copy()
    if action_df.empty:
        logging.info("No actions found in the specified file.")
        return

    logging.info(f"Found {len(action_df)} actions to process.")

    for index, row in action_df.iterrows():
        command = str(row.get('Action_Type')).upper()
        item_id = row.get('Item ID')

        if dry_run:
            print(f"[DRY RUN] Would perform '{command}' on Item ID: {item_id}")
            continue

        # --- LIVE MODE ---
        try:
            if command == 'ADD':
                new_role_ui = str(row.get('New_Role'))
                p_type = str(row.get('Add_Principal_Type')).lower()
                p_address = str(row.get('Add_Principal_Address'))
                p_role_api = REVERSE_ROLE_MAP.get(new_role_ui.strip().title())

                if not all([item_id, p_type, p_address, p_role_api]):
                    print(f"[SKIPPED] ADD action on row {index+2} is missing required info (Item ID, Type, Address, or New Role).")
                    continue
                
                perm_body = {'type': p_type, 'role': p_role_api}
                if p_type in ['user', 'group']: perm_body['emailAddress'] = p_address
                elif p_type == 'domain': perm_body['domain'] = p_address
                
                drive_service.permissions().create(fileId=item_id, body=perm_body, sendNotificationEmail=False).execute()
                print(f"[SUCCESS] Performed ADD for '{p_address}' with role '{new_role_ui}' on Item ID: {item_id}")

            elif command == 'REMOVE':
                p_type = str(row.get('Principal Type')).lower()
                p_address = str(row.get('Email Address'))
                p_role_ui = str(row.get('Role'))
                p_role_api = REVERSE_ROLE_MAP.get(p_role_ui.strip().title())
                
                permission_id = _find_permission_id(drive_service, item_id, p_type, p_address, p_role_api)
                if permission_id:
                    drive_service.permissions().delete(fileId=item_id, permissionId=permission_id).execute()
                    print(f"[SUCCESS] Performed REMOVE for '{p_address}' with role '{p_role_ui}' on Item ID: {item_id}")
                else:
                    print(f"[SKIPPED] Could not find permission for '{p_address}' with role '{p_role_ui}' to remove on Item ID: {item_id}")

            elif command == 'MODIFY':
                p_type = str(row.get('Principal Type')).lower()
                p_address = str(row.get('Email Address'))
                old_role_ui = str(row.get('Role'))
                new_role_ui = str(row.get('New_Role'))
                
                old_role_api = REVERSE_ROLE_MAP.get(old_role_ui.strip().title())
                new_role_api = REVERSE_ROLE_MAP.get(new_role_ui.strip().title())

                if not new_role_api:
                    print(f"[SKIPPED] MODIFY action on row {index+2} is missing a valid New Role.")
                    continue

                permission_id = _find_permission_id(drive_service, item_id, p_type, p_address, old_role_api)
                if permission_id:
                    drive_service.permissions().update(fileId=item_id, permissionId=permission_id, body={'role': new_role_api}).execute()
                    print(f"[SUCCESS] Performed MODIFY for '{p_address}' from '{old_role_ui}' to '{new_role_ui}' on Item ID: {item_id}")
                else:
                    print(f"[SKIPPED] Could not find permission for '{p_address}' with role '{old_role_ui}' to modify on Item ID: {item_id}")

        except Exception as e:
            print(f"[ERROR] An unexpected error occurred for action on row {index+2}. Details: {e}")