# src/spreadsheet_handler.py

import pandas as pd
import logging
from openpyxl import load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import PatternFill
from openpyxl.formatting.rule import Rule, FormulaRule
from openpyxl.styles.colors import Color

def write_report_to_csv(report_data, filename):
    """Writes report data to a CSV file. Used for backups."""
    if not report_data:
        logging.warning("No data to write to CSV report.")
        return
    try:
        df = pd.DataFrame(report_data)
        df.to_csv(filename, index=False, encoding='utf-8')
    except Exception as e:
        logging.error(f"Failed to write backup CSV to {filename}: {e}")


def save_audit_log(audit_data, filename):
    """Saves the audit trail (list of dicts) to a CSV log file."""
    logging.info(f"Attempting to save audit log: {filename}")
    
    if not audit_data:
        logging.warning("No audit data to write to log file.")
        return
    try:
        df = pd.DataFrame(audit_data)
        
        if df.empty:
            logging.warning("Audit DataFrame is empty after conversion.")
            return

        # *** START: MODIFIED SECTION ***
        # Define the complete and ordered list of columns for the audit log.
        log_column_order = [
            'Timestamp', 
            'Root Folder ID', 
            'Full Path', 
            'Item Name', 
            'Item ID', 
            'Action_Command', 
            'Status', 
            'Details',
            'Original_Principal_Type', 
            'Original_Email_Address', 
            'Original_Role',
            'New_Principal_Type', 
            'New_Email_Address', 
            'New_Role'
        ]
        
        # Reindex the DataFrame to ensure consistent column order.
        # This will add any missing columns with blank values.
        df = df.reindex(columns=log_column_order)
        # *** END: MODIFIED SECTION ***
        
        df.to_csv(filename, index=False, encoding='utf-8')
        logging.info(f"Audit log successfully written to {filename}")
    except Exception as e:
        logging.error(f"Failed to write audit log to {filename}: {e}")


def add_dropdowns_to_sheet(filename):
    """Opens an existing Excel file and adds Data Validation dropdowns and Conditional Formatting."""
    try:
        wb = load_workbook(filename)
        ws = wb.active

        dv_action = DataValidation(type="list", formula1='"MODIFY,REMOVE,ADD"', allow_blank=True)
        dv_role = DataValidation(type="list", formula1='"Viewer,Commenter,Editor"', allow_blank=True)
        dv_principal = DataValidation(type="list", formula1='"user,group,domain"', allow_blank=True)

        # Columns for Data Validation: J, K, L
        # Action_Type is J, New_Role is K, Type (for ADD) is L
        dv_action.add('J2:J1048576')      # Column J for Action_Type
        dv_role.add('K2:K1048576')        # Column K for New_Role
        dv_principal.add('L2:L1048576')   # Column L for Type (for ADD)
        
        ws.add_data_validation(dv_action)
        ws.add_data_validation(dv_role)
        ws.add_data_validation(dv_principal)

        fill_add = PatternFill(start_color=Color("FFD8E9BB"), end_color=Color("FFD8E9BB"), fill_type="solid")
        fill_remove = PatternFill(start_color=Color("FFFFC7CE"), end_color=Color("FFFFC7CE"), fill_type="solid")
        fill_modify = PatternFill(start_color=Color("FFFFEB9C"), end_color=Color("FFFFEB9C"), fill_type="solid")

        # Range now extends to column N to include all action builder columns
        full_range = 'A2:N1048576'

        # Formulas reference column J for the Action_Type
        rule_add = FormulaRule(formula=['=$J2="ADD"'], fill=fill_add)
        ws.conditional_formatting.add(full_range, rule_add)

        rule_remove = FormulaRule(formula=['=$J2="REMOVE"'], fill=fill_remove)
        ws.conditional_formatting.add(full_range, rule_remove)

        rule_modify = FormulaRule(formula=['=$J2="MODIFY"'], fill=fill_modify)
        ws.conditional_formatting.add(full_range, rule_modify)

        wb.save(filename)
        logging.info(f"Successfully added dropdown menus and conditional formatting to {filename}")
    except Exception as e:
        logging.error(f"Could not add dropdown menus or conditional formatting to {filename}. Reason: {e}")


def write_report_to_excel(report_data, filename):
    """Writes the report data to a user-friendly Excel file with Action Builder columns."""
    if not report_data:
        logging.warning("No data to write to Excel report.")
        return
    try:
        df = pd.DataFrame(report_data)
        
        # Add the action builder columns
        action_columns = ['Action_Type', 'New_Role', 'Type (for ADD)', 'Email/Domain (for ADD)']
        for col in action_columns:
            df[col] = ''
        
        # Define the full column order for the interactive report
        column_order = [
            'Full Path', 'Item Name', 'Item ID', 'Role', 'Principal Type', 
            'Email Address', 'Owner', 'Google Drive URL', 'Root Folder ID',
            'Allow Discovery', 'Expiration Time'
        ] + action_columns
        
        # Reorder the DataFrame columns
        df = df.reindex(columns=[col for col in column_order if col in df.columns])

        df.to_excel(filename, index=False, engine='openpyxl')
        
        add_dropdowns_to_sheet(filename)
        
    except Exception as e:
        logging.error(f"Failed to write Excel file to {filename}: {e}")