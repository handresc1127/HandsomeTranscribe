"""Unit tests for SessionManager error handling."""

import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from handsome_transcribe.ui.session_manager import SessionManager
from handsome_transcribe.ui.models import SessionState, SessionConfig
from handsome_transcribe.ui.exceptions import SessionError


def _make_manager(config, event_bus, temp_db, speaker_manager):
    """Helper to create a SessionManager with mocked RecorderWorker."""
    with patch("handsome_transcribe.ui.session_manager.RecorderWorker"):
        manager = SessionManager(config, event_bus, temp_db, speaker_manager)
    return manager


def _cleanup(manager):
    if manager._autosave_timer.isActive():
        manager._autosave_timer.stop()


@pytest.fixture
def transcribing_manager(temp_db, event_bus, speaker_manager, qapp, session_config):
    """SessionManager in TRANSCRIBING state with error signal connected."""
    manager = _make_manager(session_config, event_bus, temp_db, speaker_manager)
    recorder = MagicMock()
    recorder.save_final = MagicMock()
    with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=recorder), \
         patch("handsome_transcribe.ui.session_manager.TranscriberWorker"):
        manager.start_session()
        manager.stop_recording()
    yield manager
    _cleanup(manager)


class TestTranscriptionErrorHandling:
    """Tests for transcription error signal handling."""

    def test_transcription_error_transitions_to_error_state(
        self, transcribing_manager, event_bus, qapp
    ):
        """transcription_error signal transitions SessionManager to ERROR state."""
        assert transcribing_manager.current_state == SessionState.TRANSCRIBING

        event_bus.transcription_error.emit("Whisper failed")
        QApplication.processEvents()

        assert transcribing_manager.current_state == SessionState.ERROR

    def test_error_handler_disconnects_signals(
        self, transcribing_manager, event_bus, qapp
    ):
        """After transcription error fires, error and success signals are disconnected."""
        assert transcribing_manager.current_state == SessionState.TRANSCRIBING

        # First error transitions to ERROR
        event_bus.transcription_error.emit("First error")
        QApplication.processEvents()
        assert transcribing_manager.current_state == SessionState.ERROR

        # Transition back to IDLE manually
        transcribing_manager._transition_state(SessionState.IDLE)

        # Second emission should NOT re-trigger the handler (already disconnected)
        # If handler fired again it would try ERROR->ERROR which would raise SessionError
        # and be caught by the fallback assignment — but the key check is state == IDLE
        event_bus.transcription_error.emit("Second error")
        QApplication.processEvents()

        assert transcribing_manager.current_state == SessionState.IDLE


