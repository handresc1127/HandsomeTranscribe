"""Tests for recorder flow integration with SessionManager and RecorderWorker."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from PySide6.QtCore import QThreadPool

from handsome_transcribe.ui.config_manager import ConfigManager
from handsome_transcribe.ui.database import Database
from handsome_transcribe.ui.event_bus import EventBus
from handsome_transcribe.ui.models import SessionState
from handsome_transcribe.ui.session_manager import SessionManager
from handsome_transcribe.ui.speaker_manager import SpeakerManager
from handsome_transcribe.ui.workers import RecorderWorker


@pytest.fixture
def tmp_outputs_dir(tmp_path: Path) -> Path:
    """Create temporary outputs directory."""
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir


@pytest.fixture
def event_bus() -> EventBus:
    """Create EventBus instance."""
    return EventBus()


@pytest.fixture
def config_manager(tmp_outputs_dir: Path) -> ConfigManager:
    """Create ConfigManager with test configuration."""
    mgr = ConfigManager()
    config = mgr.load_config()
    
    # Set test values
    config.dispositivo_audio = "Test Device"
    config.modelo_whisper = "base"
    config.habilitar_diarizacion = False
    config.habilitar_resumen = False
    config.session_context = None
    
    mgr.save_config(config)
    return mgr


@pytest.fixture
def database(tmp_path: Path) -> Database:
    """Create test database."""
    db_path = tmp_path / "test_database.db"
    return Database(db_path)


@pytest.fixture
def speaker_manager(database: Database) -> SpeakerManager:
    """Create SpeakerManager instance."""
    return SpeakerManager(database)


@pytest.fixture
def session_manager(
    config_manager: ConfigManager,
    event_bus: EventBus,
    database: Database,
    speaker_manager: SpeakerManager
) -> SessionManager:
    """Create SessionManager instance."""
    # Load SessionConfig from ConfigManager
    config = config_manager.load_config()
    return SessionManager(config, event_bus, database, speaker_manager)


def _make_audio_data(sample_rate: int = 16000, duration: float = 1.0) -> np.ndarray:
    """
    Generate a simple sine-wave audio array (float32 format for RecorderWorker).
    
    Args:
        sample_rate: Sample rate in Hz
        duration: Duration in seconds
        
    Returns:
        Audio data as float32 numpy array
    """
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32).reshape(-1, 1)


class TestRecorderFlow:
    """Test complete recording flow with SessionManager and workers."""
    
    def test_record_and_save_wav(
        self,
        session_manager: SessionManager,
        event_bus: EventBus,
        tmp_outputs_dir: Path
    ) -> None:
        """Test basic recording and WAV file creation."""
        # Mock RecorderWorker to simulate recording
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker") as MockRecorder:
            mock_worker = Mock()
            mock_worker.save_final = Mock()
            MockRecorder.return_value = mock_worker
            
            # Start session
            session_manager.start_session()
            assert session_manager.current_state == SessionState.RECORDING
            assert session_manager.current_session is not None
            
            # Verify directory structure created
            session_dir = session_manager.current_session.session_dir
            assert session_dir.exists()
            assert (session_dir / "temp").exists()
            
            # Stop recording
            session_manager.stop_recording()
            
            # Verify save_final was called with correct path
            mock_worker.save_final.assert_called_once()
            call_args = mock_worker.save_final.call_args[0]
            assert call_args[0] == session_manager.current_session.recording_path
    
    def test_progress_updates(
        self,
        event_bus: EventBus,
        tmp_outputs_dir: Path
    ) -> None:
        """Test that RecorderWorker emits recording_frame_ready periodically."""
        # Track emitted signals
        progress_signals = []
        
        def capture_progress(frames_count: int, duration_sec: float):
            progress_signals.append((frames_count, duration_sec))
        
        event_bus.recording_frame_ready.connect(capture_progress)
        
        # Create RecorderWorker with mock sounddevice
        with patch("handsome_transcribe.ui.workers.sd") as mock_sd:
            # Mock InputStream to simulate recording
            mock_stream = MagicMock()
            mock_stream.__enter__ = Mock(return_value=mock_stream)
            mock_stream.__exit__ = Mock(return_value=None)
            mock_sd.InputStream.return_value = mock_stream
            
            worker = RecorderWorker(
                event_bus=event_bus,
                device_name="Test Device",
                sample_rate=16000,
                channels=1
            )
            
            # Simulate audio callback
            audio_chunk = _make_audio_data(16000, 0.1)  # 100ms chunk
            for i in range(10):  # 10 chunks = 1 second
                worker._audio_callback(audio_chunk, len(audio_chunk), None, None)
            
            # Manually emit signal (worker.run() does this in real scenario)
            event_bus.emit_recording_frame(worker._frames_count, worker._duration_sec)
            
            # Verify progress signal emitted
            assert len(progress_signals) > 0
            frames, duration = progress_signals[-1]
            assert frames > 0
            assert 0.9 <= duration <= 1.1  # ~1 second
            
            worker.stop()
    
    def test_stop_recording(
        self,
        session_manager: SessionManager,
        event_bus: EventBus
    ) -> None:
        """Test SessionManager.stop_recording() creates recording.wav and transitions state."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker") as MockRecorder, \
             patch("handsome_transcribe.ui.session_manager.TranscriberWorker"):
            
            mock_worker = Mock()
            mock_worker.save_final = Mock()
            mock_worker.stop = Mock()
            MockRecorder.return_value = mock_worker
            
            # Start and stop session
            session_manager.start_session()
            session_manager.stop_recording()
            
            # Verify worker methods called
            mock_worker.stop.assert_called_once()
            mock_worker.save_final.assert_called_once()
            
            # Verify state transition
            assert session_manager.current_state == SessionState.TRANSCRIBING
    
    def test_pause_and_save_partial(
        self,
        session_manager: SessionManager,
        event_bus: EventBus
    ) -> None:
        """Test SessionManager.pause_recording() creates temp/partN.wav."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker") as MockRecorder:
            mock_worker = Mock()
            mock_worker.pause = Mock()
            mock_worker.save_partial = Mock()
            MockRecorder.return_value = mock_worker
            
            # Start session
            session_manager.start_session()
            initial_count = session_manager.current_session.partial_audio_count
            
            # Pause recording (should trigger save_partial)
            session_manager.pause_recording()
            
            # Verify pause called
            mock_worker.pause.assert_called_once()
            
            # Verify save_partial called with incremented counter
            mock_worker.save_partial.assert_called_once()
            call_args = mock_worker.save_partial.call_args[0]
            assert call_args[0] == session_manager.current_session.temp_dir
            assert call_args[1] == initial_count + 1
            
            # Verify counter incremented
            assert session_manager.current_session.partial_audio_count == initial_count + 1
            
            # Verify state transition
            assert session_manager.current_state == SessionState.PAUSED
    
    def test_consolidate_final_recording(
        self,
        event_bus: EventBus,
        tmp_outputs_dir: Path
    ) -> None:
        """Test RecorderWorker.save_final() consolidates complete audio."""
        # Create temp directory with mock partial files
        temp_dir = tmp_outputs_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Create RecorderWorker and simulate audio accumulation
        worker = RecorderWorker(
            event_bus=event_bus,
            device_name="Test Device",
            sample_rate=16000,
            channels=1
        )
        
        # Simulate recording (accumulate audio in buffer)
        audio_chunk1 = _make_audio_data(16000, 0.5)  # 0.5 seconds
        audio_chunk2 = _make_audio_data(16000, 0.5)  # 0.5 seconds
        
        for _ in range(5):
            worker._audio_callback(audio_chunk1, len(audio_chunk1), None, None)
        for _ in range(5):
            worker._audio_callback(audio_chunk2, len(audio_chunk2), None, None)
        
        # Mock wave.open to verify consolidation
        with patch("handsome_transcribe.ui.workers.wave.open") as mock_wave_open:
            mock_wf = MagicMock()
            mock_wave_open.return_value.__enter__ = Mock(return_value=mock_wf)
            mock_wave_open.return_value.__exit__ = Mock(return_value=None)
            
            output_path = tmp_outputs_dir / "recording.wav"
            worker.save_final(output_path)
            
            # Verify wave file opened with correct path
            mock_wave_open.assert_called_once_with(str(output_path), "wb")
            
            # Verify wave properties set correctly
            mock_wf.setnchannels.assert_called_once_with(1)  # mono
            mock_wf.setsampwidth.assert_called_once_with(2)  # 16-bit
            mock_wf.setframerate.assert_called_once_with(16000)  # sample_rate
            
            # Verify writeframes called (audio data consolidated)
            assert mock_wf.writeframes.called
    
    def test_device_selection(
        self,
        event_bus: EventBus
    ) -> None:
        """Test RecorderWorker uses specified device from config."""
        with patch("handsome_transcribe.ui.workers.sd") as mock_sd:
            # Mock device list
            mock_sd.query_devices.return_value = [
                {"name": "Device A"},
                {"name": "Test Device"},
                {"name": "Device C"}
            ]
            
            mock_stream = MagicMock()
            mock_stream.__enter__ = Mock(return_value=mock_stream)
            mock_stream.__exit__ = Mock(return_value=None)
            mock_sd.InputStream.return_value = mock_stream
            
            worker = RecorderWorker(
                event_bus=event_bus,
                device_name="Test Device",
                sample_rate=16000,
                channels=1
            )
            
            # Start recording (triggers device selection in run())
            # We can't call run() directly in test, so we verify initialization
            assert worker.device_name == "Test Device"
            assert worker.sample_rate == 16000
            assert worker.channels == 1
    
    def test_session_directory_creation(
        self,
        session_manager: SessionManager
    ) -> None:
        """Test SessionManager creates session_YYYYMMDD_HHMMSS/temp/ structure."""
        with patch("handsome_transcribe.ui.session_manager.RecorderWorker"):
            # Start session
            session_manager.start_session()
            
            # Verify session directory structure
            session_dir = session_manager.current_session.session_dir
            assert session_dir.exists()
            assert session_dir.name.startswith("session_")
            
            # Verify name format: session_YYYYMMDD_HHMMSS
            timestamp_part = session_dir.name.replace("session_", "")
            assert len(timestamp_part) == 15  # YYYYMMDD_HHMMSS
            assert timestamp_part[8] == "_"  # Underscore separator
            
            # Verify temp subdirectory
            temp_dir = session_dir / "temp"
            assert temp_dir.exists()
            assert temp_dir.is_dir()
            
            # Verify metadata paths set correctly
            assert session_manager.current_session.metadata_path == session_dir / "metadata.json"
            assert session_manager.current_session.recording_path == session_dir / "recording.wav"
            assert session_manager.current_session.transcript_path == session_dir / "transcript.txt"
            assert session_manager.current_session.temp_dir == temp_dir
