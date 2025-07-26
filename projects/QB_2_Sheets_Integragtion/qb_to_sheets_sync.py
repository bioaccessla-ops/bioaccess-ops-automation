
# qb_to_sheets_sync.py
import os
import json
from intuitlib.client import AuthClient
from quickbooks.objects.customer import Customer
from quickbooks.objects.invoice import Invoice
# REMOVE THIS LINE: from quickbooks.objects.report import Report # For reports like P&L
from quickbooks.exceptions import QuickbooksException

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration (now loaded from .env file) ---
QB_CLIENT_ID = os.environ.get("QB_CLIENT_ID")
QB_CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET")
QB_REFRESH_TOKEN = os.environ.get("QB_REFRESH_TOKEN")
QB_REDIRECT_URI = os.environ.get("QB_REDIRECT_URI")
QB_REALM_ID = os.environ.get("QB_REALM_ID")
QB_ENVIRONMENT = os.environ.get("QB_ENVIRONMENT") # Will be "sandbox" or "production"

GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_FILE_PATH = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE_PATH")

# Define the scopes required for Google Sheets API
GOOGLE_SHEETS_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly' # Optional: if you need to list files
]

# --- QuickBooks Functions ---
def get_quickbooks_client(refresh_token=None):
    """
    Initializes and authenticates QuickBooks client, refreshing token if needed.
    """
    if not all([QB_CLIENT_ID, QB_CLIENT_SECRET, QB_REALM_ID, QB_REFRESH_TOKEN]):
        raise ValueError("QuickBooks API credentials/tokens (Client ID, Client Secret, Refresh Token, Realm ID) are not set in your .env file.")

    # Use the persistent refresh token for subsequent authentications
    auth_client = AuthClient(
        client_id=QB_CLIENT_ID,
        client_secret=QB_CLIENT_SECRET,
        redirect_uri=QB_REDIRECT_URI, # <--- ADD THIS LINE
        refresh_token=refresh_token or QB_REFRESH_TOKEN, # Use provided refresh_token or global
        environment=QB_ENVIRONMENT,
    )

    try:
        # Refresh the access token using the refresh token
        auth_client.refresh()
        print("QuickBooks Access Token refreshed successfully.")
        
        # This is where you would ideally update your .env file
        # with the potentially new refresh token, if it changes.
        # For simplicity in this example, we're assuming it doesn't change frequently
        # or you'll manually update it if AuthClient.refresh() indicates a new one.
        # In a production setup, you might use a secrets manager or write back to .env.
        
        # In qb_to_sheets_sync.py, near the top:
        from quickbooks.client import QuickBooks # <--- CORRECTED IMPORT
        qb_client = QuickBooks(
            #consumer_key=QB_CLIENT_ID,
            #consumer_secret=QB_CLIENT_SECRET,
            #access_token=auth_client.access_token,
            auth_client=auth_client,
            sandbox=True if QB_ENVIRONMENT == "sandbox" else False,
            company_id=QB_REALM_ID,
            minorversion=65 # Use a recent minor version for broader field access
        )
        return qb_client
    except QuickbooksException as e:
        print(f"QuickBooks API Error during authentication/refresh: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during QuickBooks authentication: {e}")
        raise

