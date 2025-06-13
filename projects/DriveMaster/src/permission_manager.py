# src/permission_manager.py
import logging
import pandas as pd
from googleapiclient.errors import HttpError

# Replace the existing _find_permission_id function with this one.

def _find_permission_id(drive_service, file_id, p_type, p_address, p_role):
    """
    Helper function to find the ID of a specific permission that matches
    the type, address (email/domain), and role. This is now case-insensitive.
    """
    try:
        permissions = drive_service.permissions().list(
            fileId=file_id,
            fields='permissions(id,type,emailAddress,domain,role)'
        ).execute()

        for p in permissions.get('permissions', []):
            address_key = 'emailAddress' if p.get('type') in ['user', 'group'] else 'domain'
            
            # Get the address from the permission, or an empty string if it's not there
            permission_address = p.get(address_key, '')
            
            # Check for a match, ignoring case
            if (p.get('type') == p_type and
                permission_address.lower() == p_address.lower() and
                p.get('role') == p_role):
                return p.get('id')
                
    except HttpError as e:
        logging.error(f"Could not list permissions for file {file_id}: {e}")
    return None

def process_changes(drive_service, input_csv_path, dry_run=True):
    """
    Reads a CSV file and processes the actions (ADD, REMOVE, MODIFY).
    """
    if not dry_run:
        logging.warning("--- Starting Live Mode: Changes WILL be applied to Google Drive. ---")

    try:
        df = pd.read_csv(input_csv_path)
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_csv_path}")
        return

    action_df = df[df['ACTION'].notna() & (df['ACTION'] != '')].copy()
    if action_df.empty:
        logging.info("No actions found in the specified file.")
        return

    logging.info(f"Found {len(action_df)} actions to process.")

    for index, row in action_df.iterrows():
        item_id = row['Item ID']
        action_str = row['ACTION']
        action_parts = action_str.split(':')
        command = action_parts[0].upper()

        if dry_run:
            print(f"[DRY RUN] Would perform '{action_str}' on Item ID: {item_id}")
            continue

        # --- LIVE MODE ---
        try:
            if command == 'ADD':
                p_type, p_address, p_role = action_parts[1], action_parts[2], action_parts[3]
                perm_body = {'type': p_type, 'role': p_role}
                if p_type in ['user', 'group']:
                    perm_body['emailAddress'] = p_address
                elif p_type == 'domain':
                    perm_body['domain'] = p_address
                
                drive_service.permissions().create(fileId=item_id, body=perm_body, sendNotificationEmail=False).execute()
                print(f"[SUCCESS] Performed '{action_str}' on Item ID: {item_id}")

            elif command == 'REMOVE':
                p_type, p_address, p_role = action_parts[1], action_parts[2], action_parts[3]
                permission_id = _find_permission_id(drive_service, item_id, p_type, p_address, p_role)
                if permission_id:
                    drive_service.permissions().delete(fileId=item_id, permissionId=permission_id).execute()
                    print(f"[SUCCESS] Performed '{action_str}' on Item ID: {item_id}")
                else:
                    print(f"[SKIPPED] Could not find permission for '{p_address}' with role '{p_role}' to remove on Item ID: {item_id}")

            elif command == 'MODIFY':
                p_type, p_address, old_role, new_role = action_parts[1], action_parts[2], action_parts[3], action_parts[4]
                permission_id = _find_permission_id(drive_service, item_id, p_type, p_address, old_role)
                if permission_id:
                    drive_service.permissions().update(fileId=item_id, permissionId=permission_id, body={'role': new_role}).execute()
                    print(f"[SUCCESS] Performed '{action_str}' on Item ID: {item_id}")
                else:
                    print(f"[SKIPPED] Could not find permission for '{p_address}' with role '{old_role}' to modify on Item ID: {item_id}")

        except HttpError as e:
            print(f"[ERROR] Failed to perform '{action_str}' on Item ID: {item_id}. Reason: {e}")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred for '{action_str}' on Item ID: {item_id}. Details: {e}")