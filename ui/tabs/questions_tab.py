"""
Questions Tab - Manage AI extraction questions
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QTextEdit,
    QScrollArea, QFrame, QAbstractItemView
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont
import json
import os

from logger import get_logger

logger = get_logger(__name__)


# Default questions based on universal_schema.py fields
DEFAULT_QUESTIONS = [
    {"question": "What is the document title?", "column_name": "Title"},
    {"question": "What type of document is this (e.g., MGA Agreement, Quota Share Contract, Endorsement)?", "column_name": "Type"},
    {"question": "Provide a 2-3 sentence summary of this document.", "column_name": "AI Summary"},
    {"question": "What are all the 'As of' or 'Data as of' dates found in this document? Include the source location for each.", "column_name": "As Of Dates"},
    {"question": "What are all the effective dates or inception dates? Include the source location for each.", "column_name": "Effective Date"},
    {"question": "When was this document executed or signed?", "column_name": "Executed Date"},
    {"question": "When does this agreement expire or terminate?", "column_name": "Expiration Date"},
    {"question": "What is the primary currency used in this document?", "column_name": "Currency"},
    {"question": "What is the broker's name?", "column_name": "Broker Name"},
    {"question": "What is the carrier or insurer's name?", "column_name": "Carrier Name"},
    {"question": "What is the MGA (Managing General Agent) name?", "column_name": "MGA Name"},
    {"question": "What is the intermediary's name?", "column_name": "Intermediary Name"},
    {"question": "What is the ceded percentage or quota share percentage?", "column_name": "Ceded Percent"},
    {"question": "What are the commission rates?", "column_name": "Commission Rates"},
    {"question": "What is the actual Gross Written Premium (GWP)?", "column_name": "GWP Actual"},
    {"question": "What is the estimated Gross Written Premium (GWP)?", "column_name": "GWP Estimated"},
    {"question": "What is the actual Net Written Premium (NWP)?", "column_name": "NWP Actual"},
    {"question": "What is the estimated Net Written Premium (NWP)?", "column_name": "NWP Estimated"},
    {"question": "What lines of business are covered?", "column_name": "Lines of Business"},
    {"question": "Who are all the parties to this agreement? Include their roles (e.g., Cedent, Reinsurer, Broker).", "column_name": "Parties"},
    {"question": "Who signed this document? List all signer names.", "column_name": "Signers"},
    {"question": "What are the major sections or chapters in this document?", "column_name": "Sections/Chapters"},
    {"question": "What countries are mentioned in this document?", "column_name": "Countries"},
    {"question": "What states or jurisdictions are mentioned?", "column_name": "States"},
]


class QuestionEditDialog(QDialog):
    """Dialog for adding or editing a question."""
    
    def __init__(self, parent=None, question: str = "", column_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Edit Question" if question else "Add Question")
        self.setMinimumWidth(500)
        self.setMinimumHeight(200)
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        # Question text (multi-line)
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText("Enter the question to ask the AI...")
        self.question_input.setText(question)
        self.question_input.setMaximumHeight(100)
        form_layout.addRow("Question:", self.question_input)
        
        # Column name
        self.column_input = QLineEdit()
        self.column_input.setPlaceholderText("Column header for output (e.g., 'Effective Date')")
        self.column_input.setText(column_name)
        form_layout.addRow("Column Name:", self.column_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._validate_and_accept)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def _validate_and_accept(self):
        """Validate inputs before accepting."""
        question = self.question_input.toPlainText().strip()
        column_name = self.column_input.text().strip()
        
        if not question:
            QMessageBox.warning(self, "Validation Error", "Please enter a question.")
            return
        
        if not column_name:
            QMessageBox.warning(self, "Validation Error", "Please enter a column name.")
            return
        
        self.accept()
    
    def get_values(self) -> tuple:
        """Return the question and column name."""
        return (
            self.question_input.toPlainText().strip(),
            self.column_input.text().strip()
        )


class QuestionsTab(QWidget):
    """Tab for managing AI extraction questions."""
    
    questions_changed = pyqtSignal()
    
    def __init__(self, config_path: str = "app_config.json"):
        super().__init__()
        self.config_path = config_path
        self.config = self._load_config()
        self._init_ui()
        self._load_questions()
    
    def _init_ui(self):
        """Initialize the UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header with description
        header_label = QLabel(
            "<b>AI Extraction Questions</b><br>"
            "<i>Define the questions that the AI will answer when extracting data from documents. "
            "Each question will produce a column in the output.</i>"
        )
        header_label.setWordWrap(True)
        header_label.setStyleSheet("margin-bottom: 10px;")
        main_layout.addWidget(header_label)
        
        # Questions table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Question", "Column Name"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(True)
        self.table.doubleClicked.connect(self._edit_question)
        main_layout.addWidget(self.table)
        
        # Button row
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Add Question")
        add_btn.clicked.connect(self._add_question)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Edit")
        edit_btn.clicked.connect(self._edit_question)
        button_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(self._delete_question)
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        move_up_btn = QPushButton("⬆️ Move Up")
        move_up_btn.clicked.connect(self._move_up)
        button_layout.addWidget(move_up_btn)
        
        move_down_btn = QPushButton("⬇️ Move Down")
        move_down_btn.clicked.connect(self._move_down)
        button_layout.addWidget(move_down_btn)
        
        main_layout.addLayout(button_layout)
        
        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet("background-color: #dc3545;")
        reset_btn.clicked.connect(self._reset_to_defaults)
        action_layout.addWidget(reset_btn)
        
        save_btn = QPushButton("Save Questions")
        save_btn.setMinimumWidth(150)
        save_btn.clicked.connect(self._save_questions)
        action_layout.addWidget(save_btn)
        
        action_layout.addStretch()
        main_layout.addLayout(action_layout)
    
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
    
    def _load_questions(self):
        """Load questions from config or use defaults."""
        questions = self.config.get("custom_questions", None)
        
        if questions is None:
            # No questions saved yet, use defaults
            questions = DEFAULT_QUESTIONS.copy()
            self.config["custom_questions"] = questions
            self._save_config()
        
        self._populate_table(questions)
    
    def _populate_table(self, questions: list):
        """Populate the table with questions."""
        self.table.setRowCount(len(questions))
        
        for row, q in enumerate(questions):
            question_item = QTableWidgetItem(q.get("question", ""))
            question_item.setFlags(question_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, question_item)
            
            column_item = QTableWidgetItem(q.get("column_name", ""))
            column_item.setFlags(column_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, column_item)
        
        self.table.resizeRowsToContents()
    
    def _get_questions_from_table(self) -> list:
        """Get all questions from the table."""
        questions = []
        for row in range(self.table.rowCount()):
            question = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            column_name = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
            if question and column_name:
                questions.append({
                    "question": question,
                    "column_name": column_name
                })
        return questions
    
    def _add_question(self):
        """Add a new question."""
        dialog = QuestionEditDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            question, column_name = dialog.get_values()
            
            # Check for duplicate column names
            for row in range(self.table.rowCount()):
                existing_col = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
                if existing_col.lower() == column_name.lower():
                    QMessageBox.warning(
                        self, "Duplicate Column",
                        f"A question with column name '{column_name}' already exists."
                    )
                    return
            
            # Add to table
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            question_item = QTableWidgetItem(question)
            question_item.setFlags(question_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, question_item)
            
            column_item = QTableWidgetItem(column_name)
            column_item.setFlags(column_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, column_item)
            
            self.table.resizeRowsToContents()
            self._auto_save()
            self.questions_changed.emit()
    
    def _edit_question(self):
        """Edit the selected question."""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "No Selection", "Please select a question to edit.")
            return
        
        current_question = self.table.item(current_row, 0).text() if self.table.item(current_row, 0) else ""
        current_column = self.table.item(current_row, 1).text() if self.table.item(current_row, 1) else ""
        
        dialog = QuestionEditDialog(self, current_question, current_column)
        if dialog.exec_() == QDialog.Accepted:
            question, column_name = dialog.get_values()
            
            # Check for duplicate column names (excluding current row)
            for row in range(self.table.rowCount()):
                if row == current_row:
                    continue
                existing_col = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
                if existing_col.lower() == column_name.lower():
                    QMessageBox.warning(
                        self, "Duplicate Column",
                        f"A question with column name '{column_name}' already exists."
                    )
                    return
            
            # Update table
            self.table.item(current_row, 0).setText(question)
            self.table.item(current_row, 1).setText(column_name)
            self.table.resizeRowsToContents()
            self._auto_save()
            self.questions_changed.emit()
    
    def _delete_question(self):
        """Delete the selected question."""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "No Selection", "Please select a question to delete.")
            return
        
        question = self.table.item(current_row, 0).text() if self.table.item(current_row, 0) else ""
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete this question?\n\n{question[:100]}...",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.table.removeRow(current_row)
            self._auto_save()
            self.questions_changed.emit()
    
    def _move_up(self):
        """Move selected question up."""
        current_row = self.table.currentRow()
        if current_row <= 0:
            return
        
        self._swap_rows(current_row, current_row - 1)
        self.table.setCurrentCell(current_row - 1, 0)
        self._auto_save()
        self.questions_changed.emit()
    
    def _move_down(self):
        """Move selected question down."""
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= self.table.rowCount() - 1:
            return
        
        self._swap_rows(current_row, current_row + 1)
        self.table.setCurrentCell(current_row + 1, 0)
        self._auto_save()
        self.questions_changed.emit()
    
    def _swap_rows(self, row1: int, row2: int):
        """Swap two rows in the table."""
        for col in range(self.table.columnCount()):
            item1 = self.table.takeItem(row1, col)
            item2 = self.table.takeItem(row2, col)
            self.table.setItem(row1, col, item2)
            self.table.setItem(row2, col, item1)
    
    def _auto_save(self):
        """Automatically save questions to config file (no dialog)."""
        questions = self._get_questions_from_table()
        if questions:
            self.config["custom_questions"] = questions
            self._save_config()
            logger.debug(f"Auto-saved {len(questions)} questions")
    
    def _reset_to_defaults(self):
        """Reset questions to default list."""
        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Are you sure you want to reset all questions to defaults?\n\n"
            "This will delete any custom questions you have added.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._populate_table(DEFAULT_QUESTIONS)
            self.config["custom_questions"] = DEFAULT_QUESTIONS.copy()
            self._save_config()
            self.questions_changed.emit()
            QMessageBox.information(self, "Reset Complete", "Questions have been reset to defaults.")
    
    def _save_questions(self):
        """Save questions to config file."""
        questions = self._get_questions_from_table()
        
        if not questions:
            QMessageBox.warning(
                self, "No Questions",
                "Please add at least one question before saving."
            )
            return
        
        self.config["custom_questions"] = questions
        self._save_config()
        self.questions_changed.emit()
        QMessageBox.information(self, "Success", f"Saved {len(questions)} questions.")
    
    def get_questions(self) -> list:
        """
        Get the current list of questions.
        
        Returns:
            List of dicts with 'question' and 'column_name' keys
        """
        return self._get_questions_from_table()

