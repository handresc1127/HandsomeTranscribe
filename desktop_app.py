"""
HandsomeTranscribe Desktop Application Entry Point

Launches the PySide6 GUI for live transcription and speaker identification.
"""

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from handsome_transcribe.ui.windows import SessionWindow
from handsome_transcribe.ui.styles import apply_stylesheet
from handsome_transcribe.ui.constants import OUTPUTS_BASE_DIR, SESSIONS_DIR, REPORTS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_directories():
    """Ensure all required output directories exist."""
    try:
        for directory in [OUTPUTS_BASE_DIR, SESSIONS_DIR, REPORTS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured output directories: {SESSIONS_DIR}, {REPORTS_DIR}")
    except Exception as e:
        logger.error(f"Failed to create output directories: {e}")
        raise


def main():
    """Main entry point for HandsomeTranscribe desktop app."""
    try:
        # Ensure output directories
        ensure_directories()
        
        # Create Qt application
        app = QApplication(sys.argv)
        
        # Apply stylesheet (dark theme with HandsomeTranscribe branding)
        apply_stylesheet(app)
        
        # Create and show main window
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