def extract_quickbooks_data(qb_client, data_type="Customer"):
    """
    Extracts specified data type from QuickBooks.
    'data_type' can be 'Customer', 'Invoice', 'Bill', 'SalesReceipt', 'Report_ProfitAndLoss', etc.
    """
    data = []
    if data_type == "Customer":
        print("Extracting Customer data...")
        customers = Customer.all(qb=qb_client)
        for customer in customers:
            data.append({
                "Id": customer.Id,
                "DisplayName": customer.DisplayName,
                "CompanyName": customer.CompanyName,
                "PrimaryEmailAddr": customer.PrimaryEmailAddr.Address if hasattr(customer.PrimaryEmailAddr, 'Address') else '',
                "PrimaryPhone": customer.PrimaryPhone.FreeFormNumber if hasattr(customer.PrimaryPhone, 'FreeFormNumber') else '',
                "Active": customer.Active,
                "Balance": customer.Balance,
                "CreateTime": customer.MetaData.CreateTime.split('T')[0] if hasattr(customer.MetaData, 'CreateTime') else '', # Format date
                "LastUpdatedTime": customer.MetaData.LastUpdatedTime.split('T')[0] if hasattr(customer.MetaData, 'LastUpdatedTime') else '',
                # Add more customer fields you need
            })
        print(f"Extracted {len(data)} customers.")
    
    elif data_type == "Invoice":
        print("Extracting Invoice data...")
        # You can filter invoices, e.g., by date
        # invoices = Invoice.filter(TxnDate__gt='2024-01-01', qb=qb_client)
        invoices = Invoice.all(qb=qb_client) # Get all invoices (be careful with large datasets)
        for invoice in invoices:
            line_items = []
            if hasattr(invoice, 'Line') and invoice.Line:
                for line in invoice.Line:
                    if hasattr(line, 'SalesItemLineDetail') and line.SalesItemLineDetail:
                        line_items.append({
                            "ItemRef": line.SalesItemLineDetail.ItemRef.name if hasattr(line.SalesItemLineDetail.ItemRef, 'name') else '',
                            "ItemQty": line.SalesItemLineDetail.Qty if hasattr(line.SalesItemLineDetail, 'Qty') else 0,
                            "ItemUnitPrice": line.SalesItemLineDetail.UnitPrice if hasattr(line.SalesItemLineDetail, 'UnitPrice') else 0,
                            "LineAmount": line.Amount,
                            "LineDescription": line.Description if hasattr(line, 'Description') else ''
                        })
                    elif hasattr(line, 'Description'): # For description-only lines
                        line_items.append({
                            "ItemRef": "Description Only",
                            "ItemQty": 0,
                            "ItemUnitPrice": 0,
                            "LineAmount": line.Amount,
                            "LineDescription": line.Description
                        })
            
            data.append({
                "Id": invoice.Id,
                "DocNumber": invoice.DocNumber,
                "TxnDate": invoice.TxnDate.split('T')[0] if hasattr(invoice, 'TxnDate') else '',
                "CustomerRef": invoice.CustomerRef.name if hasattr(invoice.CustomerRef, 'name') else '',
                "TotalAmt": invoice.TotalAmt,
                "Balance": invoice.Balance,
                "DueDate": invoice.DueDate.split('T')[0] if hasattr(invoice, 'DueDate') else '',
                "Status": invoice.MetaData.LastUpdatedTime if hasattr(invoice.MetaData, 'LastUpdatedTime') else '', # You might need to derive status
                "LineItems": json.dumps(line_items) # Store line items as JSON string
                # Add more invoice fields you need
            })
        print(f"Extracted {len(data)} invoices.")

    elif data_type == "Report_ProfitAndLoss":
        print("Generating Profit and Loss Report...")
        # Use qb_client.reports directly to access report methods
        # Note: 'profit_and_loss' is typically lowercase with underscores
        report_data = qb_client.reports.profit_and_loss( # <--- CHANGED THIS LINE
            start_date='2023-01-01', # Example: specify start date
            end_date='2023-12-31',   # Example: specify end date
            summarize_by='Month',    # Example: summarize by month
            minorversion=65
        )
        # Reports data structure is complex, often involves parsing rows and columns
        # This is a simplified example, you'll need to parse based on the report structure
        # A common approach is to flatten the report structure into a tabular format
        
        # Example: Extracting rows from a simple P&L report
        if hasattr(report_data, 'Rows') and hasattr(report_data.Rows, 'Row'):
            for row in report_data.Rows.Row:
                row_type = row.type # e.g., "DataRow", "Section", "Summary"
                if row_type == "DataRow" and hasattr(row, 'ColData'):
                    row_dict = {"Account": row.ColData[0].value} # First column is often the account name
                    for i, col in enumerate(row.ColData[1:]): # Subsequent columns are values
                        # Assuming 'ColData' contains columns for periods (e.g., months)
                        # The actual column names depend on summarize_by
                        # You'll need to map these based on report_data.Columns.Column
                        col_name = f"Column_{i+1}" # Placeholder
                        if hasattr(report_data.Columns, 'Column') and i < len(report_data.Columns.Column) - 1:
                            col_name = report_data.Columns.Column[i+1].ColTitle or col_name
                        row_dict[col_name] = col.value
                    data.append(row_dict)
        print(f"Extracted P&L report data with {len(data)} rows.")

    return data

