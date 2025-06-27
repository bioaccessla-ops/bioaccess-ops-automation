# src/permission_manager.py

import logging
import pandas as pd
from googleapiclient.errors import HttpError
from datetime import datetime
from src.config import REVERSE_ROLE_MAP, ROLE_MAP
from src.report_generator import generate_permission_report

def _find_permission_id(drive_service, file_id, p_type, p_address, p_role_api):
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

def generate_rollback_actions(audit_log_path, live_report_data):
    """
    Reads an audit log and generates inverse actions using pre-fetched live data.
    """
    logging.info(f"Generating rollback actions from audit log: {audit_log_path}")
    try:
        audit_log_df = pd.read_csv(audit_log_path).fillna('')
        successful_actions_df = audit_log_df[audit_log_df['Status'] == 'SUCCESS'].copy()
    except Exception as e:
        logging.error(f"Failed to read or parse audit log file {audit_log_path}: {e}"); return []
    
    if successful_actions_df.empty:
        logging.info("No successful actions found in the log to roll back."); return []

    item_metadata_map = {item['Item ID']: {'Item Name': item['Item Name'], 'Full Path': item['Full Path']} for item in live_report_data}
    root_folder_id = live_report_data[0]['Root Folder ID'] if live_report_data else ''

    actions_to_perform = []
    for _, log_entry in successful_actions_df.iterrows():
        item_id, cmd = str(log_entry['Item ID']), str(log_entry['Action_Command'])
        metadata = item_metadata_map.get(item_id, {'Item Name': 'N/A', 'Full Path': 'N/A'})
        action = {'Item ID': item_id, 'Full Path': metadata['Full Path'], 'Item Name': metadata['Item Name'], 'Root Folder ID': root_folder_id}
        if cmd == 'ADD':
            action.update({'Action_Type': 'REMOVE', 'Principal Type': log_entry['New_Principal_Type'], 'Email Address': log_entry['New_Email_Address'], 'Role': log_entry['New_Role']})
            actions_to_perform.append(action)
        elif cmd == 'REMOVE':
            action.update({'Action_Type': 'ADD', 'New_Role': log_entry['Original_Role'], 'Type of account (for ADD)': log_entry['Original_Principal_Type'], 'Email/Domain (for ADD)': log_entry['Original_Email_Address']})
            actions_to_perform.append(action)
        elif cmd == 'MODIFY':
            action.update({'Action_Type': 'MODIFY', 'Principal Type': log_entry['Original_Principal_Type'], 'Email Address': log_entry['Original_Email_Address'], 'Role': log_entry['New_Role'], 'New_Role': log_entry['Original_Role']})
            actions_to_perform.append(action)
        elif cmd == 'SET_DOWNLOAD_RESTRICTION':
            action.update({'Restrict Download': str(log_entry['Original_Role']), 'Principal Type': log_entry['Original_Principal_Type'], 'Email Address': log_entry['Original_Email_Address']})
            actions_to_perform.append(action)
    return actions_to_perform

def process_changes(drive_service, input_excel_path=None, dry_run=True, actions_list=None, live_report_data=None):
    if not dry_run: logging.warning("--- Starting Live Mode: Changes WILL be applied to Google Drive. ---")

    audit_trail, df, root_folder_id = [], None, None

    if actions_list is not None:
        df = pd.DataFrame(actions_list).fillna(''); root_folder_id = df.iloc[0].get('Root Folder ID', '') if not df.empty else ''
    else:
        try:
            df = pd.read_excel(input_excel_path, dtype=str).fillna('')
            if 'Root Folder ID' not in df.columns or df.empty: raise ValueError("Input file missing 'Root Folder ID' or is empty.")
            root_folder_id = str(df.iloc[0]['Root Folder ID'])
        except Exception as e:
            logging.error(f"Failed to read or validate Excel file {input_excel_path}: {e}"); return [], 'N/A_RootID_FromProcess'

    if not root_folder_id:
        logging.error("Could not determine Root Folder ID. Aborting."); return [], 'N/A_RootID_FromProcess'

    if live_report_data is None:
        logging.info("Fetching current file states from Google Drive for comparison...")
        original_report_df = pd.DataFrame(generate_permission_report(drive_service, root_folder_id))
    else:
        logging.info("Using pre-fetched file state data for comparison...")
        original_report_df = pd.DataFrame(live_report_data)
    
    # ... The rest of the function for processing changes and permissions remains the same,
    # as it correctly uses the 'original_report_df' that is now passed in.
    # I am including the full logic for completeness.

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
                file_info = df[df['Item ID'] == item_id].iloc[0]
                details = f"Set Restrict Download from '{original_str}' to '{desired_str}'"
                permission_rows = df[df['Item ID'] == item_id]
                for _, p_row in permission_rows.iterrows():
                    entry = {'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Root Folder ID': root_folder_id, 'Full Path': p_row.get('Full Path', ''), 'Item Name': p_row.get('Item Name', ''), 'Item ID': item_id, 'Action_Command': 'SET_DOWNLOAD_RESTRICTION', 'Status': 'DRY_RUN' if dry_run else 'PENDING', 'Details': details, 'Original_Principal_Type': p_row.get('Principal Type', ''), 'Original_Email_Address': p_row.get('Email Address', ''), 'Original_Role': original_str, 'New_Role': desired_str, 'New_Principal_Type': '', 'New_Email_Address': ''}
                    if not dry_run: # Avoid multiple API calls in live mode, but generate full log
                        try:
                            if item_id not in [e['Item ID'] for e in audit_trail if e['Action_Command'] == 'SET_DOWNLOAD_RESTRICTION']:
                                drive_service.files().update(fileId=item_id, body={'copyRequiresWriterPermission': (desired_str == 'TRUE')}).execute()
                                print(f"[SUCCESS] {details} for Item ID: {item_id}")
                            entry['Status'] = 'SUCCESS'
                        except HttpError as e:
                            entry['Status'] = 'ERROR'; entry['Details'] = str(e); print(f"[ERROR] Failed to set restriction for {item_id}: {e}")
                    else: print(f"[DRY RUN] {details} for Item ID: {item_id}")
                    audit_trail.append(entry)

    logging.info("Analyzing permission actions (ADD/REMOVE/MODIFY)...")
    action_df = df[df['Action_Type'].str.strip() != ''].copy()
    for index, row in action_df.iterrows():
        cmd = str(row.get('Action_Type')).strip().upper(); item_id = str(row.get('Item ID'))
        entry = {'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Root Folder ID': root_folder_id, 'Full Path': row.get('Full Path', ''), 'Item Name': row.get('Item Name', ''), 'Item ID': item_id, 'Action_Command': cmd, 'Status': 'DRY_RUN' if dry_run else 'PENDING', 'Details': '', 'Original_Principal_Type': str(row.get('Principal Type', '')), 'Original_Email_Address': str(row.get('Email Address', '')), 'Original_Role': str(row.get('Role', '')), 'New_Principal_Type': str(row.get('Type of account (for ADD)', '')), 'New_Email_Address': str(row.get('Email/Domain (for ADD)', '')), 'New_Role': str(row.get('New_Role', '')) }
        if dry_run:
            print(f"[DRY RUN] Would perform '{cmd}' for '{entry['New_Email_Address'] or entry['Original_Email_Address']}' on Item ID: {item_id}")
            audit_trail.append(entry); continue
        try:
            if cmd == 'ADD':
                p_type, p_address, p_role_ui = str(row.get('Type of account (for ADD)')).lower(), str(row.get('Email/Domain (for ADD)')), str(row.get('New_Role'))
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
    return audit_trail, root_folder_id