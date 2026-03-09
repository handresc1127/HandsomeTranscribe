"""
Session manager for coordinating transcription sessions.

This module orchestrates the complete session lifecycle including recording,
transcription, diarization, summarization, and reporting with multi-threading
and auto-save capabilities.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QObject, QTimer, QThreadPool, Qt

from .models import SessionData, SessionConfig, SessionState, TranscriptSegmentData
from .database import Database
from .speaker_manager import SpeakerManager
from .event_bus import EventBus
from .workers import (
    RecorderWorker, TranscriberWorker, SpeakerEmbeddingWorker,
    DiarizerWorker, SummarizerWorker, ReporterWorker
)
from .exceptions import SessionError, ActiveSessionError
from .constants import (
    SESSIONS_DIR, REPORTS_DIR, SESSION_DIR_FORMAT,
    RECORDING_FILENAME, TRANSCRIPT_FILENAME, SUMMARY_FILENAME,
    METADATA_FILENAME, TEMP_DIR_NAME,
    AUTO_SAVE_INTERVAL_MS
)


class SessionManager(QObject):
    """
    Manages transcriptionRecorder sessions with multi-threading and auto-save.
    
    Responsibilities:
    - Session lifecycle management (start, pause, resume, stop)
    - Worker coordination (recorder, transcriber, diarizer, summarizer, reporter)
    - State transitions and validation
    - Auto-save every 2 minutes with triggers on speaker change, pause, finalization
    - Single active session enforcement
    """
    
    def __init__(
        self,
        config: SessionConfig,
        event_bus: EventBus,
        database: Database,
        speaker_manager: SpeakerManager
    ):
        """
        Initialize session manager.
        
        Args:
            config: Session configuration
            event_bus: Event bus for signals
            database: Database instance
            speaker_manager: Speaker manager instance
        """
        super().__init__()
        
        self.config = config
        self.event_bus = event_bus
        self.database = database
        self.speaker_manager = speaker_manager
        
        self.current_session: Optional[SessionData] = None
        self.current_state = SessionState.IDLE
        
        # Worker references
        self.recorder_worker: Optional[RecorderWorker] = None
        self.transcriber_worker: Optional[TranscriberWorker] = None
        
        # Thread pool for workers
        self._thread_pool = QThreadPool.globalInstance()
        
        # Auto-save timer
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._auto_save_progress)
        self._autosave_timer.setInterval(AUTO_SAVE_INTERVAL_MS)  # 2 minutes
        
        # Track current speaker for change detection
        self._current_speaker_id: Optional[int] = None
        
        # Ensure output directories exist
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    def start_session(self) -> SessionData:
        """
        Start a new recording session.
        
        This method:
        1. Validates no active session exists
        2. Creates session directory structure
        3. Initializes SessionData
        4. Saves session to database
        5. Starts recorder worker
        6. Starts auto-save timer
        
        Returns:
            Created SessionData
            
        Raises:
            ActiveSessionError: If a session is already active
        """
        # Validate no active session
        if self.current_state not in (SessionState.IDLE, SessionState.COMPLETED, SessionState.ERROR):
            raise ActiveSessionError(
                f"Cannot start new session: current state is {self.current_state.value}"
            )
        
        # Check database for active sessions
        active_db_session = self.database.get_active_session()
        if active_db_session:
            raise ActiveSessionError(
                f"Cannot start new session: session {active_db_session.id} is still active"
            )
        
        # Create session directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self._create_session_directory(timestamp)
        
        # Initialize session data
        session_data = SessionData(
            id=-1,  # Will be set by database
            created_at=datetime.now(),
            session_dir=session_dir,
            recording_path=session_dir / RECORDING_FILENAME,
            transcript_path=session_dir / TRANSCRIPT_FILENAME,
            summary_path=session_dir / SUMMARY_FILENAME if self.config.habilitar_resumen else None,
            metadata_path=session_dir / METADATA_FILENAME,
            temp_dir=session_dir / TEMP_DIR_NAME,
            config=self.config,
            state=SessionState.RECORDING,
            session_context=self.config.session_context,
            partial_audio_count=0
        )
        
        # Save to database
        session_data.id = self.database.create_session(session_data)
        
        # Set as current session
        self.current_session = session_data
        self._transition_state(SessionState.RECORDING)
        
        # Start recorder worker
        self.recorder_worker = RecorderWorker(
            event_bus=self.event_bus,
            device_name=self.config.dispositivo_audio,
            sample_rate=16000,
            channels=1
        )
        self._thread_pool.start(self.recorder_worker)
        
        # Start auto-save timer
        self._start_autosave_timer()
        
        # Emit event
        self.event_bus.emit_session_started(session_data.id)
        
        return session_data
    
    def pause_recording(self):
        """
        Pause recording without stopping.
        
        This method:
        1. Pauses recorder worker
        2. Triggers auto-save
        3. Saves partial audio
        4. Transitions to PAUSED state
        """
        if self.current_state != SessionState.RECORDING:
            raise SessionError(f"Cannot pause: current state is {self.current_state.value}")
        
        if not self.recorder_worker:
            raise SessionError("No active recorder")
        
        # Pause recorder
        self.recorder_worker.pause()
        
        # Save partial audio
        self._save_partial_audio()
        
        # Trigger auto-save
        self._auto_save_progress()
        
        # Transition state
        self._transition_state(SessionState.PAUSED)
    
    def resume_recording(self):
        """
        Resume recording from paused state.
        
        This method:
        1. Resumes recorder worker
        2. Transitions back to RECORDING state
        """
        if self.current_state != SessionState.PAUSED:
            raise SessionError(f"Cannot resume: current state is {self.current_state.value}")
        
        if not self.recorder_worker:
            raise SessionError("No active recorder")
        
        # Resume recorder
        self.recorder_worker.resume()
        
        # Transition state
        self._transition_state(SessionState.RECORDING)
    
    def stop_recording(self):
        """
        Stop recording and begin processing pipeline.
        
        This method:
        1. Stops recorder worker
        2. Saves final consolidated audio
        3. Triggers final auto-save
        4. Starts transcription worker
        5. Stops auto-save timer
        """
        if self.current_state not in (SessionState.RECORDING, SessionState.PAUSED):
            raise SessionError(f"Cannot stop: current state is {self.current_state.value}")
        
        if not self.recorder_worker:
            raise SessionError("No active recorder")
        
        # Stop recorder
        self.recorder_worker.stop()
        
        # Save final audio
        if self.current_session:
            self.recorder_worker.save_final(self.current_session.recording_path)
            
            # Consolidate partial audio files (already in temp/)
            # Final audio is saved to recording.wav
            
            # Final auto-save
            self._auto_save_progress()
        
        # Stop auto-save timer
        self._stop_autosave_timer()
        
        # Start transcription
        self._start_transcription()
    
    def cancel_session(self):
        """
        Cancel current session and cleanup.
        
        This method:
        1. Stops all workers
        2. Stops auto-save timer
        3. Updates session state to ERROR
        4. Transitions to IDLE
        """
        if self.recorder_worker:
            self.recorder_worker.stop()
        
        self._stop_autosave_timer()
        
        if self.current_session:
            self.database.update_session(
                self.current_session.id,
                state=SessionState.ERROR
            )
        
        self._transition_state(SessionState.IDLE)
        self.current_session = None
    
    def get_current_state(self) -> SessionState:
        """Get current session state."""
        return self.current_state
    
    def get_current_session(self) -> Optional[SessionData]:
        """Get current session data."""
        return self.current_session
    
    # Private methods
    
    def _transition_state(self, new_state: SessionState):
        """
        Transition to a new state with validation.
        
        Args:
            new_state: Target state
            
        Raises:
            SessionError: If transition is invalid
        """
        # Valid transitions map
        valid_transitions = {
            SessionState.IDLE: [SessionState.RECORDING],
            SessionState.RECORDING: [SessionState.PAUSED, SessionState.TRANSCRIBING, SessionState.ERROR],
            SessionState.PAUSED: [SessionState.RECORDING, SessionState.TRANSCRIBING, SessionState.ERROR],
            SessionState.TRANSCRIBING: [SessionState.DIARIZING, SessionState.SUMMARIZING, SessionState.COMPLETED, SessionState.ERROR],
            SessionState.DIARIZING: [SessionState.SUMMARIZING, SessionState.COMPLETED, SessionState.ERROR],
            SessionState.SUMMARIZING: [SessionState.COMPLETED, SessionState.ERROR],
            SessionState.COMPLETED: [SessionState.IDLE],
            SessionState.ERROR: [SessionState.IDLE]
        }
        
        if new_state not in valid_transitions.get(self.current_state, []):
            raise SessionError(
                f"Invalid state transition: {self.current_state.value} -> {new_state.value}"
            )
        
        old_state = self.current_state
        self.current_state = new_state
        
        # Update database if session exists
        if self.current_session:
            self.database.update_session(self.current_session.id, state=new_state)
        
        # Emit event
        self.event_bus.emit_session_state_changed(new_state.value)
    
    def _create_session_directory(self, timestamp: str) -> Path:
        """
        Create session directory structure.
        
        Args format: YYYYMMDD_HHMMSS
            
        Returns:
            Path to created session directory
        """
        session_name = f"session_{timestamp}"
        session_dir = SESSIONS_DIR / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Create temp subdirectory
        temp_dir = session_dir / TEMP_DIR_NAME
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        return session_dir
    
    def _save_partial_audio(self):
        """Save partial audio to temp directory."""
        if not self.current_session or not self.recorder_worker:
            return
        
        self.current_session.partial_audio_count += 1
        self.recorder_worker.save_partial(
            self.current_session.temp_dir,
            self.current_session.partial_audio_count
        )
    
    def _auto_save_progress(self):
        """
        Auto-save current session progress.
        
        This method:
        1. Emits autosave_triggered signal
        2. Updates session in database
        3. Saves accumulated transcript segments
        4. Emits autosave_complete signal
        """
        if not self.current_session:
            return
        
        try:
            self.event_bus.emit_autosave_triggered()
            
            # Update session state in database
            self.database.update_session(
                self.current_session.id,
                state=self.current_state
            )
            
            # Save metadata
            self._save_metadata()
            
            timestamp = datetime.now().isoformat()
            self.event_bus.emit_autosave_complete(timestamp)
        
        except Exception as e:
            self.event_bus.emit_autosave_error(f"Auto-save failed: {str(e)}")
    
    def _save_metadata(self):
        """Save session metadata to JSON file."""
        if not self.current_session:
            return
        
        metadata = {
            "session_id": self.current_session.id,
            "created_at": self.current_session.created_at.isoformat(),
            "state": self.current_state.value,
            "config": self.current_session.config.to_dict(),
            "partial_audio_count": self.current_session.partial_audio_count
        }
        
        with open(self.current_session.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    
    def _on_speaker_change(self, old_speaker_id: Optional[int], new_speaker_id: int):
        """
        Handle speaker change event (trigger auto-save).
        
        Args:
            old_speaker_id: Previous speaker ID
            new_speaker_id: New speaker ID
        """
        self._current_speaker_id = new_speaker_id
        
        # Trigger auto-save on speaker change
        self._auto_save_progress()
    
    def _start_autosave_timer(self):
        """Start the auto-save timer."""
        if not self._autosave_timer.isActive():
            self._autosave_timer.start()
    
    def _stop_autosave_timer(self):
        """Stop the auto-save timer."""
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
    
    def _start_transcription(self):
        """Start transcription worker after recording completes."""
        if not self.current_session:
            return
        
        self._transition_state(SessionState.TRANSCRIBING)
        
        self.transcriber_worker = TranscriberWorker(
            event_bus=self.event_bus,
            audio_path=self.current_session.recording_path,
            output_path=self.current_session.transcript_path,
            model_name=self.config.modelo_whisper
        )
        
        # Connect transcription complete -> next stage
        self.event_bus.transcription_complete.connect(self._on_transcription_complete, Qt.ConnectionType.QueuedConnection)
        
        self._thread_pool.start(self.transcriber_worker)
    
    def _start_diarization(self):
        """Start diarization worker if enabled."""
        if not self.current_session or not self.config.habilitar_diarizacion:
            # Skip to next stage
            self._start_summarization()
            return
        
        if not self.config.hf_token:
            self.event_bus.emit_session_error(
                "Diarization enabled but HF_TOKEN not provided",
                "diarization"
            )
            self._start_summarization()
            return
        
        self._transition_state(SessionState.DIARIZING)
        
        diarizer_worker = DiarizerWorker(
            event_bus=self.event_bus,
            audio_path=self.current_session.recording_path,
            hf_token=self.config.hf_token
        )
        
        # Connect diarization complete -> next stage
        self.event_bus.speaker_update_ready.connect(self._on_diarization_complete, Qt.ConnectionType.QueuedConnection)
        
        self._thread_pool.start(diarizer_worker)
    
    def _start_summarization(self):
        """Start summarization worker if enabled."""
        if not self.current_session or not self.config.habilitar_resumen:
            # Skip to reporting
            self._start_reporting()
            return
        
        self._transition_state(SessionState.SUMMARIZING)
        
        summarizer_worker = SummarizerWorker(
            event_bus=self.event_bus,
            transcript_path=self.current_session.transcript_path,
            output_path=self.current_session.summary_path,
            use_transformers=True
        )
        
        # Connect summarization complete -> next stage
        self.event_bus.summarization_complete.connect(self._on_summarization_complete, Qt.ConnectionType.QueuedConnection)
        
        self._thread_pool.start(summarizer_worker)
    
    def _start_reporting(self):
        """Start report generation worker."""
        if not self.current_session:
            return
        
        reporter_worker = ReporterWorker(
            event_bus=self.event_bus,
            session_dir=self.current_session.session_dir,
            session_id=self.current_session.id,
            reports_dir=REPORTS_DIR
        )
        
        # Connect reports ready -> completion
        self.event_bus.reports_ready.connect(self._on_reports_ready, Qt.ConnectionType.QueuedConnection)
        
        self._thread_pool.start(reporter_worker)
    
    def _complete_session(self):
        """Complete session and emit results."""
        if not self.current_session:
            return
        
        self._transition_state(SessionState.COMPLETED)
        
        # Prepare results
        results = {
            "session_id": self.current_session.id,
            "recording_path": str(self.current_session.recording_path),
            "transcript_path": str(self.current_session.transcript_path),
            "summary_path": str(self.current_session.summary_path) if self.current_session.summary_path else None,
            "session_dir": str(self.current_session.session_dir)
        }
        
        self.event_bus.emit_session_completed(results)
        
        # Reset for next session
        self.current_session = None
        self._transition_state(SessionState.IDLE)
    
    # -------------------------------------------------------------------------
    # Worker completion callbacks
    # -------------------------------------------------------------------------
    
    def _on_transcription_complete(self, transcript):
        """
        Handle transcription completion and move to next stage.
        
        Args:
            transcript: Whisper transcript result
        """
        # Disconnect signal to avoid duplicate calls
        try:
            self.event_bus.transcription_complete.disconnect(self._on_transcription_complete)
        except RuntimeError:
            pass  # Already disconnected
        
        # Move to next stage: diarization if enabled, else summarization
        self._start_diarization()
    
    def _on_diarization_complete(self, speaker_map):
        """
        Handle diarization completion and move to next stage.
        
        Args:
            speaker_map: Speaker identification map
        """
        # Disconnect signal
        try:
            self.event_bus.speaker_update_ready.disconnect(self._on_diarization_complete)
        except RuntimeError:
            pass
        
        # Move to summarization
        self._start_summarization()
    
    def _on_summarization_complete(self, summary):
        """
        Handle summarization completion and move to next stage.
        
        Args:
            summary: MeetingSummary object
        """
        # Disconnect signal
        try:
            self.event_bus.summarization_complete.disconnect(self._on_summarization_complete)
        except RuntimeError:
            pass
        
        # Move to reporting
        self._start_reporting()
    
    def _on_reports_ready(self, reports):
        """
        Handle report generation completion and complete session.
        
        Args:
            reports: Dict of generated report paths
        """
        # Disconnect signal
        try:
            self.event_bus.reports_ready.disconnect(self._on_reports_ready)
        except RuntimeError:
            pass
        
        # Complete session
        self._complete_session()
