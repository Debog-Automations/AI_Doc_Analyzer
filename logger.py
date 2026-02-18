"""
Centralized Logging Configuration for AI Document Analyzer

Provides detailed logging to both console and rotating file handlers.
Log files are stored in the 'logs/' directory with automatic rotation.

Usage:
    from logger import get_logger
    logger = get_logger(__name__)
    
    logger.debug("Detailed debug info")
    logger.info("General information")
    logger.warning("Warning message")
    logger.error("Error occurred")
    logger.exception("Error with traceback")
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


# Configuration
LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 5  # Keep 5 backup files
DEFAULT_LOG_LEVEL = logging.DEBUG

# Ensure logs directory exists
LOG_DIR.mkdir(exist_ok=True)

# Custom formatter with detailed information
class DetailedFormatter(logging.Formatter):
    """Custom formatter that includes color coding for console output."""
    
    # ANSI color codes for Windows/Unix console
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[41m',  # Red background
        'RESET': '\033[0m'       # Reset
    }
    
    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
        # Detailed format string
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        super().__init__(fmt=fmt, datefmt=datefmt)
    
    def format(self, record):
        # Save original levelname
        original_levelname = record.levelname
        
        if self.use_colors and sys.stdout.isatty():
            # Add colors for console
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        result = super().format(record)
        
        # Restore original levelname
        record.levelname = original_levelname
        return result


# File formatter (no colors)
class FileFormatter(logging.Formatter):
    """Formatter for log files without color codes."""
    
    def __init__(self):
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        super().__init__(fmt=fmt, datefmt=datefmt)


# Global flag to track if logging is initialized
_logging_initialized = False
_root_logger = None


def setup_logging(
    level: int = DEFAULT_LOG_LEVEL,
    log_to_console: bool = True,
    log_to_file: bool = True,
    log_file: Path = LOG_FILE
) -> logging.Logger:
    """
    Initialize the logging system.
    
    Args:
        level: Logging level (logging.DEBUG, logging.INFO, etc.)
        log_to_console: Whether to output logs to console
        log_to_file: Whether to output logs to file
        log_file: Path to the log file
        
    Returns:
        The root logger instance
    """
    global _logging_initialized, _root_logger
    
    if _logging_initialized:
        return _root_logger
    
    # Get the root logger for our application
    root_logger = logging.getLogger("AI_Doc_Analyzer")
    root_logger.setLevel(level)
    
    # Remove any existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(DetailedFormatter(use_colors=True))
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_to_file:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(FileFormatter())
        root_logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    root_logger.propagate = False
    
    _logging_initialized = True
    _root_logger = root_logger
    
    # Log startup message
    root_logger.info("=" * 60)
    root_logger.info(f"AI Document Analyzer - Logging initialized")
    root_logger.info(f"Log level: {logging.getLevelName(level)}")
    root_logger.info(f"Log file: {log_file}")
    root_logger.info("=" * 60)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Usually __name__ of the calling module
        
    Returns:
        Logger instance configured as a child of the root logger
        
    Usage:
        from logger import get_logger
        logger = get_logger(__name__)
        logger.info("This is a log message")
    """
    global _logging_initialized
    
    # Initialize logging if not already done
    if not _logging_initialized:
        setup_logging()
    
    # Create child logger under our application namespace
    if name.startswith("AI_Doc_Analyzer"):
        return logging.getLogger(name)
    else:
        # Prefix with our namespace for consistent hierarchy
        return logging.getLogger(f"AI_Doc_Analyzer.{name}")


def set_log_level(level: int):
    """
    Change the log level at runtime.
    
    Args:
        level: New logging level (e.g., logging.DEBUG, logging.INFO)
    """
    global _root_logger
    
    if _root_logger:
        _root_logger.setLevel(level)
        for handler in _root_logger.handlers:
            handler.setLevel(level)
        _root_logger.info(f"Log level changed to: {logging.getLevelName(level)}")


def get_log_file_path() -> Path:
    """Get the path to the current log file."""
    return LOG_FILE


def get_recent_logs(lines: int = 100) -> str:
    """
    Read the most recent log entries.
    
    Args:
        lines: Number of lines to read from the end of the log file
        
    Returns:
        String containing the recent log entries
    """
    if not LOG_FILE.exists():
        return "No log file found."
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return ''.join(recent)
    except Exception as e:
        return f"Error reading log file: {e}"


# Convenience function for logging exceptions with full traceback
def log_exception(logger: logging.Logger, message: str, exc: Exception):
    """
    Log an exception with full traceback.
    
    Args:
        logger: Logger instance to use
        message: Context message about what was happening
        exc: The exception that was caught
    """
    logger.exception(f"{message}: {type(exc).__name__}: {exc}")


