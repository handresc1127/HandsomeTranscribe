"""
Unit tests for SessionManager.

Tests session lifecycle, state transitions, and auto-save.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QThreadPool

from handsome_transcribe.ui.session_manager import SessionManager
from handsome_transcribe.ui.models import SessionConfig, SessionState
from handsome_transcribe.ui.exceptions import ActiveSessionError, ConfigurationError


class TestSessionManager:
    """Tests for SessionManager."""
    
    @pytest.fixture
    def session_manager(self, temp_db, event_bus, speaker_manager, qapp, session_config):
        """Create SessionManager instance for testing."""
        manager = SessionManager(session_config, event_bus, temp_db, speaker_manager)
        yield manager
        # Cleanup
        if manager.auto_save_timer.isActive():
            manager.auto_save_timer.stop()
    
    def test_create_session_manager(self, session_manager):
        """Test creating a SessionManager instance."""
        assert session_manager is not None
        assert session_manager.session_data is None
        assert session_manager.state == SessionState.IDLE
    
    def test_start_session_success(self, session_manager):
        """Test starting a new session successfully."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=False,
            habilitar_resumen=False
        )
        
        with patch('handsome_transcribe.ui.session_manager.Path.mkdir'):
            session_data = session_manager.start_session(config)
        
        assert session_data is not None
        assert session_manager.state == SessionState.RECORDING
        assert session_manager.session_data is not None
    
    def test_start_session_with_active_session(self, session_manager):
        """Test that starting a session while one is active raises error."""
        config = SessionConfig()
        
        with patch('handsome_transcribe.ui.session_manager.Path.mkdir'):
            session_manager.start_session(config)
        
        # Try to start another session
        with pytest.raises(ActiveSessionError):
            session_manager.start_session(config)
    
    def test_start_session_invalid_config(self, session_manager):
        """Test starting session with invalid configuration."""
        # Config with diarization but no HF token
        invalid_config = SessionConfig(
            modelo_whisper="invalid",
            habilitar_diarizacion=True,
            hf_token=None
        )
        
        with pytest.raises(ConfigurationError):
            session_manager.start_session(invalid_config)
    
    def test_pause_recording(self, session_manager):
        """Test pausing an active recording."""
        config = SessionConfig()
        
        with patch('handsome_transcribe.ui.session_manager.Path.mkdir'):
            session_manager.start_session(config)
        
        session_manager.pause_recording()
        
        assert session_manager.state == SessionState.PAUSED
    
    def test_resume_recording(self, session_manager):
        """Test resuming a paused recording."""
        config = SessionConfig()
        
        with patch('handsome_transcribe.ui.session_manager.Path.mkdir'):
            session_manager.start_session(config)
        
        session_manager.pause_recording()
        session_manager.resume_recording()
        
        assert session_manager.state == SessionState.RECORDING
    
    def test_stop_recording(self, session_manager):
        """Test stopping a recording."""
        config = SessionConfig()
        
        with patch('handsome_transcribe.ui.session_manager.Path.mkdir'):
            session_manager.start_session(config)
        
        with patch.object(session_manager, '_start_transcription_pipeline'):
            session_manager.stop_recording()
        
        # Should transition to transcribing
        assert session_manager.state == SessionState.TRANSCRIBING
    
    def test_state_transition_validation(self, session_manager):
        """Test that invalid state transitions are rejected."""
        # Can't pause when idle
        with pytest.raises(ValueError):
            session_manager.pause_recording()
    
    def test_auto_save_timer_starts(self, session_manager):
        """Test that auto-save timer starts when recording."""
        config = SessionConfig()
        
        with patch('handsome_transcribe.ui.session_manager.Path.mkdir'):
            session_manager.start_session(config)
        
        assert session_manager.auto_save_timer.isActive()
    
    def test_auto_save_timer_stops(self, session_manager):
        """Test that auto-save timer stops when recording ends."""
        config = SessionConfig()
        
        with patch('handsome_transcribe.ui.session_manager.Path.mkdir'):
            session_manager.start_session(config)
        
        session_manager.pause_recording()
        
        assert not session_manager.auto_save_timer.isActive()
    
    def test_get_session_info(self, session_manager):
        """Test retrieving session information."""
        config = SessionConfig()
        
        with patch('handsome_transcribe.ui.session_manager.Path.mkdir'):
            session_manager.start_session(config)
        
        info = session_manager.get_session_info()
        
        assert info is not None
        assert "id" in info
        assert "state" in info
        assert "created_at" in info