# --- Google Sheets Functions ---
def get_google_sheets_client():
    """Authenticates and returns a gspread client using a service account."""
    if not GOOGLE_SERVICE_ACCOUNT_FILE_PATH or not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE_PATH):
        raise FileNotFoundError(f"Service account key file not found at: {GOOGLE_SERVICE_ACCOUNT_FILE_PATH}")

    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE_PATH, scopes=GOOGLE_SHEETS_SCOPES)
    gc = gspread.authorize(creds)
    print("Google Sheets client authenticated.")
    return gc

def update_google_sheet(gc, spreadsheet_id, sheet_name, data):
    """
    Updates a Google Sheet with the given list of dictionaries.
    Assumes the first dictionary's keys are headers.
    """
    if not data:
        print(f"No data to write to Google Sheet '{sheet_name}'. Clearing existing content.")
        try:
            spreadsheet = gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            worksheet.clear()
            print(f"Cleared existing content in '{sheet_name}'.")
        except gspread.exceptions.WorksheetNotFound:
            print(f"Worksheet '{sheet_name}' not found. No content to clear.")
        except Exception as e:
            print(f"Error clearing sheet '{sheet_name}': {e}")
        return

    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        print(f"Opened spreadsheet: {spreadsheet.title}")
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: Google Sheet with ID '{spreadsheet_id}' not found. Check ID and sharing permissions.")
        return
    except Exception as e:
        print(f"Error opening spreadsheet: {e}")
        return

    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        print(f"Found worksheet: {sheet_name}")
    except gspread.exceptions.WorksheetNotFound:
        print(f"Worksheet '{sheet_name}' not found. Creating new worksheet...")
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1", cols="1")
        print(f"Created new worksheet: {sheet_name}")
    except Exception as e:
        print(f"Error accessing or creating worksheet: {e}")
        return

    # Prepare data for Google Sheets
    df = pd.DataFrame(data)
    headers = df.columns.tolist()
    values_to_write = [headers] + df.values.tolist()

    # Clear existing content and write new data in one go
    # This is more efficient than clearing and then updating rows individually
    try:
        # worksheet.clear() # Optional: clear only if you're sure you want to overwrite everything
        # Update the entire range starting from A1
        # This will automatically expand the sheet if needed
        worksheet.update(range_name=f"A1", values=values_to_write, value_input_option='RAW')
        print(f"Successfully updated Google Sheet '{sheet_name}' with {len(data)} records.")
    except Exception as e:
        print(f"Error writing data to Google Sheet '{sheet_name}': {e}")


# --- Main Automation Logic ---
def run_automation():
    try:
        # 1. Authenticate with QuickBooks
        qb_client = get_quickbooks_client()

        # 2. Extract Data (Example: Customers and Invoices)
        customer_data = extract_quickbooks_data(qb_client, data_type="Customer")
        invoice_data = extract_quickbooks_data(qb_client, data_type="Invoice")
        
        # Example for report data (more complex parsing might be needed)
        # Uncomment and uncomment the corresponding update_google_sheet call if you want to test reports
        # pnl_report_data = extract_quickbooks_data(qb_client, data_type="Report_ProfitAndLoss")


        # 3. Authenticate with Google Sheets
        gc = get_google_sheets_client()

        # 4. Update Google Sheets
        update_google_sheet(gc, GOOGLE_SHEET_ID, "Customers Data", customer_data)
        update_google_sheet(gc, GOOGLE_SHEET_ID, "Invoices Data", invoice_data)
        # update_google_sheet(gc, GOOGLE_SHEET_ID, "Profit & Loss 2023", pnl_report_data) # For reports

        print("\nAutomation process completed successfully!")

    except ValueError as ve:
        print(f"Configuration Error: {ve}")
        print("Please ensure all environment variables are set correctly in your .env file.")
    except FileNotFoundError as fnfe:
        print(f"File Error: {fnfe}")
        print("Please check the path to your Google Service Account Key file in your .env file.")
    except Exception as e:
        print(f"An unexpected error occurred during automation: {e}")

if __name__ == "__main__":
    run_automation() 