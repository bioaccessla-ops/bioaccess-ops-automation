import logging
import os
from datetime import datetime
from pathlib import Path
import pandas as pd

from src.auth import authenticate_and_get_service
from src.report_generator import generate_permission_report
from src.spreadsheet_handler import write_report_to_csv, write_report_to_excel, save_audit_log
from src.permission_manager import process_changes, generate_rollback_actions, plan_changes

def _setup_project_directories():
    Path("./reports").mkdir(exist_ok=True)
    Path("./archives").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)

def _sanitize_filename(name):
    name = str(name); sanitized_name = name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    return "".join(c for c in sanitized_name if c.isalnum() or c in ('_', '-')).strip() or "unnamed_item"

def _get_item_name(service, item_id):
    try:
        response = service.files().get(fileId=item_id, fields='name').execute()
        return response.get('name', 'UnknownItem')
    except Exception as e:
        logging.error(f"Could not retrieve name for item ID {item_id}: {e}"); return "UnknownItem"

def run_fetch(folder_id, user_email=None, progress_callback=None):
    _setup_project_directories()
    logging.info("--- Authenticating for Fetch ---")
    service, _ = authenticate_and_get_service()
    if not service: 
        logging.critical("Authentication failed.")
        return None, None
    
    logging.info(f"Starting 'fetch' command for folder ID: {folder_id}")
    root_folder_name = _sanitize_filename(_get_item_name(service, folder_id))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    report_data = generate_permission_report(service, folder_id, user_email, progress_callback)
    
    if not report_data: 
        logging.warning("No permissions data found to generate a report.")
        return [], None

    if write_report_to_csv(report_data, os.path.join('archives', f"{timestamp}_fetch_{root_folder_name}_baseline.csv")):
        logging.info(f"Successfully created baseline archive.")

    output_path = os.path.join('reports', f"permissions_editor_{root_folder_name}.xlsx")
    return report_data, output_path

def prepare_apply_changes(excel_path):
    logging.info("--- Preparing to Apply Changes ---")
    service, auth_user_email = authenticate_and_get_service()
    if not service:
        logging.critical("Authentication failed during preparation."); return None, None, None, False

    try:
        input_df = pd.read_excel(excel_path, dtype=str).fillna('')
        if 'Root Folder ID' not in input_df.columns or input_df.empty:
            raise ValueError("Input file missing 'Root Folder ID' or is empty.")
        root_id = str(input_df.iloc[0]['Root Folder ID'])
    except Exception as e:
        logging.error(f"Failed to read or validate Excel file {excel_path}: {e}"); return None, None, None, False

    logging.info("Fetching current file states from Google Drive for comparison...")
    live_data = generate_permission_report(service, root_id)
    live_data_df = pd.DataFrame(live_data)

    execution_plan, self_mod_flag = plan_changes(input_df, live_data_df, auth_user_email)
    
    return execution_plan, live_data, root_id, self_mod_flag

def execute_apply_changes(plan, live_report_data, root_id, is_live_run):
    logging.info("--- Executing Apply Changes ---")
    service, _ = authenticate_and_get_service()
    if not service:
        logging.critical("Authentication failed during execution."); return False

    root_folder_name = _sanitize_filename(_get_item_name(service, root_id))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if write_report_to_csv(live_report_data, os.path.join('archives', f"{timestamp}_apply_{root_folder_name}_pre_changes.csv")):
        logging.info(f"Successfully created pre-apply changes archive.")

    audit_trail, _ = process_changes(service, plan=plan, root_folder_id=root_id, dry_run=not is_live_run)
    
    if audit_trail:
        save_audit_log(audit_trail, os.path.join('logs', f"{timestamp}_apply_{root_folder_name}_audit.csv"))
    
    logging.info("--- Apply-Changes execution complete ---")
    return True

def prepare_rollback(log_file_path, root_id_override=None):
    logging.info("--- Preparing Rollback ---")
    service, auth_user_email = authenticate_and_get_service()
    if not service:
        logging.critical("Authentication failed during preparation."); return None, None, None, False

    try:
        log_file_abs = Path(log_file_path).resolve()
        if not Path("./logs").resolve() in log_file_abs.parents:
            raise ValueError("Security Error: Log file must be inside 'logs' directory.")
        root_id_from_log = pd.read_csv(log_file_abs).fillna('').iloc[0]['Root Folder ID']
    except Exception as e:
        logging.error(f"Failed to read or process audit log '{log_file_path}': {e}"); return None, None, None, False
    
    actual_root_id = root_id_override or root_id_from_log
    live_report_data = generate_permission_report(service, actual_root_id)
    rollback_plan, self_mod_flag = generate_rollback_actions(log_file_abs, live_report_data, auth_user_email)
    
    return rollback_plan, live_report_data, actual_root_id, self_mod_flag

def execute_rollback(plan, live_report_data, root_id, is_live_run):
    logging.info("--- Executing Rollback ---")
    service, _ = authenticate_and_get_service()
    if not service:
        logging.critical("Authentication failed during execution."); return False

    root_folder_name = _sanitize_filename(_get_item_name(service, root_id))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if write_report_to_csv(live_report_data, os.path.join('archives', f"{timestamp}_rollback_{root_folder_name}_pre_rollback.csv")):
        logging.info(f"Successfully created pre-rollback archive.")
    
    audit_trail, _ = process_changes(service, plan=plan, root_folder_id=root_id, dry_run=not is_live_run)
    
    if audit_trail:
        save_audit_log(audit_trail, os.path.join('logs', f"{timestamp}_rollback_{root_folder_name}_audit.csv"))
    
    logging.info("--- Rollback execution complete ---")
    return True
