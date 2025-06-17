import pandas as pd
import logging

def write_report_to_csv(report_data, filename):
    """Writes report data to a CSV file. Used for backups."""
    if not report_data:
        logging.warning("No data to write to CSV report.")
        return
    try:
        df = pd.DataFrame(report_data)
        df.to_csv(filename, index=False, encoding='utf-8')
        # This function is for silent backup, so no success message is needed here.
    except Exception as e:
        logging.error(f"Failed to write backup CSV to {filename}: {e}")


def write_report_to_excel(report_data, filename):
    """Writes the report data to a user-friendly Excel file with Action Builder columns."""
    if not report_data:
        logging.warning("No data to write to Excel report.")
        return
    try:
        df = pd.DataFrame(report_data)
        
        # Add the new Action Builder columns
        action_columns = ['Action_Type', 'New_Role', 'Add_Principal_Type', 'Add_Principal_Address']
        for col in action_columns:
            df[col] = ''
        
        # Define and reorder columns for usability
        column_order = [
            'Full Path', 'Item Name', 'Item ID', 'Role', 'Principal Type', 
            'Email Address', 'Owner', 'Google Drive URL'
        ] + action_columns
        
        df = df.reindex(columns=[col for col in column_order if col in df.columns])

        # Use the openpyxl engine for modern .xlsx format
        df.to_excel(filename, index=False, engine='openpyxl')
        logging.info(f"Excel report successfully written to {filename}")
    except Exception as e:
        logging.error(f"Failed to write Excel file to {filename}: {e}")