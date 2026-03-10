"""Unit tests for SessionManager."""

import pytest
from unittest.mock import MagicMock, patch

from handsome_transcribe.ui.session_manager import SessionManager
from handsome_transcribe.ui.models import SessionState
from handsome_transcribe.ui.exceptions import ActiveSessionError, SessionError


class TestSessionManager:
    """Tests for SessionManager."""

    @pytest.fixture
    def session_manager(self, temp_db, event_bus, speaker_manager, qapp, session_config):
        """Create SessionManager instance for testing."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker"):
            manager = SessionManager(session_config, event_bus, temp_db, speaker_manager)
            yield manager
            if manager._autosave_timer.isActive():
                manager._autosave_timer.stop()

    def test_create_session_manager(self, session_manager):
        """Test creating a SessionManager instance."""
        assert session_manager is not None
        assert session_manager.current_session is None
        assert session_manager.current_state == SessionState.IDLE

    def test_start_session_success(self, session_manager):
        """Test starting a new session successfully."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker"):
            session_data = session_manager.start_session()

        assert session_data is not None
        assert session_manager.current_state == SessionState.RECORDING
        assert session_manager.current_session is not None
        assert session_manager._autosave_timer.isActive()

    def test_start_session_with_active_session(self, session_manager):
        """Test that starting a session while one is active raises error."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker"):
            session_manager.start_session()

        with pytest.raises(ActiveSessionError):
            session_manager.start_session()

    def test_pause_recording(self, session_manager):
        """Test pausing an active recording."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=MagicMock()):
            session_manager.start_session()

        session_manager.pause_recording()

        assert session_manager.current_state == SessionState.PAUSED

    def test_resume_recording(self, session_manager):
        """Test resuming a paused recording."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=MagicMock()):
            session_manager.start_session()

        session_manager.pause_recording()
        session_manager.resume_recording()

        assert session_manager.current_state == SessionState.RECORDING

    def test_stop_recording_starts_transcription(self, session_manager):
        """Test stopping a recording starts transcription stage."""
        recorder = MagicMock()
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=recorder), \
             patch("handsome_transcribe.ui.session_manager.TranscriberWorker"):
            session_manager.start_session()
            session_manager.stop_recording()

        assert session_manager.current_state == SessionState.TRANSCRIBING
        recorder.stop.assert_called_once()
        recorder.save_final.assert_called_once()

    def test_state_transition_validation(self, session_manager):
        """Test invalid operation from IDLE state raises SessionError."""
        with pytest.raises(SessionError):
            session_manager.pause_recording()

    def test_auto_save_timer_starts(self, session_manager):
        """Test that auto-save timer starts when recording starts."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker"):
            session_manager.start_session()

        assert session_manager._autosave_timer.isActive()

    def test_get_current_session(self, session_manager):
        """Test retrieving current session object."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker"):
            session_manager.start_session()

        current = session_manager.get_current_session()
        assert current is not None
        assert current.id > 0

    def test_partial_transcription_uses_sample_audio(
        self,
        temp_db,
        event_bus,
        speaker_manager,
        session_config,
        sample_recording_path,
        tmp_path
    ):
        """Test partial transcription uses the provided recording.wav sample."""
        with patch("handsome_transcribe.ui.session_manager.SESSIONS_DIR", tmp_path / "sessions"), \
             patch("handsome_transcribe.ui.session_manager.REPORTS_DIR", tmp_path / "reports"), \
             patch("handsome_transcribe.ui.session_manager.RecorderWorker"), \
             patch("handsome_transcribe.ui.session_manager.TranscriberWorker") as MockTranscriber:
            manager = SessionManager(session_config, event_bus, temp_db, speaker_manager)
            manager.start_session()

            manager._start_partial_transcription(sample_recording_path)

            assert MockTranscriber.called
            _, kwargs = MockTranscriber.call_args
            assert kwargs["audio_path"] == sample_recording_path
            assert kwargs["emit_progress"] is False
            assert kwargs["emit_complete"] is False
