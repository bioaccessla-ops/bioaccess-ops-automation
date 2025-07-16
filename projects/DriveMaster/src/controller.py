import logging
import os
from datetime import datetime
from pathlib import Path
import tempfile
import pandas as pd

from .auth import authenticate_and_get_service
from .report_generator import generate_permission_report
from .spreadsheet_handler import write_report_to_csv, write_report_to_excel, save_audit_log
from .permission_manager import process_changes, generate_rollback_actions

def _setup_project_directories():
    """Ensures that all necessary output directories exist."""
    logging.info("Checking for output directories...")
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
        
def get_fetch_output_path(service, folder_id):
    """Determines the full path of the Excel report file that a fetch will create."""
    try:
        root_folder_name = _sanitize_filename(_get_item_name(service, folder_id))
        return os.path.join('reports', f"permissions_editor_{root_folder_name}.xlsx")
    except Exception as e:
        logging.error(f"Could not determine output path: {e}"); return None

def run_fetch(folder_id, user_email=None):
    _setup_project_directories()
    logging.info("--- Authenticating for Fetch ---")
    service = authenticate_and_get_service()
    if not service: logging.critical("Authentication failed."); return False
    
    logging.info(f"Starting 'fetch' command for folder ID: {folder_id}")
    root_folder_name = _sanitize_filename(_get_item_name(service, folder_id))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    logging.info("Generating data for archive and report...")
    report_data = generate_permission_report(service, folder_id, user_email)
    
    if not report_data: logging.warning("No permissions data found to generate a report."); return True

    if write_report_to_csv(report_data, os.path.join('archives', f"{timestamp}_fetch_{root_folder_name}_baseline.csv")):
        logging.info(f"Successfully created baseline archive.")

    if write_report_to_excel(report_data, os.path.join('reports', f"permissions_editor_{root_folder_name}.xlsx")):
        logging.info(f"User-facing Excel report saved.")
    logging.info("--- Fetch complete ---")
    return True

def run_apply_changes(excel_path, is_live_run, root_id_override=None):
    _setup_project_directories()
    logging.info("--- Authenticating for Apply-Changes ---")
    service = authenticate_and_get_service()
    if not service: logging.critical("Authentication failed."); return False

    audit_trail, root_id_from_file = process_changes(service, input_excel_path=excel_path, dry_run=not is_live_run)
    
    actual_root_id = root_id_override if root_id_override else root_id_from_file
    if not actual_root_id or actual_root_id == 'N/A_RootID_FromProcess':
        logging.error("Could not determine Root Folder ID."); return False
    
    if not audit_trail: return True

    root_folder_name = _sanitize_filename(_get_item_name(service, actual_root_id))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.info("Generating pre-apply changes archive...")
    if write_report_to_csv(generate_permission_report(service, actual_root_id), os.path.join('archives', f"{timestamp}_apply_{root_folder_name}_pre_changes.csv")):
        logging.info(f"Successfully created pre-apply changes archive.")

    save_audit_log(audit_trail, os.path.join('logs', f"{timestamp}_apply_{root_folder_name}_audit.csv"))
    logging.info("--- Apply-Changes complete ---")
    return True

def run_rollback(log_file_path, is_live_run, root_id_override=None):
    _setup_project_directories()
    logging.info("--- Authenticating for Rollback ---")
    service = authenticate_and_get_service()
    if not service: logging.critical("Authentication failed."); return False

    try:
        log_file_abs = Path(log_file_path).resolve()
        if not Path("./logs").resolve() in log_file_abs.parents:
            logging.error("Security Error: Log file must be inside 'logs' directory."); return False
        audit_log_df = pd.read_csv(log_file_abs).fillna('')
        if 'Root Folder ID' not in audit_log_df.columns or audit_log_df.empty:
            raise ValueError("Log is invalid or empty.")
        root_id_from_log = str(audit_log_df['Root Folder ID'].iloc[0])
        if not root_id_from_log: raise ValueError("'Root Folder ID' in log is blank.")
    except Exception as e:
        logging.error(f"Failed to read or process audit log '{log_file_path}': {e}"); return False
    
    actual_root_id = root_id_override if root_id_override else root_id_from_log
    root_folder_name = _sanitize_filename(_get_item_name(service, actual_root_id))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    logging.info(f"Fetching live permission data once for all operations...")
    live_report_data = generate_permission_report(service, actual_root_id)

    logging.info("Generating pre-rollback archive...")
    if write_report_to_csv(live_report_data, os.path.join('archives', f"{timestamp}_rollback_{root_folder_name}_pre_rollback.csv")):
        logging.info(f"Successfully created pre-rollback archive.")
    
    rollback_actions = generate_rollback_actions(log_file_abs, live_report_data)
    if not rollback_actions: 
        logging.info("No actions to perform for rollback."); return True

    temp_excel_path = os.path.join(tempfile.gettempdir(), f'temp_rollback_{timestamp}.xlsx')
    try:
        # --- MODIFIED: The column list now matches the full, current format ---
        # This ensures the temporary file for rollback has the correct columns.
        cols = [
            'Full Path', 'Item Name', 'Item ID', 'Role', 'Principal Type', 
            'Email Address', 'Owner', 'Google Drive URL', 'Root Folder ID', 
            'Current Download Restriction', 'Action_Type', 'New_Role', 
            'Type of account (for ADD)', 'Email/Domain (for ADD)', 'SET Download Restriction'
        ]
        pd.DataFrame(rollback_actions).reindex(columns=cols).fillna('').to_excel(temp_excel_path, index=False)
        # --- END MODIFICATION ---
    except Exception as e:
        logging.error(f"Failed to write temporary rollback file: {e}"); return False

    audit_trail, _ = process_changes(service, input_excel_path=temp_excel_path, dry_run=not is_live_run, live_report_data=live_report_data)
    os.remove(temp_excel_path)
    logging.info(f"Temporary rollback file deleted: {temp_excel_path}")
    
    if audit_trail:
        save_audit_log(audit_trail, os.path.join('logs', f"{timestamp}_rollback_{root_folder_name}_audit.csv"))
    
    logging.info("--- Rollback complete ---")
    return True
