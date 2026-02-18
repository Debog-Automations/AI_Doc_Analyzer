"""
Watcher Tab - Configure and control folder watching for automatic document processing

Supports both local folders and Box cloud storage.
"""

import os
import json
import tempfile
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QProgressBar,
    QSplitter, QFrame, QAbstractItemView, QDialog, QTreeWidget,
    QTreeWidgetItem, QDialogButtonBox
)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer, QThread, QObject
from PyQt5.QtGui import QTextCursor

from logger import get_logger

logger = get_logger(__name__)

# Default configuration
DEFAULT_SCAN_INTERVAL = 5  # minutes
CONFIG_PATH = "app_config.json"


class BoxFolderBrowserDialog(QDialog):
    """Dialog for browsing and selecting Box folders."""
    
    def __init__(self, box_connector, parent=None):
        super().__init__(parent)
        self.box_connector = box_connector
        self.selected_path = None
        self._init_ui()
        self._load_root()
    
    def _init_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle("Select Box Folder")
        self.setMinimumSize(400, 500)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("Select a folder to watch. Double-click to expand.")
        layout.addWidget(instructions)
        
        # Tree widget for folder browsing
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Folder Name", "Path"])
        self.tree.setColumnWidth(0, 250)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)
        
        # Selected path display
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Selected:"))
        self.path_label = QLineEdit()
        self.path_label.setReadOnly(True)
        self.path_label.setPlaceholderText("Click a folder to select")
        path_layout.addWidget(self.path_label)
        layout.addLayout(path_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_root(self):
        """Load root folders from Box."""
        try:
            folders = self.box_connector.list_folders("/")
            
            for folder in folders:
                item = QTreeWidgetItem([folder.name, folder.path])
                item.setData(0, Qt.UserRole, folder.id)
                item.setData(1, Qt.UserRole, folder.path)
                
                # Add placeholder child for expansion
                if folder.has_children:
                    placeholder = QTreeWidgetItem(["Loading..."])
                    item.addChild(placeholder)
                
                self.tree.addTopLevelItem(item)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load Box folders: {str(e)}")
    
    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Handle folder expansion - load subfolders."""
        # Check if this is a placeholder
        if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
            item.removeChild(item.child(0))
            
            folder_path = item.data(1, Qt.UserRole)
            
            try:
                subfolders = self.box_connector.list_folders(folder_path)
                
                for subfolder in subfolders:
                    child_item = QTreeWidgetItem([subfolder.name, subfolder.path])
                    child_item.setData(0, Qt.UserRole, subfolder.id)
                    child_item.setData(1, Qt.UserRole, subfolder.path)
                    
                    if subfolder.has_children:
                        placeholder = QTreeWidgetItem(["Loading..."])
                        child_item.addChild(placeholder)
                    
                    item.addChild(child_item)
                    
            except Exception as e:
                error_item = QTreeWidgetItem([f"Error: {str(e)}"])
                item.addChild(error_item)
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle folder selection."""
        folder_path = item.data(1, Qt.UserRole)
        if folder_path:
            self.selected_path = folder_path
            self.path_label.setText(folder_path)
    
    def get_selected_path(self) -> Optional[str]:
        """Get the selected folder path."""
        return self.selected_path


class WatcherWorker(QObject):
    """Worker for scanning and processing files in a background thread."""
    
    scan_started = pyqtSignal()
    scan_progress = pyqtSignal(str, int, int)  # message, current, total
    file_processing = pyqtSignal(str)  # file path
    file_completed = pyqtSignal(str, dict)  # file path, results
    file_error = pyqtSignal(str, str)  # file path, error
    scan_completed = pyqtSignal(int, int, int)  # new_count, processed_count, error_count
    log_message = pyqtSignal(str, str)  # message, level
    
    def __init__(
        self,
        folders: List[str],
        process_func: Callable,
        output_folder: str,
        source_type: str = "local",
        box_credentials: Optional[Dict[str, Any]] = None
    ):
        super().__init__()
        self.folders = folders
        self.process_func = process_func
        self.output_folder = output_folder
        self.source_type = source_type
        self.box_credentials = box_credentials
        self._is_cancelled = False
        self._temp_dir = None
    
    def run(self):
        """Scan folders and process new files."""
        from services.folder_scanner import FolderScanner, ScanFileInfo, save_result_to_json, append_result_to_excel
        
        self.scan_started.emit()
        self.log_message.emit(f"Starting {self.source_type} scan of {len(self.folders)} folder(s)...", "info")
        
        try:
            # Initialize scanner
            scanner = FolderScanner()
            
            # Scan for new files based on source type
            def progress_callback(message: str, current: int, total: int):
                self.scan_progress.emit(message, current, total)
            
            if self.source_type == "box":
                # Initialize Box connector
                from connectors.box_connector import BoxConnector
                
                box_connector = BoxConnector(
                    developer_token=self.box_credentials.get("developer_token"),
                    client_id=self.box_credentials.get("client_id"),
                    client_secret=self.box_credentials.get("client_secret"),
                    enterprise_id=self.box_credentials.get("enterprise_id"),
                    user_id=self.box_credentials.get("user_id")
                )
                
                if not box_connector.connect():
                    self.log_message.emit("Failed to connect to Box", "error")
                    self.scan_completed.emit(0, 0, 1)
                    return
                
                scan_result = scanner.scan_box_folders(self.folders, box_connector, progress_callback)
                
                # Create temp directory for Box file downloads
                self._temp_dir = tempfile.mkdtemp(prefix="watcher_box_")
            else:
                scan_result = scanner.scan_folders(self.folders, progress_callback)
            
            new_files = scan_result.new_files
            self.log_message.emit(
                f"Found {len(new_files)} new file(s) to process "
                f"({scan_result.total_files_found} total, {len(scan_result.skipped_files)} already processed)",
                "info"
            )
            
            if not new_files:
                self.scan_completed.emit(0, 0, 0)
                return
            
            # Process each new file
            processed_count = 0
            error_count = 0
            
            # Excel output path
            excel_path = os.path.join(
                self.output_folder,
                f"watcher_results_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
            
            for idx, file_info in enumerate(new_files):
                if self._is_cancelled:
                    self.log_message.emit("Scan cancelled by user", "warning")
                    break
                
                file_name = file_info.name if isinstance(file_info, ScanFileInfo) else os.path.basename(file_info)
                self.file_processing.emit(file_name)
                self.log_message.emit(f"Processing ({idx+1}/{len(new_files)}): {file_name}", "info")
                
                try:
                    # Get local file path (download from Box if needed)
                    if self.source_type == "box" and isinstance(file_info, ScanFileInfo):
                        # Download from Box to temp directory
                        local_path = os.path.join(self._temp_dir, file_info.name)
                        box_connector.download_file(file_info.file_id, local_path)
                        self.log_message.emit(f"  Downloaded from Box", "info")
                    else:
                        local_path = file_info.path if isinstance(file_info, ScanFileInfo) else file_info
                    
                    # Process the file
                    result = self.process_func(local_path)
                    
                    # Add source info to result
                    result['Source Type'] = self.source_type
                    if self.source_type == "box" and isinstance(file_info, ScanFileInfo):
                        result['Box Path'] = file_info.path
                        result['Box File ID'] = file_info.file_id
                    
                    # Save JSON output
                    json_path = save_result_to_json(result, local_path, self.output_folder)
                    self.log_message.emit(f"  Saved JSON: {os.path.basename(json_path)}", "success")
                    
                    # Append to Excel
                    append_result_to_excel(result, excel_path)
                    
                    file_path = file_info.path if isinstance(file_info, ScanFileInfo) else file_info
                    self.file_completed.emit(file_path, result)
                    processed_count += 1
                    
                except Exception as e:
                    file_path = file_info.path if isinstance(file_info, ScanFileInfo) else file_info
                    self.file_error.emit(file_path, str(e))
                    self.log_message.emit(f"  Error: {str(e)}", "error")
                    error_count += 1
            
            # Cleanup temp directory for Box downloads
            if self._temp_dir:
                try:
                    import shutil
                    shutil.rmtree(self._temp_dir, ignore_errors=True)
                except:
                    pass
            
            # Disconnect Box if connected
            if self.source_type == "box":
                try:
                    box_connector.disconnect()
                except:
                    pass
            
            self.log_message.emit(
                f"Scan complete: {processed_count} processed, {error_count} errors",
                "success" if error_count == 0 else "warning"
            )
            self.scan_completed.emit(len(new_files), processed_count, error_count)
            
        except Exception as e:
            self.log_message.emit(f"Scan failed: {str(e)}", "error")
            self.scan_completed.emit(0, 0, 1)
    
    def cancel(self):
        """Cancel the current scan."""
        self._is_cancelled = True


class WatcherTab(QWidget):
    """Tab for configuring and controlling folder watching."""
    
    # Signals
    watcher_started = pyqtSignal()
    watcher_stopped = pyqtSignal()
    files_processed = pyqtSignal(list)  # List of (file_path, results) tuples
    
    def __init__(self, config_path: str = CONFIG_PATH):
        super().__init__()
        self.config_path = config_path
        self.config = self._load_config()
        
        self.process_func: Optional[Callable] = None
        self.timer: Optional[QTimer] = None
        self.worker: Optional[WatcherWorker] = None
        self.thread: Optional[QThread] = None
        self.is_watching = False
        self.processed_results: List[tuple] = []
        self._box_credentials: Optional[Dict[str, Any]] = None
        
        self._init_ui()
        self._load_watcher_config()
    
    def _init_ui(self):
        """Initialize the watcher UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Create splitter for top/bottom sections
        splitter = QSplitter(Qt.Vertical)
        
        # Top section: Configuration
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        
        # Source Type Selection
        source_group = QGroupBox("Source")
        source_layout = QHBoxLayout()
        
        source_layout.addWidget(QLabel("Source Type:"))
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItem("Local Folders", "local")
        self.source_type_combo.addItem("Box", "box")
        self.source_type_combo.currentIndexChanged.connect(self._on_source_type_changed)
        source_layout.addWidget(self.source_type_combo)
        
        source_layout.addStretch()
        
        # Box connection status
        self.box_status_label = QLabel("")
        source_layout.addWidget(self.box_status_label)
        
        source_group.setLayout(source_layout)
        config_layout.addWidget(source_group)
        
        # Watch Folders Group
        folders_group = QGroupBox("Watch Folders")
        folders_layout = QVBoxLayout()
        
        self.folders_list = QListWidget()
        self.folders_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folders_list.setMinimumHeight(100)
        folders_layout.addWidget(self.folders_list)
        
        folders_btn_layout = QHBoxLayout()
        
        self.add_folder_btn = QPushButton("Add Folder...")
        self.add_folder_btn.clicked.connect(self._add_folder)
        folders_btn_layout.addWidget(self.add_folder_btn)
        
        remove_folder_btn = QPushButton("Remove Selected")
        remove_folder_btn.clicked.connect(self._remove_folder)
        folders_btn_layout.addWidget(remove_folder_btn)
        
        folders_btn_layout.addStretch()
        folders_layout.addLayout(folders_btn_layout)
        
        folders_group.setLayout(folders_layout)
        config_layout.addWidget(folders_group)
        
        # Settings row
        settings_layout = QHBoxLayout()
        
        # Scan Interval
        interval_group = QGroupBox("Scan Interval")
        interval_layout = QHBoxLayout()
        
        self.interval_combo = QComboBox()
        self.interval_combo.addItem("1 minute", 1)
        self.interval_combo.addItem("5 minutes", 5)
        self.interval_combo.addItem("15 minutes", 15)
        self.interval_combo.addItem("30 minutes", 30)
        self.interval_combo.addItem("60 minutes", 60)
        self.interval_combo.setCurrentIndex(1)  # Default: 5 minutes
        interval_layout.addWidget(self.interval_combo)
        
        interval_group.setLayout(interval_layout)
        settings_layout.addWidget(interval_group)
        
        # Output Folder
        output_group = QGroupBox("Output Folder")
        output_layout = QHBoxLayout()
        
        self.output_folder_input = QLineEdit()
        self.output_folder_input.setPlaceholderText("Folder for JSON and Excel output")
        self.output_folder_input.setText(self.config.get("output_folder", "output_csv"))
        output_layout.addWidget(self.output_folder_input)
        
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self._browse_output_folder)
        output_layout.addWidget(output_browse_btn)
        
        output_group.setLayout(output_layout)
        settings_layout.addWidget(output_group, 1)
        
        config_layout.addLayout(settings_layout)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Watching")
        self.start_btn.setMinimumWidth(150)
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._toggle_watcher)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        control_layout.addWidget(self.start_btn)
        
        self.scan_now_btn = QPushButton("Scan Now")
        self.scan_now_btn.setMinimumWidth(120)
        self.scan_now_btn.setMinimumHeight(40)
        self.scan_now_btn.clicked.connect(self._scan_now)
        control_layout.addWidget(self.scan_now_btn)
        
        control_layout.addStretch()
        
        self.save_config_btn = QPushButton("Save Configuration")
        self.save_config_btn.clicked.connect(self._save_watcher_config)
        control_layout.addWidget(self.save_config_btn)
        
        config_layout.addLayout(control_layout)
        
        # Status bar
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.next_scan_label = QLabel("")
        status_layout.addWidget(self.next_scan_label)
        
        config_layout.addLayout(status_layout)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        config_layout.addWidget(self.progress_bar)
        
        splitter.addWidget(config_widget)
        
        # Bottom section: Log
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, Monaco, monospace;
                font-size: 11px;
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        log_btn_layout = QHBoxLayout()
        log_btn_layout.addStretch()
        
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self._clear_log)
        log_btn_layout.addWidget(clear_log_btn)
        
        log_layout.addLayout(log_btn_layout)
        
        log_group.setLayout(log_layout)
        splitter.addWidget(log_group)
        
        # Set splitter proportions
        splitter.setSizes([350, 200])
        
        layout.addWidget(splitter)
    
    def _on_source_type_changed(self, index: int):
        """Handle source type change."""
        source_type = self.source_type_combo.currentData()
        
        # Clear current folders when switching source type
        self.folders_list.clear()
        
        if source_type == "box":
            self.add_folder_btn.setText("Browse Box...")
            self._check_box_connection()
        else:
            self.add_folder_btn.setText("Add Folder...")
            self.box_status_label.setText("")
    
    def _check_box_connection(self):
        """Check if Box credentials are available."""
        if self._box_credentials:
            dev_token = self._box_credentials.get("developer_token")
            client_id = self._box_credentials.get("client_id")
            
            if dev_token:
                self.box_status_label.setText("Using Developer Token")
                self.box_status_label.setStyleSheet("color: green;")
            elif client_id:
                self.box_status_label.setText("Using CCG credentials")
                self.box_status_label.setStyleSheet("color: green;")
            else:
                self.box_status_label.setText("Box not configured - check Settings")
                self.box_status_label.setStyleSheet("color: red;")
        else:
            self.box_status_label.setText("Box not configured - check Settings")
            self.box_status_label.setStyleSheet("color: red;")
    
    def set_box_credentials(self, credentials: Dict[str, Any]):
        """Set Box credentials from Settings tab."""
        self._box_credentials = credentials
        self._check_box_connection()
    
    def _load_config(self) -> dict:
        """Load config from JSON file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        return {}
    
    def _save_config(self):
        """Save config to JSON file, preserving other settings."""
        try:
            # Reload current config from file to preserve changes from other tabs
            current_config = {}
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r') as f:
                        current_config = json.load(f)
                except Exception:
                    pass
            
            # Merge our changes into the current config
            current_config.update(self.config)
            
            # Write merged config
            with open(self.config_path, 'w') as f:
                json.dump(current_config, f, indent=2)
            
            # Update our cached config
            self.config = current_config
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def _load_watcher_config(self):
        """Load watcher-specific configuration."""
        # Load source type
        source_type = self.config.get("watch_source_type", "local")
        index = self.source_type_combo.findData(source_type)
        if index >= 0:
            self.source_type_combo.setCurrentIndex(index)
        
        # Load watch folders
        watch_folders = self.config.get("watch_folders", [])
        for folder in watch_folders:
            self.folders_list.addItem(folder)
        
        # Load scan interval
        interval = self.config.get("watch_interval_minutes", DEFAULT_SCAN_INTERVAL)
        index = self.interval_combo.findData(interval)
        if index >= 0:
            self.interval_combo.setCurrentIndex(index)
        
        # Load output folder
        output_folder = self.config.get("output_folder", "output_csv")
        self.output_folder_input.setText(output_folder)
        
        self._log(f"Loaded configuration: {len(watch_folders)} watch folder(s)", "info")
    
    def _save_watcher_config(self):
        """Save watcher configuration."""
        # Collect watch folders
        folders = []
        for i in range(self.folders_list.count()):
            folders.append(self.folders_list.item(i).text())
        
        self.config["watch_source_type"] = self.source_type_combo.currentData()
        self.config["watch_folders"] = folders
        self.config["watch_interval_minutes"] = self.interval_combo.currentData()
        self.config["output_folder"] = self.output_folder_input.text()
        
        self._save_config()
        
        self._log("Configuration saved", "success")
        QMessageBox.information(self, "Success", "Watcher configuration saved!")
    
    def _add_folder(self):
        """Add a folder to watch (local or Box)."""
        source_type = self.source_type_combo.currentData()
        
        if source_type == "box":
            self._add_box_folder()
        else:
            self._add_local_folder()
    
    def _add_local_folder(self):
        """Add a local folder to watch."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Watch",
            "",
            QFileDialog.ShowDirsOnly
        )
        if folder:
            # Check if already in list
            for i in range(self.folders_list.count()):
                if self.folders_list.item(i).text() == folder:
                    QMessageBox.warning(self, "Duplicate", "This folder is already in the list.")
                    return
            
            self.folders_list.addItem(folder)
            self._log(f"Added local folder: {folder}", "info")
    
    def _add_box_folder(self):
        """Add a Box folder to watch using folder browser."""
        if not self._box_credentials:
            QMessageBox.warning(
                self, 
                "Box Not Configured", 
                "Please configure Box credentials in the Settings tab first."
            )
            return
        
        # Check if we have valid credentials
        dev_token = self._box_credentials.get("developer_token")
        client_id = self._box_credentials.get("client_id")
        
        if not dev_token and not client_id:
            QMessageBox.warning(
                self, 
                "Box Not Configured", 
                "Please configure Box credentials in the Settings tab first."
            )
            return
        
        try:
            # Create Box connector
            from connectors.box_connector import BoxConnector
            
            box_connector = BoxConnector(
                developer_token=dev_token,
                client_id=client_id,
                client_secret=self._box_credentials.get("client_secret"),
                enterprise_id=self._box_credentials.get("enterprise_id"),
                user_id=self._box_credentials.get("user_id")
            )
            
            if not box_connector.connect():
                QMessageBox.warning(self, "Connection Failed", "Failed to connect to Box.")
                return
            
            # Show folder browser dialog
            dialog = BoxFolderBrowserDialog(box_connector, self)
            
            if dialog.exec_() == QDialog.Accepted:
                folder_path = dialog.get_selected_path()
                
                if folder_path:
                    # Check if already in list
                    for i in range(self.folders_list.count()):
                        if self.folders_list.item(i).text() == folder_path:
                            QMessageBox.warning(self, "Duplicate", "This folder is already in the list.")
                            return
                    
                    self.folders_list.addItem(folder_path)
                    self._log(f"Added Box folder: {folder_path}", "info")
            
            box_connector.disconnect()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to browse Box: {str(e)}")
    
    def _remove_folder(self):
        """Remove selected folder(s) from watch list."""
        selected = self.folders_list.selectedItems()
        if not selected:
            return
        
        for item in selected:
            self._log(f"Removed watch folder: {item.text()}", "info")
            self.folders_list.takeItem(self.folders_list.row(item))
    
    def _browse_output_folder(self):
        """Browse for output folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.output_folder_input.text()
        )
        if folder:
            self.output_folder_input.setText(folder)
    
    def set_process_function(self, func: Callable):
        """Set the function to call for processing each file."""
        self.process_func = func
    
    def _toggle_watcher(self):
        """Start or stop the watcher."""
        if self.is_watching:
            self._stop_watcher()
        else:
            self._start_watcher()
    
    def _start_watcher(self):
        """Start the folder watcher."""
        # Validate configuration
        if self.folders_list.count() == 0:
            QMessageBox.warning(self, "No Folders", "Please add at least one folder to watch.")
            return
        
        if not self.process_func:
            QMessageBox.warning(self, "Not Configured", "Processing function not configured.")
            return
        
        source_type = self.source_type_combo.currentData()
        
        # Validate Box credentials if using Box
        if source_type == "box":
            if not self._box_credentials:
                QMessageBox.warning(self, "Box Not Configured", "Please configure Box credentials in Settings.")
                return
            
            dev_token = self._box_credentials.get("developer_token")
            client_id = self._box_credentials.get("client_id")
            
            if not dev_token and not client_id:
                QMessageBox.warning(self, "Box Not Configured", "Please configure Box credentials in Settings.")
                return
        
        # Get interval in milliseconds
        interval_minutes = self.interval_combo.currentData()
        interval_ms = interval_minutes * 60 * 1000
        
        # Create and start timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._scan_now)
        self.timer.start(interval_ms)
        
        self.is_watching = True
        self._update_ui_state()
        
        self._log(f"Watcher started ({source_type}) - scanning every {interval_minutes} minute(s)", "success")
        self._update_next_scan_time()
        
        # Run initial scan
        self._scan_now()
        
        self.watcher_started.emit()
    
    def _stop_watcher(self):
        """Stop the folder watcher."""
        if self.timer:
            self.timer.stop()
            self.timer = None
        
        # Cancel any running scan
        if self.worker:
            self.worker.cancel()
        
        self.is_watching = False
        self._update_ui_state()
        
        self._log("Watcher stopped", "warning")
        self.next_scan_label.setText("")
        
        self.watcher_stopped.emit()
    
    def _update_ui_state(self):
        """Update UI based on watcher state."""
        if self.is_watching:
            self.start_btn.setText("Stop Watching")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            self.status_label.setText("Status: Watching")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
            
            # Disable configuration while watching
            self.folders_list.setEnabled(False)
            self.interval_combo.setEnabled(False)
            self.output_folder_input.setEnabled(False)
            self.source_type_combo.setEnabled(False)
            self.add_folder_btn.setEnabled(False)
        else:
            self.start_btn.setText("Start Watching")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.status_label.setText("Status: Stopped")
            self.status_label.setStyleSheet("font-weight: bold; color: #666;")
            
            # Enable configuration
            self.folders_list.setEnabled(True)
            self.interval_combo.setEnabled(True)
            self.output_folder_input.setEnabled(True)
            self.source_type_combo.setEnabled(True)
            self.add_folder_btn.setEnabled(True)
    
    def _update_next_scan_time(self):
        """Update the next scan time label."""
        if self.is_watching and self.timer:
            interval_minutes = self.interval_combo.currentData()
            next_time = datetime.now()
            from datetime import timedelta
            next_time = next_time + timedelta(minutes=interval_minutes)
            self.next_scan_label.setText(f"Next scan: {next_time.strftime('%H:%M:%S')}")
    
    def _scan_now(self):
        """Trigger an immediate scan."""
        # Check if already scanning
        try:
            if self.thread is not None and self.thread.isRunning():
                self._log("Scan already in progress", "warning")
                return
        except RuntimeError:
            # Thread C++ object was deleted; clear the reference
            self.thread = None
            self.worker = None
        
        # Get folders to scan
        folders = []
        for i in range(self.folders_list.count()):
            folders.append(self.folders_list.item(i).text())
        
        if not folders:
            self._log("No folders configured", "warning")
            return
        
        if not self.process_func:
            self._log("Processing function not configured", "error")
            return
        
        # Get output folder
        output_folder = self.output_folder_input.text() or "output_csv"
        os.makedirs(output_folder, exist_ok=True)
        
        # Get source type
        source_type = self.source_type_combo.currentData()
        
        # Create worker and thread
        self.thread = QThread()
        self.worker = WatcherWorker(
            folders, 
            self.process_func, 
            output_folder,
            source_type=source_type,
            box_credentials=self._box_credentials
        )
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.scan_started.connect(self._on_scan_started)
        self.worker.scan_progress.connect(self._on_scan_progress)
        self.worker.file_processing.connect(self._on_file_processing)
        self.worker.file_completed.connect(self._on_file_completed)
        self.worker.file_error.connect(self._on_file_error)
        self.worker.log_message.connect(self._log)
        self.worker.scan_completed.connect(self._on_scan_completed)
        self.worker.scan_completed.connect(self.thread.quit)
        self.thread.finished.connect(self._on_thread_finished)
        
        # Start scan
        self.thread.start()
    
    def _on_thread_finished(self):
        """Clean up thread and worker references after scan completes."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.thread:
            self.thread.deleteLater()
            self.thread = None
    
    def _on_scan_started(self):
        """Handle scan started."""
        self.scan_now_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # Indeterminate
    
    def _on_scan_progress(self, message: str, current: int, total: int):
        """Handle scan progress update."""
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
    
    def _on_file_processing(self, file_path: str):
        """Handle file processing started."""
        pass  # Log already handled by worker
    
    def _on_file_completed(self, file_path: str, results: dict):
        """Handle file processing completed."""
        self.processed_results.append((file_path, results))
    
    def _on_file_error(self, file_path: str, error: str):
        """Handle file processing error."""
        self.processed_results.append((file_path, {"error": error}))
    
    def _on_scan_completed(self, new_count: int, processed_count: int, error_count: int):
        """Handle scan completed."""
        self.scan_now_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        # Update next scan time
        if self.is_watching:
            self._update_next_scan_time()
        
        # Emit results if any were processed
        if self.processed_results:
            self.files_processed.emit(self.processed_results)
            self.processed_results = []
    
    def _log(self, message: str, level: str = "info"):
        """Add a message to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color coding
        colors = {
            "info": "#d4d4d4",
            "success": "#4ec9b0",
            "warning": "#dcdcaa",
            "error": "#f14c4c"
        }
        color = colors.get(level, colors["info"])
        
        html = f'<span style="color: #808080;">[{timestamp}]</span> <span style="color: {color};">{message}</span><br>'
        
        self.log_text.moveCursor(QTextCursor.End)
        self.log_text.insertHtml(html)
        self.log_text.moveCursor(QTextCursor.End)
    
    def _clear_log(self):
        """Clear the activity log."""
        self.log_text.clear()
    
    def get_watch_folders(self) -> List[str]:
        """Get the list of folders being watched."""
        folders = []
        for i in range(self.folders_list.count()):
            folders.append(self.folders_list.item(i).text())
        return folders
    
    def get_scan_interval(self) -> int:
        """Get the scan interval in minutes."""
        return self.interval_combo.currentData()
    
    def stop_watcher(self):
        """Public method to stop the watcher (e.g., on app close)."""
        if self.is_watching:
            self._stop_watcher()
