import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os
import datetime as dt
import paramiko
import sys
import shutil
from ttkthemes import ThemedTk
import threading
import queue
import base64
import socket
import subprocess
import stat
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

class CryptoManager:
    def __init__(self, password: str, salt: bytes):
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000, backend=default_backend())
        key = base64.urlsafe_b64encode(kdf.derive(password.encode())); self.fernet = Fernet(key)
    def encrypt(self, data: str) -> str: return self.fernet.encrypt(data.encode()).decode() if data else ""
    def decrypt(self, encrypted_data: str) -> str:
        if not encrypted_data: return ""
        try: return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception: return "DECRYPT_FAILED"

class GUIAuthHandler(paramiko.auth_handler.AuthHandler):
    def __init__(self, root: tk.Tk, mfa_queue: queue.Queue):
        self.root, self.mfa_queue = root, mfa_queue
    def __call__(self, title, instructions, prompt_list):
        self.root.after(0, self.ask_for_code, title, prompt_list)
        response = self.mfa_queue.get()
        return [response] if response is not None else []
    def ask_for_code(self, title, prompt_list):
        prompt_text = prompt_list[0][0] if prompt_list else "Código de Verificación:"
        self.mfa_queue.put(simpledialog.askstring(title, prompt_text, parent=self.root))

###utilerias##
class UtilitiesWindow(tk.Toplevel):
    def __init__(self, parent, commands_widget):
        super().__init__(parent); self.transient(parent); self.grab_set(); self.commands_target_widget = commands_widget
        self.title("Utilerias"); self.geometry("900x600"); self.minsize(600, 400)
        self.json_path = "utilities.json"; self.utilities_data: list[dict] = []; self.selected_item_index: int | None = None
        self.columns = ('Categoria', 'Comando', 'Descripcion', 'Ejemplo'); self.search_var = tk.StringVar(); self._search_after_id: str | None = None
        self.search_var.trace_add("write", self.schedule_filter_update); self.load_utilities_data(); self.create_widgets(); self.populate_table()
    def load_utilities_data(self):
        default_data = [{'Categoria': 'Gestión de Carpetas', 'Comando': 'ls -la', 'Descripcion': 'Lista detallada con ocultos.', 'Ejemplo': 'ls -la /tmp'}]
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f: self.utilities_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): self.utilities_data = default_data; self.save_utilities_data()
    def save_utilities_data(self):
        with open(self.json_path, 'w', encoding='utf-8') as f: json.dump(self.utilities_data, f, indent=4, ensure_ascii=False)
    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10"); main_frame.pack(fill="both", expand=True)
        main_frame.grid_rowconfigure(2, weight=1); main_frame.grid_columnconfigure(0, weight=1)
        filter_frame = ttk.Frame(main_frame); filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10)); filter_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Buscar:").grid(row=0, column=0, padx=(0, 5)); ttk.Entry(filter_frame, textvariable=self.search_var).grid(row=0, column=1, sticky="ew")
        button_frame = ttk.Frame(main_frame); button_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5)); button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        ttk.Button(button_frame, text="Agregar", command=self.open_add_edit_popup).grid(row=0, column=0, padx=2, sticky="ew")
        ttk.Button(button_frame, text="Editar", command=lambda: self.open_add_edit_popup(edit_mode=True)).grid(row=0, column=1, padx=2, sticky="ew")
        ttk.Button(button_frame, text="Eliminar", command=self.delete_utility).grid(row=0, column=2, padx=2, sticky="ew")
        table_frame = ttk.Frame(main_frame); table_frame.grid(row=2, column=0, sticky="nsew"); table_frame.grid_rowconfigure(0, weight=1); table_frame.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(table_frame, columns=self.columns, show="headings")
        for col in self.columns:
            self.tree.heading(col, text=col)
            if col in ['Descripcion', 'Ejemplo']: self.tree.column(col, width=220, minwidth=120)
            else: self.tree.column(col, width=120, minwidth=80)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select); self.tree.bind("<Double-1>", self.append_command_to_main_window)
        yscrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview); xscrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscrollbar.set, xscrollcommand=xscrollbar.set); self.tree.grid(row=0, column=0, sticky="nsew"); yscrollbar.grid(row=0, column=1, sticky="ns"); xscrollbar.grid(row=1, column=0, sticky="ew")
    def on_tree_select(self, event):
        if selected_items := self.tree.selection():
            selected_values = self.tree.item(selected_items[0], 'values')
            self.selected_item_index = next((i for i, item in enumerate(self.utilities_data) if all(str(item.get(self.columns[j], '')) == str(selected_values[j]) for j in range(len(self.columns)))), None)
    def append_command_to_main_window(self, event=None):
        if not self.tree.selection(): return
        command_to_append = self.tree.item(self.tree.selection()[0], 'values')[1]
        if not command_to_append or not self.commands_target_widget or not self.commands_target_widget.winfo_exists(): return
        if current_text := self.commands_target_widget.get("1.0", tk.END).strip(): self.commands_target_widget.insert(tk.END, f"\n{command_to_append}")
        else: self.commands_target_widget.insert("1.0", command_to_append)
        self.commands_target_widget.see(tk.END); original_title = self.title(); self.title("¡Comando Añadido!")
        self.after(1000, lambda: self.title(original_title))
    def populate_table(self, data=None):
        data_to_show = data if data is not None else self.utilities_data; self.tree.delete(*self.tree.get_children()); self.selected_item_index = None
        for item in data_to_show: self.tree.insert("", "end", values=[item.get(col, "") for col in self.columns])
    def schedule_filter_update(self, *args):
        if self._search_after_id: self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(300, self.filter_table)
    def filter_table(self):
        search_term = self.search_var.get().lower()
        self.populate_table([item for item in self.utilities_data if any(search_term in str(value).lower() for value in item.values())] if search_term else self.utilities_data)
    def delete_utility(self):
        if self.selected_item_index is None: messagebox.showwarning("Advertencia", "Por favor, seleccione un comando para eliminar.", parent=self); return
        if messagebox.askyesno("Confirmar", f"¿Eliminar '{self.utilities_data[self.selected_item_index]['Comando']}'?", parent=self):
            del self.utilities_data[self.selected_item_index]; self.save_utilities_data(); self.filter_table()
    def open_add_edit_popup(self, edit_mode=False):
        if edit_mode and self.selected_item_index is None: messagebox.showwarning("Advertencia", "Por favor, seleccione un comando para editar.", parent=self); return
        popup = tk.Toplevel(self); popup.transient(self); popup.grab_set(); popup.title("Editar Comando" if edit_mode else "Agregar Comando")
        record = self.utilities_data[self.selected_item_index] if edit_mode and self.selected_item_index is not None else {col: "" for col in self.columns}
        entry_vars = {}
        for i, col in enumerate(self.columns):
            ttk.Label(popup, text=f"{col}:").grid(row=i*2, column=0, padx=10, pady=5, sticky="w")
            if col in ['Descripcion', 'Ejemplo']: entry = tk.Text(popup, height=4, width=40, wrap="word"); entry.insert("1.0", record.get(col, "")); entry.grid(row=i*2+1, column=0, columnspan=2, padx=10, pady=2, sticky="ew")
            else: entry = ttk.Entry(popup, width=50); entry.insert(0, record.get(col, "")); entry.grid(row=i*2+1, column=0, columnspan=2, padx=10, pady=2, sticky="ew")
            entry_vars[col] = entry
        def on_save():
            new_data = {col: widget.get("1.0", "end-1c") if isinstance(widget, tk.Text) else widget.get() for col, widget in entry_vars.items()}
            if not new_data.get("Comando"): messagebox.showerror("Error", "El campo 'Comando' es obligatorio.", parent=popup); return
            if edit_mode and self.selected_item_index is not None: self.utilities_data[self.selected_item_index] = new_data
            else: self.utilities_data.append(new_data)
            self.save_utilities_data(); self.filter_table(); popup.destroy()
        ttk.Button(popup, text="Guardar", command=on_save).grid(row=len(self.columns)*2, column=0, columnspan=2, pady=10)

