"""
HandsomeTranscribe Desktop Application Entry Point

Launches the PySide6 GUI for live transcription and speaker identification.
"""

import os
import shutil
import sys
import logging
import tempfile
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


def ensure_ffmpeg():
    """Ensure ffmpeg is available on PATH.

    Whisper calls ``ffmpeg`` as a subprocess to decode audio.  If the system
    has no ``ffmpeg`` binary, fall back to the one bundled with the
    ``imageio-ffmpeg`` package (if installed) by creating a shim directory.
    """
    if shutil.which("ffmpeg"):
        return  # Already available
    try:
        import imageio_ffmpeg
        src = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        logger.warning(
            "ffmpeg not found on PATH and imageio-ffmpeg not installed. "
            "Whisper transcription will fail. Install ffmpeg or run: "
            "pip install imageio-ffmpeg"
        )
        return

    tmpdir = tempfile.mkdtemp(prefix="ht_ffmpeg_")
    dst_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    dst = os.path.join(tmpdir, dst_name)
    shutil.copy2(src, dst)
    os.environ["PATH"] = tmpdir + os.pathsep + os.environ.get("PATH", "")
    logger.info(f"ffmpeg shimmed from imageio-ffmpeg: {dst}")


def main():
    """Main entry point for HandsomeTranscribe desktop app."""
    try:
        # Ensure ffmpeg is available for Whisper
        ensure_ffmpeg()

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
