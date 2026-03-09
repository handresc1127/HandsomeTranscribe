"""
Unit tests for UI models.

Tests dataclass serialization/deserialization and validation.
"""

import pytest
from datetime import datetime
from pathlib import Path
import json

from handsome_transcribe.ui.models import (
    SessionConfig, SessionData, SessionState,
    TranscriptSegmentData, SpeakerProfile, SpeakerMatch, SessionSpeaker
)


class TestSessionConfig:
    """Tests for SessionConfig model."""
    
    def test_create_default_config(self):
        """Test creating a default configuration."""
        config = SessionConfig()
        assert config.modelo_whisper == "base"
        assert config.habilitar_diarizacion is False
        assert config.habilitar_resumen is False
        assert config.dispositivo_audio is None
        assert config.hf_token is None
        assert config.session_context is None
    
    def test_create_custom_config(self):
        """Test creating a custom configuration."""
        config = SessionConfig(
            modelo_whisper="large",
            habilitar_diarizacion=True,
            hf_token="hf_test_token",
            session_context="Test meeting about project X"
        )
        assert config.modelo_whisper == "large"
        assert config.habilitar_diarizacion is True
        assert config.hf_token == "hf_test_token"
        assert config.session_context == "Test meeting about project X"
    
    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = SessionConfig(modelo_whisper="small")
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict["modelo_whisper"] == "small"
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "modelo_whisper": "medium",
            "habilitar_diarizacion": True,
            "habilitar_resumen": False,
            "dispositivo_audio": "Test Device",
            "hf_token": "hf_token",
            "session_context": None
        }
        config = SessionConfig.from_dict(data)
        assert config.modelo_whisper == "medium"
        assert config.habilitar_diarizacion is True
    
    def test_json_round_trip(self):
        """Test JSON serialization and deserialization."""
        original = SessionConfig(
            modelo_whisper="large",
            habilitar_resumen=True,
            session_context="Meeting notes"
        )
        json_str = original.to_json()
        restored = SessionConfig.from_json(json_str)
        
        assert restored.modelo_whisper == original.modelo_whisper
        assert restored.habilitar_resumen == original.habilitar_resumen
        assert restored.session_context == original.session_context


class TestSessionData:
    """Tests for SessionData model."""
    
    def test_create_session_data(self):
        """Test creating session data."""
        config = SessionConfig()
        session = SessionData(
            id=1,
            created_at=datetime.now(),
            session_dir=Path("outputs/sessions/session_20260309_140000"),
            recording_path=Path("outputs/sessions/session_20260309_140000/recording.wav"),
            transcript_path=Path("outputs/sessions/session_20260309_140000/transcript.txt"),
            summary_path=None,
            metadata_path=Path("outputs/sessions/session_20260309_140000/metadata.json"),
            temp_dir=Path("outputs/sessions/session_20260309_140000/temp"),
            config=config,
            state=SessionState.IDLE
        )
        
        assert session.id == 1
        assert session.state == SessionState.IDLE
        assert isinstance(session.session_dir, Path)
        assert session.partial_audio_count == 0
    
    def test_path_conversion(self):
        """Test that string paths are converted to Path objects."""
        config = SessionConfig()
        session = SessionData(
            id=1,
            created_at=datetime.now(),
            session_dir="outputs/sessions/test",
            recording_path="outputs/sessions/test/recording.wav",
            transcript_path="outputs/sessions/test/transcript.txt",
            summary_path=None,
            metadata_path="outputs/sessions/test/metadata.json",
            temp_dir="outputs/sessions/test/temp",
            config=config,
            state=SessionState.RECORDING
        )
        
        assert isinstance(session.session_dir, Path)
        assert isinstance(session.recording_path, Path)
        assert isinstance(session.transcript_path, Path)


class TestTranscriptSegmentData:
    """Tests for TranscriptSegmentData model."""
    
    def test_create_segment(self):
        """Test creating a transcript segment."""
        segment = TranscriptSegmentData(
            start_time=0.0,
            end_time=5.0,
            text="Hello world",
            speaker_id=1,
            confidence=0.95
        )
        
        assert segment.start_time == 0.0
        assert segment.end_time == 5.0
        assert segment.text == "Hello world"
        assert segment.speaker_id == 1
        assert segment.confidence == 0.95
    
    def test_json_round_trip(self):
        """Test JSON serialization and deserialization."""
        original = TranscriptSegmentData(
            start_time=10.5,
            end_time=15.2,
            text="Test transcript",
            speaker_id=2
        )
        json_str = original.to_json()
        restored = TranscriptSegmentData.from_json(json_str)
        
        assert restored.start_time == original.start_time
        assert restored.end_time == original.end_time
        assert restored.text == original.text
        assert restored.speaker_id == original.speaker_id


class TestSpeakerProfile:
    """Tests for SpeakerProfile model."""
    
    def test_create_speaker(self):
        """Test creating a speaker profile."""
        speaker = SpeakerProfile(
            id=1,
            name="John Doe",
            avatar_path="JD:#3498db",
            tags=["team", "manager"]
        )
        
        assert speaker.id == 1
        assert speaker.name == "John Doe"
        assert speaker.avatar_path == "JD:#3498db"
        assert "team" in speaker.tags
    
    def test_speaker_with_embedding(self):
        """Test speaker with voice embedding."""
        embedding = b'\x00\x01\x02\x03'
        speaker = SpeakerProfile(
            id=1,
            name="Test Speaker",
            voice_embedding_blob=embedding
        )
        
        assert speaker.voice_embedding_blob == embedding
    
    def test_json_serialization_with_embedding(self):
        """Test JSON serialization with binary embedding."""
        embedding = b'\x00\x01\x02\x03'
        original = SpeakerProfile(
            id=1,
            name="Test",
            voice_embedding_blob=embedding
        )
        
        speaker_dict = original.to_dict()
        assert "voice_embedding_blob" in speaker_dict
        assert isinstance(speaker_dict["voice_embedding_blob"], str)
        
        restored = SpeakerProfile.from_dict(speaker_dict)
        assert restored.voice_embedding_blob == embedding


class TestSpeakerMatch:
    """Tests for SpeakerMatch model."""
    
    def test_create_match(self):
        """Test creating a speaker match."""
        match = SpeakerMatch(
            confidence=0.95,
            speaker_id=1,
            is_new=False
        )
        
        assert match.confidence == 0.95
        assert match.speaker_id == 1
        assert match.is_new is False
    
    def test_new_speaker_match(self):
        """Test match for new speaker."""
        match = SpeakerMatch(
            confidence=0.0,
            speaker_id=3,
            is_new=True
        )
        
        assert match.is_new is True
        assert match.confidence == 0.0


class TestSessionSpeaker:
    """Tests for SessionSpeaker model."""
    
    def test_create_session_speaker(self):
        """Test creating session-speaker relationship."""
        rel = SessionSpeaker(
            session_id=1,
            speaker_id=2,
            segments_count=10,
            total_duration_sec=120.5
        )
        
        assert rel.session_id == 1
        assert rel.speaker_id == 2
        assert rel.segments_count == 10
        assert rel.total_duration_sec == 120.5
