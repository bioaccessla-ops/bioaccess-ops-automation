import pandas as pd
import logging
from openpyxl import load_workbook
from openpyxl.worksheet.datavalidation import DataValidation

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


def add_dropdowns_to_sheet(filename):
    """Opens an existing Excel file and adds Data Validation dropdowns."""
    try:
        wb = load_workbook(filename)
        ws = wb.active

        # --- CORRECTED: Define Data Validation rules ---
        # The formula must be a string containing comma-separated values, enclosed in double quotes.
        dv_action = DataValidation(type="list", formula1='"MODIFY,REMOVE,ADD"', allow_blank=True)
        dv_role = DataValidation(type="list", formula1='"Viewer,Commenter,Editor"', allow_blank=True)
        dv_principal = DataValidation(type="list", formula1='"user,group,domain"', allow_blank=True)

        # Add the validation rules to the worksheet object
        ws.add_data_validation(dv_action)
        ws.add_data_validation(dv_role)
        ws.add_data_validation(dv_principal)

        # --- Specify the cell ranges for the dropdowns ---
        # Applies the validation to all rows from row 2 downwards in the specified columns
        dv_action.add('I2:I1048576')      # Column I for Action_Type
        dv_role.add('J2:J1048576')        # Column J for New_Role
        dv_principal.add('K2:K1048576')   # Column K for Add_Principal_Type

        wb.save(filename)
        logging.info(f"Successfully added dropdown menus to {filename}")
    except Exception as e:
        logging.error(f"Could not add dropdown menus to {filename}. Reason: {e}")


def write_report_to_excel(report_data, filename):
    """Writes the report data to a user-friendly Excel file with Action Builder columns."""
    if not report_data:
        logging.warning("No data to write to Excel report.")
        return
    try:
        df = pd.DataFrame(report_data)
        
        action_columns = ['Action_Type', 'New_Role', 'Add_Principal_Type', 'Add_Principal_Address']
        for col in action_columns:
            df[col] = ''
        
        column_order = [
            'Full Path', 'Item Name', 'Item ID', 'Role', 'Principal Type', 
            'Email Address', 'Owner', 'Google Drive URL'
        ] + action_columns
        
        df = df.reindex(columns=[col for col in column_order if col in df.columns])

        # Step 1: Pandas writes the data
        df.to_excel(filename, index=False, engine='openpyxl')
        
        # Step 2: Openpyxl adds the dropdowns to the file that was just saved
        add_dropdowns_to_sheet(filename)
        
    except Exception as e:
        logging.error(f"Failed to write Excel file to {filename}: {e}")