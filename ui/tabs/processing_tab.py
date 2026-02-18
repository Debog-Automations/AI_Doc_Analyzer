"""
Processing Tab - Control document processing and view progress
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QProgressBar, QTextEdit, QSplitter
)
from PyQt5.QtCore import pyqtSignal, Qt, QThread, QObject
from PyQt5.QtGui import QTextCursor, QColor
from typing import List, Callable, Optional
from datetime import datetime


class ProcessingWorker(QObject):
    """Worker for processing files in a background thread."""
    
    progress = pyqtSignal(int, int)  # current, total
    file_started = pyqtSignal(str)  # file path
    file_completed = pyqtSignal(str, dict)  # file path, results
    file_error = pyqtSignal(str, str)  # file path, error message
    finished = pyqtSignal()
    log_message = pyqtSignal(str, str)  # message, level (info/warning/error/success)
    
    def __init__(self, files: List[str], process_func: Callable):
        super().__init__()
        self.files = files
        self.process_func = process_func
        self._is_cancelled = False
    
    def run(self):
        """Process all files."""
        total = len(self.files)
        
        for i, file_path in enumerate(self.files):
            if self._is_cancelled:
                self.log_message.emit("Processing cancelled by user", "warning")
                break
            
            self.progress.emit(i, total)
            self.file_started.emit(file_path)
            self.log_message.emit(f"Processing: {file_path}", "info")
            
            try:
                results = self.process_func(file_path)
                self.file_completed.emit(file_path, results)
                self.log_message.emit(f"Completed: {file_path}", "success")
            except Exception as e:
                self.file_error.emit(file_path, str(e))
                self.log_message.emit(f"Error: {file_path} - {str(e)}", "error")
        
        self.progress.emit(total, total)
        self.finished.emit()
    
    def cancel(self):
        """Cancel processing."""
        self._is_cancelled = True


class ProcessingTab(QWidget):
    """Tab for controlling document processing."""
    
    processing_started = pyqtSignal()
    processing_completed = pyqtSignal(list)  # List of (file_path, results) tuples
    request_files = pyqtSignal()  # Request current file list from source tab
    
    def __init__(self):
        super().__init__()
        self.worker: Optional[ProcessingWorker] = None
        self.thread: Optional[QThread] = None
        self.files_to_process: List[str] = []
        self.results: List[tuple] = []
        self.process_func: Optional[Callable] = None
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the processing UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Status summary
        status_group = QGroupBox("Processing Status")
        status_layout = QVBoxLayout()
        
        # File counts
        counts_layout = QHBoxLayout()
        
        self.total_label = QLabel("Total: 0")
        counts_layout.addWidget(self.total_label)
        
        self.processed_label = QLabel("Processed: 0")
        counts_layout.addWidget(self.processed_label)
        
        self.success_label = QLabel("Success: 0")
        self.success_label.setStyleSheet("color: green;")
        counts_layout.addWidget(self.success_label)
        
        self.error_label = QLabel("Errors: 0")
        self.error_label.setStyleSheet("color: red;")
        counts_layout.addWidget(self.error_label)
        
        counts_layout.addStretch()
        status_layout.addLayout(counts_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        status_layout.addWidget(self.progress_bar)
        
        # Current file label
        self.current_file_label = QLabel("Ready to process")
        self.current_file_label.setStyleSheet("font-style: italic;")
        status_layout.addWidget(self.current_file_label)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setMinimumWidth(150)
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._start_processing)
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
        button_layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self._clear_log)
        button_layout.addWidget(self.clear_log_btn)
        
        layout.addLayout(button_layout)
        
        # Log area
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        self.log_text.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, Monaco, monospace;
                font-size: 11px;
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group, 1)
        
        # Initialize counters
        self._reset_counters()
    
    def _reset_counters(self):
        """Reset all counters."""
        self.total_count = 0
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self._update_counter_labels()
    
    def _update_counter_labels(self):
        """Update counter labels."""
        self.total_label.setText(f"Total: {self.total_count}")
        self.processed_label.setText(f"Processed: {self.processed_count}")
        self.success_label.setText(f"Success: {self.success_count}")
        self.error_label.setText(f"Errors: {self.error_count}")
    
    def set_files(self, files: List[str]):
        """Set the files to process."""
        self.files_to_process = files
        self.total_count = len(files)
        self._update_counter_labels()
        self._log(f"Ready to process {len(files)} file(s)", "info")
    
    def set_process_function(self, func: Callable):
        """Set the function to call for processing each file."""
        self.process_func = func
    
    def _start_processing(self):
        """Start processing files."""
        if not self.files_to_process:
            self._log("No files selected. Go to Source tab to select files.", "warning")
            return
        
        if not self.process_func:
            self._log("Processing function not configured.", "error")
            return
        
        self._reset_counters()
        self.total_count = len(self.files_to_process)
        self._update_counter_labels()
        self.results = []
        
        # Update UI state
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        
        self._log("=" * 50, "info")
        self._log(f"Starting processing of {self.total_count} file(s)", "info")
        self._log("=" * 50, "info")
        
        # Create worker and thread
        self.thread = QThread()
        self.worker = ProcessingWorker(self.files_to_process, self.process_func)
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_started.connect(self._on_file_started)
        self.worker.file_completed.connect(self._on_file_completed)
        self.worker.file_error.connect(self._on_file_error)
        self.worker.log_message.connect(self._log)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.processing_started.emit()
        self.thread.start()
    
    def _cancel_processing(self):
        """Cancel current processing."""
        if self.worker:
            self.worker.cancel()
            self._log("Cancellation requested...", "warning")
    
    def _on_progress(self, current: int, total: int):
        """Handle progress update."""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
    
    def _on_file_started(self, file_path: str):
        """Handle file processing started."""
        import os
        filename = os.path.basename(file_path)
        self.current_file_label.setText(f"Processing: {filename}")
    
    def _on_file_completed(self, file_path: str, results: dict):
        """Handle file processing completed."""
        self.processed_count += 1
        self.success_count += 1
        self._update_counter_labels()
        self.results.append((file_path, results))
    
    def _on_file_error(self, file_path: str, error: str):
        """Handle file processing error."""
        self.processed_count += 1
        self.error_count += 1
        self._update_counter_labels()
        self.results.append((file_path, {"error": error}))
    
    def _on_finished(self):
        """Handle processing finished."""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.current_file_label.setText("Processing complete")
        self.progress_bar.setValue(100)
        
        self._log("=" * 50, "info")
        self._log(f"Processing complete: {self.success_count} succeeded, {self.error_count} failed", 
                  "success" if self.error_count == 0 else "warning")
        self._log("=" * 50, "info")
        
        self.processing_completed.emit(self.results)
    
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
        """Clear the log."""
        self.log_text.clear()

