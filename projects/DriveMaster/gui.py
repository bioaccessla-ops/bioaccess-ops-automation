import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import logging
from queue import Queue
import os
from PIL import Image, ImageTk

from src.controller import run_fetch, prepare_apply_changes, execute_apply_changes, prepare_rollback, execute_rollback
from src.auth import authenticate_and_get_service, reset_authentication
from src.spreadsheet_handler import write_report_to_excel

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
        self.geometry("750x750") # Increased height for progress bar

        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'app_icon.ico')
            self.iconbitmap(icon_path)
        except Exception as e:
            logging.warning(f"Could not load application icon: {e}")

        header_frame = ttk.Frame(self, padding=(10, 10, 10, 0))
        header_frame.pack(fill="x")
        header_frame.columnconfigure(0, weight=1); header_frame.columnconfigure(2, weight=1)
        title_container = ttk.Frame(header_frame); title_container.grid(row=0, column=1)

        try:
            logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
            img = Image.open(logo_path); img.thumbnail((150, 60))
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
        self.create_progress_widgets() # New progress bar section
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
        self.fetch_button = ttk.Button(frame, text="Run Fetch", command=self.on_fetch)
        self.fetch_button.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
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
        self.apply_button = ttk.Button(frame, text="Run Apply-Changes", command=self.on_apply)
        self.apply_button.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
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
        self.rollback_button = ttk.Button(frame, text="Run Rollback", command=self.on_rollback)
        self.rollback_button.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        frame.columnconfigure(1, weight=1)

    def create_advanced_widgets(self):
        frame = ttk.LabelFrame(self.main_frame, text="Advanced Settings", padding="10")
        frame.pack(fill="x", expand=False, pady=5)
        ttk.Button(frame, text="Switch User Account", command=self.on_reset_auth).pack(side="left", padx=5, pady=5)
        ttk.Label(frame, text="Deletes the saved login token to allow a different Google user to sign in.").pack(side="left", padx=10, fill="x")

    def create_progress_widgets(self):
        self.progress_frame = ttk.LabelFrame(self.main_frame, text="Progress", padding="10")
        self.progress_frame.pack(fill="x", expand=False, pady=5)
        
        self.progress_label = ttk.Label(self.progress_frame, text="Idle")
        self.progress_label.pack(fill="x", expand=True, side="left", padx=5)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", expand=True, side="right")
        self.progress_frame.pack_forget() # Hide by default

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
            self.output_text.insert(tk.END, self.log_queue.get() + '\n')
            self.output_text.see(tk.END)
        self.after(100, self.poll_log_queue)

    def clear_output(self):
        self.output_text.delete(1.0, tk.END)

    def run_in_thread(self, target, *args):
        threading.Thread(target=target, args=args, daemon=True).start()

    def update_progress(self, current, total):
        if total > 0:
            self.progress_bar['maximum'] = total
            self.progress_bar['value'] = current
            self.progress_label['text'] = f"Processing item {current} of {total}..."
        else:
            self.progress_label['text'] = "Discovering items..."
            self.progress_bar['mode'] = 'indeterminate'
            self.progress_bar.start(10)

    def on_fetch(self):
        self.clear_output()
        folder_id = self.fetch_id_var.get()
        if not folder_id:
            messagebox.showerror("Error", "Please enter a Folder ID.")
            return
        
        self.progress_frame.pack(fill="x", expand=False, pady=5)
        self.update_progress(0, 0)
        
        self.fetch_button.config(state="disabled")
        self.run_in_thread(self._fetch_worker, folder_id, self.update_progress)

    def _fetch_worker(self, folder_id, progress_callback):
        report_data, output_path = run_fetch(folder_id, progress_callback=progress_callback)
        self.after(0, self._on_fetch_complete, report_data, output_path)

    def _on_fetch_complete(self, report_data, output_path):
        self.fetch_button.config(state="normal")
        self.progress_frame.pack_forget()
        self.progress_bar.stop()
        self.progress_bar['mode'] = 'determinate'

        if report_data is None:
            logging.error("Fetch operation failed. Check logs for details.")
            return
        if not report_data:
            logging.info("--- Fetch complete (no data to write) ---")
            return

        while True:
            try:
                if write_report_to_excel(report_data, output_path):
                    logging.info(f"User-facing Excel report saved to {output_path}")
                logging.info("--- Fetch complete ---")
                break 
            except PermissionError:
                if not messagebox.askyesno("File In Use", f"The report file is currently open:\n\n{output_path}\n\nPlease close the file to proceed.\n\nRetry?"):
                    logging.warning("Fetch cancelled by user during file write.")
                    break
            except Exception as e:
                messagebox.showerror("Error", f"An unexpected error occurred: {e}")
                break

    def on_apply(self):
        excel_file, is_live = self.apply_file_var.get(), self.apply_live_var.get()
        if not excel_file:
            messagebox.showerror("Error", "Please select a permissions Excel file.")
            return

        self.clear_output()
        plan, live_data, root_id, self_mod_flag = prepare_apply_changes(excel_file)

        if plan is None: return
        num_affected = len({action['Item ID'] for action in plan})

        if num_affected == 0:
            messagebox.showinfo("No Changes", "No changes were detected.")
            return

        if self_mod_flag and not messagebox.askyesno("Confirm Self-Modification", "!!! WARNING !!!\nThis operation will modify your own permissions. Are you sure?"):
            logging.warning("Operation cancelled by user due to self-modification warning.")
            return

        if messagebox.askyesno("Confirm Action", f"This will affect {num_affected} item(s).\nMode: {'LIVE' if is_live else 'Dry Run'}\nProceed?"):
            self.run_in_thread(execute_apply_changes, plan, live_data, root_id, is_live)
        else:
            logging.warning("Operation cancelled by user.")

    def on_rollback(self):
        log_file, is_live = self.log_file_var.get(), self.rollback_live_var.get()
        if not log_file:
            messagebox.showerror("Error", "Please select an audit log file.")
            return

        self.clear_output()
        plan, live_data, root_id, self_mod_flag = prepare_rollback(log_file)

        if plan is None: return
        num_affected = len({action['Item ID'] for action in plan})

        if num_affected == 0:
            messagebox.showinfo("No Changes", "No actions to roll back.")
            return

        if self_mod_flag and not messagebox.askyesno("Confirm Self-Modification", "!!! WARNING !!!\nThis rollback will modify your own permissions. Are you sure?"):
            logging.warning("Rollback cancelled by user due to self-modification warning.")
            return

        if messagebox.askyesno("Confirm Rollback", f"This will affect {num_affected} item(s).\nMode: {'LIVE' if is_live else 'Dry Run'}\nProceed?"):
            self.run_in_thread(execute_rollback, plan, live_data, root_id, is_live)
        else:
            logging.warning("Rollback cancelled by user.")

    def on_reset_auth(self):
        if messagebox.askyesno("Confirm Action", "This will log you out. Are you sure?"):
            if reset_authentication():
                messagebox.showinfo("Success", "Authentication has been reset.")
            else:
                messagebox.showerror("Error", "Could not delete the token file.")

if __name__ == "__main__":
    app = App()
    app.mainloop()
