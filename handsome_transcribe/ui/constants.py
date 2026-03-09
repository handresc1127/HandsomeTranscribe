"""
Constants for the UI layer.
"""

from pathlib import Path

# Directory Constants
OUTPUTS_BASE_DIR = Path("outputs")
SESSIONS_DIR = OUTPUTS_BASE_DIR / "sessions"
REPORTS_DIR = OUTPUTS_BASE_DIR / "reports"
AUDIO_DIR_LEGACY = OUTPUTS_BASE_DIR / "audio"  # DEPRECATED

# Session Directory Structure
SESSION_DIR_FORMAT = "session_{timestamp}"  # timestamp format: YYYYMMDD_HHMMSS
RECORDING_FILENAME = "recording.wav"
TRANSCRIPT_FILENAME = "transcript.txt"
SUMMARY_FILENAME = "summary.md"
METADATA_FILENAME = "metadata.json"
TEMP_DIR_NAME = "temp"
PARTIAL_AUDIO_FORMAT = "part{num}.wav"

# Auto-save Configuration
AUTO_SAVE_INTERVAL_MS = 120000  # 2 minutes in milliseconds
AUTO_SAVE_INTERVAL_SEC = 120  # 2 minutes

# Audio Chunking Configuration
AUDIO_CHUNK_DURATION_SEC = 30  # 30 seconds chunks for parallel processing
AUDIO_CHUNK_MIN_DURATION_SEC = 10  # Minimum 10 seconds per chunk

# Speaker Recognition Thresholds
SPEAKER_MATCH_AUTO_THRESHOLD = 0.98  # 98% confidence for auto-identification
SPEAKER_MATCH_REVIEW_THRESHOLD = 0.60  # 60% confidence for manual review

# Database Configuration
DB_FILENAME = "handsome_transcribe.db"
DB_VERSION = 1

# Whisper Models
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
DEFAULT_WHISPER_MODEL = "base"

# UI Configuration
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800

# Color Palette
COLOR_SUCCESS = "#27ae60"
COLOR_ERROR = "#e74c3c"
COLOR_INFO = "#3498db"
COLOR_WARNING = "#f39c12"
COLOR_REVIEW = "#f39c12"

# Fonts
FONT_FAMILY_WINDOWS = "Segoe UI"
FONT_FAMILY_LINUX = "Ubuntu"
FONT_FAMILY_FALLBACK = "Arial"
