"""
Event bus for UI communication.

This module provides a centralized event system using Qt signals
for decoupled communication between UI components and workers.
"""

from PySide6.QtCore import QObject, Signal
from typing import List, Dict, Any


class EventBus(QObject):
    """
    Central event bus for application-wide signals.
    
    This class uses Qt signals to enable loosely-coupled communication
    between different parts of the application (UI, workers, managers).
    """
    
    # Recording signals
    recording_frame_ready = Signal(int, float)  # frames_count, duration_sec
    recording_paused = Signal(float)  # duration_at_pause
    recording_resumed = Signal(float)  # duration_at_resume
    recording_stopped = Signal(str)  # audio_path
    recording_error = Signal(str)  # error_msg
    
    # Transcription signals
    partial_transcript_ready = Signal(list)  # list of TranscriptSegmentData
    transcription_complete = Signal(object)  # full Transcript object
    transcription_error = Signal(str)  # error_msg
    
    # Speaker identification signals
    speaker_identified = Signal(int, str, float)  # speaker_id, name, confidence
    speaker_needs_review = Signal(int, float, bytes)  # temp_id, confidence, embedding
    speaker_update_ready = Signal(dict)  # speaker_map {segment_id: speaker_id}
    
    # Diarization signals
    diarization_progress = Signal(int)  # percent
    diarization_complete = Signal(dict)  # speaker_map
    diarization_error = Signal(str)  # error_msg
    
    # Summarization signals
    summarization_progress = Signal(int)  # percent
    summarization_complete = Signal(object)  # MeetingSummary object
    summarization_error = Signal(str)  # error_msg
    
    # Reporting signals
    report_generation_progress = Signal(int)  # percent
    reports_ready = Signal(dict)  # {format: path} dict
    report_generation_error = Signal(str)  # error_msg
    
    # Stage progress signal (generic progress indicator)
    stage_progress = Signal(str, int)  # stage_name, percent
    
    # Session request signals (from UI to manager)
    start_session_requested = Signal(object)  # SessionConfig object
    pause_recording_requested = Signal()
    resume_recording_requested = Signal()
    stop_recording_requested = Signal()
    
    # Session lifecycle signals
    session_started = Signal(str)  # session_info_json
    session_completed = Signal(str, str)  # session_info_json, result_json
    session_error = Signal(str, str)  # error_title, error_message
    session_state_changed = Signal(str)  # new_state (SessionState.value)
    
    # Auto-save signals
    autosave_triggered = Signal()  # Emitted when auto-save is triggered
    autosave_complete = Signal(str)  # timestamp of last save
    autosave_error = Signal(str)  # error_msg
    
    def __init__(self, parent: QObject = None):
        """
        Initialize the event bus.
        
        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
    
    def emit_recording_frame(self, frames_count: int, duration_sec: float):
        """
        Emit recording frame update.
        
        Args:
            frames_count: Number of frames recorded
            duration_sec: Duration in seconds
        """
        self.recording_frame_ready.emit(frames_count, duration_sec)
    
    def emit_recording_paused(self, duration: float):
        """
        Emit recording paused event.
        
        Args:
            duration: Duration at pause in seconds
        """
        self.recording_paused.emit(duration)
    
    def emit_recording_resumed(self, duration: float):
        """
        Emit recording resumed event.
        
        Args:
            duration: Duration at resume in seconds
        """
        self.recording_resumed.emit(duration)
    
    def emit_recording_stopped(self, audio_path: str):
        """
        Emit recording stopped event.
        
        Args:
            audio_path: Path to saved audio file
        """
        self.recording_stopped.emit(audio_path)
    
    def emit_recording_error(self, error_msg: str):
        """
        Emit recording error.
        
        Args:
            error_msg: Error message
        """
        self.recording_error.emit(error_msg)
    
    def emit_partial_transcript(self, segments: List):
        """
        Emit partial transcript update.
        
        Args:
            segments: List of TranscriptSegmentData objects
        """
        self.partial_transcript_ready.emit(segments)
    
    def emit_transcription_complete(self, transcript: Any):
        """
        Emit transcription complete event.
        
        Args:
            transcript: Complete transcript object
        """
        self.transcription_complete.emit(transcript)
    
    def emit_transcription_error(self, error_msg: str):
        """
        Emit transcription error.
        
        Args:
            error_msg: Error message
        """
        self.transcription_error.emit(error_msg)
    
    def emit_speaker_identified(self, speaker_id: int, name: str, confidence: float):
        """
        Emit speaker identified event.
        
        Args:
            speaker_id: Identified speaker ID
            name: Speaker name
            confidence: Matching confidence (0.0 to 1.0)
        """
        self.speaker_identified.emit(speaker_id, name, confidence)
    
    def emit_speaker_needs_review(self, temp_id: int, confidence: float, embedding: bytes):
        """
        Emit speaker needs review event (moderate confidence match).
        
        Args:
            temp_id: Temporary speaker ID
            confidence: Matching confidence
            embedding: Voice embedding for review
        """
        self.speaker_needs_review.emit(temp_id, confidence, embedding)
    
    def emit_speaker_update(self, speaker_map: Dict[int, int]):
        """
        Emit speaker update event.
        
        Args:
            speaker_map: Mapping of segment/temp IDs to speaker IDs
        """
        self.speaker_update_ready.emit(speaker_map)
    
    def emit_stage_progress(self, stage_name: str, percent: int):
        """
        Emit generic stage progress.
        
        Args:
            stage_name: Name of current stage (e.g., "Transcribing", "Diarizing")
            percent: Progress percentage (0-100)
        """
        self.stage_progress.emit(stage_name, percent)
    
    def emit_start_session_requested(self, config: 'SessionConfig'):
        """
        Emit start session request (from UI).
        
        Args:
            config: SessionConfig object with settings
        """
        self.start_session_requested.emit(config)
    
    def emit_pause_recording(self):
        """Emit pause recording request."""
        self.pause_recording_requested.emit()
    
    def emit_resume_recording(self):
        """Emit resume recording request."""
        self.resume_recording_requested.emit()
    
    def emit_stop_recording(self):
        """Emit stop recording request."""
        self.stop_recording_requested.emit()
    
    def emit_session_started(self, session_info_json: str):
        """
        Emit session started event.
        
        Args:
            session_info_json: JSON string with session info
        """
        self.session_started.emit(session_info_json)
    
    def emit_session_completed(self, session_info_json: str, result_json: str):
        """
        Emit session completed event.
        
        Args:
            session_info_json: JSON string with session info
            result_json: JSON string with results and paths
        """
        self.session_completed.emit(session_info_json, result_json)
    
    def emit_session_error(self, error_title: str, error_message: str):
        """
        Emit session error.
        
        Args:
            error_title: Error title/type
            error_message: Error message
        """
        self.session_error.emit(error_title, error_message)
    
    def emit_session_state_changed(self, new_state: str):
        """
        Emit session state change.
        
        Args:
            new_state: New session state (SessionState.value)
        """
        self.session_state_changed.emit(new_state)
    
    def emit_autosave_triggered(self):
        """Emit auto-save triggered event."""
        self.autosave_triggered.emit()
    
    def emit_autosave_complete(self, timestamp: str):
        """
        Emit auto-save complete event.
        
        Args:
            timestamp: Timestamp of the save operation
        """
        self.autosave_complete.emit(timestamp)
    
    def emit_autosave_error(self, error_msg: str):
        """
        Emit auto-save error.
        
        Args:
            error_msg: Error message
        """
        self.autosave_error.emit(error_msg)
    
    def emit_summarization_complete(self, summary: Any):
        """
        Emit summarization complete event.
        
        Args:
            summary: MeetingSummary object
        """
        self.summarization_complete.emit(summary)
    
    def emit_reports_ready(self, reports: Dict[str, str]):
        """
        Emit reports ready event.
        
        Args:
            reports: Dictionary mapping format names to file paths
        """
        self.reports_ready.emit(reports)

    def emit_diarization_error(self, error_msg: str):
        """
        Emit diarization error.
        
        Args:
            error_msg: Error message
        """
        self.diarization_error.emit(error_msg)

    def emit_summarization_error(self, error_msg: str):
        """
        Emit summarization error.
        
        Args:
            error_msg: Error message
        """
        self.summarization_error.emit(error_msg)

    def emit_report_generation_error(self, error_msg: str):
        """
        Emit report generation error.
        
        Args:
            error_msg: Error message
        """
        self.report_generation_error.emit(error_msg)
