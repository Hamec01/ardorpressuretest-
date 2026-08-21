import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import List, Optional

from wika_report import __version__
from wika_report.config import AppConfig, load_config
from wika_report.file_processor import process_single_csv
from wika_report.logging_setup import setup_logging


class WikaAppGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WIKA CPG1500 Pressure Analyzer")
        self.root.geometry("860x820")
        self.root.minsize(800, 780)

        # Set window icon if available
        self.icon_path = Path(__file__).parent.parent.parent / "resources" / "app_icon.ico"
        if self.icon_path.exists():
            try:
                self.root.iconbitmap(str(self.icon_path))
            except Exception:
                pass

        self.project_root = Path.cwd()
        self.config_path = self.project_root / "config.json"
        self.config = load_config(self.config_path)

        self.selected_files: List[Path] = []
        self.is_processing = False

        self._create_widgets()

    def _create_widgets(self):
        # Configure styles
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Header.TFrame", background="#1F4E79")
        style.configure("HeaderTitle.TLabel", font=("Segoe UI", 16, "bold"), foreground="#FFFFFF", background="#1F4E79")
        style.configure("HeaderSub.TLabel", font=("Segoe UI", 9), foreground="#D9EAD3", background="#1F4E79")
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=8)

        # Header Frame
        header_frame = ttk.Frame(self.root, style="Header.TFrame")
        header_frame.pack(fill=tk.X, side=tk.TOP)

        title_lbl = ttk.Label(
            header_frame,
            text="WIKA CPG1500 Pressure CSV Analyzer",
            style="HeaderTitle.TLabel"
        )
        title_lbl.pack(anchor=tk.W, padx=20, pady=(15, 2))

        sub_lbl = ttk.Label(
            header_frame,
            text=f"Automatic parsing, pressure cleaning, 0-160 bar visualization & report generator | v{__version__}",
            style="HeaderSub.TLabel"
        )
        sub_lbl.pack(anchor=tk.W, padx=20, pady=(0, 15))

        # Main Container
        main_container = ttk.Frame(self.root, padding=15)
        main_container.pack(fill=tk.BOTH, expand=True)

        # File Selection Frame
        btn_frame = ttk.LabelFrame(main_container, text=" File Selection ", padding=10)
        btn_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 10))

        btn_files = ttk.Button(
            btn_frame,
            text="📁 Select CSV File(s)...",
            style="Action.TButton",
            command=self._select_files
        )
        btn_files.pack(side=tk.LEFT, padx=(0, 10))

        btn_folder = ttk.Button(
            btn_frame,
            text="📂 Select Folder...",
            style="Action.TButton",
            command=self._select_folder
        )
        btn_folder.pack(side=tk.LEFT, padx=(0, 10))

        btn_clear = ttk.Button(
            btn_frame,
            text="Clear Selection",
            command=self._clear_selection
        )
        btn_clear.pack(side=tk.RIGHT)

        # Selected Files Label
        self.selection_status_var = tk.StringVar(value="No files selected. Click buttons above to add CSV files.")
        selection_lbl = ttk.Label(main_container, textvariable=self.selection_status_var, font=("Segoe UI", 9, "italic"))
        selection_lbl.pack(anchor=tk.W, pady=(0, 5))

        # Metadata & Options Box
        meta_frame = ttk.LabelFrame(main_container, text=" Report Metadata (ARDOR Template) ", padding=10)
        meta_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 10))

        # Column 0: Left side metadata
        ttk.Label(meta_frame, text="Test Pressure:").grid(row=0, column=0, sticky=tk.W, pady=3, padx=(0, 5))
        self.test_pressure_var = tk.StringVar(value=self.config.graph.default_test_pressure)
        ttk.Entry(meta_frame, textvariable=self.test_pressure_var, width=18).grid(row=0, column=1, sticky=tk.W, pady=3, padx=(0, 15))

        ttk.Label(meta_frame, text="System:").grid(row=1, column=0, sticky=tk.W, pady=3, padx=(0, 5))
        self.system_var = tk.StringVar(value=self.config.graph.default_system)
        ttk.Entry(meta_frame, textvariable=self.system_var, width=18).grid(row=1, column=1, sticky=tk.W, pady=3, padx=(0, 15))

        ttk.Label(meta_frame, text="Log.No:").grid(row=2, column=0, sticky=tk.W, pady=3, padx=(0, 5))
        self.log_no_var = tk.StringVar(value=self.config.graph.default_log_no)
        ttk.Entry(meta_frame, textvariable=self.log_no_var, width=18).grid(row=2, column=1, sticky=tk.W, pady=3, padx=(0, 15))

        ttk.Label(meta_frame, text="Ins.No:").grid(row=3, column=0, sticky=tk.W, pady=3, padx=(0, 5))
        self.ins_no_var = tk.StringVar(value=self.config.graph.default_ins_no)
        ttk.Entry(meta_frame, textvariable=self.ins_no_var, width=18).grid(row=3, column=1, sticky=tk.W, pady=3, padx=(0, 15))

        # Column 2: Right side metadata
        ttk.Label(meta_frame, text="Project:").grid(row=0, column=2, sticky=tk.W, pady=3, padx=(10, 5))
        self.project_var = tk.StringVar(value=self.config.graph.default_project)
        ttk.Entry(meta_frame, textvariable=self.project_var, width=18).grid(row=0, column=3, sticky=tk.W, pady=3, padx=(0, 15))

        ttk.Label(meta_frame, text="Note:").grid(row=1, column=2, sticky=tk.W, pady=3, padx=(10, 5))
        self.note_var = tk.StringVar(value=self.config.graph.default_note)
        ttk.Entry(meta_frame, textvariable=self.note_var, width=18).grid(row=1, column=3, sticky=tk.W, pady=3, padx=(0, 15))

        ttk.Label(meta_frame, text="Wika.Nr:").grid(row=2, column=2, sticky=tk.W, pady=3, padx=(10, 5))
        
        self.wika_nr_var = tk.StringVar(value=self.config.graph.wika_nr_active)
        self.wika_combo = ttk.Combobox(meta_frame, textvariable=self.wika_nr_var, values=self.config.graph.wika_nr_list, width=16)
        self.wika_combo.grid(row=2, column=3, sticky=tk.W, pady=3, padx=(0, 5))
        
        btn_add_wika = ttk.Button(meta_frame, text="+", width=2, command=self._add_wika_nr)
        btn_add_wika.grid(row=2, column=4, sticky=tk.W, pady=3)

        # Date Row with manual override checkbox
        self.auto_date_var = tk.BooleanVar(value=True)
        chk_auto_date = ttk.Checkbutton(meta_frame, text="Auto Date from CSV", variable=self.auto_date_var, command=self._toggle_date_state)
        chk_auto_date.grid(row=3, column=2, columnspan=2, sticky=tk.W, pady=3, padx=(10, 0))

        self.custom_date_var = tk.StringVar(value="")
        self.custom_date_entry = ttk.Entry(meta_frame, textvariable=self.custom_date_var, width=12)
        self.custom_date_entry.grid(row=3, column=3, sticky=tk.E, pady=3, padx=(0, 15))
        self._toggle_date_state()

        # Settings Box (Y-axis, Temp, etc.)
        settings_frame = ttk.LabelFrame(main_container, text=" Graph & Scale Settings ", padding=10)
        settings_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 10))

        ttk.Label(settings_frame, text="Y-Axis Min (bar):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.ymin_var = tk.StringVar(value=str(self.config.graph.y_min_bar if self.config.graph.y_min_bar is not None else 0.0))
        ymin_entry = ttk.Entry(settings_frame, textvariable=self.ymin_var, width=10)
        ymin_entry.grid(row=0, column=1, padx=(0, 20))

        ttk.Label(settings_frame, text="Y-Axis Max (bar):").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.ymax_var = tk.StringVar(value=str(self.config.graph.y_max_bar if self.config.graph.y_max_bar is not None else 160.0))
        ymax_entry = ttk.Entry(settings_frame, textvariable=self.ymax_var, width=10)
        ymax_entry.grid(row=0, column=3, padx=(0, 20))

        self.auto_open_var = tk.BooleanVar(value=self.config.open_output_folder_after_finish)
        auto_open_chk = ttk.Checkbutton(settings_frame, text="Open output folder after processing", variable=self.auto_open_var)
        auto_open_chk.grid(row=0, column=4, sticky=tk.W)

        # Row 1: Temperature checkbox & Pipe Checkbox
        self.plot_temperature_var = tk.BooleanVar(value=self.config.graph.plot_temperature)
        plot_temp_chk = ttk.Checkbutton(settings_frame, text="Plot Temperature (if in CSV)", variable=self.plot_temperature_var)
        plot_temp_chk.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        self.show_pipe_logs_var = tk.BooleanVar(value=self.config.graph.show_pipe_logs)
        show_pipes_chk = ttk.Checkbutton(
            settings_frame, 
            text="Add Pipe Logs to PNG", 
            variable=self.show_pipe_logs_var,
            command=self._toggle_pipe_logs_state
        )
        show_pipes_chk.grid(row=1, column=2, columnspan=2, sticky=tk.W, pady=(5, 0))

        # Row 2: PDF generation option & Photo attachments selection
        self.create_pdf_var = tk.BooleanVar(value=False)
        create_pdf_chk = ttk.Checkbutton(settings_frame, text="Create PDF Report", variable=self.create_pdf_var, command=self._toggle_pdf_photos_state)
        create_pdf_chk.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        self.attached_photos: List[str] = []
        self.btn_attach_photos = ttk.Button(settings_frame, text="📸 Attach Photos (0)", command=self._attach_photos, state=tk.DISABLED)
        self.btn_attach_photos.grid(row=2, column=2, sticky=tk.W, pady=(5, 0))
        self.btn_clear_photos = ttk.Button(settings_frame, text="❌ Clear", command=self._clear_photos, state=tk.DISABLED)
        self.btn_clear_photos.grid(row=2, column=3, sticky=tk.W, pady=(5, 0), padx=(5, 0))

        # Row 3: PipeCloud Workflow checkbox
        self.pipecloud_added_var = tk.BooleanVar(value=False)
        pipecloud_chk = ttk.Checkbutton(settings_frame, text="☁ Added to PipeCloud", variable=self.pipecloud_added_var)
        pipecloud_chk.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        # Row 4: Pipe Logs Text Entry
        ttk.Label(settings_frame, text="Pipe Logs (one per line):").grid(row=4, column=0, sticky=tk.NW, padx=(0, 5), pady=(5, 0))
        self.pipe_logs_text = tk.Text(settings_frame, font=("Consolas", 9), height=3, width=40)
        self.pipe_logs_text.insert("1.0", self.config.graph.pipe_logs_text)
        self.pipe_logs_text.grid(row=4, column=1, columnspan=4, sticky=tk.W, pady=(5, 0))
        
        self._toggle_pipe_logs_state()
        self._toggle_pdf_photos_state()

        # Log & Progress Frame
        log_frame = ttk.LabelFrame(main_container, text=" Processing Log & Status ", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP, pady=(0, 10))

        self.progress_bar = ttk.Progressbar(log_frame, mode="determinate")
        self.progress_bar.pack(fill=tk.X, side=tk.TOP, pady=(0, 10))

        # Log Text Box
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 9), height=4, bg="#F8F9FA")
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bottom Action Bar
        bottom_frame = ttk.Frame(main_container)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_run = ttk.Button(
            bottom_frame,
            text="▶ START PROCESSING",
            style="Primary.TButton",
            command=self._start_processing
        )
        self.btn_run.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_sync = ttk.Button(
            bottom_frame,
            text="🔄 Sync Server",
            style="Action.TButton",
            command=self._start_server_sync
        )
        self.btn_sync.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_queue = ttk.Button(
            bottom_frame,
            text="📋 Queue",
            command=self._show_queue_dialog
        )
        self.btn_queue.pack(side=tk.LEFT)

        btn_open_out = ttk.Button(
            bottom_frame,
            text="📂 Open Output Folder",
            style="Action.TButton",
            command=self._open_output_folder
        )
        btn_open_out.pack(side=tk.RIGHT)

    def _toggle_date_state(self):
        """Enable custom date field if manual mode is selected."""
        if self.auto_date_var.get():
            self.custom_date_entry.configure(state=tk.DISABLED)
        else:
            self.custom_date_entry.configure(state=tk.NORMAL)

    def _add_wika_nr(self):
        """Allows user to add new WIKA measurement serial numbers to the list."""
        from tkinter import simpledialog
        new_nr = simpledialog.askstring("Add WIKA Nr", "Enter new WIKA serial/instrument number:")
        if new_nr:
            new_nr = new_nr.strip()
            if new_nr and new_nr not in self.config.graph.wika_nr_list:
                self.config.graph.wika_nr_list.append(new_nr)
                self.wika_combo.configure(values=self.config.graph.wika_nr_list)
                self.wika_nr_var.set(new_nr)

    def _log(self, message: str):
        """Appends a message to the live GUI log box."""
        def append():
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        self.root.after(0, append)

    def _select_files(self):
        files = filedialog.askopenfilenames(
            title="Select WIKA CPG1500 CSV Files",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if files:
            for f in files:
                p = Path(f).resolve()
                if p not in self.selected_files:
                    self.selected_files.append(p)
            self._update_selection_status()

    def _select_folder(self):
        folder = filedialog.askdirectory(title="Select Folder Containing CSV Files")
        if folder:
            f_path = Path(folder).resolve()
            found = [
                f for f in f_path.glob("*.csv")
                if f.is_file() and not f.name.startswith("~") and not f.name.startswith(".")
            ]
            if not found:
                messagebox.showwarning("No CSV Files Found", f"No *.csv files were found in:\n{folder}")
                return
            for f in found:
                if f not in self.selected_files:
                    self.selected_files.append(f)
            self._update_selection_status()

    def _clear_selection(self):
        self.selected_files.clear()
        self._update_selection_status()
        self.progress_bar["value"] = 0
        self.log_text.delete("1.0", tk.END)

    def _update_selection_status(self):
        count = len(self.selected_files)
        if count == 0:
            self.selection_status_var.set("No files selected. Click buttons above to add CSV files.")
        elif count == 1:
            self.selection_status_var.set(f"1 file selected: {self.selected_files[0].name}")
        else:
            self.selection_status_var.set(f"{count} files selected: {', '.join(f.name for f in self.selected_files[:3])}...")

    def _open_output_folder(self):
        out_dir = self.project_root / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(out_dir))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open output folder:\n{e}")

    def _start_processing(self):
        if self.is_processing:
            return

        if not self.selected_files:
            messagebox.showwarning("Selection Required", "Please select at least one CSV file or folder before processing.")
            return

        # Validate Date format if manual date is enabled
        if not self.auto_date_var.get():
            date_str = self.custom_date_var.get().strip()
            # Simple check for DD.MM.YYYY format
            import re
            if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
                messagebox.showerror(
                    "Invalid Date",
                    f"Manual date '{date_str}' is invalid.\nPlease use DD.MM.YYYY format (e.g. 12.08.2026)."
                )
                return

        # Update Y-axis settings from entry fields
        try:
            ymin = float(self.ymin_var.get())
            ymax = float(self.ymax_var.get())
            self.config.graph.y_min_bar = ymin
            self.config.graph.y_max_bar = ymax
        except ValueError:
            messagebox.showerror("Invalid Input", "Y-Axis Min and Max must be valid numbers.")
            return

        # Set configs from user interface inputs
        self.config.open_output_folder_after_finish = self.auto_open_var.get()
        self.config.graph.plot_temperature = self.plot_temperature_var.get()
        self.config.graph.show_pipe_logs = self.show_pipe_logs_var.get()
        self.config.graph.pipe_logs_text = self.pipe_logs_text.get("1.0", tk.END).strip()
        self.config.graph.wika_nr_active = self.wika_nr_var.get()

        # Update defaults in config based on current inputs
        self.config.graph.default_test_pressure = self.test_pressure_var.get()
        self.config.graph.default_system = self.system_var.get()
        self.config.graph.default_log_no = self.log_no_var.get()
        self.config.graph.default_ins_no = self.ins_no_var.get()
        self.config.graph.default_project = self.project_var.get()
        self.config.graph.default_note = self.note_var.get()

        self.is_processing = True
        self.btn_run.configure(state=tk.DISABLED)
        self.log_text.delete("1.0", tk.END)
        self.progress_bar["value"] = 0

        # Run batch processing in background thread
        thread = threading.Thread(target=self._run_processing_thread, daemon=True)
        thread.start()

    def _toggle_pipe_logs_state(self):
        """Enable or disable the pipe logs text field depending on the checkbox."""
        if self.show_pipe_logs_var.get():
            self.pipe_logs_text.configure(state=tk.NORMAL, bg="#FFFFFF")
        else:
            self.pipe_logs_text.configure(state=tk.DISABLED, bg="#F0F0F0")

    def _toggle_pdf_photos_state(self):
        """Enable/Disable photo selection based on PDF checkbox state."""
        state = tk.NORMAL if self.create_pdf_var.get() else tk.DISABLED
        self.btn_attach_photos.configure(state=state)
        self.btn_clear_photos.configure(state=state)

    def _attach_photos(self):
        """Browse and select photo attachments."""
        files = filedialog.askopenfilenames(
            title="Select Photos (Gauge/Pipe)",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.webp"), ("All Files", "*.*")]
        )
        if files:
            self.attached_photos = list(files)
            self.btn_attach_photos.configure(text=f"📸 Attach Photos ({len(self.attached_photos)})")

    def _clear_photos(self):
        """Clear all attached photos."""
        self.attached_photos = []
        self.btn_attach_photos.configure(text="📸 Attach Photos (0)")

    def _run_processing_thread(self):
        total = len(self.selected_files)
        output_dir = self.project_root / "output"
        processed_dir = self.project_root / "processed"
        failed_dir = self.project_root / "failed"

        setup_logging(output_dir / "logs")

        self._log(f"============================================================")
        self._log(f" Starting Processing Batch: {total} file(s)")
        self._log(f" Scale: {self.config.graph.y_min_bar} to {self.config.graph.y_max_bar} bar")
        self._log(f"============================================================\n")

        success_count = 0
        failed_count = 0

        for idx, file_path in enumerate(self.selected_files, 1):
            self._log(f"[{idx}/{total}] Processing: {file_path.name}...")
            
            # Extract metadata from GUI elements
            from wika_report.models import CustomMetadata
            override_meta = CustomMetadata(
                test_pressure=self.test_pressure_var.get(),
                system=self.system_var.get(),
                log_no=self.log_no_var.get(),
                ins_no=self.ins_no_var.get(),
                custom_date="" if self.auto_date_var.get() else self.custom_date_var.get(),
                project=self.project_var.get(),
                note=self.note_var.get(),
                wika_nr=self.wika_nr_var.get(),
                create_pdf=self.create_pdf_var.get(),
                attach_photos=list(self.attached_photos),
                pipe_logs_text=self.pipe_logs_text.get("1.0", tk.END).strip()
            )

            # Process CSV with GUI metadata overrides directly
            res = process_single_csv(
                file_path=file_path,
                output_dir=output_dir,
                processed_dir=processed_dir,
                failed_dir=failed_dir,
                config=self.config,
                override_custom_meta=override_meta
            )

            if res.success:
                success_count += 1
                folder_name = res.graph_path.parent.name if res.graph_path else "output"
                self._log(f"  --> [SUCCESS] PNG, XLSX, TXT & PDF reports saved to output/{folder_name}/")

            else:
                failed_count += 1
                self._log(f"  --> [FAILED] {res.error_message}")

            # Update progress bar
            pct = (idx / total) * 100
            self.root.after(0, lambda p=pct: self.progress_bar.configure(value=p))

        self._log("\n============================================================")
        self._log(f"BATCH COMPLETE:")
        self._log(f"  Total Files:  {total}")
        self._log(f"  Successful:   {success_count}")
        self._log(f"  Failed:       {failed_count}")
        self._log(f"============================================================\n")

        # Save config.json with updated defaults/lists
        try:
            import json
            # Read current file to preserve other structures, then save
            # For simplicity, write a clean serialized version of config
            # But to keep it robust:
            cfg_to_save = {
                "target_unit": self.config.target_unit,
                "default_input_unit": self.config.default_input_unit,
                "move_processed_files": self.config.move_processed_files,
                "open_output_folder_after_finish": self.config.open_output_folder_after_finish,
                "graph": {
                    "y_min_bar": self.config.graph.y_min_bar,
                    "y_max_bar": self.config.graph.y_max_bar,
                    "show_datetime": self.config.graph.show_datetime,
                    "show_pipe_logs": self.config.graph.show_pipe_logs,
                    "pipe_logs_text": self.config.graph.pipe_logs_text,
                    "plot_temperature": self.config.graph.plot_temperature,
                    "wika_nr_list": self.config.graph.wika_nr_list,
                    "wika_nr_active": self.config.graph.wika_nr_active,
                    "default_test_pressure": self.config.graph.default_test_pressure,
                    "default_system": self.config.graph.default_system,
                    "default_log_no": self.config.graph.default_log_no,
                    "default_ins_no": self.config.graph.default_ins_no,
                    "default_project": self.config.graph.default_project,
                    "default_note": self.config.graph.default_note
                }
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg_to_save, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self._log(f"Warning: Failed to save updated config: {e}")

        # Re-enable button & open folder
        def on_complete():
            self.is_processing = False
            self.btn_run.configure(state=tk.NORMAL)

            if self.config.open_output_folder_after_finish:
                self._open_output_folder()

            messagebox.showinfo(
                "Processing Complete",
                f"Batch processing complete!\n\nSuccessful: {success_count}\nFailed: {failed_count}\n\nResults saved to: output/"
            )

        self.root.after(0, on_complete)

    def _start_server_sync(self):
        """Запускает синхронизацию локальной очереди с бэкенд-сервером."""
        from wika_report.sync_client import SyncClient
        from wika_report.sync_queue import sync_queue

        summary = sync_queue.get_summary()
        pending_count = summary.get("pending", 0) + summary.get("failed", 0)
        if pending_count == 0:
            self._log("[СИНХРОНИЗАЦИЯ] Все ревизии уже синхронизированы с сервером.")
            messagebox.showinfo("Sync", "All test logs are already synced with the server.")
            return

        server_url = self.config.get("server_url") or os.environ.get("ARDOR_SERVER_URL") or "http://127.0.0.1:8080"
        self._log(f"\n[СИНХРОНИЗАЦИЯ] Начало отправки {pending_count} элементов на сервер ({server_url})...")
        self.btn_sync.configure(state=tk.DISABLED)

        def sync_worker():
            client = SyncClient(base_url=server_url)
            if not client.check_health():
                self._log(f"[СЕРВЕР НЕДОСТУПЕН] Сервер не отвечает ({server_url}). Логи безопасно сохранены в локальной офлайн-очереди.")
                self.root.after(0, lambda: self.btn_sync.configure(state=tk.NORMAL))
                self.root.after(0, lambda: messagebox.showwarning(
                    "Server Offline",
                    f"Backend server is offline or unreachable ({server_url}).\n\nPlease verify connection and server status.\nAll test logs remain safely queued offline in SQLite."
                ))
                return

            res = client.sync_all_pending()
            self._log(f"[СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА] Синхронизировано: {res['synced']}, Ошибок: {res['failed']}")
            self.root.after(0, lambda: self.btn_sync.configure(state=tk.NORMAL))
            self.root.after(0, lambda: messagebox.showinfo(
                "Sync Finished",
                f"Synchronization complete!\n\nSynced: {res['synced']}\nFailed: {res['failed']}"
            ))

        threading.Thread(target=sync_worker, daemon=True).start()

    def _show_queue_dialog(self):
        """Отображает окно с историей и статусом очереди синхронизации."""
        from wika_report.sync_queue import sync_queue
        items = sync_queue.get_all_items()

        win = tk.Toplevel(self.root)
        win.title("Offline Sync Queue")
        win.geometry("680x400")
        win.minsize(550, 300)

        top_frame = ttk.Frame(win, padding=10)
        top_frame.pack(fill=tk.X)

        summary = sync_queue.get_summary()
        lbl_stats = ttk.Label(
            top_frame,
            text=f"Total: {summary['total']} | Pending: {summary['pending']} | Synced: {summary['synced']} | Failed: {summary['failed']}",
            font=("Segoe UI", 10, "bold")
        )
        lbl_stats.pack(side=tk.LEFT)

        btn_sync_now = ttk.Button(top_frame, text="Sync Now", command=lambda: [win.destroy(), self._start_server_sync()])
        btn_sync_now.pack(side=tk.RIGHT)

        tree_frame = ttk.Frame(win, padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("log_no", "revision_id", "status", "created_at", "receipt")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        tree.heading("log_no", text="Log No.")
        tree.heading("revision_id", text="Revision ID")
        tree.heading("status", text="Status")
        tree.heading("created_at", text="Created At")
        tree.heading("receipt", text="Receipt / Info")

        tree.column("log_no", width=90, anchor=tk.CENTER)
        tree.column("revision_id", width=140, anchor=tk.CENTER)
        tree.column("status", width=80, anchor=tk.CENTER)
        tree.column("created_at", width=150, anchor=tk.CENTER)
        tree.column("receipt", width=180, anchor=tk.W)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for it in items:
            tree.insert("", tk.END, values=(
                it.log_no,
                it.revision_id,
                it.status.upper(),
                it.created_at[:19].replace("T", " "),
                it.receipt_id or it.last_error or "-"
            ))


def launch_gui():
    root = tk.Tk()
    app = WikaAppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
