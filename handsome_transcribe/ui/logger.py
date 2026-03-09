"""
Logging configuration for HandsomeTranscribe Desktop.

Provides centralized logging for UI components, backend services, and workers.
Logs to both console (INFO+) and file (DEBUG+) with rotation.
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional


class AppLogger:
    """
    Application-wide logger with console and file handlers.
    
    Features:
    - Console logging (INFO level, colored output)
    - File logging (DEBUG level, rotated daily)
    - Separate loggers for UI, backend, workers
    - Automatically creates logs directory
    """
    
    _instance: Optional['AppLogger'] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not AppLogger._initialized:
            self._setup_logging()
            AppLogger._initialized = True
    
    def _setup_logging(self):
        """Configure logging with console and file handlers."""
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Log file path with date
        log_file = logs_dir / f"handsome_transcribe_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Root logger configuration
        root_logger = logging.getLogger("handsome_transcribe")
        root_logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers (prevent duplicates)
        root_logger.handlers.clear()
        
        # Console handler (INFO+)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler (DEBUG+) with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)-8s] %(name)-30s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Log startup
        root_logger.info("=" * 80)
        root_logger.info("HandsomeTranscribe Desktop - Logging initialized")
        root_logger.info(f"Log file: {log_file}")
        root_logger.info("=" * 80)
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get a logger instance for a specific component.
        
        Args:
            name: Logger name (e.g., 'ui.session_window', 'backend.transcription')
        
        Returns:
            Logger instance under 'handsome_transcribe' namespace
        """
        # Ensure AppLogger is initialized
        AppLogger()
        
        # Create namespaced logger
        full_name = f"handsome_transcribe.{name}"
        return logging.getLogger(full_name)


# Convenience function for getting loggers
def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a component.
    
    Usage:
        from handsome_transcribe.ui.logger import get_logger
        logger = get_logger('ui.panels.results')
        logger.info("ResultsPanel initialized")
    
    Args:
        name: Component name (e.g., 'ui.session_window', 'workers.transcription')
    
    Returns:
        Logger instance
    """
    return AppLogger.get_logger(name)


# Initialize logging on module import
AppLogger()