class TestDiarizationErrorHandling:
    """Tests for diarization error signal handling."""

    def test_diarization_error_transitions_to_error_state(
        self, temp_db, event_bus, speaker_manager, qapp
    ):
        """session_error('diarization') transitions SessionManager to ERROR state."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=True,
            habilitar_resumen=False,
            dispositivo_audio=None,
            hf_token="fake-token",
        )
        manager = _make_manager(config, event_bus, temp_db, speaker_manager)
        try:
            recorder = MagicMock()
            recorder.save_final = MagicMock()
            with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=recorder), \
                 patch("handsome_transcribe.ui.session_manager.TranscriberWorker"), \
                 patch("handsome_transcribe.ui.session_manager.DiarizerWorker"):
                manager.start_session()
                manager.stop_recording()
                # Advance pipeline past transcription into diarization
                manager._on_transcription_complete(MagicMock())

            assert manager.current_state == SessionState.DIARIZING

            event_bus.session_error.emit("Diarization failed", "diarization")
            QApplication.processEvents()

            assert manager.current_state == SessionState.ERROR
        finally:
            _cleanup(manager)

    def test_session_error_wrong_stage_ignored(
        self, temp_db, event_bus, speaker_manager, qapp
    ):
        """session_error with a stage tag other than 'diarization' is ignored during diarization."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=True,
            habilitar_resumen=False,
            dispositivo_audio=None,
            hf_token="fake-token",
        )
        manager = _make_manager(config, event_bus, temp_db, speaker_manager)
        try:
            recorder = MagicMock()
            recorder.save_final = MagicMock()
            with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=recorder), \
                 patch("handsome_transcribe.ui.session_manager.TranscriberWorker"), \
                 patch("handsome_transcribe.ui.session_manager.DiarizerWorker"):
                manager.start_session()
                manager.stop_recording()
                manager._on_transcription_complete(MagicMock())

            assert manager.current_state == SessionState.DIARIZING

            # Emit session_error with unrelated stage — should be ignored
            event_bus.session_error.emit("Some unrelated error", "unrelated_stage")
            QApplication.processEvents()

            # State must remain DIARIZING
            assert manager.current_state == SessionState.DIARIZING
        finally:
            _cleanup(manager)

    def test_diarization_skip_does_not_trigger_error(
        self, temp_db, event_bus, speaker_manager, qapp
    ):
        """When diarization is enabled but HF token is missing, pipeline skips gracefully."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=True,
            habilitar_resumen=False,
            dispositivo_audio=None,
            hf_token=None,  # missing -> benign skip
        )
        manager = _make_manager(config, event_bus, temp_db, speaker_manager)
        try:
            recorder = MagicMock()
            recorder.save_final = MagicMock()
            with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=recorder), \
                 patch("handsome_transcribe.ui.session_manager.TranscriberWorker"), \
                 patch("handsome_transcribe.ui.session_manager.ReporterWorker"):
                manager.start_session()
                manager.stop_recording()
                # _on_transcription_complete -> _start_diarization (benign skip) -> _start_reporting
                manager._on_transcription_complete(MagicMock())

            QApplication.processEvents()

            # Must NOT be ERROR — the benign session_error emitted before the wrapper was connected
            assert manager.current_state != SessionState.ERROR
        finally:
            _cleanup(manager)


class TestSummarizationErrorHandling:
    """Tests for summarization error signal handling."""

    def test_summarization_error_transitions_to_error_state(
        self, temp_db, event_bus, speaker_manager, qapp
    ):
        """session_error('summarization') transitions SessionManager to ERROR state."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=False,
            habilitar_resumen=True,
            dispositivo_audio=None,
            hf_token=None,
        )
        manager = _make_manager(config, event_bus, temp_db, speaker_manager)
        try:
            recorder = MagicMock()
            recorder.save_final = MagicMock()
            with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=recorder), \
                 patch("handsome_transcribe.ui.session_manager.TranscriberWorker"), \
                 patch("handsome_transcribe.ui.session_manager.SummarizerWorker"):
                manager.start_session()
                manager.stop_recording()
                # Advance: transcription done -> skip diarization -> start summarization
                manager._on_transcription_complete(MagicMock())

            assert manager.current_state == SessionState.SUMMARIZING

            event_bus.session_error.emit("Summarization failed", "summarization")
            QApplication.processEvents()

            assert manager.current_state == SessionState.ERROR
        finally:
            _cleanup(manager)


class TestReportingErrorHandling:
    """Tests for reporting error signal handling."""

    def test_reporting_error_transitions_to_error_state(
        self, temp_db, event_bus, speaker_manager, qapp
    ):
        """session_error('reporting') transitions SessionManager to ERROR state."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=False,
            habilitar_resumen=False,
            dispositivo_audio=None,
            hf_token=None,
        )
        manager = _make_manager(config, event_bus, temp_db, speaker_manager)
        try:
            recorder = MagicMock()
            recorder.save_final = MagicMock()
            with patch("handsome_transcribe.ui.session_manager.RecorderWorker", return_value=recorder), \
                 patch("handsome_transcribe.ui.session_manager.TranscriberWorker"), \
                 patch("handsome_transcribe.ui.session_manager.ReporterWorker"):
                manager.start_session()
                manager.stop_recording()
                # Advance: transcription done -> skip diarization -> skip summarization -> start reporting
                manager._on_transcription_complete(MagicMock())

            event_bus.session_error.emit("Report generation failed", "reporting")
            QApplication.processEvents()

            assert manager.current_state == SessionState.ERROR
        finally:
            _cleanup(manager)
