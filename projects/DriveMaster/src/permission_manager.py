# src/permission_manager.py
import logging
import pandas as pd
from googleapiclient.errors import HttpError
from src.config import REVERSE_ROLE_MAP, ROLE_MAP # Added ROLE_MAP
from src.report_generator import generate_permission_report # Import to get current state

def _find_permission_id(drive_service, file_id, p_type, p_address, p_role_api):
    """
    Helper function to find the ID of a specific permission that matches
    the type, address (email/domain), and role. This is case-insensitive.
    """
    try:
        permissions = drive_service.permissions().list(
            fileId=file_id, fields='permissions(id,type,emailAddress,domain,role)').execute()

        for p in permissions.get('permissions', []):
            address_key = 'emailAddress' if p.get('type') in ['user', 'group'] else 'domain'
            permission_address = p.get(address_key, '')
            
            # Check for a perfect match (type, address, and role)
            if (p.get('type') == p_type and
                permission_address.lower() == p_address.lower() and
                p.get('role') == p_role_api):
                return p.get('id')
                
    except HttpError as e:
        logging.error(f"Could not list permissions for file {file_id}: {e}")
    return None

def _permission_to_canonical(permission_row, is_api_role=False):
    """
    Converts a permission row from a report DataFrame into a canonical tuple.
    Used for set comparison in rollback.
    """
    item_id = permission_row['Item ID']
    p_type = str(permission_row['Principal Type']).lower()
    p_address = str(permission_row['Email Address']).lower()
    
    # Handle 'anyone' type specifically, as it doesn't have a real email/domain
    if p_type == 'anyone':
        p_address = 'anyone'

    # Get the role in API format for canonical comparison
    if is_api_role:
        p_role = str(permission_row['Role']).lower() # Assumes Role column contains API role
    else:
        # Report provides UI role, convert to API role
        p_role = REVERSE_ROLE_MAP.get(str(permission_row['Role']).strip().title(), '').lower()
    
    return (item_id, p_type, p_address, p_role)


def generate_rollback_actions(drive_service, root_folder_id, backup_csv_path):
    """
    Compares current Drive permissions with a backup and generates inverse actions.
    Returns a list of action dictionaries suitable for process_changes.
    """
    logging.info(f"Generating rollback actions from backup: {backup_csv_path}")

    # 1. Get current live permissions from Drive
    current_report_data = generate_permission_report(drive_service, root_folder_id)
    current_df = pd.DataFrame(current_report_data).fillna('') # Fill NaN for consistent comparison
    current_permissions_set = {_permission_to_canonical(row) for _, row in current_df.iterrows()}

    # 2. Read backup permissions from CSV
    try:
        backup_df = pd.read_csv(backup_csv_path).fillna('')
        # For backup, the 'Role' column is the UI role, convert to API for canonical
        backup_permissions_set = {_permission_to_canonical(row) for _, row in backup_df.iterrows()}
    except FileNotFoundError:
        logging.error(f"Backup file not found: {backup_csv_path}")
        return []
    except Exception as e:
        logging.error(f"Failed to read backup file {backup_csv_path}: {e}")
        return []

    actions_to_perform = []

    # 3. Identify permissions to REMOVE (exist now, but shouldn't be in backup)
    for perm_tuple in current_permissions_set - backup_permissions_set:
        item_id, p_type, p_address, p_role_api = perm_tuple
        
        # Convert API role back to UI role for the action string
        p_role_ui = ROLE_MAP.get(p_role_api, p_role_api.capitalize())
        
        actions_to_perform.append({
            'item_id': item_id,
            'action_command': 'REMOVE',
            'parts': [p_type, p_address, p_role_ui] # REMOVE action string needs UI role
        })
        logging.info(f"Rollback: Identified REMOVE action for {p_address} ({p_role_ui}) on {item_id}")

    # 4. Identify permissions to ADD (should be in backup, but don't exist now)
    for perm_tuple in backup_permissions_set - current_permissions_set:
        item_id, p_type, p_address, p_role_api = perm_tuple
        
        # Convert API role back to UI role for the action string
        p_role_ui = ROLE_MAP.get(p_role_api, p_role_api.capitalize())

        actions_to_perform.append({
            'item_id': item_id,
            'action_command': 'ADD',
            'parts': [p_type, p_address, p_role_ui] # ADD action string needs UI role
        })
        logging.info(f"Rollback: Identified ADD action for {p_address} ({p_role_ui}) on {item_id}")

    return actions_to_perform


def process_changes(drive_service, input_excel_path, dry_run=True):
    """
    Reads an Excel file and processes actions based on the new Action Builder columns.
    """
    if not dry_run:
        logging.warning("--- Starting Live Mode: Changes WILL be applied to Google Drive. ---")

    try:
        df = pd.read_excel(input_excel_path).fillna('') # Use fillna to treat blank cells as empty strings
    except FileNotFoundError:
        logging.error(f"Input file not found: {input_excel_path}")
        return
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
                p_type = str(row.get('Type (for ADD)')).lower()
                p_address = str(row.get('Email/Domain (for ADD)'))
                p_role_ui = str(row.get('New_Role'))
                p_role_api = REVERSE_ROLE_MAP.get(p_role_ui.strip().title())

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

                if not new_role_api: # Old_role_api can be ignored if new_role_api is invalid
                    print(f"[SKIPPED] MODIFY action on row {index+2} has an invalid New Role: '{new_role_ui}'.")
                    continue
                if not old_role_api:
                    print(f"[SKIPPED] MODIFY action on row {index+2} has an invalid Old Role: '{old_role_ui}'.")
                    continue

                permission_id = _find_permission_id(drive_service, item_id, p_type, p_address, old_role_api)
                if permission_id:
                    drive_service.permissions().update(fileId=item_id, permissionId=permission_id, body={'role': new_role_api}).execute()
                    print(f"[SUCCESS] Performed MODIFY for '{p_address}' from '{old_role_ui}' to '{new_role_ui}' on Item ID: {item_id}")
                else:
                    print(f"[SKIPPED] Could not find permission for '{p_address}' with role '{old_role_ui}' to modify on Item ID: {item_id}")

        except HttpError as e:
            print(f"[ERROR] Failed to perform '{command}' on Item ID: {item_id}. Reason: {e}")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred for '{command}' on Item ID: {item_id}. Details: {e}")