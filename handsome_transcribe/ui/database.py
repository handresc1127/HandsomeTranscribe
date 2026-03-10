"""
Database layer for managing sessions, speakers, and transcripts.

This module provides SQLite-based persistence for the desktop UI.
"""

import sqlite3
import json
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
from contextlib import contextmanager

from .models import (
    SessionData, SessionConfig, SessionState,
    SpeakerProfile, SessionSpeaker, TranscriptSegmentData
)
from .exceptions import DatabaseError
from .constants import DB_FILENAME, DB_VERSION


class Database:
    """SQLite database manager for HandsomeTranscribe."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Optional custom database path. If None, uses default location.
        """
        if db_path is None:
            # Use default location in .config directory
            from PySide6.QtCore import QStandardPaths
            config_dir = Path(QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            ))
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = config_dir / DB_FILENAME
        
        self.db_path = Path(db_path)
        self._initialize_database()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"Database operation failed: {e}") from e
        finally:
            conn.close()
    
    def _initialize_database(self):
        """Create database schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    session_dir TEXT NOT NULL,
                    state TEXT NOT NULL,
                    recording_path TEXT,
                    transcript_path TEXT,
                    summary_path TEXT,
                    context_text TEXT,
                    config_json TEXT,
                    metadata_json TEXT
                )
            """)
            
            # Speakers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS speakers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    avatar_path TEXT,
                    voice_embedding BLOB,
                    tags TEXT,
                    created_at TEXT NOT NULL,
                    last_seen TEXT
                )
            """)
            
            # Session-speakers relationship table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_speakers (
                    session_id INTEGER NOT NULL,
                    speaker_id INTEGER NOT NULL,
                    segments_count INTEGER DEFAULT 0,
                    total_duration_sec REAL DEFAULT 0.0,
                    PRIMARY KEY (session_id, speaker_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(id),
                    FOREIGN KEY (speaker_id) REFERENCES speakers(id)
                )
            """)
            
            # Transcript segments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcript_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    speaker_id INTEGER,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    text TEXT NOT NULL,
                    confidence REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id),
                    FOREIGN KEY (speaker_id) REFERENCES speakers(id)
                )
            """)
            
            # Create indices for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_state 
                ON sessions(state)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transcript_segments_session 
                ON transcript_segments(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_speakers_session 
                ON session_speakers(session_id)
            """)
            
            conn.commit()
    
    # Session CRUD operations
    
    def create_session(self, session_data: SessionData) -> int:
        """
        Create a new session in the database.
        
        Args:
            session_data: Session data to store
            
        Returns:
            The ID of the created session
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (
                    created_at, session_dir, state, recording_path,
                    transcript_path, summary_path, context_text, config_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_data.created_at.isoformat(),
                str(session_data.session_dir),
                session_data.state.value,
                str(session_data.recording_path),
                str(session_data.transcript_path),
                str(session_data.summary_path) if session_data.summary_path else None,
                session_data.session_context,
                session_data.config.to_json(),
                None  # metadata_json will be updated later
            ))
            return cursor.lastrowid
    
    def update_session(self, session_id: int, **kwargs):
        """
        Update session fields.
        
        Args:
            session_id: Session ID to update
            **kwargs: Fields to update (state, recording_path, etc.)
        """
        allowed_fields = {
            "state", "recording_path", "transcript_path", "summary_path",
            "context_text", "metadata_json"
        }
        
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                if key == "state" and isinstance(value, SessionState):
                    values.append(value.value)
                elif isinstance(value, Path):
                    values.append(str(value))
                else:
                    values.append(value)
        
        if not updates:
            return
        
        values.append(session_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
                values
            )
    
    def get_session(self, session_id: int) -> Optional[SessionData]:
        """
        Retrieve a session by ID.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            SessionData object or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return self._row_to_session_data(row)
    
    def get_all_sessions(self) -> List[SessionData]:
        """
        Retrieve all sessions.
        
        Returns:
            List of SessionData objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
            return [self._row_to_session_data(row) for row in rows]
    
    def get_active_session(self) -> Optional[SessionData]:
        """
        Get currently active session (RECORDING or PAUSED state).
        
        Returns:
            SessionData object or None if no active session
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sessions 
                WHERE state IN (?, ?)
                ORDER BY created_at DESC
                LIMIT 1
            """, (SessionState.RECORDING.value, SessionState.PAUSED.value))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return self._row_to_session_data(row)

    def recover_stale_active_sessions(self) -> int:
        """
        Mark stale active sessions as ERROR.

        This recovery is intended for app startup after an unclean shutdown
        where sessions remained in RECORDING/PAUSED state in the database.

        Returns:
            Number of recovered sessions
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET state = ?
                WHERE state IN (?, ?)
                """,
                (
                    SessionState.ERROR.value,
                    SessionState.RECORDING.value,
                    SessionState.PAUSED.value,
                ),
            )
            return cursor.rowcount
    
    def delete_session(self, session_id: int):
        """
        Delete a session and its related data.
        
        Args:
            session_id: Session ID to delete
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete related data first (foreign key constraints)
            cursor.execute("DELETE FROM transcript_segments WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM session_speakers WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    
    # Speaker CRUD operations
    
    def create_speaker(self, speaker: SpeakerProfile) -> int:
        """
        Create a new speaker in the database.
        
        Args:
            speaker: Speaker profile to store
            
        Returns:
            The ID of the created speaker
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO speakers (
                    name, avatar_path, voice_embedding, tags, created_at, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                speaker.name,
                speaker.avatar_path,
                speaker.voice_embedding_blob,
                json.dumps(speaker.tags),
                speaker.created_at.isoformat(),
                speaker.last_seen.isoformat() if speaker.last_seen else None
            ))
            return cursor.lastrowid
    
    def update_speaker(self, speaker_id: int, **kwargs):
        """
        Update speaker fields.
        
        Args:
            speaker_id: Speaker ID to update
            **kwargs: Fields to update (name, avatar_path, voice_embedding, tags, last_seen)
        """
        allowed_fields = {"name", "avatar_path", "voice_embedding", "tags", "last_seen"}
        
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                if key == "tags" and isinstance(value, list):
                    values.append(json.dumps(value))
                elif key == "last_seen" and isinstance(value, datetime):
                    values.append(value.isoformat())
                else:
                    values.append(value)
        
        if not updates:
            return
        
        values.append(speaker_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE speakers SET {', '.join(updates)} WHERE id = ?",
                values
            )
    
    def get_speaker(self, speaker_id: int) -> Optional[SpeakerProfile]:
        """
        Retrieve a speaker by ID.
        
        Args:
            speaker_id: Speaker ID to retrieve
            
        Returns:
            SpeakerProfile object or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM speakers WHERE id = ?", (speaker_id,))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return self._row_to_speaker_profile(row)
    
    def get_all_speakers(self) -> List[SpeakerProfile]:
        """
        Retrieve all speakers.
        
        Returns:
            List of SpeakerProfile objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM speakers ORDER BY last_seen DESC")
            rows = cursor.fetchall()
            
            return [self._row_to_speaker_profile(row) for row in rows]
    
    def delete_speaker(self, speaker_id: int):
        """
        Delete a speaker.
        
        Args:
            speaker_id: Speaker ID to delete
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM speakers WHERE id = ?", (speaker_id,))
    
    def get_or_create_speaker(self, embedding: np.ndarray, threshold: float = 0.98) -> Tuple[SpeakerProfile, bool]:
        """
        Find matching speaker by embedding or create new one.
        
        Args:
            embedding: Voice embedding to match
            threshold: Similarity threshold for matching (default 0.98)
            
        Returns:
            Tuple of (SpeakerProfile, is_new) where is_new indicates if speaker was created
        """
        # Get all speakers with embeddings
        speakers = self.get_all_speakers()
        
        best_match = None
        best_similarity = 0.0
        
        for speaker in speakers:
            if speaker.voice_embedding_blob:
                stored_embedding = np.frombuffer(speaker.voice_embedding_blob, dtype=np.float32)
                similarity = self._cosine_similarity(embedding, stored_embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = speaker
        
        # If similarity above threshold, return existing speaker
        if best_match and best_similarity >= threshold:
            return best_match, False
        
        # Create new speaker
        speaker_count = len(speakers) + 1
        new_speaker = SpeakerProfile(
            id=-1,  # Will be set by database
            name=f"Speaker {speaker_count}",
            voice_embedding_blob=embedding.astype(np.float32).tobytes(),
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        new_speaker.id = self.create_speaker(new_speaker)
        return new_speaker, True
    
    # Transcript segment operations
    
    def add_transcript_segment(self, segment: TranscriptSegmentData, session_id: int):
        """
        Add a transcript segment to a session.
        
        Args:
            segment: Transcript segment to add
            session_id: Session ID to associate with
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transcript_segments (
                    session_id, speaker_id, start_time, end_time, text, confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                segment.speaker_id,
                segment.start_time,
                segment.end_time,
                segment.text,
                segment.confidence
            ))
    
    def get_transcript_segments(self, session_id: int) -> List[TranscriptSegmentData]:
        """
        Retrieve all transcript segments for a session.
        
        Args:
            session_id: Session ID to retrieve segments for
            
        Returns:
            List of TranscriptSegmentData objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT speaker_id, start_time, end_time, text, confidence
                FROM transcript_segments 
                WHERE session_id = ?
                ORDER BY start_time
            """, (session_id,))
            rows = cursor.fetchall()
            
            return [
                TranscriptSegmentData(
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    text=row["text"],
                    speaker_id=row["speaker_id"],
                    confidence=row["confidence"]
                )
                for row in rows
            ]
    
    # Session-speaker relationship operations
    
    def add_session_speaker(self, session_speaker: SessionSpeaker):
        """
        Add or update session-speaker relationship.
        
        Args:
            session_speaker: SessionSpeaker relationship to store
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO session_speakers (
                    session_id, speaker_id, segments_count, total_duration_sec
                ) VALUES (?, ?, ?, ?)
            """, (
                session_speaker.session_id,
                session_speaker.speaker_id,
                session_speaker.segments_count,
                session_speaker.total_duration_sec
            ))
    
    def get_session_speakers(self, session_id: int) -> List[SessionSpeaker]:
        """
        Get all speakers for a session.
        
        Args:
            session_id: Session ID to retrieve speakers for
            
        Returns:
            List of SessionSpeaker objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM session_speakers WHERE session_id = ?
            """, (session_id,))
            rows = cursor.fetchall()
            
            return [
                SessionSpeaker(
                    session_id=row["session_id"],
                    speaker_id=row["speaker_id"],
                    segments_count=row["segments_count"],
                    total_duration_sec=row["total_duration_sec"]
                )
                for row in rows
            ]
    
    # Helper methods
    
    def _row_to_session_data(self, row: sqlite3.Row) -> SessionData:
        """Convert database row to SessionData object."""
        return SessionData(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            session_dir=Path(row["session_dir"]),
            recording_path=Path(row["recording_path"]) if row["recording_path"] else None,
            transcript_path=Path(row["transcript_path"]) if row["transcript_path"] else None,
            summary_path=Path(row["summary_path"]) if row["summary_path"] else None,
            metadata_path=Path(row["session_dir"]) / "metadata.json",
            temp_dir=Path(row["session_dir"]) / "temp",
            config=SessionConfig.from_json(row["config_json"]),
            state=SessionState(row["state"]),
            session_context=row["context_text"],
            partial_audio_count=0
        )
    
    def _row_to_speaker_profile(self, row: sqlite3.Row) -> SpeakerProfile:
        """Convert database row to SpeakerProfile object."""
        return SpeakerProfile(
            id=row["id"],
            name=row["name"],
            avatar_path=row["avatar_path"],
            voice_embedding_blob=row["voice_embedding"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_seen=datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None
        )
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
