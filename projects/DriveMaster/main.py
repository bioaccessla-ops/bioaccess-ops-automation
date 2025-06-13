# main.py

import argparse
import logging
import os

# Imports from the 'src' package
from src.auth import authenticate_and_get_service
from src.report_generator import generate_permission_report
from src.spreadsheet_handler import write_report_to_csv
from src.permission_manager import process_changes

# Configure logging to show info-level messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Main function to parse commands and orchestrate the tool's functionality.
    """
    parser = argparse.ArgumentParser(description="Google Drive Permission Management Tool")
    # Make a command (like 'report' or 'apply-changes') required
    subparsers = parser.add_subparsers(dest='command', required=True)

    # --- Reporting Command ---
    parser_report = subparsers.add_parser('report', help="Generate a full permission report.")
    parser_report.add_argument('--root', required=True, help="Google Drive root folder ID to scan.")
    parser_report.add_argument('--output', required=True, help="Output CSV file name (will be saved in the 'reports' folder).")
    parser_report.add_argument('--email', help="(Optional) Filter report for a single user's access.", default=None)

    # --- Apply Changes Command ---
    parser_apply = subparsers.add_parser('apply-changes', help="Apply permission changes from a CSV.")
    parser_apply.add_argument('--input', required=True, help="Input CSV file with ACTION column.")
    parser_apply.add_argument('--live', action='store_true', help="Apply changes live. USE WITH CAUTION.")
    parser_apply.add_argument('--dry-run', action='store_true', help="Simulate changes without applying them.")

    # Parse the arguments provided by the user
    args = parser.parse_args()

    # --- Authenticate ---
    # This must happen before any command is executed.
    service = authenticate_and_get_service()
    if not service:
        logging.critical("Could not authenticate with Google Drive. Exiting.")
        return

    # --- Execute Commands ---
    if args.command == 'report':
        logging.info(f"Starting 'report' command for folder ID: {args.root}")

        # Get the directory where main.py is located (which is our project root)
        PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))
        # Build the full, correct path to the 'reports' subdirectory
        output_path = os.path.join(PROJECT_ROOT, 'reports', args.output)

        report_data = generate_permission_report(service, args.root, args.email)
        write_report_to_csv(report_data, output_path)

        logging.info(f"Report generation complete. Output saved to {output_path}")
    
    elif args.command == 'apply-changes':
        # If the --live flag is NOT used, it's a dry run. This makes dry-run the default and safer option.
        is_dry_run = not args.live

        if is_dry_run:
            logging.info(f"--- Starting 'apply-changes' in DRY RUN mode from file: {args.input} ---")
        else:
            # Add a final safety confirmation before making live changes
            confirm = input(f"You are about to apply changes in LIVE mode from file '{args.input}'.\nThis cannot be undone. Are you sure? (yes/no): ")
            if confirm.lower() not in ['y', 'yes']:
                logging.warning("Live run cancelled by user.")
                return # Stop the script if the user does not confirm
            logging.info(f"--- Starting 'apply-changes' in LIVE mode from file: {args.input} ---")

        # Call the actual function from the permission manager module
        process_changes(drive_service=service, input_csv_path=args.input, dry_run=is_dry_run)
        logging.info("'apply-changes' command finished.")


if __name__ == '__main__':
    main()