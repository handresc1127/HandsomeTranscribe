"""
Pytest configuration and fixtures for UI tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication

from handsome_transcribe.ui.database import Database
from handsome_transcribe.ui.event_bus import EventBus
from handsome_transcribe.ui.speaker_manager import SpeakerManager
from handsome_transcribe.ui.config_manager import ConfigManager
from handsome_transcribe.ui.models import SessionConfig


@pytest.fixture(scope="session")
def qapp():
    """
    Create QApplication instance for tests.
    
    This is needed for any PySide6/Qt functionality.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def temp_db():
    """
    Create a temporary database for testing.
    
    Yields:
        Database instance with temporary file
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    db = Database(db_path)
    yield db
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def event_bus(qapp):
    """
    Create EventBus instance for testing.
    
    Args:
        qapp: QApplication fixture
        
    Yields:
        EventBus instance
    """
    bus = EventBus()
    yield bus


@pytest.fixture
def speaker_manager(temp_db):
    """
    Create SpeakerManager instance for testing.
    
    Args:
        temp_db: Temporary database fixture
        
    Yields:
        SpeakerManager instance
    """
    manager = SpeakerManager(temp_db)
    yield manager


@pytest.fixture
def session_config():
    """
    Create a default SessionConfig for testing.
    
    Yields:
        SessionConfig instance
    """
    config = SessionConfig(
        modelo_whisper="base",
        habilitar_diarizacion=False,
        habilitar_resumen=False,
        dispositivo_audio=None,
        hf_token=None
    )
    yield config


@pytest.fixture
def config_manager(qapp):
    """
    Create ConfigManager instance for testing.
    
    Args:
        qapp: QApplication fixture
        
    Yields:
        ConfigManager instance
    """
    manager = ConfigManager()
    # Clear any existing settings
    manager.clear_settings()
    yield manager
    # Cleanup
    manager.clear_settings()


@pytest.fixture
def sample_recording_path(tmp_path: Path) -> Path:
    """Copy a real recording.wav into a temp path for unit tests."""
    source = Path("outputs/sessions/session_20260309_233252/recording.wav")
    if not source.exists():
        pytest.skip("Sample recording.wav not found in outputs/sessions")

    dest = tmp_path / "recording.wav"
    shutil.copyfile(source, dest)
    return dest