class JsonTableApp:
    DEFAULT_COLUMNS_ORDER = [ "id", "hostname", "tag", "ip", "user", "auth_method", "password", "key_path", "port", "cargar", "subir" ]
    COLUMN_LABELS = { "id": "ID", "hostname": "Hostname", "tag": "Tag", "ip": "IP", "user": "Usuario", "auth_method": "Método Auth", "password": "Password / Passphrase", "key_path": "Ruta de Llave SSH", "port": "Puerto", "cargar": "Ruta Remota / Origen Local", "subir": "Ruta Destino Remoto" }
    SALT = b'\x12\xfa\x8e\x90\x1a\xde\xcc\xee\x11\x22\x33\x44\x55\x66\x77\x88'
    
    def __init__(self, root: ThemedTk):
        self.root = root; self.initialized_ok = False
        master_password = simpledialog.askstring("🔐 Seguridad KIOsko 🔐", "Ingrese su Contraseña Maestra para descifrar las configuraciones:", show='*')
        if not master_password: return
        self.crypto = CryptoManager(master_password, self.SALT); self.root.set_theme("arc"); self.root.title("KIOsko")
        try: self.root.iconbitmap("uno.ico")
        except tk.TclError: print("No se pudo encontrar el archivo 'uno.ico'.")
        self.root.geometry("1400x700"); self.root.minsize(900, 500) 
        self.root.grid_rowconfigure(0, weight=1); self.root.grid_columnconfigure(0, weight=1)
        self.json_file_path = "ssh_configs.json"; self.command_history_path = "command_history.json"; self.deploy_source_folder = "deploy"; self.downloads_folder = "descargas"; self.log_folder = "logs"; self.error_log_folder = os.path.join(self.log_folder, "errors")
        os.makedirs(self.deploy_source_folder, exist_ok=True); os.makedirs(self.downloads_folder, exist_ok=True); os.makedirs(self.log_folder, exist_ok=True); os.makedirs(self.error_log_folder, exist_ok=True)
        self.tree: ttk.Treeview | None = None; self.data: list[dict] = []; self.checked_items: dict[str, bool] = {}; self.entry_fields: dict[str, tk.Widget] = {}
        self.columns = ["*"] + self.DEFAULT_COLUMNS_ORDER
        self.search_var = tk.StringVar(); self._search_after_id: str | None = None; self.search_var.trace_add("write", self.schedule_filter_update)
        self.mfa_queue: "queue.Queue[str | None]" = queue.Queue(); self.select_all_var = tk.BooleanVar()
        self.original_stdout = sys.stdout; self.original_stderr = sys.stderr
        self.log_text_widget: tk.Text | None = None; self.error_log_widget: tk.Text | None = None; self.commands_text_area: tk.Text | None = None; self.history_listbox: tk.Listbox | None = None
        self.command_history = self.load_command_history(); self.sort_column = "id"; self.sort_descending = False
        self.test_type_var = tk.StringVar(value='ping'); self.test_port_var = tk.StringVar(value='22'); self.test_path_var = tk.StringVar(value='/')
        self.create_widgets()
        if not self.load_json_data(): return
        self.filter_table(); self.load_today_log()
        sys.stdout = self.TextRedirector(self, self.log_text_widget, 'stdout'); sys.stderr = self.TextRedirector(self, self.error_log_widget, 'stderr')
        self.initialized_ok = True

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="15"); main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1); main_frame.grid_rowconfigure(1, weight=0); main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=3); main_frame.grid_columnconfigure(1, weight=1, minsize=400)
        
        left_panel = ttk.Frame(main_frame); left_panel.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 10))
        left_panel.grid_rowconfigure(0, weight=1); left_panel.grid_rowconfigure(1, weight=0); left_panel.grid_rowconfigure(2, weight=1); left_panel.grid_columnconfigure(0, weight=1)
        table_frame = ttk.LabelFrame(left_panel, text="Servidores", padding=10); table_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        table_frame.grid_rowconfigure(1, weight=1); table_frame.grid_columnconfigure(0, weight=1)
        filter_frame = ttk.Frame(table_frame); filter_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,10)); filter_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Buscar:").grid(row=0, column=0, padx=(0, 5)); ttk.Entry(filter_frame, textvariable=self.search_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(filter_frame, text="Limpiar", command=self.clear_filter).grid(row=0, column=2, padx=(5, 0))
        self.select_all_checkbutton = ttk.Checkbutton(filter_frame, text="Seleccionar Visibles", variable=self.select_all_var, command=self.toggle_select_all)
        self.select_all_checkbutton.grid(row=0, column=3, padx=(10, 0))
        yscrollbar_table = ttk.Scrollbar(table_frame, orient="vertical"); xscrollbar_table = ttk.Scrollbar(table_frame, orient="horizontal")
        self.tree = ttk.Treeview(table_frame, yscrollcommand=yscrollbar_table.set, xscrollcommand=xscrollbar_table.set, show="headings")
        yscrollbar_table.config(command=self.tree.yview); xscrollbar_table.config(command=self.tree.xview)
        self.tree.grid(row=1, column=0, sticky="nsew"); yscrollbar_table.grid(row=1, column=1, sticky="ns"); xscrollbar_table.grid(row=2, column=0, sticky="ew")
        self.tree.bind("<Button-1>", self.on_item_click)
        self.tree.bind("<Double-1>", self.edit_record_popup)

        button_frame = ttk.Frame(left_panel); button_frame.grid(row=1, column=0, sticky="ew", pady=10)
        button_frame.grid_columnconfigure(tuple(range(7)), weight=1)
        ttk.Button(button_frame, text="➕ Agregar", command=self.add_record_popup).grid(row=0, column=0, sticky="ew", padx=3)
        ttk.Button(button_frame, text="✏️ Editar", command=self.edit_selected_record).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(button_frame, text="🗑️ Eliminar", command=self.delete_selected_records).grid(row=0, column=2, sticky="ew", padx=3)
        ttk.Button(button_frame, text="⚙️ Utilerias", command=self.open_utilities_window).grid(row=0, column=3, sticky="ew", padx=3)
        ttk.Button(button_frame, text="📂 Cargar", command=self.load_file_for_deploy).grid(row=0, column=4, sticky="ew", padx=3)
        ttk.Button(button_frame, text="⬆️ Subir", command=self.upload_files).grid(row=0, column=5, sticky="ew", padx=3)
        ttk.Button(button_frame, text="⬇️ Descargar", command=self.download_file).grid(row=0, column=6, sticky="ew", padx=3)
        
        log_frame = ttk.LabelFrame(left_panel, text="Registro de Actividad", padding=5); log_frame.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
        log_frame.grid_rowconfigure(0, weight=1); log_frame.grid_columnconfigure(0, weight=1)
        self.log_text_widget = tk.Text(log_frame, wrap="word", state="disabled", bg="black", fg="#4AE14A", insertbackground="#4AE14A", font=("Consolas", 10), relief="flat")
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text_widget.yview)
        self.log_text_widget.config(yscrollcommand=log_scrollbar.set); log_scrollbar.pack(side="right", fill="y"); self.log_text_widget.pack(side="left", fill="both", expand=True)
        
        right_panel = ttk.Frame(main_frame); right_panel.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=(10, 0))
        right_panel.grid_rowconfigure((0, 2), weight=1); right_panel.grid_rowconfigure(1, weight=0); right_panel.grid_columnconfigure(0, weight=1)
        
        error_log_frame = ttk.LabelFrame(right_panel, text="Errores", padding=5); error_log_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        error_log_frame.grid_rowconfigure(0, weight=1); error_log_frame.grid_columnconfigure(0, weight=1)
        self.error_log_widget = tk.Text(error_log_frame, wrap="word", state="disabled", bg="black", fg="#FF6B6B", insertbackground="#FF6B6B", font=("Consolas", 10), relief="flat")
        error_log_scrollbar = ttk.Scrollbar(error_log_frame, orient="vertical", command=self.error_log_widget.yview)
        self.error_log_widget.config(yscrollcommand=error_log_scrollbar.set); error_log_scrollbar.pack(side="right", fill="y"); self.error_log_widget.pack(side="left", fill="both", expand=True)
        
        commands_main_frame = ttk.LabelFrame(right_panel, text="Acciones", padding=5)
        commands_main_frame.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
        commands_main_frame.grid_rowconfigure(2, weight=1)
        commands_main_frame.grid_columnconfigure(0, weight=1)
        
        diag_tools_subframe = ttk.LabelFrame(commands_main_frame, text="Herramientas de Diagnóstico"); diag_tools_subframe.grid(row=0, column=0, sticky="ew", pady=5); diag_tools_subframe.grid_columnconfigure(4, weight=1)
        test_selector = ttk.Combobox(diag_tools_subframe, textvariable=self.test_type_var, values=['ping', 'telnet', 'curl'], state='readonly', width=8); test_selector.grid(row=0, column=0, padx=5, pady=5)
        test_selector.bind("<<ComboboxSelected>>", self._on_test_type_selected)
        self.diag_port_label = ttk.Label(diag_tools_subframe, text="Puerto:"); self.diag_port_entry = ttk.Entry(diag_tools_subframe, textvariable=self.test_port_var, width=6)
        self.diag_path_label = ttk.Label(diag_tools_subframe, text="Ruta:"); self.diag_path_entry = ttk.Entry(diag_tools_subframe, textvariable=self.test_path_var)
        self.diag_port_label.grid(row=0, column=1, padx=(10, 2), pady=5); self.diag_port_entry.grid(row=0, column=2, padx=2, pady=5)
        self.diag_path_label.grid(row=0, column=3, padx=(10, 2), pady=5); self.diag_path_entry.grid(row=0, column=4, padx=2, pady=5, sticky="ew")
        ttk.Button(diag_tools_subframe, text="Ejecutar Test", command=self.start_diagnostic_test_thread).grid(row=0, column=5, padx=5, pady=5)

        ssh_commands_subframe = ttk.LabelFrame(commands_main_frame, text="Comandos SSH"); ssh_commands_subframe.grid(row=1, column=0, sticky="ew", pady=(5, 5)); ssh_commands_subframe.grid_columnconfigure(0, weight=1)
        self.commands_text_area = tk.Text(ssh_commands_subframe, height=4, font=("Consolas", 10)); self.commands_text_area.pack(fill="x", expand=True, padx=5, pady=5)
        ttk.Button(ssh_commands_subframe, text="Lanzar Actividad SSH", command=self.start_ssh_thread).pack(fill="x", padx=5, pady=(0,5))
        
        history_frame = ttk.LabelFrame(commands_main_frame, text="Historial"); history_frame.grid(row=2, column=0, sticky="nsew"); history_frame.grid_rowconfigure(0, weight=1); history_frame.grid_columnconfigure(0, weight=1)
        history_scrollbar = ttk.Scrollbar(history_frame, orient="vertical"); self.history_listbox = tk.Listbox(history_frame, yscrollcommand=history_scrollbar.set, font=("Consolas", 10)); history_scrollbar.config(command=self.history_listbox.yview)
        self.history_listbox.grid(row=0, column=0, sticky="nsew"); history_scrollbar.grid(row=0, column=1, sticky="ns"); self.history_listbox.bind("<Double-1>", self._on_history_select)
        for cmd in self.command_history: self.history_listbox.insert(tk.END, cmd)
        
        self._on_test_type_selected()

    def _on_test_type_selected(self, event=None):
        test_type = self.test_type_var.get()
        if test_type == 'ping':
            self.diag_port_label.grid_remove(); self.diag_port_entry.grid_remove()
            self.diag_path_label.grid_remove(); self.diag_path_entry.grid_remove()
        elif test_type == 'telnet':
            self.diag_port_label.grid(); self.diag_port_entry.grid()
            self.diag_path_label.grid_remove(); self.diag_path_entry.grid_remove()
        elif test_type == 'curl':
            self.diag_port_label.grid(); self.diag_port_entry.grid()
            self.diag_path_label.grid(); self.diag_path_entry.grid()

    def _on_history_select(self, event=None):
        if not self.history_listbox.curselection(): return
        selected_command = self.history_listbox.get(self.history_listbox.curselection())
        if current_text := self.commands_text_area.get("1.0", tk.END).strip(): self.commands_text_area.insert(tk.END, f"\n{selected_command}")
        else: self.commands_text_area.insert("1.0", selected_command)
        self.commands_text_area.see(tk.END)

    def open_utilities_window(self): _ = UtilitiesWindow(self.root, self.commands_text_area)
    def clear_filter(self): self.search_var.set("")
    
    def schedule_filter_update(self, *args):
        if self._search_after_id: self.root.after_cancel(self._search_after_id)
        self._search_after_id = self.root.after(300, self.filter_table)
    
    def filter_table(self, *args): self.sort_by_column(self.sort_column, keep_direction=True)
    
    def toggle_select_all(self):
        new_state = self.select_all_var.get()
        for item_id in self.tree.get_children(): 
            self.checked_items[item_id] = new_state
            self.update_selection_marker(item_id, new_state)
        self.update_select_all_state()

    def update_select_all_state(self):
        items = self.tree.get_children()
        if not items: self.select_all_checkbutton.state(['!alternate']); self.select_all_var.set(False); return
        is_all = all(self.checked_items.get(i, False) for i in items)
        self.select_all_checkbutton.state(['!alternate']); self.select_all_var.set(is_all)
        if not is_all and any(self.checked_items.get(i, False) for i in items): self.select_all_checkbutton.state(['alternate'])
    
    def on_item_click(self, event):
        if (item_id := self.tree.identify_row(event.y)) and self.tree.identify_region(event.x, event.y) != "heading":
            if self.tree.identify_column(event.x) == "#1":
                new_state = not self.checked_items.get(item_id, False); self.checked_items[item_id] = new_state
                self.update_selection_marker(item_id, new_state); self.update_select_all_state()
    
    def load_command_history(self):
        if os.path.exists(self.command_history_path):
            try:
                with open(self.command_history_path, 'r', encoding='utf-8') as f: return json.load(f)
            except (json.JSONDecodeError, IOError): return []
        return []

    def save_command_history(self):
        try:
            with open(self.command_history_path, 'w', encoding='utf-8') as f: json.dump(self.command_history, f, indent=2)
        except IOError: self.error_log_message("No se pudo guardar el historial de comandos.")

    def update_command_history(self, command_text):
        commands = [cmd.strip() for cmd in command_text.strip().split('\n') if cmd.strip()]
        for command in reversed(commands):
            if command in self.command_history: self.command_history.remove(command)
            self.command_history.insert(0, command)
        self.command_history = self.command_history[:30]
        if self.history_listbox:
            self.history_listbox.delete(0, tk.END); [self.history_listbox.insert(tk.END, cmd) for cmd in self.command_history]
        self.save_command_history()

    def _get_next_id(self): return (max(int(r.get('id',0)) for r in self.data if str(r.get('id','0')).isdigit()) + 1) if self.data else 1
    
    def save_json_data(self):
        try:
            self.data.sort(key=lambda item: int(item.get('id', 0) or 0))
            encrypted_data = [ {**record, 'password': self.crypto.encrypt(record.get('password', ''))} for record in self.data ]
            with open(self.json_file_path, 'w', encoding='utf-8') as f: json.dump(encrypted_data, f, indent=4, ensure_ascii=False)
            self.log_message("Configuraciones cifradas y guardadas.")
        except Exception as e: messagebox.showerror("Error de Guardado", f"No se pudieron guardar las configuraciones: {e}")
    
    def load_json_data(self):
        if not os.path.exists(self.json_file_path): self.data = []; return True
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f: data = json.load(f)
            self.data = []
            for record in data:
                decrypted_record = record.copy()
                password = self.crypto.decrypt(record.get('password', ''))
                if password == "DECRYPT_FAILED": messagebox.showerror("Error de Contraseña", "La Contraseña Maestra es incorrecta."); return False
                decrypted_record['password'] = password
                if 'tag' not in decrypted_record: decrypted_record['tag'] = ''
                self.data.append(decrypted_record)
            self.log_message("Configuraciones descifradas y cargadas.")
            return True
        except Exception as e: messagebox.showerror("Error de Carga", f"No se pudo cargar/descifrar el archivo: {e}"); return False
    
    def populate_table(self, data_to_display):
        self.tree.delete(*self.tree.get_children())
        all_columns = ("*",) + tuple(self.DEFAULT_COLUMNS_ORDER)
        self.tree["columns"] = all_columns
        self.tree.column("#0", width=0, stretch=tk.NO); self.tree.column("*", width=40, minwidth=40, anchor="center"); self.tree.heading("*", text="✔")
        for col in self.DEFAULT_COLUMNS_ORDER:
            self.tree.heading(col, text=self.COLUMN_LABELS.get(col, col.title()), anchor="center", command=lambda c=col: self.sort_by_column(c))
            width, minwidth, anchor = 120, 80, "w"
            if col == 'id': width, minwidth, anchor = 40, 40, "center"
            elif col == 'tag': width = 100
            elif col == 'key_path': width = 150
            self.tree.column(col, width=width, minwidth=minwidth, anchor=anchor)

        for item_data in data_to_display:
            values = [""] + ["********" if col == "password" and item_data.get(col) else "🔑" if col == "key_path" and item_data.get(col) else item_data.get(col, "") for col in self.DEFAULT_COLUMNS_ORDER]
            item_id = self.tree.insert("", "end", values=tuple(values))
            is_checked = self.checked_items.get(item_id, False)
            self.update_selection_marker(item_id, is_checked)
        self.update_select_all_state()

    def sort_by_column(self, col, keep_direction=False):
        if not keep_direction:
            if self.sort_column == col: self.sort_descending = not self.sort_descending
            else: self.sort_descending = False
        self.sort_column = col
        is_numeric = col in ['id', 'port']
        def sort_key(item):
            value = item.get(col)
            if is_numeric:
                try: return int(value or 0)
                except (ValueError, TypeError): return 0
            return str(value or "").lower()
        search_term = self.search_var.get().lower()
        data_to_sort = [r for r in self.data if any(search_term in str(v).lower() for k, v in r.items() if k != 'password')] if search_term else self.data.copy()
        data_to_sort.sort(key=sort_key, reverse=self.sort_descending)
        self.populate_table(data_to_sort)
        if not keep_direction: self.log_message(f"Tabla ordenada por '{col}' en orden {'descendente' if self.sort_descending else 'ascendente'}.")

    def update_selection_marker(self, item_id, checked): self.tree.set(item_id, column="*", value="✔" if checked else "")
    
    def add_record_popup(self, edit_mode=False, item_id=None):
        if edit_mode and not item_id: messagebox.showwarning("Advertencia", "Seleccione un registro para editar."); return
        popup = tk.Toplevel(self.root); popup.transient(self.root); popup.grab_set(); popup.title("Editar Configuración" if edit_mode else "Agregar")
        if edit_mode:
            record = next((r for r in self.data if r.get('id') == int(self.tree.item(item_id,'values')[1])), None)
            if not record: messagebox.showerror("Error", "No se pudo encontrar el registro."); popup.destroy(); return
        else: record = {'id': self._get_next_id(), 'auth_method': 'password', 'tag': ''}
        self.entry_fields, auth_method_var = {}, tk.StringVar(value=record.get('auth_method', 'password'))
        def toggle_auth_fields(*args):
            is_key = auth_method_var.get() in ['key', 'interactive']
            self.entry_fields['password_frame'].grid(); self.entry_fields['key_path_frame'].grid() if is_key else self.entry_fields['key_path_frame'].grid_remove()
        for i, col in enumerate(self.DEFAULT_COLUMNS_ORDER):
            frame = ttk.Frame(popup); frame.grid(row=i, column=0, columnspan=2, padx=10, pady=3, sticky="ew"); frame.grid_columnconfigure(1, weight=1)
            ttk.Label(frame, text=f"{self.COLUMN_LABELS.get(col, col.title())}:").grid(row=0, column=0, padx=(0, 5), sticky="w"); self.entry_fields[f"{col}_frame"] = frame
            if col == 'auth_method': widget = ttk.Combobox(frame, textvariable=auth_method_var, values=['password', 'key', 'interactive'], state='readonly'); widget.bind('<<ComboboxSelected>>', toggle_auth_fields)
            elif col == 'password': widget = ttk.Entry(frame, show="*")
            elif col == 'key_path': widget = ttk.Entry(frame); ttk.Button(frame, text="Buscar...", command=lambda e=widget: self._browse_key_file(e)).grid(row=0, column=2, padx=(5,0))
            else: widget = ttk.Entry(frame)
            widget.grid(row=0, column=1, sticky="ew")
            if record.get(col) is not None and col != 'password': widget.insert(0, str(record.get(col, "")))
            if col == 'id': widget.config(state='readonly')
            self.entry_fields[col] = widget
        def on_save():
            new_record = {col: widget.get() for col, widget in self.entry_fields.items() if not isinstance(widget, ttk.Frame)}
            if edit_mode and not new_record['password']: new_record['password'] = record.get('password', '')
            new_record['auth_method'] = auth_method_var.get()
            try: new_record['port'], new_record['id'] = int(new_record.get('port') or 22), int(new_record['id'])
            except ValueError: messagebox.showwarning("Advertencia", "Puerto e ID deben ser números.", parent=popup); return
            if edit_mode: self.data[next(i for i, r in enumerate(self.data) if r.get('id') == new_record['id'])] = new_record
            else: self.data.append(new_record)
            self.save_json_data(); self.filter_table(); popup.destroy()
        ttk.Button(popup, text="Guardar", command=on_save).grid(row=len(self.DEFAULT_COLUMNS_ORDER), column=0, columnspan=2, pady=10); toggle_auth_fields()

    def _browse_key_file(self, entry_widget):
        if file_path := filedialog.askopenfilename(title="Seleccionar llave SSH privada"): entry_widget.delete(0, tk.END); entry_widget.insert(0, file_path)

    def get_selected_configs(self):
        return [c for i, ch in self.checked_items.items() if ch and self.tree.exists(i) and (c := next((r for r in self.data if r.get('id') == int(self.tree.item(i,'values')[1])),None))]
    
    def edit_selected_record(self):
        selected_configs = self.get_selected_configs()
        if len(selected_configs) != 1: messagebox.showwarning("Advertencia", "Seleccione un único registro para editar."); return
        record_id_to_edit = selected_configs[0].get('id')
        for item_id in self.tree.get_children():
            if int(self.tree.item(item_id, 'values')[1]) == record_id_to_edit:
                self.add_record_popup(edit_mode=True, item_id=item_id); return
    
    def edit_record_popup(self, event=None):
        if item_id := self.tree.focus():
            if self.tree.identify_region(event.x, event.y) != "heading":
                self.add_record_popup(edit_mode=True, item_id=item_id)

    def delete_selected_records(self):
        selected_configs = self.get_selected_configs()
        if not selected_configs:
            messagebox.showwarning("Advertencia", "Seleccione al menos un registro para eliminar.")
            return
        if not messagebox.askyesno("Confirmar", f"¿Eliminar {len(selected_configs)} configuración(es)?"): 
            return
        ids_to_delete = {c.get('id') for c in selected_configs}
        self.data = [r for r in self.data if r.get('id') not in ids_to_delete]
        
        # Limpiar los checkboxes de la memoria
        item_ids_to_remove = [item_id for item_id, checked in self.checked_items.items() if checked]
        for item_id in item_ids_to_remove:
            del self.checked_items[item_id]
        
        self.save_json_data(); self.filter_table(); self.log_message(f"Se eliminaron {len(ids_to_delete)} configuración(es).")

    def load_file_for_deploy(self):
        selected_configs = self.get_selected_configs()
        if not selected_configs: messagebox.showwarning("Advertencia", "Seleccione al menos una configuración."); return
        if not (file_path := filedialog.askopenfilename()): return
        file_name = os.path.basename(file_path)
        try:
            dest_path = os.path.join(self.deploy_source_folder, file_name)
            if not os.path.exists(dest_path) or not os.path.samefile(file_path, dest_path): shutil.copy(file_path, dest_path)
        except Exception as e: messagebox.showerror("Error", f"Error al copiar archivo: {e}"); return
        for config in selected_configs: config['cargar'] = file_name
        self.save_json_data(); self.filter_table(); self.log_message(f"Archivo '{file_name}' asociado a {len(selected_configs)} configs.")

    def upload_files(self):
        selected_configs = self.get_selected_configs()
        if not selected_configs: messagebox.showwarning("Advertencia", "Seleccione al menos un servidor para la subida."); return
        self.log_message(f"\n--- Iniciando Proceso de Subida en {len(selected_configs)} servidor(es) ---")
        for config in selected_configs: threading.Thread(target=self._execute_upload_for_config, args=(config,), daemon=True).start()
    
    def start_diagnostic_test_thread(self): threading.Thread(target=self.run_diagnostic_tests, daemon=True).start()
    
    def run_diagnostic_tests(self):
        selected_configs = self.get_selected_configs()
        if not selected_configs: self.root.after(0, lambda: messagebox.showwarning("Advertencia", "Seleccione al menos un servidor.")); return
        test_type, port_str, path_str = self.test_type_var.get(), self.test_port_var.get(), self.test_path_var.get()
        try: port = int(port_str) if port_str else 0
        except ValueError: self.error_log_message(f"Error: El puerto '{port_str}' no es un número válido."); return
        self.log_message(f"\n--- Iniciando Test '{test_type.upper()}' para {len(selected_configs)} servidor(es) ---")
        for config in selected_configs:
            if test_type == 'ping': self._run_ping_for_server(config)
            elif test_type == 'telnet': self._run_telnet_for_server(config, port)
            elif test_type == 'curl': self._run_curl_for_server(config, port, path_str)

    def start_ssh_thread(self): 
        threading.Thread(target=self.launch_ssh_operations, daemon=True).start()
    
    def launch_ssh_operations(self):
        selected_configs = self.get_selected_configs()
        if not selected_configs: messagebox.showwarning("Advertencia", "No hay servidores seleccionados."); return
        command_text = self.commands_text_area.get("1.0", tk.END).strip()
        if not command_text: messagebox.showwarning("Advertencia", "Por favor, ingrese al menos un comando para ejecutar."); return
        self.update_command_history(command_text)
        commands_list = [cmd.strip() for cmd in command_text.split('\n') if cmd.strip()]
        self.log_message(f"\n--- Iniciando Operaciones SSH en {len(selected_configs)} servidor(es) ---")
        for config in selected_configs: threading.Thread(target=self._execute_ssh_for_config, args=(config, commands_list), daemon=True).start()

    def _load_any_private_key(self, key_path, passphrase):
        for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey, paramiko.DSSKey]:
            try: return key_class.from_private_key_file(key_path, password=passphrase)
            except paramiko.SSHException: continue
        raise paramiko.SSHException(f"No se pudo cargar la llave o tipo no soportado: {key_path}")

    def _connect_ssh(self, config):
        host, ip, user, password, port, auth_method, key_path = [config.get(k, "") for k in ["hostname", "ip", "user", "password", "port", "auth_method", "key_path"]]
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, int(port or 22)))
        transport = paramiko.Transport(sock)
        transport.start_client()
        
        pkey = self._load_any_private_key(key_path, password or None) if key_path else None
        
        if auth_method == 'interactive':
            handler = GUIAuthHandler(self.root, self.mfa_queue)
            if pkey: transport.auth_publickey(user, pkey)
            else: transport.auth_password(user, password)
            if not transport.is_authenticated():
                transport.auth_interactive(user, handler)
        elif auth_method == 'key':
            if not pkey: raise paramiko.AuthenticationException(f"No se pudo cargar la llave o tipo no soportado: {key_path}")
            transport.auth_publickey(user, pkey)
        else:
            transport.auth_password(user, password)
            
        if not transport.is_authenticated():
            raise paramiko.AuthenticationException("La autenticación falló.")
            
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client._transport = transport
        self.log_message(f"Conexión exitosa a {host} ({ip}).")
        return ssh_client

    def _execute_ssh_for_config(self, config, commands_list):
        try:
            with self._connect_ssh(config) as ssh_client:
                for command in commands_list:
                    self._execute_ssh_command(ssh_client, command, config['id'], config['hostname'])
        except Exception as e:
            self.error_log_message(f"ID {config.get('id', 'N/A')} - {config.get('hostname', 'N/A')}: {e}")

    def _execute_upload_for_config(self, config):
        host = config.get("hostname", "N/A")
        try:
            with self._connect_ssh(config) as ssh_client:
                self._deploy_file(ssh_client, config.get("cargar"), config.get("subir"), config.get('id'), host)
        except Exception as e:
            self.error_log_message(f"ID {config.get('id', 'N/A')} - {host}: Error en el proceso de subida: {e}")
    
    # --- LA LÓGICA DE DESCARGA SE MUEVE A ESTAS TRES FUNCIONES ---
    
    def download_file(self):
        selected_configs = self.get_selected_configs()
        if not selected_configs: messagebox.showwarning("Advertencia", "Seleccione al menos un servidor para la descarga."); return
        self.log_message(f"Iniciando proceso de descarga para {len(selected_configs)} servidor(es).")
        for config in selected_configs:
            if not (remote_path := config.get("cargar")):
                self.error_log_message(f"ID {config.get('id')} - {config.get('hostname', 'N/A')}: No hay ruta remota especificada."); continue
            
            hostname = config.get("hostname", "unknown_host")
            base_name = os.path.basename(remote_path)
            local_path = os.path.join(self.downloads_folder, f"{hostname}_{base_name}")
            
            threading.Thread(target=self.execute_download_thread, args=(config, remote_path, local_path), daemon=True).start()

    def execute_download_thread(self, config, remote_path, local_path):
        host = config.get("hostname", "N/A")
        try:
            with self._connect_ssh(config) as ssh_client:
                with ssh_client.open_sftp() as sftp:
                    self._download_item(sftp, remote_path, local_path)
            self.log_message(f"Descarga desde {host} finalizada.")
        except Exception as e:
            error_msg = f"ID {config.get('id', 'N/A')} - {host}: Error durante la descarga: {e}"
            self.error_log_message(error_msg)
    
    def _download_item(self, sftp, remote_path, local_path):
        try:
            if stat.S_ISDIR(sftp.stat(remote_path).st_mode):
                self._download_folder_recursive(sftp, remote_path, local_path)
            else:
                sftp.get(remote_path, local_path)
                self.log_message(f"Archivo descargado: '{remote_path}' -> '{local_path}'")
        except FileNotFoundError:
            self.error_log_message(f"No se encontró la ruta remota: {remote_path}")
        except Exception as e:
            self.error_log_message(f"Falla en la descarga de '{remote_path}': {e}")
            
    def _download_folder_recursive(self, sftp, remote_dir, local_dir):
        os.makedirs(local_dir, exist_ok=True)
        self.log_message(f"Creando y entrando en directorio: {local_dir}")
        for item in sftp.listdir(remote_dir):
            remote_item_path = os.path.join(remote_dir, item).replace("\\", "/")
            local_item_path = os.path.join(local_dir, item)
            
            if stat.S_ISDIR(sftp.stat(remote_item_path).st_mode):
                self._download_folder_recursive(sftp, remote_item_path, local_item_path)
            else:
                self.log_message(f"Descargando archivo: {remote_item_path}")
                sftp.get(remote_item_path, local_item_path)

    def _deploy_file(self, ssh_client, local_file, remote_path, record_id, hostname):
        if not local_file or not remote_path: self.error_log_message(f"ID {record_id} - {hostname}: Faltan rutas para la subida."); return
        local_full_path = os.path.join(self.deploy_source_folder, local_file)
        if not os.path.exists(local_full_path): self.error_log_message(f"ID {record_id} - {hostname}: Archivo no encontrado: {local_full_path}"); return
        try:
            with ssh_client.open_sftp() as sftp:
                dest = os.path.join(remote_path, os.path.basename(local_file))
                self.log_message(f"ID {record_id} - Subiendo '{local_full_path}' a '{dest}'...")
                sftp.put(local_full_path, dest); self.log_message(f"ID {record_id} - {hostname}: Archivo '{local_file}' subido a '{dest}'.")
        except Exception as e: self.error_log_message(f"ID {record_id} - {hostname}: Error al subir archivo: {e}")

    def _execute_ssh_command(self, ssh_client, command, record_id, hostname):
        self.log_message(f"ID {record_id} - {hostname} | Ejecutando: '{command}'")
        try:
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=300)
            output = stdout.read().decode('utf-8', 'ignore').strip()
            error_output = stderr.read().decode('utf-8', 'ignore').strip()
            exit_status = stdout.channel.recv_exit_status()
            
            self.log_message(f"ID {record_id} - {hostname} | Comando '{command}' finalizó con código de salida: {exit_status}")
            
            if output:
                self.log_message(f"Salida:\n------\n{output}\n------")
            if error_output:
                self.error_log_message(f"Error:\n------\n{error_output}\n------")

            if not output and not error_output and exit_status == 0:
                self.log_message("Comando ejecutado exitosamente sin salida.")
                
        except Exception as e:
            self.error_log_message(f"ID {record_id} - {hostname} | Falla al ejecutar '{command}': {e}")
    
    def _run_ping_for_server(self, config):
        ip, hostname = config.get("ip"), config.get("hostname"); param = '-n' if sys.platform == 'win32' else '-c'
        if not ip: self.error_log_message(f"PING OMITIDO: {hostname} no tiene IP."); return
        try:
            command = ['ping', param, '1', '-w' if sys.platform == 'win32' else '-W', '1', ip]
            if subprocess.run(command, capture_output=True, text=True, timeout=5).returncode == 0: self.log_message(f"PING OK: {hostname} ({ip}) responde.")
            else: self.error_log_message(f"PING FALLÓ: {hostname} ({ip}) no responde.")
        except Exception as e: self.error_log_message(f"PING ERROR: {hostname} ({ip}): {e}")

    def _run_telnet_for_server(self, config, port):
        ip, hostname = config.get("ip"), config.get("hostname")
        if not ip: self.error_log_message(f"TELNET OMITIDO: {hostname} no tiene IP."); return
        try:
            with socket.create_connection((ip, port), timeout=3): self.log_message(f"TELNET OK: Puerto {port} en {hostname} ({ip}) está abierto.")
        except socket.timeout: self.error_log_message(f"TELNET FALLÓ: Timeout en puerto {port} de {hostname} ({ip}).")
        except ConnectionRefusedError: self.error_log_message(f"TELNET FALLÓ: Conexión rechazada en puerto {port} de {hostname} ({ip}).")
        except Exception as e: self.error_log_message(f"TELNET ERROR: {hostname} ({ip}): {e}")

    def _run_curl_for_server(self, config, port, path):
        ip, hostname = config.get("ip"), config.get("hostname")
        if not ip: self.error_log_message(f"CURL OMITIDO: {hostname} no tiene IP."); return
        protocol = "https" if port == 443 else "http"
        if path and not path.startswith('/'): path = f"/{path}"
        url = f"{protocol}://{ip}:{port}{path or ''}"
        try:
            result = subprocess.run(['curl', '-I', '-L', '-k', '--connect-timeout', '5', url], capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0 and "HTTP/" in result.stdout: self.log_message(f"CURL OK: {hostname} ({url}) respondió: {result.stdout.splitlines()[0]}")
            else: self.error_log_message(f"CURL FALLÓ: {hostname} ({url}). Error: {(result.stderr or result.stdout).splitlines()[0] if (result.stderr or result.stdout) else 'Sin respuesta'}")
        except FileNotFoundError: self.error_log_message("CURL ERROR: 'curl' no está instalado o no se encuentra en el PATH."); return
        except Exception as e: self.error_log_message(f"CURL ERROR: {hostname} ({url}): {e}")

    def load_today_log(self):
        log_file = os.path.join(self.log_folder, f"{dt.date.today()}.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self._update_log_widget(self.log_text_widget, content)
            except Exception as e: self.log_message(f"Error al cargar log: {e}")
    
    def log_message(self, message):
        entry = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
        self.root.after(0, self._update_log_widget, self.log_text_widget, entry)
        try:
            with open(os.path.join(self.log_folder, f"{dt.date.today()}.log"), 'a', encoding='utf-8') as f: f.write(entry)
        except Exception as e: print(f"Error al escribir en log: {e}\n")
    
    def error_log_message(self, message):
        entry = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
        self.root.after(0, self._update_log_widget, self.error_log_widget, entry)
        try:
            with open(os.path.join(self.error_log_folder, f"error_{dt.date.today()}.log"), 'a', encoding='utf-8') as f: f.write(entry)
        except Exception as e: print(f"Error al escribir en log de errores: {e}\n")

    def _update_log_widget(self, widget, text):
        if widget and widget.winfo_exists():
            widget.config(state="normal")
            widget.insert(tk.END, text)
            widget.see(tk.END)
            widget.config(state="disabled")

    class TextRedirector:
        def __init__(self, app_instance, widget, tag="stdout"):
            self.app_instance = app_instance
            self.widget = widget
            self.original_stream = sys.__stdout__ if tag == 'stdout' else sys.__stderr__

        def write(self, text):
            if self.widget and self.widget.winfo_exists():
                self.app_instance.root.after(0, self.app_instance._update_log_widget, self.widget, text)
            self.original_stream.write(text)

        def flush(self):
            self.original_stream.flush()

if __name__ == "__main__":
    root = ThemedTk()
    root.withdraw()
    
    app = JsonTableApp(root)
    
    if app.initialized_ok:
        app.root.deiconify()
        app.root.mainloop()
    elif root.winfo_exists():
        root.destroy()
