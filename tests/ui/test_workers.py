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
        assert worker._recording is False
    
    def test_pause_and_resume(self, event_bus):
        """Test pausing and resuming recorder."""
        worker = RecorderWorker(event_bus)
        
        worker.pause()
        assert worker._paused is True
        
        worker.resume()
        assert worker._paused is False
    
    def test_stop_recording(self, event_bus):
        """Test stopping the recorder."""
        worker = RecorderWorker(event_bus)
        
        worker.stop()
        assert worker._recording is False


class TestTranscriberWorker:
    """Tests for TranscriberWorker."""
    
    def test_create_transcriber_worker(self, event_bus):
        """Test creating a TranscriberWorker instance."""
        worker = TranscriberWorker(
            event_bus=event_bus,
            audio_path=Path("test.wav"),
            output_path=Path("transcript.txt"),
            model_name="base",
            language=None
        )
        
        assert worker is not None
        assert worker.audio_path == Path("test.wav")
        assert worker.model_name == "base"

    def test_create_transcriber_worker_with_language(self, event_bus):
        """Test creating a TranscriberWorker with explicit language."""
        worker = TranscriberWorker(
            event_bus=event_bus,
            audio_path=Path("test.wav"),
            output_path=Path("transcript.txt"),
            model_name="base",
            language="es"
        )
        assert worker.language == "es"

    def test_create_transcriber_worker_language_none(self, event_bus):
        """Test creating a TranscriberWorker without language defaults to None."""
        worker = TranscriberWorker(
            event_bus=event_bus,
            audio_path=Path("test.wav"),
            output_path=Path("transcript.txt"),
            model_name="base"
        )
        assert worker.language is None


class TestSpeakerEmbeddingWorker:
    """Tests for SpeakerEmbeddingWorker."""
    
    def test_create_embedding_worker(self, event_bus):
        """Test creating a SpeakerEmbeddingWorker instance."""
        worker = SpeakerEmbeddingWorker(
            event_bus=event_bus,
            audio_chunk=np.zeros(16000, dtype=np.float32),
            chunk_id=1,
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
            transcript_path=Path("transcript.txt"),
            output_path=Path("summary.md")
        )
        
        assert worker is not None
        assert worker.transcript_json_path == Path("transcript.json")


class TestReporterWorker:
    """Tests for ReporterWorker."""
    
    def test_create_reporter_worker(self, event_bus):
        """Test creating a ReporterWorker instance."""
        worker = ReporterWorker(
            event_bus=event_bus,
            session_dir=Path("outputs/sessions/test"),
            session_id=1,
            reports_dir=Path("outputs/reports")
        )
        
        assert worker is not None
        assert worker.session_id == 1
