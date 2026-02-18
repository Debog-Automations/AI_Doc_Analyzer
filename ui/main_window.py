"""
Main Window for AI Document Analyzer
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QMenuBar, QAction, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFont
import os
import sys

from .tabs import SettingsTab, SourceTab, ProcessingTab, ResultsTab, QuestionsTab, WatcherTab

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import DedupService, AIExtractor, extract_document
from extractors import MetadataExtractor


class MainWindow(QMainWindow):
    """Main application window with tabbed interface."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Document Analyzer")
        self.setMinimumSize(600, 400)
        
        # Initialize services
        self.dedup_service = DedupService()
        
        # Set application style
        self._set_style()
        
        # Initialize UI components
        self._init_ui()
        self._init_menu()
        self._connect_signals()
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def _set_style(self):
        """Set application styling."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                border: 1px solid #c0c0c0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #c0c0c0;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: #0078d4;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QComboBox {
                padding: 8px;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget, QTreeWidget, QTableWidget {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: white;
            }
            QProgressBar {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                text-align: center;
                background-color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
        """)
    
    def _init_ui(self):
        """Initialize the main UI."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        
        # Create tabs
        self.settings_tab = SettingsTab()
        self.source_tab = SourceTab()
        self.questions_tab = QuestionsTab()
        self.processing_tab = ProcessingTab()
        self.results_tab = ResultsTab()
        self.watcher_tab = WatcherTab()
        
        # Add tabs
        self.tab_widget.addTab(self.source_tab, "Source")
        self.tab_widget.addTab(self.questions_tab, "Questions")
        self.tab_widget.addTab(self.processing_tab, "Processing")
        self.tab_widget.addTab(self.watcher_tab, "Watcher")
        self.tab_widget.addTab(self.results_tab, "Results")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        layout.addWidget(self.tab_widget)
    
    def _init_menu(self):
        """Initialize the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open Files...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_files)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("&Export Results...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_results)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _connect_signals(self):
        """Connect signals between tabs."""
        # When files are selected in source tab, update processing tab
        self.source_tab.files_selected.connect(self._on_files_selected)
        
        # When processing completes, show results
        self.processing_tab.processing_completed.connect(self._on_processing_completed)
        
        # When settings change, update source tab with Box config
        self.settings_tab.settings_changed.connect(self._on_settings_changed)
        
        # Set up the processing function (placeholder for now)
        self.processing_tab.set_process_function(self._process_file)
        
        # Watcher tab signals
        self.watcher_tab.set_process_function(self._process_file)
        self.watcher_tab.files_processed.connect(self._on_watcher_files_processed)
        
        # Initialize watcher with Box credentials if available
        box_credentials = self.settings_tab.get_box_credentials()
        if box_credentials.get("developer_token") or (box_credentials.get("client_id") and box_credentials.get("client_secret")):
            self.watcher_tab.set_box_credentials(box_credentials)
    
    def _on_files_selected(self, files: list):
        """Handle files selected from source tab."""
        # Convert file info dicts to paths for processing tab
        file_paths = self.source_tab.get_selected_file_paths()
        self.processing_tab.set_files(file_paths)
    
    def _on_settings_changed(self):
        """Handle settings changes."""
        # Update source tab with Box CCG credentials
        box_credentials = self.settings_tab.get_box_credentials()
        if box_credentials.get("developer_token") or (box_credentials.get("client_id") and box_credentials.get("client_secret")):
            self.source_tab.set_box_credentials(box_credentials)
            self.watcher_tab.set_box_credentials(box_credentials)
    
    def _process_file(self, file_path: str) -> dict:
        """
        Process a single file and return results.
        Includes deduplication check, programmatic field extraction, and AI extraction.
        """
        import json
        
        # Check for duplicates (Phase 3)
        dedup_status = self.dedup_service.check_and_get_status(file_path)
        file_hash = dedup_status['file_hash']
        is_duplicate = dedup_status['is_duplicate']

        is_duplicate = False # TODO: Remove this
        
        # Extract programmatic fields (Phase 4)
        prog_fields = MetadataExtractor.extract_all(
            file_path=file_path,
            file_hash=file_hash,
            has_been_processed=is_duplicate
        )
        
        # Convert to dict
        result = prog_fields.to_dict()
        result['file_path'] = file_path
        
        if is_duplicate:
            prev = dedup_status['previous_record']
            result['Status'] = "Skipped (Duplicate)"
            result['Previous Processing'] = prev.get('processed_at', 'Unknown')
            result['Title'] = "(Skipped - already processed)"
            result['Type'] = "(Skipped - already processed)"
            result['Effective Date'] = "(Skipped)"
            result['Expiration Date'] = "(Skipped)"
            result['Parties'] = "(Skipped)"
            result['AI Summary'] = "(Skipped - see previous extraction)"
            return result
        
        # AI Extraction (Phase 5)
        try:
            # Get API key from settings
            api_key = self.settings_tab.get_openai_key()
            if not api_key:
                # Try environment variable
                api_key = os.getenv("OPENAI_API_KEY")
            
            if api_key:
                # Get custom questions from Questions tab
                questions = self.questions_tab.get_questions()
                
                if questions:
                    # Use custom questions for extraction
                    ai_result, ai_metadata = extract_document(
                        file_path, 
                        api_key=api_key,
                        questions=questions
                    )
                else:
                    # Fallback to legacy extraction if no questions defined
                    ai_result, ai_metadata = extract_document(file_path, api_key=api_key)
                
                # Merge AI results with programmatic fields
                result.update(ai_result)
                result['Status'] = "Success"
                result['_ai_retries'] = ai_metadata.get('retries', 0)
                result['_ai_missing'] = ', '.join(ai_metadata.get('final_missing', []))
            else:
                result['Status'] = "Partial (No API Key)"
                result['Title'] = "(Configure OpenAI API key in Settings)"
                result['Type'] = "(Configure OpenAI API key in Settings)"
                result['AI Summary'] = "(OpenAI API key required for AI extraction)"
                
        except Exception as e:
            result['Status'] = f"Error: {str(e)[:50]}"
            result['_error'] = str(e)
        
        # Register as processed (Phase 3)
        self.dedup_service.register_document(
            file_path=file_path,
            file_hash=file_hash,
            source_type='local',
            status='completed' if 'Error' not in result.get('Status', '') else 'failed',
            extraction_data=json.dumps(result)
        )
        
        return result
    
    def _on_processing_completed(self, results: list):
        """Handle processing completion."""
        self.results_tab.add_results(results)
        self.tab_widget.setCurrentWidget(self.results_tab)
        self.statusBar().showMessage(f"Processing complete: {len(results)} files processed")
    
    def _on_watcher_files_processed(self, results: list):
        """Handle files processed by the watcher."""
        if results:
            self.results_tab.add_results(results)
            self.statusBar().showMessage(f"Watcher processed {len(results)} file(s)")
    
    def _open_files(self):
        """Open files from menu."""
        self.tab_widget.setCurrentWidget(self.source_tab)
        self.source_tab._add_files_dialog()
    
    def _export_results(self):
        """Export results from menu."""
        self.tab_widget.setCurrentWidget(self.results_tab)
        self.results_tab._export_results()
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About AI Document Analyzer",
            """<h2>AI Document Analyzer</h2>
            <p>Version 1.0.0</p>
            <p>A tool for extracting structured data from documents using AI.</p>
            <p><b>Features:</b></p>
            <ul>
                <li>Process PDF, Excel, and image files</li>
                <li>Extract metadata and AI-powered field extraction</li>
                <li>Export to Excel/CSV</li>
                <li>Integration with Box, AWS S3, and more</li>
            </ul>
            """
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Check if processing is in progress
        if hasattr(self.processing_tab, 'thread') and \
           self.processing_tab.thread and \
           self.processing_tab.thread.isRunning():
            
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "Processing is in progress. Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
            
            # Cancel processing
            self.processing_tab._cancel_processing()
        
        # Stop the watcher if running
        if hasattr(self, 'watcher_tab'):
            self.watcher_tab.stop_watcher()
        
        event.accept()

