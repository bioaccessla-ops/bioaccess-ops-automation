# spreadsheet_handler.py
import pandas as pd
import logging

def write_report_to_csv(report_data, filename):
    """Writes the report data to a CSV file with an ACTION column."""
    if not report_data:
        logging.warning("No data to write to report.")
        return

    df = pd.DataFrame(report_data)
    
    # Add the empty ACTION column for user input
    df['ACTION'] = ''
    
    # Reorder columns for usability
    column_order = ['Full Path', 'Item Name', 'Item ID', 'Role', 'Principal Type', 
                    'Email Address', 'Owner', 'Google Drive URL', 'ACTION']
    # Filter to only include columns that exist, in case some are missing
    df = df.reindex(columns=[col for col in column_order if col in df.columns])

    df.to_csv(filename, index=False)
    logging.info(f"Report successfully written to {filename}")