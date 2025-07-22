import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import logging
from queue import Queue
import os
from PIL import Image, ImageTk

from src.controller import run_fetch, prepare_apply_changes, execute_apply_changes, prepare_rollback, execute_rollback, get_fetch_output_path
from src.auth import authenticate_and_get_service, reset_authentication

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
        self.geometry("750x700")

        header_frame = ttk.Frame(self, padding=(10, 10, 10, 0))
        header_frame.pack(fill="x")
        header_frame.columnconfigure(0, weight=1)
        header_frame.columnconfigure(2, weight=1)

        title_container = ttk.Frame(header_frame)
        title_container.grid(row=0, column=1)

        self.logo_image = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
            img = Image.open(logo_path)
            img.thumbnail((150, 60))
            self.logo_image = ImageTk.PhotoImage(img)
            ttk.Label(title_container, image=self.logo_image).pack(side="left", padx=(0, 10))
        except FileNotFoundError:
            ttk.Label(title_container, text="[Logo]", font=('Helvetica', 12, 'italic')).pack(side="left", padx=(0, 10))
            
        ttk.Label(title_container, text='DriveMaster: Permissions Control Panel', font=('Helvetica', 16, 'bold')).pack(side="left")

        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill="both", expand=True)
        
        self.create_fetch_widgets()
        self.create_apply_widgets()
        self.create_rollback_widgets()
        self.create_advanced_widgets()
        self.create_output_widgets()
        
        self.log_queue = Queue()
        self.queue_handler = GuiHandler(self.log_queue)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[self.queue_handler])
        
        self.after(100, self.poll_log_queue)

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

    def create_advanced_widgets(self):
        frame = ttk.LabelFrame(self.main_frame, text="Advanced Settings", padding="10")
        frame.pack(fill="x", expand=False, pady=5)
        ttk.Button(frame, text="Switch User Account", command=self.on_reset_auth).pack(side="left", padx=5, pady=5)
        ttk.Label(frame, text="Deletes the saved login token to allow a different Google user to sign in on the next run.").pack(side="left", padx=10, fill="x")
        frame.columnconfigure(1, weight=1)

    def create_output_widgets(self):
        frame = ttk.LabelFrame(self.main_frame, text="Output Log", padding="10")
        frame.pack(fill="both", expand=True, pady=5)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=(0, 5))
        ttk.Button(button_frame, text="Clear Log", command=self.clear_output).pack(side="right")
        self.output_text = tk.Text(frame, wrap="word", height=10, font=("Courier New", 9))
        self.output_text.pack(fill="both", expand=True)

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
        self.clear_output(); folder_id = self.fetch_id_var.get()
        if not folder_id: messagebox.showerror("Error", "Please enter a Folder ID."); return
        self.run_in_thread(run_fetch, folder_id, self.fetch_email_var.get() or None)

    def on_apply(self):
        excel_file, is_live = self.apply_file_var.get(), self.apply_live_var.get()
        if not excel_file:
            messagebox.showerror("Error", "Please select a permissions Excel file.")
            return

        self.clear_output()
        
        plan, live_data, root_id = prepare_apply_changes(excel_file)

        if plan is None:
            messagebox.showerror("Error", "Failed to prepare changes. Please check the logs for details.")
            return

        affected_item_ids = {action['Item ID'] for action in plan}
        num_affected = len(affected_item_ids)

        if num_affected == 0:
            messagebox.showinfo("No Changes", "No changes were detected between the Excel file and the current Google Drive state.")
            return

        confirmation_message = (
            f"This operation will affect {num_affected} file(s)/folder(s).\n\n"
            f"Mode: {'**LIVE RUN**' if is_live else 'Dry Run (No changes will be made)'}\n\n"
            "Do you want to proceed?"
        )
        
        if messagebox.askyesno("Confirm Action", confirmation_message):
            logging.info(f"User confirmed. Executing plan with {len(plan)} actions...")
            self.run_in_thread(execute_apply_changes, plan, live_data, root_id, is_live)
        else:
            logging.warning("Operation cancelled by user.")

    def on_rollback(self):
        """
        Handles the new two-step rollback process:
        1. Prepare the plan (blocking, in main thread).
        2. Ask for confirmation.
        3. Execute the plan (non-blocking, in a new thread).
        """
        log_file, is_live = self.log_file_var.get(), self.rollback_live_var.get()
        if not log_file:
            messagebox.showerror("Error", "Please select an audit log file.")
            return

        self.clear_output()
        
        plan, live_data, root_id = prepare_rollback(log_file)

        if plan is None:
            messagebox.showerror("Error", "Failed to prepare rollback. Please check the logs for details.")
            return

        affected_item_ids = {action['Item ID'] for action in plan}
        num_affected = len(affected_item_ids)

        if num_affected == 0:
            messagebox.showinfo("No Changes", "No successful actions found in the audit log to roll back.")
            return

        confirmation_message = (
            f"This rollback operation will affect {num_affected} file(s)/folder(s).\n\n"
            f"Mode: {'**LIVE ROLLBACK**' if is_live else 'Dry Run (No changes will be made)'}\n\n"
            "This will revert permissions on Google Drive.\n\n"
            "Are you sure you want to proceed?"
        )
        
        if messagebox.askyesno("Confirm Rollback", confirmation_message):
            logging.info(f"User confirmed. Executing rollback plan with {len(plan)} actions...")
            self.run_in_thread(execute_rollback, plan, live_data, root_id, is_live)
        else:
            logging.warning("Rollback operation cancelled by user.")

    def on_reset_auth(self):
        if messagebox.askyesno("Confirm Action", "This will log you out. You will need to re-authenticate on the next action.\n\nAre you sure you want to proceed?"):
            if reset_authentication():
                messagebox.showinfo("Success", "Authentication has been reset.\n\nYou will be prompted to log in with a new Google account on the next run.")
            else:
                messagebox.showerror("Error", "Could not delete the authentication token file. Please check the logs or file permissions.")

if __name__ == "__main__":
    app = App()
    app.mainloop()
