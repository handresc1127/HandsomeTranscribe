"""
Data models for the UI layer.

This module defines dataclasses for session configurations, session data,
speaker profiles, and transcript segments.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List
import json


class SessionState(Enum):
    """Enumeration of session states."""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class SessionConfig:
    """Configuration for a transcription session."""
    modelo_whisper: str = "base"
    habilitar_diarizacion: bool = False
    habilitar_resumen: bool = False
    dispositivo_audio: Optional[str] = None
    hf_token: Optional[str] = None
    session_context: Optional[str] = None  # Optional context text (markdown/plain text)
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionConfig":
        """Create configuration from dictionary."""
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "SessionConfig":
        """Create configuration from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SessionData:
    """Data model for a transcription session."""
    id: int
    created_at: datetime
    session_dir: Path
    recording_path: Path
    transcript_path: Path
    summary_path: Optional[Path]
    metadata_path: Path
    temp_dir: Path
    config: SessionConfig
    state: SessionState
    session_context: Optional[str] = None
    partial_audio_count: int = 0
    
    def __post_init__(self):
        """Ensure paths are Path objects."""
        if not isinstance(self.session_dir, Path):
            self.session_dir = Path(self.session_dir)
        if not isinstance(self.recording_path, Path):
            self.recording_path = Path(self.recording_path)
        if not isinstance(self.transcript_path, Path):
            self.transcript_path = Path(self.transcript_path)
        if self.summary_path is not None and not isinstance(self.summary_path, Path):
            self.summary_path = Path(self.summary_path)
        if not isinstance(self.metadata_path, Path):
            self.metadata_path = Path(self.metadata_path)
        if not isinstance(self.temp_dir, Path):
            self.temp_dir = Path(self.temp_dir)
        if not isinstance(self.state, SessionState):
            self.state = SessionState(self.state)
    
    def to_dict(self) -> dict:
        """Convert session data to dictionary."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "session_dir": str(self.session_dir),
            "recording_path": str(self.recording_path),
            "transcript_path": str(self.transcript_path),
            "summary_path": str(self.summary_path) if self.summary_path else None,
            "metadata_path": str(self.metadata_path),
            "temp_dir": str(self.temp_dir),
            "config": self.config.to_dict(),
            "state": self.state.value,
            "session_context": self.session_context,
            "partial_audio_count": self.partial_audio_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        """Create session data from dictionary."""
        data_copy = data.copy()
        data_copy["created_at"] = datetime.fromisoformat(data["created_at"])
        data_copy["config"] = SessionConfig.from_dict(data["config"])
        data_copy["state"] = SessionState(data["state"])
        return cls(**data_copy)
    
    def to_json(self) -> str:
        """Convert session data to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "SessionData":
        """Create session data from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class TranscriptSegmentData:
    """Data model for a transcript segment."""
    start_time: float
    end_time: float
    text: str
    speaker_id: Optional[int] = None
    confidence: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert segment to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptSegmentData":
        """Create segment from dictionary."""
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert segment to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "TranscriptSegmentData":
        """Create segment from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SpeakerProfile:
    """Data model for a speaker profile."""
    id: int
    name: str
    avatar_path: Optional[str] = None
    voice_embedding_blob: Optional[bytes] = None
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_seen: Optional[datetime] = None
    
    def __post_init__(self):
        """Ensure datetime objects are properly typed."""
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.last_seen, str):
            self.last_seen = datetime.fromisoformat(self.last_seen)
    
    def to_dict(self) -> dict:
        """Convert speaker profile to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "avatar_path": self.avatar_path,
            "voice_embedding_blob": self.voice_embedding_blob.hex() if self.voice_embedding_blob else None,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SpeakerProfile":
        """Create speaker profile from dictionary."""
        data_copy = data.copy()
        if data.get("voice_embedding_blob") and isinstance(data["voice_embedding_blob"], str):
            data_copy["voice_embedding_blob"] = bytes.fromhex(data["voice_embedding_blob"])
        return cls(**data_copy)
    
    def to_json(self) -> str:
        """Convert speaker profile to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "SpeakerProfile":
        """Create speaker profile from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SpeakerMatch:
    """Data model for speaker matching result."""
    confidence: float
    speaker_id: int
    is_new: bool
    
    def to_dict(self) -> dict:
        """Convert match result to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SpeakerMatch":
        """Create match result from dictionary."""
        return cls(**data)


@dataclass
class SessionSpeaker:
    """Data model for session-speaker relationship."""
    session_id: int
    speaker_id: int
    segments_count: int = 0
    total_duration_sec: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert session-speaker to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionSpeaker":
        """Create session-speaker from dictionary."""
        return cls(**data)
