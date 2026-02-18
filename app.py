"""
AI Document Analyzer - Desktop Application

Main entry point for the PyQt5 desktop application.

Usage:
    python app.py
"""

import sys
import os
import logging

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Initialize logging BEFORE importing other modules
from logger import setup_logging, get_logger

# Setup logging with DEBUG level for detailed output
setup_logging(level=logging.DEBUG)
logger = get_logger(__name__)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui import MainWindow


def main():
    """Main application entry point."""
    logger.info("Starting AI Document Analyzer application")
    
    try:
        # Enable high DPI scaling
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("AI Document Analyzer")
        app.setOrganizationName("AI Doc Analyzer")
        app.setApplicationVersion("1.0.0")
        logger.debug("QApplication created successfully")
        
        # Set default font
        font = QFont("Segoe UI", 10)
        app.setFont(font)
        
        # Create and show main window
        logger.debug("Creating main window")
        window = MainWindow()
        window.show()
        logger.info("Main window displayed")
        
        # Run application
        logger.info("Entering application event loop")
        exit_code = app.exec_()
        logger.info(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.exception(f"Fatal error in main application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

