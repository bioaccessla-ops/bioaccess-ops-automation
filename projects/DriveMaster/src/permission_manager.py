# src/permission_manager.py

import logging
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime
from src.config import REVERSE_ROLE_MAP, ROLE_MAP
from src.report_generator import generate_permission_report

def _find_permission_id(drive_service, file_id, p_type, p_address, p_role_api):
    """Finds the permission ID for a given principal and role."""
    try:
        permissions = drive_service.permissions().list(fileId=file_id, fields='permissions(id,type,emailAddress,domain,role)').execute()
        for p in permissions.get('permissions', []):
            address_key = 'emailAddress' if p.get('type') in ['user', 'group'] else 'domain'
            permission_address = p.get(address_key, '')
            if (p.get('type') == p_type and permission_address.lower() == p_address.lower() and p.get('role') == p_role_api):
                return p.get('id')
    except HttpError as e:
        logging.error(f"Could not list permissions for file {file_id}: {e}")
    return None

def generate_rollback_actions(drive_service, root_folder_id, audit_log_path):
    """Generates inverse actions for rollback."""
    logging.info(f"Generating rollback actions from audit log: {audit_log_path}")
    try:
        audit_log_df = pd.read_csv(audit_log_path).fillna('')
        successful_actions_df = audit_log_df[audit_log_df['Status'] == 'SUCCESS'].copy()
    except Exception as e:
        logging.error(f"Failed to read or parse audit log file {audit_log_path}: {e}")
        return []
    
    if successful_actions_df.empty:
        logging.info("No successful actions found in the log to roll back.")
        return []

    current_report_data = generate_permission_report(drive_service, root_folder_id)
    item_metadata_map = {item['Item ID']: {'Item Name': item['Item Name'], 'Full Path': item['Full Path']} for item in current_report_data}

    actions_to_perform = []
    for _, log_entry in successful_actions_df.iterrows():
        item_id = str(log_entry['Item ID'])
        original_command = str(log_entry['Action_Command'])
        metadata = item_metadata_map.get(item_id, {'Item Name': 'N/A', 'Full Path': 'N/A'})

        rollback_action = {
            'Item ID': item_id, 'Full Path': metadata['Full Path'], 'Item Name': metadata['Item Name'],
            'Role': '', 'Principal Type': '', 'Email Address': '',
            'Action_Type': '', 'New_Role': '', 'Type (for ADD)': '', 'Email/Domain (for ADD)': '',
            'Restrict Download': '', 'Root Folder ID': root_folder_id
        }

        if original_command == 'ADD':
            rollback_action.update({'Action_Type': 'REMOVE', 'Principal Type': log_entry['New_Principal_Type'], 'Email Address': log_entry['New_Email_Address'], 'Role': log_entry['New_Role']})
            actions_to_perform.append(rollback_action)
        elif original_command == 'REMOVE':
            rollback_action.update({'Action_Type': 'ADD', 'New_Role': log_entry['Original_Role'], 'Type (for ADD)': log_entry['Original_Principal_Type'], 'Email/Domain (for ADD)': log_entry['Original_Email_Address']})
            actions_to_perform.append(rollback_action)
        elif original_command == 'MODIFY':
            rollback_action.update({'Action_Type': 'MODIFY', 'Principal Type': log_entry['New_Principal_Type'], 'Email Address': log_entry['New_Email_Address'], 'Role': log_entry['New_Role'], 'New_Role': log_entry['Original_Role']})
            actions_to_perform.append(rollback_action)
        elif original_command == 'SET_DOWNLOAD_RESTRICTION':
            # This action now needs to be associated with a principal to be reversed correctly.
            # We will generate one rollback action per principal affected.
            rollback_action['Restrict Download'] = str(log_entry['Original_Role'])
            rollback_action['Principal Type'] = log_entry['Original_Principal_Type']
            rollback_action['Email Address'] = log_entry['Original_Email_Address']
            actions_to_perform.append(rollback_action)
            
    return actions_to_perform


