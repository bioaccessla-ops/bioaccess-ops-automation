# src/permission_manager.py
import logging
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime
from src.config import REVERSE_ROLE_MAP, ROLE_MAP
from src.report_generator import generate_permission_report

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
            
            if (p.get('type') == p_type and
                permission_address.lower() == p_address.lower() and
                p.get('role') == p_role_api):
                return p.get('id')
                
    except HttpError as e:
        logging.error(f"Could not list permissions for file {file_id}: {e}")
    return None

def _permission_to_canonical(permission_row):
    """
    Converts a permission row (from a report DataFrame) into a canonical tuple.
    Used for set comparison in rollback. Assumes Role is API format.
    """
    item_id = str(permission_row['Item ID']) # Ensure string
    p_type = str(permission_row['Principal Type']).lower()
    p_address = str(permission_row['Email Address']).lower()
    
    if p_type == 'anyone':
        p_address = 'anyone' # Canonical address for 'anyone'
    
    p_role_api = str(permission_row['Role']).lower()
    root_folder_id = str(permission_row.get('Root Folder ID', 'N/A_RootID_FromCanonical')) 

    return (item_id, p_type, p_address, p_role_api, root_folder_id)


def generate_rollback_actions(drive_service, root_folder_id, audit_log_path):
    """
    Compares current Drive permissions with a backup (from an audit log) and generates inverse actions.
    Returns a list of action dictionaries formatted for the Excel columns.
    """
    logging.info(f"Generating rollback actions from audit log: {audit_log_path}")

    # 1. Get current live permissions from Drive (returns UI roles)
    current_report_data_ui_roles = generate_permission_report(drive_service, root_folder_id)
    current_df_ui_roles = pd.DataFrame(current_report_data_ui_roles).fillna('')

    # Convert current roles from UI to API for canonical comparison
    current_df_ui_roles['Role_API'] = current_df_ui_roles['Role'].apply(lambda x: REVERSE_ROLE_MAP.get(x, x)).str.lower()
    current_permissions_set = {_permission_to_canonical(row) for _, row in current_df_ui_roles.iterrows()}


    # 2. Read the audit log (which contains the original changes)
    try:
        audit_log_df = pd.read_csv(audit_log_path).fillna('')
        successful_actions_df = audit_log_df[audit_log_df['Status'] == 'SUCCESS'].copy()
    except FileNotFoundError:
        logging.error(f"Audit log file not found: {audit_log_path}")
        return []
    except Exception as e:
        logging.error(f"Failed to read audit log file {audit_log_path}: {e}")
        return []

    actions_to_perform = []

    for _, action_log_entry in successful_actions_df.iterrows():
        item_id = str(action_log_entry['Item ID'])
        original_command = str(action_log_entry['Action_Command'])
        
        # Original details from the log
        original_principal_type_ui = str(action_log_entry['Original_Principal_Type'])
        original_email_address = str(action_log_entry['Original_Email_Address'])
        original_role_ui = str(action_log_entry['Original_Role'])
        
        # New details from the log (for ADD/MODIFY)
        new_principal_type_ui = str(action_log_entry['New_Principal_Type'])
        new_email_address = str(action_log_entry['New_Email_Address'])
        new_role_ui = str(action_log_entry['New_Role'])

        # Prepare base dictionary for the rollback action, matching Excel columns
        rollback_action_dict = {
            'Item ID': item_id,
            'Full Path': '', # For Excel structure
            'Item Name': '',
            'Role': '', # Will be set by action type
            'Principal Type': '', # Will be set by action type
            'Email Address': '', # Will be set by action type
            'Owner': '',
            'Google Drive URL': '',
            'Root Folder ID': root_folder_id, # Pass root_folder_id to the action dict
            'Action_Type': '', # Set below
            'New_Role': '', # Set below
            'Type (for ADD)': '', # Set below
            'Email/Domain (for ADD)': '' # Set below
        }

        if original_command == 'ADD':
            # To rollback an ADD, we REMOVE what was added
            rollback_action_dict['Action_Type'] = 'REMOVE'
            rollback_action_dict['Principal Type'] = new_principal_type_ui
            rollback_action_dict['Email Address'] = new_email_address
            rollback_action_dict['Role'] = new_role_ui # Role to remove is the one that was added
            logging.info(f"Rollback: Identified REMOVE action for ADD of {new_email_address} ({new_role_ui}) on {item_id}")

        elif original_command == 'REMOVE':
            # To rollback a REMOVE, we ADD what was removed
            rollback_action_dict['Action_Type'] = 'ADD'
            rollback_action_dict['New_Role'] = original_role_ui # Role to add back
            rollback_action_dict['Type (for ADD)'] = original_principal_type_ui
            rollback_action_dict['Email/Domain (for ADD)'] = original_email_address
            logging.info(f"Rollback: Identified ADD action for REMOVE of {original_email_address} ({original_role_ui}) on {item_id}")

        elif original_command == 'MODIFY':
            # To rollback a MODIFY, we MODIFY back to the original role
            rollback_action_dict['Action_Type'] = 'MODIFY'
            rollback_action_dict['Principal Type'] = original_principal_type_ui
            rollback_action_dict['Email Address'] = original_email_address
            rollback_action_dict['Role'] = new_role_ui # Old role for rollback is the new role that was set
            rollback_action_dict['New_Role'] = original_role_ui # New role for rollback is the original role
            logging.info(f"Rollback: Identified MODIFY action for {original_email_address} from {new_role_ui} back to {original_role_ui} on {item_id}")

        actions_to_perform.append(rollback_action_dict)

    return actions_to_perform


