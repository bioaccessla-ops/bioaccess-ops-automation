# main.py

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

# Imports from the 'src' package
from src.auth import authenticate_and_get_service
from src.report_generator import generate_permission_report
from src.spreadsheet_handler import write_report_to_csv, write_report_to_excel
from src.permission_manager import process_changes

# Configure logging to show info-level messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Main function to parse commands and orchestrate the tool's functionality.
    """
    parser = argparse.ArgumentParser(description="Google Drive Permission Management Tool")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # --- Fetch Command (replaces 'report') ---
    parser_fetch = subparsers.add_parser('fetch', help="Fetch permissions and save to an Excel file for editing.")
    parser_fetch.add_argument('--root', required=True, help="Google Drive root folder ID to scan.")
    parser_fetch.add_argument('--output', required=True, help="Output .xlsx file name (will be saved in the 'reports' folder).")
    parser_fetch.add_argument('--email', help="(Optional) Filter report for a single user's access.", default=None)

    # --- Apply Changes Command ---
    parser_apply = subparsers.add_parser('apply-changes', help="Apply permission changes from an Excel file.")
    parser_apply.add_argument('--input', required=True, help="Input .xlsx file with ACTION column.")
    parser_apply.add_argument('--live', action='store_true', help="Apply changes live. USE WITH CAUTION.")

    # --- Rollback Command ---
    parser_rollback = subparsers.add_parser('rollback', help="Rollback changes using a backup file.")
    parser_rollback.add_argument('--from-backup', required=True, help="The timestamped backup CSV file to restore permissions from.")
    parser_rollback.add_argument('--live', action='store_true', help="Perform the rollback live. USE WITH CAUTION.")
    
    args = parser.parse_args()

    # --- Authenticate ---
    service = authenticate_and_get_service()
    if not service:
        logging.critical("Could not authenticate with Google Drive. Exiting.")
        return

    # --- Execute Commands ---
    if args.command == 'fetch':
        logging.info(f"Starting 'fetch' command for folder ID: {args.root}")

        # --- Automatic Backup ---
        Path("./backups").mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{timestamp}_permissions_backup.csv"
        backup_path = os.path.join('backups', backup_filename)
        
        logging.info("Generating data for backup and report...")
        report_data = generate_permission_report(service, args.root, args.email)
        
        write_report_to_csv(report_data, backup_path)
        logging.info(f"Successfully created backup: {backup_path}")
        # --- End Automatic Backup ---

        PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))
        output_path = os.path.join(PROJECT_ROOT, 'reports', args.output)

        write_report_to_excel(report_data, output_path)
        logging.info(f"User-facing Excel report saved to {output_path}")

    elif args.command == 'apply-changes':
        is_dry_run = not args.live
        
        if is_dry_run:
            logging.info(f"--- Starting 'apply-changes' in DRY RUN mode from file: {args.input} ---")
        else:
            confirm = input(f"You are about to apply changes in LIVE mode from file '{args.input}'.\nThis cannot be undone. Are you sure? (yes/no): ")
            if confirm.lower() not in ['y', 'yes']:
                logging.warning("Live run cancelled by user.")
                return
            logging.info(f"--- Starting 'apply-changes' in LIVE mode from file: {args.input} ---")
        
        process_changes(drive_service=service, input_excel_path=args.input, dry_run=is_dry_run)
        logging.info("'apply-changes' command finished.")
    
    elif args.command == 'rollback':
        logging.warning(f"--- The 'rollback' feature is not yet fully implemented. ---")
        logging.warning(f"--- Planned rollback from file: {args.from_backup} ---")
        # Future logic for rollback will go here

if __name__ == '__main__':
    main()