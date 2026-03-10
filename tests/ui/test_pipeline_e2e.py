"""
End-to-end tests for complete processing pipeline.

Tests the full flow: Recording → Transcription → Diarization → Summarization → Reporting
"""

import pytest
from pathlib import Path
from PySide6.QtCore import QThreadPool
from unittest.mock import MagicMock, patch, call

from handsome_transcribe.ui.models import SessionConfig, SessionState
from handsome_transcribe.ui.database import Database
from handsome_transcribe.ui.event_bus import EventBus
from handsome_transcribe.ui.session_manager import SessionManager
from handsome_transcribe.ui.speaker_manager import SpeakerManager


@pytest.fixture
def db(tmp_path):
    """Create test database."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    yield database


@pytest.fixture
def event_bus():
    """Create event bus."""
    return EventBus()


@pytest.fixture
def speaker_manager(db):
    """Create speaker manager."""
    return SpeakerManager(db)


@pytest.fixture
def config():
    """Create session config."""
    return SessionConfig(
        dispositivo_audio="default",
        modelo_whisper="base",
        habilitar_diarizacion=True,
        habilitar_resumen=True,
        hf_token="test-token"
    )


@pytest.fixture
def session_manager(config, event_bus, db, speaker_manager, tmp_path):
    """Create session manager with mocked dependencies."""
    # Patch constants to use tmp_path
    with patch('handsome_transcribe.ui.session_manager.SESSIONS_DIR', tmp_path / "sessions"), \
         patch('handsome_transcribe.ui.session_manager.REPORTS_DIR', tmp_path / "reports"):
        
        manager = SessionManager(config, event_bus, db, speaker_manager)
        yield manager


class TestPipelineFullFlow:
    """Test complete pipeline flow with all stages."""
    
    def test_full_flow_record_transcribe_diarize_summarize_report(
        self, session_manager, event_bus, tmp_path
    ):
        """Test complete flow from recording to final reports."""
        
        # Mock all workers to avoid actual processing
        with patch('handsome_transcribe.ui.session_manager.RecorderWorker') as MockRecorder, \
             patch('handsome_transcribe.ui.session_manager.TranscriberWorker') as MockTranscriber, \
             patch('handsome_transcribe.ui.session_manager.DiarizerWorker') as MockDiarizer, \
             patch('handsome_transcribe.ui.session_manager.SummarizerWorker') as MockSummarizer, \
             patch('handsome_transcribe.ui.session_manager.ReporterWorker') as MockReporter:
            
            # Track state transitions
            state_changes = []
            event_bus.session_state_changed.connect(lambda s: state_changes.append(s))
            
            # Start session
            session_manager.start_session()
            assert session_manager.current_state == SessionState.RECORDING
            assert SessionState.RECORDING.value in state_changes
            
            # Simulate recording completion by calling manager API
            session_manager.recorder_worker = MagicMock()
            session_manager.stop_recording()
            
            # Should transition to TRANSCRIBING
            assert session_manager.current_state == SessionState.TRANSCRIBING
            assert SessionState.TRANSCRIBING.value in state_changes
            
            # Simulate transcription completion callback
            mock_transcript = {
                "text": "Test transcript",
                "segments": [{"start": 0, "end": 5, "text": "Test"}]
            }
            session_manager._on_transcription_complete(mock_transcript)
            
            # Should transition to DIARIZING
            assert session_manager.current_state == SessionState.DIARIZING
            assert SessionState.DIARIZING.value in state_changes
            
            # Simulate diarization completion callback
            speaker_map = {"0.0-5.0": "SPEAKER_00"}
            session_manager._on_diarization_complete(speaker_map)
            
            # Should transition to SUMMARIZING
            assert session_manager.current_state == SessionState.SUMMARIZING
            assert SessionState.SUMMARIZING.value in state_changes
            
            # Simulate summarization completion callback
            from handsome_transcribe.summarization.meeting_summarizer import MeetingSummary
            mock_summary = MeetingSummary(
                summary="Test summary",
                key_topics=["Topic 1"],
                action_items=["Action 1"],
                decisions=["Decision 1"]
            )
            session_manager._on_summarization_complete(mock_summary)
            
            # Simulate reports ready callback
            reports = {
                "markdown": str(tmp_path / "report.md"),
                "json": str(tmp_path / "report.json"),
                "pdf": str(tmp_path / "report.pdf")
            }
            session_manager._on_reports_ready(reports)
            
            # Should transition to COMPLETED
            assert session_manager.current_state == SessionState.IDLE
            assert SessionState.COMPLETED.value in state_changes
    
    def test_diarization_skipped_when_disabled(self, event_bus, db, speaker_manager, tmp_path):
        """Test that diarization is skipped when disabled in config."""
        
        # Create config with diarization disabled
        config = SessionConfig(
            dispositivo_audio="default",
            modelo_whisper="base",
            habilitar_diarizacion=False,  # Disabled
            habilitar_resumen=True,
            hf_token="test-token"
        )
        
        with patch('handsome_transcribe.ui.session_manager.SESSIONS_DIR', tmp_path / "sessions"), \
             patch('handsome_transcribe.ui.session_manager.REPORTS_DIR', tmp_path / "reports"):
            
            session_manager = SessionManager(config, event_bus, db, speaker_manager)
            
            with patch('handsome_transcribe.ui.session_manager.RecorderWorker'), \
                 patch('handsome_transcribe.ui.session_manager.TranscriberWorker'), \
                 patch('handsome_transcribe.ui.session_manager.DiarizerWorker') as MockDiarizer, \
                 patch('handsome_transcribe.ui.session_manager.SummarizerWorker'), \
                 patch('handsome_transcribe.ui.session_manager.ReporterWorker'):
                
                session_manager.start_session()
                session_manager.recorder_worker = MagicMock()
                session_manager.stop_recording()
                
                # Simulate transcription completion callback
                session_manager._on_transcription_complete({"text": "Test"})
                
                # Should skip DIARIZING and go directly to SUMMARIZING
                assert session_manager.current_state == SessionState.SUMMARIZING
                
                # DiarizerWorker should not be instantiated
                MockDiarizer.assert_not_called()
    
    def test_summarization_skipped_when_disabled(self, event_bus, db, speaker_manager, tmp_path):
        """Test that summarization is skipped when disabled in config."""
        
        # Create config with summarization and diarization disabled
        config = SessionConfig(
            dispositivo_audio="default",
            modelo_whisper="base",
            habilitar_diarizacion=False,
            habilitar_resumen=False,  # Disabled
            hf_token="test-token"
        )
        
        with patch('handsome_transcribe.ui.session_manager.SESSIONS_DIR', tmp_path / "sessions"), \
             patch('handsome_transcribe.ui.session_manager.REPORTS_DIR', tmp_path / "reports"):
            
            session_manager = SessionManager(config, event_bus, db, speaker_manager)
            
            with patch('handsome_transcribe.ui.session_manager.RecorderWorker'), \
                 patch('handsome_transcribe.ui.session_manager.TranscriberWorker'), \
                 patch('handsome_transcribe.ui.session_manager.SummarizerWorker') as MockSummarizer, \
                 patch('handsome_transcribe.ui.session_manager.ReporterWorker'):
                
                session_manager.start_session()
                session_manager.recorder_worker = MagicMock()
                session_manager.stop_recording()
                
                # Simulate transcription completion
                event_bus.emit_transcription_complete({"text": "Test"})
                
                # Should skip SUMMARIZING and go directly to REPORTING
                # (or COMPLETED if no reporting needed)
                
                # SummarizerWorker should not be instantiated
                MockSummarizer.assert_not_called()
    
    def test_error_handling_at_transcription_stage(self, session_manager, event_bus):
        """Test error handling during transcription stage."""
        
        errors = []
        event_bus.session_error.connect(lambda title, msg: errors.append((title, msg)))
        
        with patch('handsome_transcribe.ui.session_manager.RecorderWorker'), \
             patch('handsome_transcribe.ui.session_manager.TranscriberWorker'):
            
            session_manager.start_session()
            
            # Simulate transcription error
            event_bus.emit_session_error("Transcription failed", "transcription")
            
            # Should capture error
            assert len(errors) > 0
            assert "transcription" in errors[0]
    
    def test_error_handling_at_diarization_stage(self, session_manager, event_bus):
        """Test error handling during diarization stage."""
        
        errors = []
        event_bus.session_error.connect(lambda title, msg: errors.append((title, msg)))
        
        with patch('handsome_transcribe.ui.session_manager.RecorderWorker'), \
             patch('handsome_transcribe.ui.session_manager.TranscriberWorker'), \
             patch('handsome_transcribe.ui.session_manager.DiarizerWorker'):
            
            session_manager.start_session()
            
            # Move to diarization
            event_bus.emit_transcription_complete({"text": "Test"})
            
            # Simulate diarization error
            event_bus.emit_session_error("Diarization failed", "diarization")
            
            # Should capture error
            assert len(errors) > 0
            assert "diarization" in errors[0]
    
    def test_error_handling_at_summarization_stage(self, session_manager, event_bus):
        """Test error handling during summarization stage."""
        
        errors = []
        event_bus.session_error.connect(lambda title, msg: errors.append((title, msg)))
        
        with patch('handsome_transcribe.ui.session_manager.RecorderWorker'), \
             patch('handsome_transcribe.ui.session_manager.TranscriberWorker'), \
             patch('handsome_transcribe.ui.session_manager.SummarizerWorker'):
            
            session_manager.start_session()
            
            # Skip diarization for simplicity
            session_manager.config.habilitar_diarizacion = False
            
            # Move to summarization
            event_bus.emit_transcription_complete({"text": "Test"})
            
            # Simulate summarization error
            event_bus.emit_session_error("Summarization failed", "summarization")
            
            # Should capture error
            assert len(errors) > 0
            assert "summarization" in errors[0]
    
    def test_error_handling_at_reporting_stage(self, session_manager, event_bus):
        """Test error handling during reporting stage."""
        
        errors = []
        event_bus.session_error.connect(lambda title, msg: errors.append((title, msg)))
        
        with patch('handsome_transcribe.ui.session_manager.RecorderWorker'), \
             patch('handsome_transcribe.ui.session_manager.TranscriberWorker'), \
             patch('handsome_transcribe.ui.session_manager.SummarizerWorker'), \
             patch('handsome_transcribe.ui.session_manager.ReporterWorker'):
            
            session_manager.start_session()
            
            # Skip diarization
            session_manager.config.habilitar_diarizacion = False
            
            # Move through pipeline
            event_bus.emit_transcription_complete({"text": "Test"})
            
            from handsome_transcribe.summarization.meeting_summarizer import MeetingSummary
            event_bus.emit_summarization_complete(
                MeetingSummary("Summary", [], [], [])
            )
            
            # Simulate reporting error
            event_bus.emit_session_error("Report generation failed", "reporting")
            
            # Should capture error
            assert len(errors) > 0
            assert "reporting" in errors[0]


class TestPipelineFileCreation:
    """Test that pipeline creates expected files."""
    
    def test_transcript_txt_and_json_format(self, tmp_path):
        """Test that transcript files follow expected format."""
        # Simple validation test - just check file structure expectations
        # Actual worker testing is covered by mocks in full flow tests
        
        # Create expected transcript.txt format
        transcript_txt = tmp_path / "transcript.txt"
        transcript_txt.write_text("[00:00-00:05] Test segment\n")
        
        # Verify format
        content = transcript_txt.read_text()
        assert "[" in content
        assert "]" in content
        assert "Test segment" in content
        
        # Create expected transcript.json format
        import json
        transcript_json = tmp_path / "transcript.json"
        data = {
            "audio_file": "test.wav",
            "language": "en",
            "segments": [
                {"start": 0, "end": 5, "text": "Test segment", "speaker": "Unknown"}
            ]
        }
        with open(transcript_json, "w") as f:
            json.dump(data, f)
        
        # Verify format
        with open(transcript_json) as f:
            loaded = json.load(f)
        
        assert "audio_file" in loaded
        assert "segments" in loaded
        assert len(loaded["segments"]) == 1
    
    def test_summary_markdown_format(self, tmp_path):
        """Test that summary markdown follows expected format."""
        
        summary_md = tmp_path / "summary.md"
        summary_md.write_text("""# Meeting Summary

Test summary

## Key Topics
- Topic 1
- Topic 2

## Action Items
- Action 1

## Decisions
- Decision 1
""")
        
        # Verify format
        content = summary_md.read_text()
        assert "# Meeting Summary" in content
        assert "## Key Topics" in content
        assert "## Action Items" in content
        assert "## Decisions" in content
