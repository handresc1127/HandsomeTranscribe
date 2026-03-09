"""
Unit tests for Workers.

Tests worker lifecycle and basic execution.
"""

import pytest
from unittest.mock import Mock, patch
import numpy as np

from PySide6.QtCore import QThreadPool

from handsome_transcribe.ui.workers import (
    RecorderWorker, TranscriberWorker, SpeakerEmbeddingWorker,
    DiarizerWorker, SummarizerWorker, ReporterWorker
)
from handsome_transcribe.ui.event_bus import EventBus
from handsome_transcribe.ui.models import SessionData, SessionConfig, SessionState
from pathlib import Path
from datetime import datetime


class TestRecorderWorker:
    """Tests for RecorderWorker."""
    
    def test_create_recorder_worker(self, event_bus):
        """Test creating a RecorderWorker instance."""
        worker = RecorderWorker(event_bus, sample_rate=16000)
        
        assert worker is not None
        assert worker.sample_rate == 16000
        assert worker.is_recording is False
    
    def test_pause_and_resume(self, event_bus):
        """Test pausing and resuming recorder."""
        worker = RecorderWorker(event_bus)
        
        worker.pause()
        assert worker.is_paused is True
        
        worker.resume()
        assert worker.is_paused is False
    
    def test_stop_recording(self, event_bus):
        """Test stopping the recorder."""
        worker = RecorderWorker(event_bus)
        
        worker.stop()
        assert worker.is_recording is False


class TestTranscriberWorker:
    """Tests for TranscriberWorker."""
    
    def test_create_transcriber_worker(self, event_bus):
        """Test creating a TranscriberWorker instance."""
        worker = TranscriberWorker(
            event_bus=event_bus,
            audio_path=Path("test.wav"),
            model_name="base",
            language=None
        )
        
        assert worker is not None
        assert worker.audio_path == Path("test.wav")
        assert worker.model_name == "base"


class TestSpeakerEmbeddingWorker:
    """Tests for SpeakerEmbeddingWorker."""
    
    def test_create_embedding_worker(self, event_bus):
        """Test creating a SpeakerEmbeddingWorker instance."""
        worker = SpeakerEmbeddingWorker(
            event_bus=event_bus,
            audio_chunk=np.zeros(16000, dtype=np.float32),
            sample_rate=16000
        )
        
        assert worker is not None
        assert len(worker.audio_chunk) == 16000


class TestDiarizerWorker:
    """Tests for DiarizerWorker."""
    
    def test_create_diarizer_worker(self, event_bus):
        """Test creating a DiarizerWorker instance."""
        worker = DiarizerWorker(
            event_bus=event_bus,
            audio_path=Path("test.wav"),
            hf_token="hf_test_token"
        )
        
        assert worker is not None
        assert worker.audio_path == Path("test.wav")


class TestSummarizerWorker:
    """Tests for SummarizerWorker."""
    
    def test_create_summarizer_worker(self, event_bus):
        """Test creating a SummarizerWorker instance."""
        worker = SummarizerWorker(
            event_bus=event_bus,
            transcript="Test transcript text"
        )
        
        assert worker is not None
        assert worker.transcript == "Test transcript text"


class TestReporterWorker:
    """Tests for ReporterWorker."""
    
    def test_create_reporter_worker(self, event_bus):
        """Test creating a ReporterWorker instance."""
        config = SessionConfig()
        session_data = SessionData(
            id=1,
            created_at=datetime.now(),
            session_dir=Path("outputs/sessions/test"),
            recording_path=Path("outputs/sessions/test/recording.wav"),
            transcript_path=Path("outputs/sessions/test/transcript.txt"),
            summary_path=None,
            metadata_path=Path("outputs/sessions/test/metadata.json"),
            temp_dir=Path("outputs/sessions/test/temp"),
            config=config,
            state=SessionState.COMPLETED
        )
        
        worker = ReporterWorker(
            event_bus=event_bus,
            session_data=session_data,
            transcript_text="Test transcript",
            summary_text=None,
            speakers=[]
        )
        
        assert worker is not None
        assert worker.session_data.id == 1