def process_changes(drive_service, input_excel_path=None, dry_run=True, actions_list=None):
    if not dry_run: logging.warning("--- Starting Live Mode: Changes WILL be applied to Google Drive. ---")

    audit_trail = []
    df, root_folder_id_found = None, None

    # Load data from either the action list (for rollback) or an Excel file
    if actions_list is not None:
        df = pd.DataFrame(actions_list).fillna('')
        if not df.empty: root_folder_id_found = str(df.iloc[0].get('Root Folder ID', ''))
    else:
        try:
            df = pd.read_excel(input_excel_path, dtype=str).fillna('')
            if 'Root Folder ID' not in df.columns or df.empty: raise ValueError("Input file is missing 'Root Folder ID' column or is empty.")
            root_folder_id_found = str(df.iloc[0]['Root Folder ID'])
        except Exception as e:
            logging.error(f"Failed to read or validate Excel file {input_excel_path}: {e}"); return [], 'N/A_RootID_FromProcess'

    if not root_folder_id_found:
        logging.error("Could not determine Root Folder ID from the input. Aborting."); return [], 'N/A_RootID_FromProcess'

    logging.info("Fetching current file states from Google Drive for comparison...")
    original_report_df = pd.DataFrame(generate_permission_report(drive_service, root_folder_id_found))
    
    # --- Step 1: Process File-Level Property Changes ---
    if 'Restrict Download' in df.columns and not original_report_df.empty:
        logging.info("Analyzing 'Restrict Download' settings...")
        original_map = original_report_df.drop_duplicates(subset=['Item ID']).set_index('Item ID')['Restrict Download'].to_dict()
        desired_map = {}
        for item_id, group in df.groupby('Item ID'):
            restrictions = [str(val).strip().upper() for val in group['Restrict Download'].tolist() if str(val).strip()]
            if 'TRUE' in restrictions: desired_map[item_id] = 'TRUE'
            elif 'FALSE' in restrictions: desired_map[item_id] = 'FALSE'
        
        for item_id, desired_str in desired_map.items():
            original_str = str(original_map.get(item_id, 'N/A')).upper()
            if desired_str != original_str:
                # A change is detected. Perform the API call ONCE.
                final_status, details = 'PENDING', ''
                if dry_run:
                    details = f"Set Restrict Download from '{original_str}' to '{desired_str}'"
                    print(f"[DRY RUN] {details} for Item ID: {item_id}")
                    final_status = 'DRY_RUN'
                else:
                    try:
                        drive_service.files().update(fileId=item_id, body={'copyRequiresWriterPermission': (desired_str == 'TRUE')}).execute()
                        details = f"Set Restrict Download from '{original_str}' to '{desired_str}'"
                        print(f"[SUCCESS] {details} for Item ID: {item_id}")
                        final_status = 'SUCCESS'
                    except HttpError as e:
                        details = str(e)
                        print(f"[ERROR] Failed to set restriction for {item_id}: {e}")
                        final_status = 'ERROR'
                
                # *** MODIFIED: Create a separate log entry for EACH permission on the affected file ***
                permission_rows = df[df['Item ID'] == item_id]
                for _, p_row in permission_rows.iterrows():
                    entry = {
                        'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Root Folder ID': root_folder_id_found,
                        'Full Path': p_row.get('Full Path', ''), 'Item Name': p_row.get('Item Name', ''), 'Item ID': item_id,
                        'Action_Command': 'SET_DOWNLOAD_RESTRICTION', 'Status': final_status, 'Details': details,
                        'Original_Principal_Type': p_row.get('Principal Type', ''),
                        'Original_Email_Address': p_row.get('Email Address', ''),
                        'Original_Role': original_str, 'New_Role': desired_str,
                        'New_Principal_Type': '', 'New_Email_Address': ''
                    }
                    audit_trail.append(entry)

    # --- Step 2: Process Permission-Level Changes ---
    logging.info("Analyzing permission actions (ADD/REMOVE/MODIFY)...")
    action_df = df[df['Action_Type'].str.strip() != ''].copy()
    for index, row in action_df.iterrows():
        cmd = str(row.get('Action_Type')).strip().upper(); item_id = str(row.get('Item ID'))
        entry = {'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Root Folder ID': root_folder_id_found, 'Full Path': row.get('Full Path', ''), 'Item Name': row.get('Item Name', ''), 
                 'Item ID': item_id, 'Action_Command': cmd, 'Status': 'DRY_RUN' if dry_run else 'PENDING', 'Details': '', 'Original_Principal_Type': str(row.get('Principal Type', '')), 
                 'Original_Email_Address': str(row.get('Email Address', '')), 'Original_Role': str(row.get('Role', '')), 'New_Principal_Type': str(row.get('Type (for ADD)', '')), 
                 'New_Email_Address': str(row.get('Email/Domain (for ADD)', '')), 'New_Role': str(row.get('New_Role', '')) }
        if dry_run:
            print(f"[DRY RUN] Would perform '{cmd}' for '{entry['New_Email_Address'] or entry['Original_Email_Address']}' on Item ID: {item_id}")
            audit_trail.append(entry); continue
        try:
            if cmd == 'ADD':
                p_type, p_address, p_role_ui = str(row.get('Type (for ADD)')).lower(), str(row.get('Email/Domain (for ADD)')), str(row.get('New_Role'))
                p_role_api = REVERSE_ROLE_MAP.get(p_role_ui.strip().title())
                if not all([p_type, p_address, p_role_api]): raise ValueError(f"Missing info for ADD on row {index+2}.")
                drive_service.permissions().create(fileId=item_id, body={'type': p_type, 'role': p_role_api, 'emailAddress' if p_type in ['user', 'group'] else 'domain': p_address}, sendNotificationEmail=False).execute()
                entry['Details'] = f"Added {p_address} as {p_role_ui}."
            elif cmd == 'REMOVE':
                p_type, p_address, p_role_ui = str(row.get('Principal Type')).lower(), str(row.get('Email Address')), str(row.get('Role'))
                p_role_api = REVERSE_ROLE_MAP.get(p_role_ui.strip().title())
                if not all([p_type, p_address, p_role_api]): raise ValueError(f"Missing info for REMOVE on row {index+2}.")
                pid = _find_permission_id(drive_service, item_id, p_type, p_address, p_role_api)
                if pid:
                    drive_service.permissions().delete(fileId=item_id, permissionId=pid).execute()
                    entry['Details'] = f"Removed {p_address} as {p_role_ui}."
                else: raise ValueError(f"Permission not found for {p_address} with role {p_role_ui} to remove.")
            elif cmd == 'MODIFY':
                p_type, p_address, old_ui, new_ui = str(row.get('Principal Type')).lower(), str(row.get('Email Address')), str(row.get('Role')), str(row.get('New_Role'))
                old_api, new_api = REVERSE_ROLE_MAP.get(old_ui.strip().title()), REVERSE_ROLE_MAP.get(new_ui.strip().title())
                if not all([p_type, p_address, old_api, new_api]): raise ValueError(f"Missing/invalid role info for MODIFY on row {index+2}.")
                pid = _find_permission_id(drive_service, item_id, p_type, p_address, old_api)
                if pid:
                    drive_service.permissions().update(fileId=item_id, permissionId=pid, body={'role': new_api}).execute()
                    entry['Details'] = f"Modified {p_address} from {old_ui} to {new_ui}."
                else: raise ValueError(f"Permission not found for {p_address} with role {old_ui} to modify.")
            entry['Status'] = 'SUCCESS'; print(f"[SUCCESS] Performed {cmd} for '{p_address or entry.get('New_Email_Address')}' on Item ID: {item_id}")
        except (ValueError, HttpError) as e:
            entry['Status'] = 'ERROR' if isinstance(e, HttpError) else 'SKIPPED'; entry['Details'] = str(e)
            print(f"[{entry['Status']}] {cmd} on Item ID: {item_id}. Reason: {e}")
        audit_trail.append(entry)

    if not audit_trail: logging.info("No changes were detected between the input file and the current Drive state.")
    return audit_trail, root_folder_id_found