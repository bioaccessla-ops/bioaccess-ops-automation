import pandas as pd
import logging
from openpyxl import load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import PatternFill
from openpyxl.formatting.rule import Rule, FormulaRule
from openpyxl.styles.colors import Color

def write_report_to_csv(report_data, filename):
    """Writes report data to a CSV file. Returns True on success, False on failure."""
    if not report_data:
        logging.warning("No data to write to CSV report.")
        return True
    try:
        df = pd.DataFrame(report_data)
        df.to_csv(filename, index=False, encoding='utf-8')
        return True
    except Exception as e:
        logging.error(f"Failed to write backup CSV to {filename}: {e}")
        return False

def save_audit_log(audit_data, filename):
    """Saves the audit trail to a CSV log file. Returns True on success, False on failure."""
    if not audit_data:
        logging.warning("No audit data to write to log file.")
        return True
    try:
        df = pd.DataFrame(audit_data)
        if df.empty:
            logging.warning("Audit DataFrame is empty after conversion.")
            return True
        log_column_order = ['Timestamp', 'Root Folder ID', 'Full Path', 'Item Name', 'Item ID', 'Action_Command', 'Status', 'Details', 'Original_Principal_Type', 'Original_Email_Address', 'Original_Role', 'New_Principal_Type', 'New_Email_Address', 'New_Role']
        df = df.reindex(columns=log_column_order)
        df.to_csv(filename, index=False, encoding='utf-8')
        logging.info(f"Audit log successfully written to {filename}")
        return True
    except Exception as e:
        logging.error(f"Failed to write audit log to {filename}: {e}")
        return False

def add_dropdowns_to_sheet(filename):
    """Adds dropdowns, formatting, and auto-filter to an Excel sheet."""
    try:
        wb = load_workbook(filename)
        ws = wb.active
        
        ws.auto_filter.ref = ws.dimensions
        
        # --- MODIFIED: New dropdown for the explicit SET action column ---
        dv_set_restrict = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True)
        # --- END MODIFICATION ---

        dv_action = DataValidation(type="list", formula1='"MODIFY,REMOVE,ADD"', allow_blank=True)
        dv_role = DataValidation(type="list", formula1='"Viewer,Commenter,Editor"', allow_blank=True)
        dv_principal = DataValidation(type="list", formula1='"user,group,domain"', allow_blank=True)
        
        # --- MODIFIED: Column letters updated for the new layout ---
        # Note: 'Current Download Restriction' is now column J (read-only, no dropdown)
        dv_action.add('K2:K1048576')      # Action_Type
        dv_role.add('L2:L1048576')        # New_Role
        dv_principal.add('M2:M1048576')   # Type of account (for ADD)
        dv_set_restrict.add('O2:O1048576') # SET Download Restriction
        
        ws.add_data_validation(dv_action)
        ws.add_data_validation(dv_role)
        ws.add_data_validation(dv_principal)
        ws.add_data_validation(dv_set_restrict) # Add the new dropdown validation
        # --- END MODIFICATION ---

        fill_add = PatternFill(start_color="FFD8E9BB", end_color="FFD8E9BB", fill_type="solid")
        fill_remove = PatternFill(start_color="FFFFC7CE", end_color="FFFFC7CE", fill_type="solid")
        fill_modify = PatternFill(start_color="FFFFEB9C", end_color="FFFFEB9C", fill_type="solid")
        
        # --- MODIFIED: Range extended to cover the new column O ---
        full_range = 'A2:O1048576'
        ws.conditional_formatting.add(full_range, FormulaRule(formula=['=$K2="ADD"'], fill=fill_add))
        ws.conditional_formatting.add(full_range, FormulaRule(formula=['=$K2="REMOVE"'], fill=fill_remove))
        ws.conditional_formatting.add(full_range, FormulaRule(formula=['=$K2="MODIFY"'], fill=fill_modify))
        
        wb.save(filename)
        logging.info(f"Successfully added auto-filter, dropdowns, and formatting to {filename}")
    except Exception as e:
        logging.error(f"Could not add dropdowns or formatting to {filename}. Reason: {e}")

def write_report_to_excel(report_data, filename):
    """Writes the report data to an Excel file. Returns True on success, False on failure."""
    if not report_data:
        logging.warning("No data to write to Excel report.")
        return True
    try:
        df = pd.DataFrame(report_data)
        
        # --- MODIFIED: New action column for setting download restriction ---
        action_columns = ['Action_Type', 'New_Role', 'Type of account (for ADD)', 'Email/Domain (for ADD)', 'SET Download Restriction']
        for col in action_columns: df[col] = ''
        
        # --- MODIFIED: Column order updated to reflect the new design ---
        column_order = ['Full Path', 'Item Name', 'Item ID', 'Role', 'Principal Type', 'Email Address', 'Owner', 'Google Drive URL', 'Root Folder ID', 'Current Download Restriction'] + action_columns
        
        df = df.reindex(columns=column_order)
        df.to_excel(filename, index=False, engine='openpyxl')
        add_dropdowns_to_sheet(filename)
        return True
    except Exception as e:
        logging.error(f"Failed to write Excel file to {filename}: {e}")
        return False
