"""
Source Tab - Select files and folders to process
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QFileDialog, QAbstractItemView, QSplitter, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QStackedWidget, QLineEdit
)
from PyQt5.QtCore import pyqtSignal, Qt, QThread, QObject
from PyQt5.QtGui import QIcon
import os
import tempfile
from typing import List, Optional

from logger import get_logger

logger = get_logger(__name__)


class BoxLoaderWorker(QObject):
    """Worker for loading Box folders in background."""
    
    folders_loaded = pyqtSignal(str, list)  # path, list of folder dicts
    files_loaded = pyqtSignal(str, list)  # path, list of file dicts
    error = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, connector, path: str, load_files: bool = False):
        super().__init__()
        self.connector = connector
        self.path = path
        self.load_files = load_files
    
    def run(self):
        try:
            # Load folders
            folders = self.connector.list_folders(self.path)
            folder_dicts = [{"id": f.id, "name": f.name, "path": f.path, "has_children": f.has_children} for f in folders]
            self.folders_loaded.emit(self.path, folder_dicts)
            
            # Load files if requested
            if self.load_files:
                files = self.connector.list_files(self.path)
                file_dicts = [{"id": f.id, "name": f.name, "path": f.path, "size": f.size} for f in files]
                self.files_loaded.emit(self.path, file_dicts)
                
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class SourceTab(QWidget):
    """Tab for selecting document sources (local files or Box)."""
    
    files_selected = pyqtSignal(list)  # Emits list of file paths or FileInfo dicts
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.xlsx', '.xlsm', '.xls', '.docx', '.png', '.jpg', '.jpeg', '.tiff'}
    
    def __init__(self):
        super().__init__()
        self.selected_files: List[dict] = []  # List of file info dicts
        self.box_connector = None
        self.box_credentials: Optional[dict] = None  # CCG credentials
        self._temp_dir = tempfile.mkdtemp(prefix="doc_analyzer_")
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the source selection UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Source Type Selection
        source_type_layout = QHBoxLayout()
        source_type_layout.addWidget(QLabel("Source Type:"))
        
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems(["Local Files", "Box"])
        self.source_type_combo.currentIndexChanged.connect(self._on_source_type_changed)
        self.source_type_combo.setMinimumWidth(200)
        source_type_layout.addWidget(self.source_type_combo)
        source_type_layout.addStretch()
        
        layout.addLayout(source_type_layout)
        
        # Main content area with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Browser (stacked for Local/Box)
        browser_group = QGroupBox("File Browser")
        browser_main_layout = QVBoxLayout()
        
        self.browser_stack = QStackedWidget()
        
        # === LOCAL BROWSER ===
        local_browser = QWidget()
        local_layout = QVBoxLayout(local_browser)
        local_layout.setContentsMargins(0, 0, 0, 0)
        
        # Folder path and browse button
        folder_path_layout = QHBoxLayout()
        self.folder_path_label = QLabel("No folder selected")
        self.folder_path_label.setWordWrap(True)
        folder_path_layout.addWidget(self.folder_path_label, 1)
        
        browse_folder_btn = QPushButton("Browse Folder...")
        browse_folder_btn.clicked.connect(self._browse_folder)
        folder_path_layout.addWidget(browse_folder_btn)
        
        local_layout.addLayout(folder_path_layout)
        
        # Folder tree
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabel("Files")
        self.folder_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folder_tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        local_layout.addWidget(self.folder_tree)
        
        # Add selected button
        add_selected_btn = QPushButton("Add Selected")
        add_selected_btn.clicked.connect(self._add_selected_from_tree)
        local_layout.addWidget(add_selected_btn)
        
        self.browser_stack.addWidget(local_browser)
        
        # === BOX BROWSER ===
        box_browser = QWidget()
        box_layout = QVBoxLayout(box_browser)
        box_layout.setContentsMargins(0, 0, 0, 0)
        
        # Box connection status
        box_status_layout = QHBoxLayout()
        self.box_status_label = QLabel("Not connected")
        self.box_status_label.setStyleSheet("color: gray;")
        box_status_layout.addWidget(self.box_status_label)
        
        self.box_connect_btn = QPushButton("Connect to Box")
        self.box_connect_btn.clicked.connect(self._connect_to_box)
        box_status_layout.addWidget(self.box_connect_btn)
        box_status_layout.addStretch()
        
        box_layout.addLayout(box_status_layout)
        
        # Box path input
        box_path_layout = QHBoxLayout()
        box_path_layout.addWidget(QLabel("Path:"))
        self.box_path_input = QLineEdit()
        self.box_path_input.setPlaceholderText("/")
        self.box_path_input.returnPressed.connect(self._load_box_path)
        box_path_layout.addWidget(self.box_path_input)
        
        box_go_btn = QPushButton("Go")
        box_go_btn.clicked.connect(self._load_box_path)
        box_path_layout.addWidget(box_go_btn)
        
        box_layout.addLayout(box_path_layout)
        
        # Box folder tree
        self.box_tree = QTreeWidget()
        self.box_tree.setHeaderLabels(["Name", "Size"])
        self.box_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.box_tree.itemDoubleClicked.connect(self._on_box_item_double_clicked)
        self.box_tree.itemExpanded.connect(self._on_box_item_expanded)
        box_layout.addWidget(self.box_tree)
        
        # Add selected from Box button
        box_add_btn = QPushButton("Add Selected")
        box_add_btn.clicked.connect(self._add_selected_from_box)
        box_layout.addWidget(box_add_btn)
        
        self.browser_stack.addWidget(box_browser)
        
        browser_main_layout.addWidget(self.browser_stack)
        browser_group.setLayout(browser_main_layout)
        splitter.addWidget(browser_group)
        
        # Right side - Selected files queue
        queue_group = QGroupBox("Files to Process")
        queue_layout = QVBoxLayout()
        
        # File count label
        self.file_count_label = QLabel("0 files selected")
        queue_layout.addWidget(self.file_count_label)
        
        # Selected files list
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.selected_list.setDragDropMode(QAbstractItemView.InternalMove)
        queue_layout.addWidget(self.selected_list)
        
        # Queue action buttons
        queue_btn_layout = QHBoxLayout()
        
        add_files_btn = QPushButton("Add Files...")
        add_files_btn.clicked.connect(self._add_files_dialog)
        queue_btn_layout.addWidget(add_files_btn)
        
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        queue_btn_layout.addWidget(remove_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        queue_btn_layout.addWidget(clear_btn)
        
        queue_layout.addLayout(queue_btn_layout)
        
        queue_group.setLayout(queue_layout)
        splitter.addWidget(queue_group)
        
        # Set initial splitter sizes
        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)
        
        # Info label
        info_label = QLabel(
            f"Supported file types: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
        )
        info_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(info_label)
    
    def _on_source_type_changed(self, index: int):
        """Handle source type change."""
        self.browser_stack.setCurrentIndex(index)
        
        if index == 1:  # Box
            self._init_box_browser()
    
    def _browse_folder(self):
        """Open folder selection dialog."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path_label.setText(folder)
            self._populate_folder_tree(folder)
    
    def _populate_folder_tree(self, folder_path: str):
        """Populate the folder tree with files."""
        self.folder_tree.clear()
        
        root_item = QTreeWidgetItem([os.path.basename(folder_path)])
        root_item.setData(0, Qt.UserRole, folder_path)
        self.folder_tree.addTopLevelItem(root_item)
        
        self._add_folder_contents(root_item, folder_path)
        root_item.setExpanded(True)
    
    def _add_folder_contents(self, parent_item: QTreeWidgetItem, folder_path: str):
        """Recursively add folder contents to tree."""
        try:
            entries = sorted(os.listdir(folder_path))
            
            # Add folders first
            for entry in entries:
                full_path = os.path.join(folder_path, entry)
                if os.path.isdir(full_path) and not entry.startswith('.'):
                    folder_item = QTreeWidgetItem([f"📁 {entry}"])
                    folder_item.setData(0, Qt.UserRole, full_path)
                    parent_item.addChild(folder_item)
                    self._add_folder_contents(folder_item, full_path)
            
            # Then add files
            for entry in entries:
                full_path = os.path.join(folder_path, entry)
                if os.path.isfile(full_path):
                    ext = os.path.splitext(entry)[1].lower()
                    if ext in self.SUPPORTED_EXTENSIONS:
                        file_item = QTreeWidgetItem([f"📄 {entry}"])
                        file_item.setData(0, Qt.UserRole, full_path)
                        parent_item.addChild(file_item)
        except PermissionError:
            pass
    
    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click on tree item."""
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            self._add_file_to_queue(path)
    
    def _add_selected_from_tree(self):
        """Add selected files from tree to queue."""
        selected_items = self.folder_tree.selectedItems()
        added_count = 0
        
        for item in selected_items:
            path = item.data(0, Qt.UserRole)
            if path:
                if os.path.isfile(path):
                    if self._add_file_to_queue(path):
                        added_count += 1
                elif os.path.isdir(path):
                    # Add all files from directory
                    added_count += self._add_folder_files(path)
        
        if added_count > 0:
            self._update_file_count()
    
    def _add_folder_files(self, folder_path: str) -> int:
        """Add all supported files from a folder. Returns count added."""
        count = 0
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    full_path = os.path.join(root, file)
                    if self._add_file_to_queue(full_path):
                        count += 1
        return count
    
    def _add_file_to_queue(self, file_path: str) -> bool:
        """Add a local file to the processing queue. Returns True if added."""
        # Check if already added
        for f in self.selected_files:
            if isinstance(f, dict):
                if f.get("path") == file_path:
                    return False
            elif f == file_path:
                return False
        
        # Create file info dict for consistency
        file_info = {
            "type": "file",
            "id": file_path,  # For local files, path is the ID
            "name": os.path.basename(file_path),
            "path": file_path,
            "size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            "source_type": "local"
        }
        self.selected_files.append(file_info)
        
        # Create list item with filename and tooltip with full path
        size_str = self._format_size(file_info["size"])
        item = QListWidgetItem(f"{file_info['name']} ({size_str})")
        item.setToolTip(file_path)
        item.setData(Qt.UserRole, file_info)
        self.selected_list.addItem(item)
        
        self._update_file_count()
        self.files_selected.emit(self.get_selected_files())
        return True
    
    def _add_files_dialog(self):
        """Open file selection dialog."""
        file_filter = "Documents (*.pdf *.xlsx *.xlsm *.xls *.docx);;Images (*.png *.jpg *.jpeg *.tiff);;All Files (*)"
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", file_filter
        )
        
        for file_path in files:
            self._add_file_to_queue(file_path)
    
    def _remove_selected(self):
        """Remove selected files from queue."""
        selected_items = self.selected_list.selectedItems()
        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            if file_path in self.selected_files:
                self.selected_files.remove(file_path)
            self.selected_list.takeItem(self.selected_list.row(item))
        
        self._update_file_count()
        self.files_selected.emit(self.selected_files)
    
    def _clear_all(self):
        """Clear all files from queue."""
        self.selected_files.clear()
        self.selected_list.clear()
        self._update_file_count()
        self.files_selected.emit(self.selected_files)
    
    def _update_file_count(self):
        """Update the file count label."""
        count = len(self.selected_files)
        self.file_count_label.setText(f"{count} file{'s' if count != 1 else ''} selected")
    
    def get_selected_files(self) -> List[dict]:
        """Get the list of selected file info dicts."""
        return self.selected_files.copy()
    
    def get_selected_file_paths(self) -> List[str]:
        """
        Get local file paths for all selected files.
        For Box files, downloads them first if not already downloaded.
        """
        paths = []
        for f in self.selected_files:
            if isinstance(f, dict):
                if f.get("source_type") == "box":
                    # Need to download Box file
                    if "local_path" not in f:
                        try:
                            local_path = self.download_box_file(f)
                            f["local_path"] = local_path
                        except Exception as e:
                            logger.error(f"Failed to download Box file {f.get('name', 'unknown')}: {e}")
                            continue
                    paths.append(f["local_path"])
                else:
                    # Local file
                    paths.append(f.get("path", f.get("id", "")))
            else:
                # String path (legacy)
                paths.append(f)
        return paths
    
    def clear_processed_file(self, file_path: str):
        """Remove a processed file from the queue."""
        # Find the file in selected_files by path
        for f in self.selected_files[:]:
            if isinstance(f, dict):
                if f.get('path') == file_path or f.get('local_path') == file_path:
                    self.selected_files.remove(f)
                    break
            elif f == file_path:
                self.selected_files.remove(f)
                break
        
        # Find and remove from list widget
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            item_data = item.data(Qt.UserRole)
            if isinstance(item_data, dict):
                if item_data.get('path') == file_path or item_data.get('local_path') == file_path:
                    self.selected_list.takeItem(i)
                    break
            elif item_data == file_path:
                self.selected_list.takeItem(i)
                break
        
        self._update_file_count()
    
    # ==================== BOX METHODS ====================
    
    def set_box_credentials(self, credentials: dict):
        """
        Set the Box CCG credentials.
        
        Args:
            credentials: Dictionary with client_id, client_secret, enterprise_id, user_id
        """
        self.box_credentials = credentials
    
    def set_box_config_path(self, config_path: str):
        """
        Legacy method - kept for backward compatibility.
        Use set_box_credentials() instead.
        """
        pass  # No longer used with CCG authentication
    
    def _init_box_browser(self):
        """Initialize Box browser when switching to Box source."""
        if not self.box_connector:
            self.box_status_label.setText("Not connected - Click 'Connect to Box'")
            self.box_status_label.setStyleSheet("color: orange;")
    
    def _connect_to_box(self):
        """Connect to Box using Developer Token or CCG credentials."""
        # Try to get credentials if not set
        if not self.box_credentials:
            try:
                import json
                import keyring
                
                # Get developer token first (takes priority)
                developer_token = keyring.get_password("AI_Doc_Analyzer", "box_developer_token")
                
                # Get CCG credentials from keyring and config
                client_id = keyring.get_password("AI_Doc_Analyzer", "box_client_id")
                client_secret = keyring.get_password("AI_Doc_Analyzer", "box_client_secret")
                
                enterprise_id = None
                user_id = None
                if os.path.exists("app_config.json"):
                    with open("app_config.json", "r") as f:
                        config = json.load(f)
                        enterprise_id = config.get("box_enterprise_id") or None
                        user_id = config.get("box_user_id") or None
                
                if developer_token or (client_id and client_secret):
                    self.box_credentials = {
                        "developer_token": developer_token or None,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "enterprise_id": enterprise_id,
                        "user_id": user_id
                    }
            except Exception as e:
                logger.warning(f"Error loading Box credentials: {e}")
        
        # Validate credentials
        if not self.box_credentials:
            QMessageBox.warning(
                self,
                "Box Configuration Required",
                "Please configure Box settings in the Settings tab first.\n\n"
                "You can use a Developer Token (quick testing) or CCG credentials (production)."
            )
            return
        
        developer_token = self.box_credentials.get("developer_token")
        client_id = self.box_credentials.get("client_id")
        client_secret = self.box_credentials.get("client_secret")
        enterprise_id = self.box_credentials.get("enterprise_id")
        user_id = self.box_credentials.get("user_id")
        
        # Check if we have valid credentials (developer token OR complete CCG credentials)
        has_developer_token = bool(developer_token)
        has_ccg_credentials = client_id and client_secret and (enterprise_id or user_id)
        
        if not has_developer_token and not has_ccg_credentials:
            QMessageBox.warning(
                self,
                "Box Configuration Required",
                "Please configure Box credentials in the Settings tab:\n\n"
                "• Developer Token (quick testing, valid 60 min)\n"
                "  OR\n"
                "• CCG credentials (Client ID, Secret, and Enterprise/User ID)"
            )
            return
        
        auth_method = "Developer Token" if has_developer_token else "CCG"
        self.box_status_label.setText(f"Connecting via {auth_method}...")
        self.box_status_label.setStyleSheet("color: blue;")
        self.box_connect_btn.setEnabled(False)
        
        try:
            from connectors import BoxConnector
            
            self.box_connector = BoxConnector(
                developer_token=developer_token,
                client_id=client_id,
                client_secret=client_secret,
                enterprise_id=enterprise_id,
                user_id=user_id
            )
            if self.box_connector.connect():
                self.box_status_label.setText(f"Connected via {auth_method}")
                self.box_status_label.setStyleSheet("color: green;")
                self.box_connect_btn.setText("Reconnect")
                
                # Load root folder
                self._load_box_folder("/")
            else:
                raise Exception("Connection failed")
                
        except Exception as e:
            self.box_status_label.setText(f"Connection failed: {str(e)[:50]}")
            self.box_status_label.setStyleSheet("color: red;")
            self.box_connector = None
        
        self.box_connect_btn.setEnabled(True)
    
    def _load_box_path(self):
        """Load the Box path from the input field."""
        path = self.box_path_input.text().strip() or "/"
        self._load_box_folder(path)
    
    def _load_box_folder(self, path: str):
        """Load folder contents from Box."""
        if not self.box_connector or not self.box_connector.is_connected():
            QMessageBox.warning(self, "Not Connected", "Please connect to Box first.")
            return
        
        self.box_tree.clear()
        self.box_path_input.setText(path)
        
        try:
            # Load folders
            folders = self.box_connector.list_folders(path)
            for folder in folders:
                folder_item = QTreeWidgetItem([f"📁 {folder.name}", ""])
                folder_item.setData(0, Qt.UserRole, {
                    "type": "folder",
                    "id": folder.id,
                    "name": folder.name,
                    "path": folder.path
                })
                # Add placeholder child so it can be expanded
                if folder.has_children:
                    folder_item.addChild(QTreeWidgetItem(["Loading...", ""]))
                self.box_tree.addTopLevelItem(folder_item)
            
            # Load files
            files = self.box_connector.list_files(path)
            for f in files:
                size_str = self._format_size(f.size)
                file_item = QTreeWidgetItem([f"📄 {f.name}", size_str])
                file_item.setData(0, Qt.UserRole, {
                    "type": "file",
                    "id": f.id,
                    "name": f.name,
                    "path": f.path,
                    "size": f.size,
                    "source_type": "box"
                })
                self.box_tree.addTopLevelItem(file_item)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load Box folder: {e}")
    
    def _on_box_item_expanded(self, item: QTreeWidgetItem):
        """Handle Box tree item expansion - load children."""
        data = item.data(0, Qt.UserRole)
        if not data or data.get("type") != "folder":
            return
        
        # Check if we need to load children (placeholder present)
        if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
            item.takeChild(0)  # Remove placeholder
            
            try:
                folder_path = data.get("path", "/")
                
                # Load subfolders
                folders = self.box_connector.list_folders(folder_path)
                for folder in folders:
                    folder_item = QTreeWidgetItem([f"📁 {folder.name}", ""])
                    folder_item.setData(0, Qt.UserRole, {
                        "type": "folder",
                        "id": folder.id,
                        "name": folder.name,
                        "path": folder.path
                    })
                    if folder.has_children:
                        folder_item.addChild(QTreeWidgetItem(["Loading...", ""]))
                    item.addChild(folder_item)
                
                # Load files in folder
                files = self.box_connector.list_files(folder_path)
                for f in files:
                    size_str = self._format_size(f.size)
                    file_item = QTreeWidgetItem([f"📄 {f.name}", size_str])
                    file_item.setData(0, Qt.UserRole, {
                        "type": "file",
                        "id": f.id,
                        "name": f.name,
                        "path": f.path,
                        "size": f.size,
                        "source_type": "box"
                    })
                    item.addChild(file_item)
                    
            except Exception as e:
                error_item = QTreeWidgetItem([f"Error: {e}", ""])
                item.addChild(error_item)
    
    def _on_box_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click on Box tree item."""
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        if data.get("type") == "folder":
            # Navigate into folder
            self._load_box_folder(data.get("path", "/"))
        elif data.get("type") == "file":
            # Add file to queue
            self._add_box_file_to_queue(data)
    
    def _add_selected_from_box(self):
        """Add selected files from Box tree to queue."""
        selected_items = self.box_tree.selectedItems()
        added_count = 0
        
        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data and data.get("type") == "file":
                if self._add_box_file_to_queue(data):
                    added_count += 1
        
        if added_count > 0:
            self._update_file_count()
    
    def _add_box_file_to_queue(self, file_data: dict) -> bool:
        """Add a Box file to the processing queue."""
        # Check if already added
        for f in self.selected_files:
            if isinstance(f, dict) and f.get("id") == file_data.get("id"):
                return False
        
        self.selected_files.append(file_data)
        
        # Create list item
        name = file_data.get("name", "Unknown")
        size_str = self._format_size(file_data.get("size", 0))
        item = QListWidgetItem(f"[Box] {name} ({size_str})")
        item.setToolTip(f"Box: {file_data.get('path', '')}")
        item.setData(Qt.UserRole, file_data)
        self.selected_list.addItem(item)
        
        self._update_file_count()
        self.files_selected.emit(self.get_selected_files())
        return True
    
    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        if size is None:
            return "Unknown"
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"
    
    def download_box_file(self, file_data: dict) -> str:
        """
        Download a Box file to temp directory for processing.
        
        Returns the local file path.
        """
        if not self.box_connector or not self.box_connector.is_connected():
            raise ConnectionError("Not connected to Box")
        
        file_id = file_data.get("id")
        filename = file_data.get("name", f"file_{file_id}")
        
        local_path = os.path.join(self._temp_dir, filename)
        self.box_connector.download_file(file_id, local_path)
        
        return local_path