def process_changes(drive_service, input_excel_path=None, dry_run=True, actions_list=None):
    """
    Reads an Excel file or processes a list of actions and applies changes.
    Returns a list of audit dictionaries and the root_folder_id found (or 'N/A').
    """
    if not dry_run:
        logging.warning("--- Starting Live Mode: Changes WILL be applied to Google Drive. ---")

    audit_trail = []
    root_folder_id_found = 'N/A_RootID_FromProcess'

    if actions_list is not None:
        action_df = pd.DataFrame(actions_list).fillna('')
        action_df['Item ID'] = action_df['Item ID'].astype(str)
        if 'Root Folder ID' in action_df.columns and not action_df.empty:
            root_folder_id_found = str(action_df['Root Folder ID'].iloc[0])

    else:
        try:
            df = pd.read_excel(input_excel_path).fillna('')
        except FileNotFoundError:
            logging.error(f"Input file not found: {input_excel_path}")
            return audit_trail, root_folder_id_found
        except Exception as e:
            logging.error(f"Failed to read Excel file {input_excel_path}: {e}")
            return audit_trail, root_folder_id_found

        if 'Root Folder ID' in df.columns and not df.empty:
            root_folder_id_found = str(df['Root Folder ID'].iloc[0])

        action_df = df[df['Action_Type'] != ''].copy()

    if action_df.empty:
        logging.info("No actions found to process.")
        return audit_trail, root_folder_id_found

    logging.info(f"Found {len(action_df)} actions to process.")

    for index, row in action_df.iterrows():
        command = str(row.get('Action_Type')).upper()
        item_id = str(row.get('Item ID'))
        
        current_audit_entry = {
            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Root Folder ID': root_folder_id_found,
            'Item ID': item_id,
            'Action_Command': command,
            'Status': 'PENDING',
            'Details': ''
        }
        current_audit_entry['Original_Principal_Type'] = str(row.get('Principal Type', ''))
        current_audit_entry['Original_Email_Address'] = str(row.get('Email Address', ''))
        current_audit_entry['Original_Role'] = str(row.get('Role', ''))
        current_audit_entry['New_Principal_Type'] = str(row.get('Type (for ADD)', ''))
        current_audit_entry['New_Email_Address'] = str(row.get('Email/Domain (for ADD)', ''))
        current_audit_entry['New_Role'] = str(row.get('New_Role', ''))

        if dry_run:
            print(f"[DRY RUN] Would perform '{command}' on Item ID: {item_id}")
            current_audit_entry['Status'] = 'DRY_RUN'
            current_audit_entry['Details'] = "Action simulated in dry run."
            audit_trail.append(current_audit_entry)
            continue

        try:
            if command == 'ADD':
                p_type = str(row.get('Type (for ADD)')).lower()
                p_address = str(row.get('Email/Domain (for ADD)'))
                p_role_ui = str(row.get('New_Role'))
                p_role_api = REVERSE_ROLE_MAP.get(p_role_ui.strip().title())

                if not all([item_id, p_type, p_address, p_role_api]):
                    current_audit_entry['Status'] = 'SKIPPED'
                    current_audit_entry['Details'] = "Missing required info for ADD."
                    print(f"[SKIPPED] ADD action on row {index+2} is missing required info (Item ID, Type, Address, or New Role).")
                    audit_trail.append(current_audit_entry)
                    continue
                
                perm_body = {'type': p_type, 'role': p_role_api}
                if p_type in ['user', 'group']: perm_body['emailAddress'] = p_address
                elif p_type == 'domain': perm_body['domain'] = p_address
                
                drive_service.permissions().create(fileId=item_id, body=perm_body, sendNotificationEmail=False).execute()
                current_audit_entry['Status'] = 'SUCCESS'
                current_audit_entry['Details'] = f"Added {p_address} as {p_role_ui}."
                print(f"[SUCCESS] Performed ADD for '{p_address}' with role '{p_role_ui}' on Item ID: {item_id}")

            elif command == 'REMOVE':
                p_type = str(row.get('Principal Type')).lower()
                p_address = str(row.get('Email Address'))
                p_role_ui = str(row.get('Role'))
                p_role_api = REVERSE_ROLE_MAP.get(p_role_ui.strip().title())
                
                if not all([item_id, p_type, p_address, p_role_api]):
                    current_audit_entry['Status'] = 'SKIPPED'
                    current_audit_entry['Details'] = "Missing required info for REMOVE."
                    print(f"[SKIPPED] REMOVE action on row {index+2} is missing required info.")
                    audit_trail.append(current_audit_entry)
                    continue

                permission_id = _find_permission_id(drive_service, item_id, p_type, p_address, p_role_api)
                if permission_id:
                    drive_service.permissions().delete(fileId=item_id, permissionId=permission_id).execute()
                    current_audit_entry['Status'] = 'SUCCESS'
                    current_audit_entry['Details'] = f"Removed {p_address} as {p_role_ui}."
                    print(f"[SUCCESS] Performed REMOVE for '{p_address}' with role '{p_role_ui}' on Item ID: {item_id}")
                else:
                    current_audit_entry['Status'] = 'SKIPPED'
                    current_audit_entry['Details'] = f"Permission not found for {p_address} with role {p_role_ui}."
                    print(f"[SKIPPED] Could not find permission for '{p_address}' with role '{p_role_ui}' to remove on Item ID: {item_id}")

            elif command == 'MODIFY':
                p_type = str(row.get('Principal Type')).lower()
                p_address = str(row.get('Email Address'))
                old_role_ui = str(row.get('Role'))
                new_role_ui = str(row.get('New_Role'))
                
                old_role_api = REVERSE_ROLE_MAP.get(old_role_ui.strip().title())
                new_role_api = REVERSE_ROLE_MAP.get(new_role_ui.strip().title())

                if not new_role_api:
                    current_audit_entry['Status'] = 'SKIPPED'
                    current_audit_entry['Details'] = f"Invalid New Role: '{new_role_ui}'."
                    print(f"[SKIPPED] MODIFY action on row {index+2} has an invalid New Role: '{new_role_ui}'.")
                    audit_trail.append(current_audit_entry)
                    continue
                if not old_role_api:
                    current_audit_entry['Status'] = 'SKIPPED'
                    current_audit_entry['Details'] = f"Invalid Old Role: '{old_role_ui}'."
                    print(f"[SKIPPED] MODIFY action on row {index+2} has an invalid Old Role: '{old_role_ui}'.")
                    audit_trail.append(current_audit_entry)
                    continue

                permission_id = _find_permission_id(drive_service, item_id, p_type, p_address, old_role_api)
                if permission_id:
                    drive_service.permissions().update(fileId=item_id, permissionId=permission_id, body={'role': new_role_api}).execute()
                    current_audit_entry['Status'] = 'SUCCESS'
                    current_audit_entry['Details'] = f"Modified {p_address} from {old_role_ui} to {new_role_ui}."
                    print(f"[SUCCESS] Performed MODIFY for '{p_address}' from '{old_role_ui}' to '{new_role_ui}' on Item ID: {item_id}")
                else:
                    current_audit_entry['Status'] = 'SKIPPED'
                    current_audit_entry['Details'] = f"Permission not found for {p_address} with role {old_role_ui} to modify."
                    print(f"[SKIPPED] Could not find permission for '{p_address}' with role '{old_role_ui}' to modify on Item ID: {item_id}")

        except HttpError as e:
            current_audit_entry['Status'] = 'ERROR'
            current_audit_entry['Details'] = f"API Error: {e}"
            print(f"[ERROR] Failed to perform '{command}' on Item ID: {item_id}. Reason: {e}")
        except Exception as e:
            current_audit_entry['Status'] = 'ERROR'
            current_audit_entry['Details'] = f"Unexpected Error: {e}"
            print(f"[ERROR] An unexpected error occurred for '{command}' on Item ID: {item_id}. Details: {e}")
        
        audit_trail.append(current_audit_entry)
    
    return audit_trail, root_folder_id_found