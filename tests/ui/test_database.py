"""
Unit tests for Database.

Tests CRUD operations, embeddings matching, and schema.
"""

import pytest
import numpy as np
from datetime import datetime
from pathlib import Path

from handsome_transcribe.ui.database import Database
from handsome_transcribe.ui.models import (
    SessionData, SessionConfig, SessionState,
    SpeakerProfile, SessionSpeaker, TranscriptSegmentData
)


class TestDatabase:
    """Tests for Database operations."""
    
    def test_create_database(self, temp_db):
        """Test database initialization."""
        assert temp_db is not None
        assert temp_db.db_path.exists()
    
    def test_create_session(self, temp_db):
        """Test creating a session."""
        config = SessionConfig()
        session = SessionData(
            id=-1,
            created_at=datetime.now(),
            session_dir=Path("outputs/sessions/test"),
            recording_path=Path("outputs/sessions/test/recording.wav"),
            transcript_path=Path("outputs/sessions/test/transcript.txt"),
            summary_path=None,
            metadata_path=Path("outputs/sessions/test/metadata.json"),
            temp_dir=Path("outputs/sessions/test/temp"),
            config=config,
            state=SessionState.IDLE
        )
        
        session_id = temp_db.create_session(session)
        assert session_id > 0
    
    def test_get_session(self, temp_db):
        """Test retrieving a session."""
        # Create session first
        config = SessionConfig()
        session = SessionData(
            id=-1,
            created_at=datetime.now(),
            session_dir=Path("outputs/sessions/test"),
            recording_path=Path("outputs/sessions/test/recording.wav"),
            transcript_path=Path("outputs/sessions/test/transcript.txt"),
            summary_path=None,
            metadata_path=Path("outputs/sessions/test/metadata.json"),
            temp_dir=Path("outputs/sessions/test/temp"),
            config=config,
            state=SessionState.RECORDING
        )
        session_id = temp_db.create_session(session)
        
        # Retrieve it
        retrieved = temp_db.get_session(session_id)
        assert retrieved is not None
        assert retrieved.id == session_id
        assert retrieved.state == SessionState.RECORDING
    
    def test_update_session(self, temp_db):
        """Test updating a session."""
        config = SessionConfig()
        session = SessionData(
            id=-1,
            created_at=datetime.now(),
            session_dir=Path("outputs/sessions/test"),
            recording_path=Path("outputs/sessions/test/recording.wav"),
            transcript_path=Path("outputs/sessions/test/transcript.txt"),
            summary_path=None,
            metadata_path=Path("outputs/sessions/test/metadata.json"),
            temp_dir=Path("outputs/sessions/test/temp"),
            config=config,
            state=SessionState.RECORDING
        )
        session_id = temp_db.create_session(session)
        
        # Update state
        temp_db.update_session(session_id, state=SessionState.COMPLETED)
        
        # Verify update
        retrieved = temp_db.get_session(session_id)
        assert retrieved.state == SessionState.COMPLETED
    
    def test_get_active_session(self, temp_db):
        """Test retrieving active session."""
        config = SessionConfig()
        
        # Create an active session
        active_session = SessionData(
            id=-1,
            created_at=datetime.now(),
            session_dir=Path("outputs/sessions/active"),
            recording_path=Path("outputs/sessions/active/recording.wav"),
            transcript_path=Path("outputs/sessions/active/transcript.txt"),
            summary_path=None,
            metadata_path=Path("outputs/sessions/active/metadata.json"),
            temp_dir=Path("outputs/sessions/active/temp"),
            config=config,
            state=SessionState.RECORDING
        )
        active_id = temp_db.create_session(active_session)
        
        # Create a completed session
        completed_session = SessionData(
            id=-1,
            created_at=datetime.now(),
            session_dir=Path("outputs/sessions/completed"),
            recording_path=Path("outputs/sessions/completed/recording.wav"),
            transcript_path=Path("outputs/sessions/completed/transcript.txt"),
            summary_path=None,
            metadata_path=Path("outputs/sessions/completed/metadata.json"),
            temp_dir=Path("outputs/sessions/completed/temp"),
            config=config,
            state=SessionState.COMPLETED
        )
        temp_db.create_session(completed_session)
        
        # Get active session
        active = temp_db.get_active_session()
        assert active is not None
        assert active.id == active_id
        assert active.state == SessionState.RECORDING
    
    def test_create_speaker(self, temp_db):
        """Test creating a speaker."""
        speaker = SpeakerProfile(
            id=-1,
            name="Test Speaker",
            avatar_path="TS:#3498db",
            tags=["test"]
        )
        
        speaker_id = temp_db.create_speaker(speaker)
        assert speaker_id > 0
    
    def test_get_speaker(self, temp_db):
        """Test retrieving a speaker."""
        speaker = SpeakerProfile(
            id=-1,
            name="John Doe",
            avatar_path="JD:#e74c3c"
        )
        speaker_id = temp_db.create_speaker(speaker)
        
        retrieved = temp_db.get_speaker(speaker_id)
        assert retrieved is not None
        assert retrieved.id == speaker_id
        assert retrieved.name == "John Doe"
    
    def test_speaker_embedding_match(self, temp_db):
        """Test speaker matching by embedding."""
        # Create speaker with embedding
        embedding1 = np.random.randn(128).astype(np.float32)
        speaker = SpeakerProfile(
            id=-1,
            name="Speaker 1",
            voice_embedding_blob=embedding1.tobytes()
        )
        temp_db.create_speaker(speaker)
        
        # Try to match with very similar embedding
        similar_embedding = embedding1 + np.random.randn(128).astype(np.float32) * 0.01
        matched_speaker, is_new = temp_db.get_or_create_speaker(similar_embedding, threshold=0.95)
        
        # Should match existing speaker
        assert is_new is False
        assert matched_speaker.name == "Speaker 1"
    
    def test_add_transcript_segment(self, temp_db):
        """Test adding transcript segment."""
        # Create session first
        config = SessionConfig()
        session = SessionData(
            id=-1,
            created_at=datetime.now(),
            session_dir=Path("outputs/sessions/test"),
            recording_path=Path("outputs/sessions/test/recording.wav"),
            transcript_path=Path("outputs/sessions/test/transcript.txt"),
            summary_path=None,
            metadata_path=Path("outputs/sessions/test/metadata.json"),
            temp_dir=Path("outputs/sessions/test/temp"),
            config=config,
            state=SessionState.TRANSCRIBING
        )
        session_id = temp_db.create_session(session)
        
        # Add segment
        segment = TranscriptSegmentData(
            start_time=0.0,
            end_time=5.0,
            text="Hello world",
            speaker_id=None
        )
        temp_db.add_transcript_segment(segment, session_id)
        
        # Retrieve segments
        segments = temp_db.get_transcript_segments(session_id)
        assert len(segments) == 1
        assert segments[0].text == "Hello world"
