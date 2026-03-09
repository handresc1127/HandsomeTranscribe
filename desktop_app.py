"""
Desktop application entry point for HandsomeTranscribe.

Launches the main SessionWindow with all UI components.
"""

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from handsome_transcribe.ui.windows import SessionWindow
from handsome_transcribe.ui.constants import SESSIONS_DIR, REPORTS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_directories():
    """Ensure required output directories exist."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured directories: {SESSIONS_DIR}, {REPORTS_DIR}")


def setup_application_style():
    """Configure application-wide styling."""
    # Placeholder for future styling
    pass


def main():
    """Main entry point for desktop application."""
    # Ensure directories exist
    ensure_directories()
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Setup styling
    setup_application_style()
    
    # Create and show main window
    try:
        window = SessionWindow()
        window.show()
        logger.info("HandsomeTranscribe desktop application started")
        
        # Run event loop
        sys.exit(app.exec())
    
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
