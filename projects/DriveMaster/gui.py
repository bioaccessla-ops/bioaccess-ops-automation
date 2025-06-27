# gui.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import logging
from queue import Queue
import os # Import the os module

# Import the controller functions
from src.controller import run_fetch, run_apply_changes, run_rollback, get_fetch_output_path
from src.auth import authenticate_and_get_service # Import auth for the pre-check

# --- Custom Logging Handler to safely update the GUI from other threads ---
class GuiHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DriveMaster Control Panel")
        self.geometry("700x600")
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill="both", expand=True)
        self.create_fetch_widgets()
        self.create_apply_widgets()
        self.create_rollback_widgets()
        self.create_output_widgets()
        self.log_queue = Queue()
        self.queue_handler = GuiHandler(self.log_queue)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[self.queue_handler])
        self.after(100, self.poll_log_queue)

    # ... (create_apply_widgets, create_rollback_widgets, create_output_widgets are unchanged) ...
    def create_fetch_widgets(self):
        frame = ttk.LabelFrame(self.main_frame, text="1. Fetch Permissions", padding="10")
        frame.pack(fill="x", expand=False, pady=5)
        ttk.Label(frame, text="Google Drive Folder ID:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.fetch_id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.fetch_id_var).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(frame, text="Optional User Email:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.fetch_email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.fetch_email_var).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(frame, text="Run Fetch", command=self.on_fetch).grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        frame.columnconfigure(1, weight=1)

    def create_apply_widgets(self):
        frame = ttk.LabelFrame(self.main_frame, text="2. Apply Changes", padding="10")
        frame.pack(fill="x", expand=False, pady=5)
        self.apply_file_var = tk.StringVar()
        ttk.Label(frame, text="Permissions Excel File:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(frame, textvariable=self.apply_file_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(frame, text="Browse...", command=lambda: self.apply_file_var.set(filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")]))).grid(row=0, column=2, padx=5)
        self.apply_live_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Make LIVE changes (default is a safe Dry Run)", variable=self.apply_live_var).grid(row=1, column=0, columnspan=3, sticky="w", padx=5)
        ttk.Button(frame, text="Run Apply-Changes", command=self.on_apply).grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        frame.columnconfigure(1, weight=1)

    def create_rollback_widgets(self):
        frame = ttk.LabelFrame(self.main_frame, text="3. Rollback Changes", padding="10")
        frame.pack(fill="x", expand=False, pady=5)
        self.log_file_var = tk.StringVar()
        ttk.Label(frame, text="Audit Log File:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(frame, textvariable=self.log_file_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(frame, text="Browse...", command=lambda: self.log_file_var.set(filedialog.askopenfilename(filetypes=[("Log Files", "*.csv")]))).grid(row=0, column=2, padx=5)
        self.rollback_live_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Perform LIVE rollback (default is a safe Dry Run)", variable=self.rollback_live_var).grid(row=1, column=0, columnspan=3, sticky="w", padx=5)
        ttk.Button(frame, text="Run Rollback", command=self.on_rollback).grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        frame.columnconfigure(1, weight=1)

    def create_output_widgets(self):
        frame = ttk.LabelFrame(self.main_frame, text="Output Log", padding="10")
        frame.pack(fill="both", expand=True, pady=5)
        self.output_text = tk.Text(frame, wrap="word", height=10, font=("Courier New", 9))
        self.output_text.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1); frame.rowconfigure(0, weight=1)

    def poll_log_queue(self):
        while not self.log_queue.empty():
            record = self.log_queue.get()
            self.output_text.insert(tk.END, record + '\n')
            self.output_text.see(tk.END)
        self.after(100, self.poll_log_queue)

    def clear_output(self):
        self.output_text.delete(1.0, tk.END)

    def run_in_thread(self, target, *args):
        threading.Thread(target=target, args=args, daemon=True).start()

    def on_fetch(self):
        """Handles the 'Run Fetch' button click, with a pre-check for locked files."""
        self.clear_output()
        folder_id = self.fetch_id_var.get()
        if not folder_id:
            messagebox.showerror("Error", "Please enter a Folder ID.")
            return

        # --- START: New Pre-Check Logic ---
        # First, we need an authenticated service to get the folder name
        service = authenticate_and_get_service()
        if not service:
            logging.critical("Authentication failed. Cannot proceed with fetch.")
            return
        
        # Determine the exact path of the file we are about to create
        output_path = get_fetch_output_path(service, folder_id)
        if not output_path:
            messagebox.showerror("Error", "Could not determine the output file path. Check logs for details.")
            return

        # Now, check if the file exists and is locked
        while os.path.exists(output_path):
            try:
                # Try to open the file in append mode to test the lock.
                # If it's locked by Excel, this will raise a PermissionError.
                with open(output_path, 'a'):
                    pass
                # If we get here, the file exists but is not locked, so we can break the loop.
                break
            except PermissionError:
                # The file is locked! Ask the user what to do.
                user_choice = messagebox.askyesno(
                    "File In Use",
                    f"The report file is currently open:\n\n{output_path}\n\nPlease close the file to allow it to be overwritten.\n\nDo you want to retry?",
                    icon='warning'
                )
                if not user_choice: # If user clicks "No"
                    logging.warning("Fetch operation cancelled by user because file is in use.")
                    return
                # If user clicks "Yes", the while loop will repeat the check
            except Exception as e:
                messagebox.showerror("Error", f"An unexpected error occurred while checking the file: {e}")
                return
        # --- END: New Pre-Check Logic ---

        # If we get here, the file is either not locked or doesn't exist. It's safe to run the fetch.
        logging.info("Pre-flight check passed. Starting fetch operation...")
        self.run_in_thread(run_fetch, folder_id, self.fetch_email_var.get() or None)

    # ... (on_apply and on_rollback methods are unchanged) ...
    def on_apply(self):
        excel_file = self.apply_file_var.get(); is_live = self.apply_live_var.get()
        if not excel_file: messagebox.showerror("Error", "Please select a permissions Excel file."); return
        if is_live and not messagebox.askyesno("Live Run Confirmation", "!!! WARNING !!!\nThis will apply changes to Google Drive.\n\nAre you sure you want to proceed?"):
            logging.warning("Live Apply-Changes cancelled by user."); return
        self.clear_output()
        self.run_in_thread(run_apply_changes, excel_file, is_live)

    def on_rollback(self):
        log_file = self.log_file_var.get(); is_live = self.rollback_live_var.get()
        if not log_file: messagebox.showerror("Error", "Please select an audit log file."); return
        if is_live and not messagebox.askyesno("Live Rollback Confirmation", "!!! WARNING !!!\nThis will revert permissions on Google Drive.\n\nAre you sure you want to proceed?"):
            logging.warning("Live Rollback cancelled by user."); return
        self.clear_output()
        self.run_in_thread(run_rollback, log_file, is_live)


if __name__ == "__main__":
    app = App()
    app.mainloop()