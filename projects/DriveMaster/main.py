# main.py

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import tempfile
from googleapiclient.errors import HttpError

from src.auth import authenticate_and_get_service
from src.report_generator import generate_permission_report
from src.spreadsheet_handler import write_report_to_csv, write_report_to_excel, save_audit_log
from src.permission_manager import process_changes, generate_rollback_actions

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _sanitize_filename(name):
    """Sanitizes a string to be safe for use as a filename."""
    name = str(name)
    sanitized_name = name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    sanitized_name = "".join(c for c in sanitized_name if c.isalnum() or c in ('_', '-')).strip()
    return sanitized_name if sanitized_name else "unnamed_item"

def _get_item_name(service, item_id):
    """Fetches the name of a Drive item given its ID."""
    try:
        response = service.files().get(fileId=item_id, fields='name').execute()
        return response.get('name', 'UnknownItem')
    except HttpError as e:
        logging.error(f"Could not retrieve name for item ID {item_id}: {e}")
        return "UnknownItem"

def main():
    """
    Main function to parse commands and orchestrate the tool's functionality.
    """
    parser = argparse.ArgumentParser(description="Google Drive Permission Management Tool")
    subparsers = parser.add_subparsers(dest='command', required=True)

    parser_fetch = subparsers.add_parser('fetch', help="Fetch permissions and save to an Excel file for editing.")
    parser_fetch.add_argument('--root', required=True, help="Google Drive root folder ID to scan.")
    parser_fetch.add_argument('--email', help="(Optional) Filter report for a single user's access.", default=None)

    parser_apply = subparsers.add_parser('apply-changes', help="Apply permission changes from an Excel file.")
    parser_apply.add_argument('--input', required=True, help="Input .xlsx file with ACTION column.")
    parser_apply.add_argument('--root', required=False, default=None, help="(Optional) Root folder ID.")
    parser_apply.add_argument('--live', action='store_true', help="Apply changes live. USE WITH CAUTION.")
    
    parser_rollback = subparsers.add_parser('rollback', help="Rollback changes using an audit log.")
    parser_rollback.add_argument('--from-log', required=True, help="The apply-changes audit log (.csv) file to rollback from.")
    parser_rollback.add_argument('--root', required=False, default=None, help="(Optional) Root folder ID.")
    parser_rollback.add_argument('--live', action='store_true', help="Perform the rollback live. USE WITH CAUTION.")
    
    args = parser.parse_args()

    # --- MODIFIED: Authentication is now handled within each command block ---
    
    Path("./reports").mkdir(exist_ok=True)
    Path("./archives").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.command == 'fetch':
        service = authenticate_and_get_service()
        if not service: logging.critical("Authentication failed. Exiting."); return
        
        logging.info(f"Starting 'fetch' command for folder ID: {args.root}")
        root_folder_name = _sanitize_filename(_get_item_name(service, args.root))
        archive_filename = f"{timestamp}_fetch_{root_folder_name}_baseline.csv"
        archive_path = os.path.join('archives', archive_filename)
        logging.info("Generating data for archive and report...")
        report_data = generate_permission_report(service, args.root, args.email)
        write_report_to_csv(report_data, archive_path)
        logging.info(f"Successfully created baseline archive: {archive_path}")
        output_filename_with_name = f"permissions_editor_{root_folder_name}.xlsx" 
        output_path = os.path.join('reports', output_filename_with_name)
        write_report_to_excel(report_data, output_path)
        logging.info(f"User-facing Excel report saved to {output_path}")

    elif args.command == 'apply-changes':
        service = authenticate_and_get_service()
        if not service: logging.critical("Authentication failed. Exiting."); return

        is_dry_run = not args.live
        audit_trail_data, root_id_from_file = process_changes(drive_service=service, input_excel_path=args.input, dry_run=is_dry_run)
        actual_root_id = args.root if args.root else root_id_from_file
        if not actual_root_id or actual_root_id == 'N/A_RootID_FromProcess':
            logging.error("Could not determine Root Folder ID. Please provide --root argument."); return
        
        root_folder_name = _sanitize_filename(_get_item_name(service, actual_root_id))
        if not audit_trail_data: return

        archive_filename = f"{timestamp}_apply_{root_folder_name}_pre_changes.csv"
        archive_path = os.path.join('archives', archive_filename)
        logging.info("Generating pre-apply changes archive...")
        pre_apply_report_data = generate_permission_report(service, actual_root_id, user_email=None) 
        write_report_to_csv(pre_apply_report_data, archive_path)
        logging.info(f"Successfully created pre-apply changes archive: {archive_path}")

        if not is_dry_run:
            print("\n!!! WARNING: YOU ARE ABOUT TO MAKE LIVE CHANGES !!!"); print("This cannot be undone.")
            confirm = input(f"Are you sure you want to apply changes from '{args.input}'? (type 'yes' to proceed): ").strip()
            if confirm.lower() not in ['y', 'yes']: logging.warning("Live run cancelled by user."); return
        
        log_filename = f"{timestamp}_apply_{root_folder_name}_audit.csv"
        log_path = os.path.join('logs', log_filename)
        save_audit_log(audit_trail_data, log_path)
        logging.info("'apply-changes' command finished.")
    
    elif args.command == 'rollback':
        service = authenticate_and_get_service()
        if not service: logging.critical("Authentication failed. Exiting."); return

        logging.info(f"--- Starting 'rollback' command from audit log: {args.from_log} ---")
        try:
            log_file_abs = Path(args.from_log).resolve()
            if not Path("./logs").resolve() in log_file_abs.parents:
                logging.error(f"Security Error: Log file must be inside the 'logs' directory."); return
            audit_log_df = pd.read_csv(log_file_abs).fillna('')
            if 'Root Folder ID' not in audit_log_df.columns or audit_log_df.empty:
                logging.error(f"Log file '{args.from_log}' is invalid or empty."); return
            root_id_from_log = str(audit_log_df['Root Folder ID'].iloc[0])
            if not root_id_from_log: logging.error(f"'Root Folder ID' in log is blank."); return
        except Exception as e:
            logging.error(f"Failed to read or process audit log '{args.from_log}': {e}"); return
        
        actual_root_id = args.root if args.root else root_id_from_log
        root_folder_name = _sanitize_filename(_get_item_name(service, actual_root_id))
        logging.info(f"--- Rolling back changes for folder ID: {actual_root_id} ---")

        archive_filename = f"{timestamp}_rollback_{root_folder_name}_pre_rollback.csv"
        archive_path = os.path.join('archives', archive_filename)
        logging.info("Generating pre-rollback archive...")
        write_report_to_csv(generate_permission_report(service, actual_root_id, user_email=None), archive_path)
        logging.info(f"Successfully created pre-rollback archive: {archive_path}")

        is_dry_run = not args.live
        if not is_dry_run:
            print("\n!!! WARNING: YOU ARE ABOUT TO PERFORM A LIVE ROLLBACK !!!"); print("This cannot be undone.")
            confirm = input(f"Are you sure you want to perform rollback from '{args.from_log}'? (type 'yes' to proceed): ").strip()
            if confirm.lower() not in ['y', 'yes']: logging.warning("Rollback cancelled by user."); return
        
        logging.info(f"--- Rollback is in {'LIVE' if not is_dry_run else 'DRY RUN'} mode. ---")
        rollback_actions = generate_rollback_actions(service, actual_root_id, log_file_abs)
        if not rollback_actions: return
            
        temp_excel_file_path = os.path.join(tempfile.gettempdir(), f'temp_rollback_actions_{timestamp}.xlsx')
        try:
            action_builder_cols = ['Item ID', 'Action_Type', 'New_Role', 'Type (for ADD)', 'Email/Domain (for ADD)','Principal Type', 'Email Address', 'Role', 'Full Path', 'Item Name', 'Owner', 'Google Drive URL', 'Root Folder ID', 'Restrict Download']
            pd.DataFrame(rollback_actions).reindex(columns=action_builder_cols).fillna('').to_excel(temp_excel_file_path, index=False, engine='openpyxl')
        except Exception as e:
            logging.error(f"Failed to write temporary rollback file: {e}"); return
            
        audit_trail_data, _ = process_changes(service, input_excel_path=temp_excel_file_path, dry_run=is_dry_run)
        os.remove(temp_excel_file_path)
        logging.info(f"Temporary rollback file deleted: {temp_excel_file_path}")
        
        if audit_trail_data:
            log_filename = f"{timestamp}_rollback_{root_folder_name}_audit.csv"
            save_audit_log(audit_trail_data, os.path.join('logs', log_filename))
        
        logging.info("'rollback' command finished.")

if __name__ == '__main__':
    main()