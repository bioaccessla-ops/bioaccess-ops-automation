# main.py

import argparse
import logging
from src.controller import run_fetch, run_apply_changes, run_rollback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description="Google Drive Permission Management Tool")
    subparsers = parser.add_subparsers(dest='command', required=True)

    parser_fetch = subparsers.add_parser('fetch', help="Fetch permissions and save to an Excel file.")
    parser_fetch.add_argument('--root', required=True, help="Google Drive root folder ID.")
    parser_fetch.add_argument('--email', default=None, help="Optional: Filter for a single user's access.")

    parser_apply = subparsers.add_parser('apply-changes', help="Apply permission changes from an Excel file.")
    parser_apply.add_argument('--input', required=True, help="Input .xlsx file with changes.")
    parser_apply.add_argument('--root', default=None, help="Optional: Root folder ID if not in file.")
    parser_apply.add_argument('--live', action='store_true', help="Apply changes live. Default is a dry run.")
    
    parser_rollback = subparsers.add_parser('rollback', help="Rollback changes using an audit log.")
    parser_rollback.add_argument('--from-log', required=True, help="The apply-changes audit log (.csv) in the 'logs' folder.")
    parser_rollback.add_argument('--root', default=None, help="Optional: Root folder ID if not in log.")
    parser_rollback.add_argument('--live', action='store_true', help="Perform the rollback live. Default is a dry run.")
    
    args = parser.parse_args()

    if args.command == 'fetch':
        run_fetch(folder_id=args.root, user_email=args.email)

    elif args.command == 'apply-changes':
        if args.live:
            print("\n!!! WARNING: YOU ARE ABOUT TO MAKE LIVE CHANGES !!!")
            if input(f"Are you sure you want to apply changes from '{args.input}'? (yes/no): ").strip().lower() != 'yes':
                logging.warning("Live run cancelled by user."); return
        run_apply_changes(excel_path=args.input, is_live_run=args.live, root_id_override=args.root)

    elif args.command == 'rollback':
        if args.live:
            print("\n!!! WARNING: YOU ARE ABOUT TO PERFORM A LIVE ROLLBACK !!!")
            if input(f"Are you sure you want to rollback from '{args.from_log}'? (yes/no): ").strip().lower() != 'yes':
                logging.warning("Live run cancelled by user."); return
        run_rollback(log_file_path=args.from_log, is_live_run=args.live, root_id_override=args.root)

if __name__ == '__main__':
    main()