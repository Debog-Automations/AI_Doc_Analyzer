"""
Settings Tab - Manage credentials and application settings
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QFormLayout, QMessageBox, QCheckBox,
    QScrollArea, QFrame, QSpinBox, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import pyqtSignal, Qt
import keyring
import json
import os

from logger import get_logger

logger = get_logger(__name__)

# Service name for keyring storage
KEYRING_SERVICE = "AI_Doc_Analyzer"


class SettingsTab(QWidget):
    """Tab for managing API credentials and application settings."""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, config_path: str = "app_config.json"):
        super().__init__()
        self.config_path = config_path
        self.config = self._load_config()
        self._init_ui()
        self._load_credentials()
    
    def _init_ui(self):
        """Initialize the settings UI."""
        # Main layout for the tab
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create content widget for scroll area
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # AI Provider Selection
        provider_group = QGroupBox("AI Provider")
        provider_layout = QVBoxLayout()

        self.provider_button_group = QButtonGroup(self)
        self.openai_radio = QRadioButton("OpenAI (GPT-4o)")
        self.anthropic_radio = QRadioButton("Anthropic (Claude)")
        self.provider_button_group.addButton(self.openai_radio)
        self.provider_button_group.addButton(self.anthropic_radio)
        self.openai_radio.setChecked(True)

        provider_layout.addWidget(self.openai_radio)
        provider_layout.addWidget(self.anthropic_radio)
        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)

        # OpenAI Settings
        openai_group = QGroupBox("OpenAI Settings")
        openai_layout = QFormLayout()

        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.Password)
        self.openai_key_input.setPlaceholderText("sk-...")
        openai_layout.addRow("API Key:", self.openai_key_input)

        self.openai_show_key = QCheckBox("Show Key")
        self.openai_show_key.toggled.connect(
            lambda checked: self.openai_key_input.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        openai_layout.addRow("", self.openai_show_key)

        openai_group.setLayout(openai_layout)
        layout.addWidget(openai_group)

        # Anthropic Settings
        anthropic_group = QGroupBox("Anthropic Settings")
        anthropic_layout = QFormLayout()

        self.anthropic_key_input = QLineEdit()
        self.anthropic_key_input.setEchoMode(QLineEdit.Password)
        self.anthropic_key_input.setPlaceholderText("sk-ant-...")
        anthropic_layout.addRow("API Key:", self.anthropic_key_input)

        self.anthropic_show_key = QCheckBox("Show Key")
        self.anthropic_show_key.toggled.connect(
            lambda checked: self.anthropic_key_input.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        anthropic_layout.addRow("", self.anthropic_show_key)

        anthropic_group.setLayout(anthropic_layout)
        layout.addWidget(anthropic_group)
        
        # Box Settings - Developer Token (Quick Testing)
        box_dev_group = QGroupBox("Box API - Developer Token (Quick Testing)")
        box_dev_layout = QFormLayout()
        
        self.box_developer_token_input = QLineEdit()
        self.box_developer_token_input.setEchoMode(QLineEdit.Password)
        self.box_developer_token_input.setPlaceholderText("Developer token from Box Developer Console")
        box_dev_layout.addRow("Developer Token:", self.box_developer_token_input)
        
        self.box_show_dev_token = QCheckBox("Show Token")
        self.box_show_dev_token.toggled.connect(
            lambda checked: self.box_developer_token_input.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        box_dev_layout.addRow("", self.box_show_dev_token)
        
        # Help text for developer token
        box_dev_help_label = QLabel(
            "<i><b>Quick Testing:</b> Get a developer token from Box Developer Console → Your App → Configuration → Developer Token. "
            "Valid for 60 minutes. No Enterprise account needed. "
            "<b>If set, this takes priority over CCG credentials below.</b></i>"
        )
        box_dev_help_label.setWordWrap(True)
        box_dev_help_label.setStyleSheet("color: gray; font-size: 10px;")
        box_dev_layout.addRow("", box_dev_help_label)
        
        box_dev_group.setLayout(box_dev_layout)
        layout.addWidget(box_dev_group)
        
        # Box Settings (CCG Authentication)
        box_group = QGroupBox("Box API Settings (Client Credentials Grant - Production)")
        box_layout = QFormLayout()
        
        self.box_client_id_input = QLineEdit()
        self.box_client_id_input.setPlaceholderText("Your Box application Client ID")
        box_layout.addRow("Client ID:", self.box_client_id_input)
        
        self.box_client_secret_input = QLineEdit()
        self.box_client_secret_input.setEchoMode(QLineEdit.Password)
        self.box_client_secret_input.setPlaceholderText("Your Box application Client Secret")
        box_layout.addRow("Client Secret:", self.box_client_secret_input)
        
        self.box_enterprise_id_input = QLineEdit()
        self.box_enterprise_id_input.setPlaceholderText("Enterprise ID (for service account auth)")
        box_layout.addRow("Enterprise ID:", self.box_enterprise_id_input)
        
        self.box_user_id_input = QLineEdit()
        self.box_user_id_input.setPlaceholderText("User ID (optional, for user-level auth)")
        box_layout.addRow("User ID:", self.box_user_id_input)
        
        # Help text
        box_help_label = QLabel(
            "<i>Use Enterprise ID for service account authentication, "
            "or User ID for user-level authentication. "
            "Enterprise ID takes precedence if both are provided.</i>"
        )
        box_help_label.setWordWrap(True)
        box_help_label.setStyleSheet("color: gray; font-size: 10px;")
        box_layout.addRow("", box_help_label)
        
        self.box_show_secret = QCheckBox("Show Secret")
        self.box_show_secret.toggled.connect(
            lambda checked: self.box_client_secret_input.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        box_layout.addRow("", self.box_show_secret)
        
        box_group.setLayout(box_layout)
        layout.addWidget(box_group)
        
        # AWS Settings
        aws_group = QGroupBox("AWS Settings")
        aws_layout = QFormLayout()
        
        self.aws_access_key_input = QLineEdit()
        self.aws_access_key_input.setEchoMode(QLineEdit.Password)
        self.aws_access_key_input.setPlaceholderText("AKIA...")
        aws_layout.addRow("Access Key ID:", self.aws_access_key_input)
        
        self.aws_secret_key_input = QLineEdit()
        self.aws_secret_key_input.setEchoMode(QLineEdit.Password)
        aws_layout.addRow("Secret Access Key:", self.aws_secret_key_input)
        
        self.aws_region_input = QLineEdit()
        self.aws_region_input.setPlaceholderText("us-east-1")
        aws_layout.addRow("Region:", self.aws_region_input)
        
        self.aws_s3_bucket_input = QLineEdit()
        self.aws_s3_bucket_input.setPlaceholderText("my-bucket-name")
        aws_layout.addRow("S3 Bucket:", self.aws_s3_bucket_input)
        
        self.aws_rds_host_input = QLineEdit()
        self.aws_rds_host_input.setPlaceholderText("mydb.xxxxx.us-east-1.rds.amazonaws.com")
        aws_layout.addRow("RDS Host:", self.aws_rds_host_input)
        
        self.aws_show_keys = QCheckBox("Show Keys")
        self.aws_show_keys.toggled.connect(self._toggle_aws_visibility)
        aws_layout.addRow("", self.aws_show_keys)
        
        aws_group.setLayout(aws_layout)
        layout.addWidget(aws_group)
        
        # Output Settings
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout()
        
        self.output_folder_input = QLineEdit()
        self.output_folder_input.setPlaceholderText("Output folder for Excel/CSV files")
        self.output_folder_input.setText(self.config.get("output_folder", "output_csv"))
        output_layout.addRow("Output Folder:", self.output_folder_input)
        
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self._browse_output_folder)
        output_layout.addRow("", output_browse_btn)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # PDF Processing Settings
        pdf_group = QGroupBox("PDF Processing Settings")
        pdf_layout = QFormLayout()
        
        self.process_all_pages_checkbox = QCheckBox("Send ALL pages as images to AI")
        self.process_all_pages_checkbox.setChecked(self.config.get("process_all_pages", False))
        self.process_all_pages_checkbox.toggled.connect(self._toggle_max_pages_visibility)
        pdf_layout.addRow("", self.process_all_pages_checkbox)
        
        # Max pages spinbox (only relevant when not processing all)
        max_pages_layout = QHBoxLayout()
        self.max_vision_pages_spinbox = QSpinBox()
        self.max_vision_pages_spinbox.setMinimum(1)
        self.max_vision_pages_spinbox.setMaximum(100)
        self.max_vision_pages_spinbox.setValue(self.config.get("max_vision_pages", 10))
        self.max_vision_pages_spinbox.setEnabled(not self.config.get("process_all_pages", False))
        max_pages_layout.addWidget(self.max_vision_pages_spinbox)
        max_pages_layout.addStretch()
        pdf_layout.addRow("Max pages to process:", max_pages_layout)
        
        # Help text
        pdf_help_label = QLabel(
            "<i>Pages with tables/images are automatically detected and prioritized. "
            "Processing all pages costs ~1 cent extra per document (low detail mode). "
            "Useful for complex documents with tables throughout.</i>"
        )
        pdf_help_label.setWordWrap(True)
        pdf_help_label.setStyleSheet("color: gray; font-size: 10px;")
        pdf_layout.addRow("", pdf_help_label)
        
        pdf_group.setLayout(pdf_layout)
        layout.addWidget(pdf_group)
        
        # Save Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("Save Settings")
        save_btn.setMinimumWidth(150)
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)
        
        test_btn = QPushButton("Test Connections")
        test_btn.setMinimumWidth(150)
        test_btn.clicked.connect(self._test_connections)
        button_layout.addWidget(test_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Add stretch at the end to push content to top
        layout.addStretch()
        
        # Set the content widget on scroll area
        scroll_area.setWidget(content_widget)
        
        # Add scroll area to main layout
        main_layout.addWidget(scroll_area)
    
    def _toggle_aws_visibility(self, checked: bool):
        """Toggle visibility of AWS secret keys."""
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.aws_access_key_input.setEchoMode(mode)
        self.aws_secret_key_input.setEchoMode(mode)
    
    def _toggle_max_pages_visibility(self, checked: bool):
        """Enable/disable max pages spinbox based on 'process all pages' checkbox."""
        self.max_vision_pages_spinbox.setEnabled(not checked)
    
    def _browse_output_folder(self):
        """Open folder dialog to select output folder."""
        from PyQt5.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder_input.setText(folder)
    
    def _load_config(self) -> dict:
        """Load config from JSON file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_config(self):
        """Save config to JSON file, preserving other settings."""
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
    
    def _load_credentials(self):
        """Load credentials from keyring."""
        try:
            # AI Provider selection
            ai_provider = self.config.get("ai_provider", "openai")
            if ai_provider == "anthropic":
                self.anthropic_radio.setChecked(True)
            else:
                self.openai_radio.setChecked(True)

            # OpenAI
            openai_key = keyring.get_password(KEYRING_SERVICE, "openai_api_key")
            if openai_key:
                self.openai_key_input.setText(openai_key)

            # Anthropic
            anthropic_key = keyring.get_password(KEYRING_SERVICE, "anthropic_api_key")
            if anthropic_key:
                self.anthropic_key_input.setText(anthropic_key)
            
            # Box Developer Token
            box_developer_token = keyring.get_password(KEYRING_SERVICE, "box_developer_token")
            if box_developer_token:
                self.box_developer_token_input.setText(box_developer_token)
            
            # Box CCG credentials
            box_client_id = keyring.get_password(KEYRING_SERVICE, "box_client_id")
            if box_client_id:
                self.box_client_id_input.setText(box_client_id)
            
            box_client_secret = keyring.get_password(KEYRING_SERVICE, "box_client_secret")
            if box_client_secret:
                self.box_client_secret_input.setText(box_client_secret)
            
            # Box IDs (stored in config, not keyring - not as sensitive)
            box_enterprise_id = self.config.get("box_enterprise_id", "")
            self.box_enterprise_id_input.setText(box_enterprise_id)
            
            box_user_id = self.config.get("box_user_id", "")
            self.box_user_id_input.setText(box_user_id)
            
            # AWS
            aws_access = keyring.get_password(KEYRING_SERVICE, "aws_access_key")
            if aws_access:
                self.aws_access_key_input.setText(aws_access)
            
            aws_secret = keyring.get_password(KEYRING_SERVICE, "aws_secret_key")
            if aws_secret:
                self.aws_secret_key_input.setText(aws_secret)
            
            aws_region = self.config.get("aws_region", "")
            self.aws_region_input.setText(aws_region)
            
            aws_bucket = self.config.get("aws_s3_bucket", "")
            self.aws_s3_bucket_input.setText(aws_bucket)
            
            aws_rds = self.config.get("aws_rds_host", "")
            self.aws_rds_host_input.setText(aws_rds)
            
        except Exception as e:
            logger.error(f"Error loading credentials from keyring: {e}")
    
    def _save_settings(self):
        """Save all settings to keyring and config file."""
        try:
            # Save AI provider selection
            self.config["ai_provider"] = "anthropic" if self.anthropic_radio.isChecked() else "openai"

            # Save to keyring (sensitive data)
            if self.openai_key_input.text():
                keyring.set_password(KEYRING_SERVICE, "openai_api_key",
                                    self.openai_key_input.text())

            if self.anthropic_key_input.text():
                keyring.set_password(KEYRING_SERVICE, "anthropic_api_key",
                                    self.anthropic_key_input.text())
            
            # Box Developer Token (sensitive)
            if self.box_developer_token_input.text():
                keyring.set_password(KEYRING_SERVICE, "box_developer_token",
                                    self.box_developer_token_input.text())
            else:
                # Clear the developer token if field is empty
                try:
                    keyring.delete_password(KEYRING_SERVICE, "box_developer_token")
                except keyring.errors.PasswordDeleteError:
                    pass  # Token wasn't set
            
            # Box CCG credentials (sensitive)
            if self.box_client_id_input.text():
                keyring.set_password(KEYRING_SERVICE, "box_client_id",
                                    self.box_client_id_input.text())
            
            if self.box_client_secret_input.text():
                keyring.set_password(KEYRING_SERVICE, "box_client_secret",
                                    self.box_client_secret_input.text())
            
            if self.aws_access_key_input.text():
                keyring.set_password(KEYRING_SERVICE, "aws_access_key",
                                    self.aws_access_key_input.text())
            
            if self.aws_secret_key_input.text():
                keyring.set_password(KEYRING_SERVICE, "aws_secret_key",
                                    self.aws_secret_key_input.text())
            
            # Save to config file (non-sensitive data)
            self.config["box_enterprise_id"] = self.box_enterprise_id_input.text()
            self.config["box_user_id"] = self.box_user_id_input.text()
            self.config["aws_region"] = self.aws_region_input.text()
            self.config["aws_s3_bucket"] = self.aws_s3_bucket_input.text()
            self.config["aws_rds_host"] = self.aws_rds_host_input.text()
            self.config["output_folder"] = self.output_folder_input.text()
            
            # PDF Processing settings
            self.config["process_all_pages"] = self.process_all_pages_checkbox.isChecked()
            self.config["max_vision_pages"] = self.max_vision_pages_spinbox.value()
            
            self._save_config()
            
            self.settings_changed.emit()
            
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
    
    def _test_connections(self):
        """Test API connections."""
        results = []

        # Test OpenAI
        if self.openai_key_input.text():
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_key_input.text())
                client.models.list()
                results.append("[OK] OpenAI: Connected")
            except Exception as e:
                results.append(f"[FAIL] OpenAI: {str(e)[:50]}")
        else:
            results.append("[--] OpenAI: No API key configured")

        # Test Anthropic
        if self.anthropic_key_input.text():
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key_input.text())
                client.models.list()
                results.append("[OK] Anthropic: Connected")
            except Exception as e:
                results.append(f"[FAIL] Anthropic: {str(e)[:50]}")
        else:
            results.append("[--] Anthropic: No API key configured")
        
        # Test Box connection (Developer Token takes priority)
        box_developer_token = self.box_developer_token_input.text()
        box_client_id = self.box_client_id_input.text()
        box_client_secret = self.box_client_secret_input.text()
        box_enterprise_id = self.box_enterprise_id_input.text()
        box_user_id = self.box_user_id_input.text()
        
        if box_developer_token:
            # Test with developer token
            try:
                from boxAPI import BoxAPI
                box_api = BoxAPI(developer_token=box_developer_token)
                results.append("[OK] Box: Connected with Developer Token")
            except Exception as e:
                results.append(f"[FAIL] Box (Developer Token): {str(e)[:50]}")
        elif box_client_id and box_client_secret and (box_enterprise_id or box_user_id):
            try:
                from boxAPI import BoxAPI
                box_api = BoxAPI(
                    client_id=box_client_id,
                    client_secret=box_client_secret,
                    enterprise_id=box_enterprise_id if box_enterprise_id else None,
                    user_id=box_user_id if box_user_id else None
                )
                results.append("[OK] Box: Connected with CCG credentials")
            except Exception as e:
                results.append(f"[FAIL] Box (CCG): {str(e)[:50]}")
        elif box_client_id or box_client_secret:
            results.append("[--] Box: Incomplete CCG credentials (need Client ID, Secret, and Enterprise/User ID)")
        else:
            results.append("[--] Box: Not configured (add Developer Token or CCG credentials)")
        
        # AWS test would require actual credentials
        if self.aws_access_key_input.text() and self.aws_secret_key_input.text():
            results.append("[--] AWS: Credentials configured (not tested)")
        else:
            results.append("[--] AWS: Not configured")
        
        QMessageBox.information(self, "Connection Test Results", "\n".join(results))
    
    def get_openai_key(self) -> str:
        """Get the OpenAI API key."""
        return self.openai_key_input.text()

    def get_anthropic_key(self) -> str:
        """Get the Anthropic API key."""
        return self.anthropic_key_input.text()

    def get_ai_provider(self) -> str:
        """Get the selected AI provider ('openai' or 'anthropic')."""
        return "anthropic" if self.anthropic_radio.isChecked() else "openai"
    
    def get_box_credentials(self) -> dict:
        """
        Get Box credentials (Developer Token or CCG).
        
        Returns:
            Dictionary with developer_token, client_id, client_secret, enterprise_id, user_id
        """
        return {
            "developer_token": self.box_developer_token_input.text() or None,
            "client_id": self.box_client_id_input.text(),
            "client_secret": self.box_client_secret_input.text(),
            "enterprise_id": self.box_enterprise_id_input.text() or None,
            "user_id": self.box_user_id_input.text() or None
        }
    
    def get_box_config_path(self) -> str:
        """
        Legacy method - returns empty string since we no longer use config file.
        Kept for backward compatibility.
        """
        return ""
    
    def get_output_folder(self) -> str:
        """Get the output folder path."""
        return self.output_folder_input.text() or "output_csv"
    
    def get_process_all_pages(self) -> bool:
        """Get whether to process all PDF pages."""
        return self.process_all_pages_checkbox.isChecked()
    
    def get_max_vision_pages(self) -> int:
        """Get the maximum number of pages to process (when not processing all)."""
        return self.max_vision_pages_spinbox.value()
    
    def get_pdf_settings(self) -> dict:
        """Get all PDF processing settings."""
        return {
            "process_all_pages": self.get_process_all_pages(),
            "max_vision_pages": self.get_max_vision_pages()
        }
