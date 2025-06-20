# main.py

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import tempfile
from googleapiclient.errors import HttpError

# Imports from the 'src' package
from src.auth import authenticate_and_get_service
from src.report_generator import generate_permission_report
from src.spreadsheet_handler import write_report_to_csv, write_report_to_excel, save_audit_log
from src.permission_manager import process_changes, generate_rollback_actions

# Configure logging to show info-level messages
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

    # --- Fetch Command ---
    parser_fetch = subparsers.add_parser('fetch', help="Fetch permissions and save to an Excel file for editing.")
    parser_fetch.add_argument('--root', required=True, help="Google Drive root folder ID to scan.")
    # --output argument removed as it's now dynamically generated
    parser_fetch.add_argument('--email', help="(Optional) Filter report for a single user's access.", default=None)

    # --- Apply Changes Command ---
    parser_apply = subparsers.add_parser('apply-changes', help="Apply permission changes from an Excel file.")
    parser_apply.add_argument('--input', required=True, help="Input .xlsx file with ACTION column.")
    parser_apply.add_argument('--root', required=False, default=None, help="(Optional) Root folder ID. If not provided, extracted from input file.")
    parser_apply.add_argument('--live', action='store_true', help="Apply changes live. USE WITH CAUTION.")
    parser_apply.add_argument('--dry-run', action='store_true', help="Simulate changes without applying them.")

    # --- Rollback Command ---
    parser_rollback = subparsers.add_parser('rollback', help="Rollback changes using an audit log.")
    parser_rollback.add_argument('--from-log', required=True, help="The apply-changes audit log (.csv) file to rollback from (must be in 'logs' folder).")
    parser_rollback.add_argument('--root', required=False, default=None, help="(Optional) Root folder ID. If not provided, extracted from audit log.")
    parser_rollback.add_argument('--live', action='store_true', help="Perform the rollback live. USE WITH CAUTION.")
    
    args = parser.parse_args()

    # --- Authenticate ---
    service = authenticate_and_get_service()
    if not service:
        logging.critical("Could not authenticate with Google Drive. Exiting.")
        return

    # --- Setup common paths for logging/archiving ---
    Path("./reports").mkdir(exist_ok=True)
    Path("./archives").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


    # --- Execute Commands ---
    if args.command == 'fetch':
        logging.info(f"Starting 'fetch' command for folder ID: {args.root}")
        root_folder_name = _sanitize_filename(_get_item_name(service, args.root))

        # --- ARCHIVE: Baseline Snapshot ---
        archive_filename = f"{timestamp}_fetch_{root_folder_name}_baseline.csv"
        archive_path = os.path.join('archives', archive_filename)
        
        logging.info("Generating data for archive and report...")
        report_data = generate_permission_report(service, args.root, args.email)
        
        write_report_to_csv(report_data, archive_path)
        logging.info(f"Successfully created baseline archive: {archive_path}")

        PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))
        output_filename_with_name = f"permissions_editor_{root_folder_name}.xlsx" 
        output_path = os.path.join(PROJECT_ROOT, 'reports', output_filename_with_name)

        write_report_to_excel(report_data, output_path)
        logging.info(f"User-facing Excel report saved to {output_path}")

    elif args.command == 'apply-changes':
        is_dry_run = not args.live
        
        # Process changes and get the audit trail AND root_folder_id from the file
        audit_trail_data, root_id_from_file = process_changes(drive_service=service, input_excel_path=args.input, dry_run=is_dry_run)
        
        # Determine actual_root_id: Use command line --root if provided, else from file
        actual_root_id = args.root if args.root else root_id_from_file
        
        if actual_root_id == 'N/A_RootID_FromProcess':
            logging.error("Could not determine Root Folder ID for archiving. Please provide --root argument.")
            return

        root_folder_name = _sanitize_filename(_get_item_name(service, actual_root_id))
        
        if not audit_trail_data:
            logging.info("No actions were processed or audit trail generated. Exiting apply-changes.")
            return

        # --- ARCHIVE: Pre-Apply Snapshot ---
        archive_filename = f"{timestamp}_apply_{root_folder_name}_pre_changes.csv"
        archive_path = os.path.join('archives', archive_filename)
        logging.info("Generating pre-apply changes archive...")
        pre_apply_report_data = generate_permission_report(service, actual_root_id, user_email=None) 
        write_report_to_csv(pre_apply_report_data, archive_path)
        logging.info(f"Successfully created pre-apply changes archive: {archive_path}")

        if is_dry_run:
            logging.info(f"--- Running 'apply-changes' in DRY RUN mode from file: {args.input} ---")
        else:
            print("\n!!! WARNING: YOU ARE ABOUT TO MAKE LIVE CHANGES !!!")
            print("This cannot be undone. Please review your Excel file carefully.")
            confirm = input(f"Are you sure you want to apply changes from '{args.input}'? (type 'yes' to proceed): ").strip()
            if confirm.lower() not in ['y', 'yes']:
                logging.warning("Live run cancelled by user.")
                return
            logging.info(f"--- Starting 'apply-changes' in LIVE mode from file: {args.input} ---")
        
        # audit_trail_data is already populated from the call above
        
        # --- LOG: Apply Changes Audit ---
        log_filename = f"{timestamp}_apply_{root_folder_name}_audit.csv"
        log_path = os.path.join('logs', log_filename)
        save_audit_log(audit_trail_data, log_path)

        logging.info("'apply-changes' command finished.")
    
    elif args.command == 'rollback':
        logging.info(f"--- Starting 'rollback' command from audit log: {args.from_log} ---")
        
        # *** START: MODIFIED SECTION - Input Sanitation & Validation ***
        try:
            # Get the absolute path of the 'logs' directory for comparison
            logs_dir_abs = Path("./logs").resolve()
            # Resolve the user-provided path to prevent traversal attacks (e.g., ../../file)
            log_file_abs = Path(args.from_log).resolve()

            # SECURITY CHECK: Ensure the requested log file is inside the 'logs' directory
            if logs_dir_abs not in log_file_abs.parents:
                logging.error(f"Security Error: The specified log file '{args.from_log}' must be inside the 'logs' directory. Operation aborted.")
                return

            # FILE CHECK: Ensure the file actually exists
            if not log_file_abs.is_file():
                logging.error(f"File Not Found: The specified log file does not exist at '{log_file_abs}'.")
                return
        
        except Exception as e:
            logging.error(f"An error occurred while validating the log file path '{args.from_log}': {e}")
            return

        is_dry_run = not args.live

        # Read the audit log with improved error handling for content validation
        try:
            audit_log_df = pd.read_csv(log_file_abs).fillna('')
            
            # CONTENT CHECK 1: Ensure the required column exists
            if 'Root Folder ID' not in audit_log_df.columns:
                logging.error(f"Invalid Log: The audit log '{args.from_log}' is missing the required 'Root Folder ID' column.")
                return

            # CONTENT CHECK 2: Ensure the log file is not empty
            if audit_log_df.empty:
                logging.error(f"Invalid Log: The audit log '{args.from_log}' is empty and contains no actions to roll back.")
                return

            root_id_from_log = str(audit_log_df['Root Folder ID'].iloc[0])

            # CONTENT CHECK 3: Ensure the Root Folder ID itself is not blank
            if not root_id_from_log:
                logging.error(f"Invalid Log: The 'Root Folder ID' in the first row of '{args.from_log}' is blank.")
                return

        except pd.errors.ParserError:
            logging.error(f"Failed to parse the log file '{args.from_log}'. Please ensure it is a valid CSV file.")
            return
        except Exception as e:
            logging.error(f"Failed to read or process the audit log '{args.from_log}': {e}")
            return
        # *** END: MODIFIED SECTION ***
        
        # Use root_id from log for naming, unless overridden by --root argument
        actual_root_id = args.root if args.root else root_id_from_log
        
        if actual_root_id == 'UnknownRoot': # This case is now less likely with better checks
            logging.error("Could not determine Root Folder ID for rollback. Please provide --root argument.")
            return

        root_folder_name = _sanitize_filename(_get_item_name(service, actual_root_id))

        logging.info(f"--- Rolling back changes for folder ID: {actual_root_id} ---")

        # --- ARCHIVE: Pre-Rollback Snapshot ---
        archive_filename = f"{timestamp}_rollback_{root_folder_name}_pre_rollback.csv"
        archive_path = os.path.join('archives', archive_filename)
        logging.info("Generating pre-rollback archive...")
        pre_rollback_report_data = generate_permission_report(service, actual_root_id, user_email=None)
        write_report_to_csv(pre_rollback_report_data, archive_path)
        logging.info(f"Successfully created pre-rollback archive: {archive_path}")

        if is_dry_run:
            logging.info(f"--- Rollback is in DRY RUN mode. No changes will be made to Drive. ---")
        else:
            print("\n!!! WARNING: YOU ARE ABOUT TO PERFORM A LIVE ROLLBACK !!!")
            print("This cannot be undone. Please ensure you are rolling back to the correct state.")
            confirm = input(f"Are you sure you want to perform rollback from '{args.from_log}'? (type 'yes' to proceed): ").strip()
            if confirm.lower() not in ['y', 'yes']:
                logging.warning("Rollback cancelled by user.")
                return
            logging.info(f"--- Rollback is in LIVE mode. Changes WILL be applied to Google Drive. ---")

        # --- Generate Rollback Actions ---
        try:
            # Generate the inverse actions directly from the audit log
            rollback_actions = generate_rollback_actions(
                drive_service=service, 
                root_folder_id=actual_root_id,
                audit_log_path=log_file_abs # Use the validated, absolute path
            )
        except Exception as e:
            logging.error(f"Failed to generate rollback actions: {e}")
            return

        if not rollback_actions:
            logging.info("No successful actions found in the log to roll back.")
            return
            
        # Write generated rollback actions to a temporary Excel file
        temp_excel_file_path = os.path.join(tempfile.gettempdir(), f'temp_rollback_actions_{timestamp}.xlsx')
        try:
            temp_df = pd.DataFrame(rollback_actions)
            action_builder_cols = [
                'Item ID', 'Action_Type', 'New_Role', 'Type (for ADD)', 'Email/Domain (for ADD)',
                'Principal Type', 'Email Address', 'Role', 'Full Path', 'Item Name', 'Owner', 'Google Drive URL', 'Root Folder ID'
            ]
            temp_df = temp_df.reindex(columns=action_builder_cols).fillna('')
            
            temp_df.to_excel(temp_excel_file_path, index=False, engine='openpyxl')
        except Exception as e:
            logging.error(f"Failed to write temporary rollback file: {e}")
            return
            
        # Call process_changes with the temporary Excel file
        audit_trail_data_rollback, _ = process_changes(drive_service=service, input_excel_path=temp_excel_file_path, dry_run=is_dry_run)
        os.remove(temp_excel_file_path)
        logging.info(f"Temporary rollback file deleted: {temp_excel_file_path}")
        
        # --- LOG: Rollback Audit ---
        log_filename = f"{timestamp}_rollback_{root_folder_name}_audit.csv"
        log_path = os.path.join('logs', log_filename)
        save_audit_log(audit_trail_data_rollback, log_path)

        logging.info("'rollback' command finished.")


if __name__ == '__main__':
    main()