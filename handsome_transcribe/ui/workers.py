"""
Background workers for audio recording, transcription, and processing.

This module provides QRunnable workers that execute tasks in background threads
without blocking the UI.
"""

import numpy as np
import sounddevice as sd
import wave
from pathlib import Path
from typing import Optional, List
from PySide6.QtCore import QRunnable, QObject, Signal
import time

from .event_bus import EventBus
from .models import TranscriptSegmentData
from .constants import AUDIO_CHUNK_DURATION_SEC


class WorkerSignals(QObject):
    """
    Signals for worker communication.
    
    Since QRunnable doesn't inherit from QObject, we need a separate
    QObject class to hold signals.
    """
    finished = Signal()
    error = Signal(str)
    progress = Signal(int)
    result = Signal(object)


class RecorderWorker(QRunnable):
    """
    Background worker for audio recording.
    
    Records audio from microphone, generates chunks for parallel processing,
    and saves partial/final audio files.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        device_name: Optional[str] = None,
        sample_rate: int = 16000,
        channels: int = 1
    ):
        """
        Initialize recorder worker.
        
        Args:
            event_bus: EventBus for emitting signals
            device_name: Audio device name (None for default)
            sample_rate: Sample rate in Hz (default 16000 for Whisper)
            channels: Number of audio channels (default 1 for mono)
        """
        super().__init__()
        self.event_bus = event_bus
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels
        
        self._recording = False
        self._paused = False
        self._audio_buffer = []
        self._frames_count = 0
        self._duration_sec = 0.0
    
    def run(self):
        """Execute recording in background thread."""
        try:
            self._recording = True
            
            # Determine device index
            device_idx = None
            if self.device_name:
                devices = sd.query_devices()
                for idx, device in enumerate(devices):
                    if device["name"] == self.device_name:
                        device_idx = idx
                        break
            
            # Record audio until stopped
            with sd.InputStream(
                device=device_idx,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                callback=self._audio_callback
            ):
                while self._recording:
                    time.sleep(0.1)  # Check status every 100ms
                    
                    # Emit progress updates
                    if not self._paused:
                        self.event_bus.emit_recording_frame(
                            self._frames_count,
                            self._duration_sec
                        )
        
        except Exception as e:
            self.event_bus.emit_recording_error(f"Recording failed: {str(e)}")
    
    def _audio_callback(self, indata, frames, time_info, status):
        """
        Callback for audio stream processing.
        
        Args:
            indata: Input audio data
            frames: Number of frames
            time_info: Timing information
            status: Status flags
        """
        if status:
            print(f"Audio callback status: {status}")
        
        if not self._paused:
            # Add to buffer
            self._audio_buffer.append(indata.copy())
            self._frames_count += frames
            self._duration_sec = self._frames_count / self.sample_rate
    
    def stop(self):
        """Stop recording."""
        self._recording = False
    
    def pause(self):
        """Pause recording (continues capturing but doesn't process)."""
        self._paused = True
        self.event_bus.emit_recording_paused(self._duration_sec)
    
    def resume(self):
        """Resume recording."""
        self._paused = False
        self.event_bus.emit_recording_resumed(self._duration_sec)
    
    def get_audio_data(self) -> np.ndarray:
        """
        Get accumulated audio data.
        
        Returns:
            Numpy array of audio samples
        """
        if not self._audio_buffer:
            return np.array([], dtype=np.float32)
        return np.concatenate(self._audio_buffer, axis=0)
    
    def save_partial(self, path: Path, part_num: int):
        """
        Save accumulated audio to partial file without stopping recording.
        
        Args:
            path: Path to save partial audio (session_dir/temp/)
            part_num: Part number for filename
        """
        try:
            audio_data = self.get_audio_data()
            if len(audio_data) == 0:
                return
            
            # Convert float32 to int16 for WAV format
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # Save to WAV file
            with wave.open(str(path / f"part{part_num}.wav"), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_int16.tobytes())
        
        except Exception as e:
            self.event_bus.emit_recording_error(f"Failed to save partial audio: {str(e)}")
    
    def save_final(self, path: Path):
        """
        Save final complete audio file.
        
        Args:
            path: Path to save final recording (session_dir/recording.wav)
        """
        try:
            audio_data = self.get_audio_data()
            if len(audio_data) == 0:
                self.event_bus.emit_recording_error("No audio data to save")
                return
            
            # Convert float32 to int16 for WAV format
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # Save to WAV file
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_int16.tobytes())
            
            self.event_bus.emit_recording_stopped(str(path))
        
        except Exception as e:
            self.event_bus.emit_recording_error(f"Failed to save final audio: {str(e)}")


class TranscriberWorker(QRunnable):
    """
    Background worker for audio transcription using Whisper.
    
    Processes audio chunks in parallel or full audio file after recording.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        audio_path: Path,
        output_path: Path,
        model_name: str = "base",
        language: Optional[str] = None
    ):
        """
        Initialize transcriber worker.
        
        Args:
            event_bus: EventBus for emitting signals
            audio_path: Path to audio file to transcribe
            output_path: Path to save transcript
            model_name: Whisper model name (default "base")
            language: Optional language code (auto-detect if None)
        """
        super().__init__()
        self.event_bus = event_bus
        self.audio_path = audio_path
        self.output_path = output_path
        self.model_name = model_name
        self.language = language
    
    def run(self):
        """Execute transcription in background thread."""
        try:
            # Import here to avoid loading Whisper at module import time
            import whisper
            
            # Load model
            self.event_bus.emit_stage_progress("Transcribing", 25)
            model = whisper.load_model(self.model_name)
            
            # Transcribe audio
            self.event_bus.emit_stage_progress("Transcribing", 50)
            result = model.transcribe(
                str(self.audio_path),
                language=self.language,
                verbose=False
            )
            
            # Process segments
            self.event_bus.emit_stage_progress("Transcribing", 75)
            segments = []
            for seg in result.get("segments", []):
                segment = TranscriptSegmentData(
                    start_time=seg["start"],
                    end_time=seg["end"],
                    text=seg["text"].strip(),
                    confidence=seg.get("no_speech_prob", 0.0)
                )
                segments.append(segment)
            
            # Save transcript to file
            self._save_transcript(segments)
            
            # Emit completion
            self.event_bus.emit_stage_progress("Transcribing", 100)
            self.event_bus.emit_partial_transcript(segments)
            self.event_bus.emit_transcription_complete(result)
        
        except Exception as e:
            self.event_bus.emit_transcription_error(f"Transcription failed: {str(e)}")
    
    def _save_transcript(self, segments: List[TranscriptSegmentData]):
        """
        Save transcript to text file.
        
        Args:
            segments: List of transcript segments
        """
        with open(self.output_path, "w", encoding="utf-8") as f:
            for seg in segments:
                # Format: [MM:SS-MM:SS] Text
                start_min, start_sec = divmod(int(seg.start_time), 60)
                end_min, end_sec = divmod(int(seg.end_time), 60)
                f.write(f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}] {seg.text}\n")


class SpeakerEmbeddingWorker(QRunnable):
    """
    Background worker for extracting speaker embeddings from audio chunks.
    
    Processes audio to generate voice embeddings for speaker identification.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        audio_chunk: np.ndarray,
        chunk_id: int,
        sample_rate: int = 16000
    ):
        """
        Initialize speaker embedding worker.
        
        Args:
            event_bus: EventBus for emitting signals
            audio_chunk: Audio data chunk  
            chunk_id: Unique identifier for this chunk
            sample_rate: Audio sample rate
        """
        super().__init__()
        self.event_bus = event_bus
        self.audio_chunk = audio_chunk
        self.chunk_id = chunk_id
        self.sample_rate = sample_rate
    
    def run(self):
        """Execute embedding extraction in background thread."""
        try:
            # Placeholder: in a real implementation, this would use a model
            # like pyannote or resemblyzer to extract embeddings
            
            # For MVP, generate a simple placeholder embedding
            # TODO: Replace with actual embedding extraction
            embedding = self._extract_placeholder_embedding()
            
            # Emit result (this would trigger speaker matching in SessionManager)
            # Format: (chunk_id, embedding)
            # The SessionManager will handle matching via SpeakerManager
            
        except Exception as e:
            self.event_bus.emit_session_error(f"Embedding extraction failed: {str(e)}", "speaker_embedding")
    
    def _extract_placeholder_embedding(self) -> np.ndarray:
        """
        Generate placeholder embedding for testing.
        
        In real implementation, replace with actual embedding model.
        
        Returns:
            Placeholder embedding vector
        """
        # Generate a random embedding vector (512 dimensions)
        return np.random.randn(512).astype(np.float32)


class DiarizerWorker(QRunnable):
    """
    Background worker for speaker diarization using pyannote.
    
    Identifies speaker segments in audio file.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        audio_path: Path,
        hf_token: str
    ):
        """
        Initialize diarizer worker.
        
        Args:
            event_bus: EventBus for emitting signals
            audio_path: Path to audio file
            hf_token: Hugging Face token for pyannote
        """
        super().__init__()
        self.event_bus = event_bus
        self.audio_path = audio_path
        self.hf_token = hf_token
    
    def run(self):
        """Execute diarization in background thread."""
        try:
            # Import here to avoid loading pyannote at module import time
            from pyannote.audio import Pipeline
            
            self.event_bus.emit_stage_progress("Diarizing", 25)
            
            # Load pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization",
                use_auth_token=self.hf_token
            )
            
            self.event_bus.emit_stage_progress("Diarizing", 50)
            
            # Run diarization
            diarization = pipeline(str(self.audio_path))
            
            self.event_bus.emit_stage_progress("Diarizing", 75)
            
            # Convert to speaker map format
            speaker_map = {}
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                # Map time segments to speaker labels
                segment_key = f"{turn.start:.2f}-{turn.end:.2f}"
                speaker_map[segment_key] = speaker
            
            self.event_bus.emit_stage_progress("Diarizing", 100)
            self.event_bus.emit_speaker_update(speaker_map)
        
        except Exception as e:
            self.event_bus.emit_session_error(f"Diarization failed: {str(e)}", "diarization")


class SummarizerWorker(QRunnable):
    """
    Background worker for meeting summarization.
    
    Generates summaries from transcripts using extractive or abstractive methods.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        transcript_path: Path,
        output_path: Path,
        use_transformers: bool = True
    ):
        """
        Initialize summarizer worker.
        
        Args:
            event_bus: EventBus for emitting signals
            transcript_path: Path to transcript file
            output_path: Path to save summary
            use_transformers: Whether to use transformers (abstractive) or extractive
        """
        super().__init__()
        self.event_bus = event_bus
        self.transcript_path = transcript_path
        self.output_path = output_path
        self.use_transformers = use_transformers
    
    def run(self):
        """Execute summarization in background thread."""
        try:
            # Read transcript
            with open(self.transcript_path, "r", encoding="utf-8") as f:
                transcript_text = f.read()
            
            self.event_bus.emit_stage_progress("Summarizing", 50)
            
            # Generate summary (placeholder - integrate with actual summarizer)
            summary = self._generate_placeholder_summary(transcript_text)
            
            # Save summary
            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write(summary)
            
            self.event_bus.emit_stage_progress("Summarizing", 100)
            # self.event_bus.emit_summarization_complete(summary_obj)
        
        except Exception as e:
            self.event_bus.emit_session_error(f"Summarization failed: {str(e)}", "summarization")
    
    def _generate_placeholder_summary(self, text: str) -> str:
        """
        Generate placeholder summary.
        
        TODO: Integrate with actual MeetingSummarizer from handsome_transcribe.summarization
        
        Args:
            text: Transcript text
            
        Returns:
            Summary text in markdown format
        """
        return f"""# Meeting Summary

## Overview
This is a placeholder summary.

## Key Points
- Point 1
- Point 2

## Transcript
{text[:500]}...
"""


class ReporterWorker(QRunnable):
    """
    Background worker for generating reports (PDF, Markdown, JSON).
    
    Creates various report formats from session data.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        session_dir: Path,
        session_id: int,
        reports_dir: Path
    ):
        """
        Initialize reporter worker.
        
        Args:
            event_bus: EventBus for emitting signals
            session_dir: Session directory containing transcript and summary
            session_id: Session ID for report naming
            reports_dir: Directory to save reports
        """
        super().__init__()
        self.event_bus = event_bus
        self.session_dir = session_dir
        self.session_id = session_id
        self.reports_dir = reports_dir
    
    def run(self):
        """Execute report generation in background thread."""
        try:
            reports = {}
            
            # Generate Markdown report
            self.event_bus.emit_stage_progress("Generating reports", 33)
            md_path = self.reports_dir / f"session_{self.session_id}_report.md"
            self._generate_markdown_report(md_path)
            reports["markdown"] = md_path
            
            # Generate JSON report
            self.event_bus.emit_stage_progress("Generating reports", 66)
            json_path = self.reports_dir / f"session_{self.session_id}_report.json"
            self._generate_json_report(json_path)
            reports["json"] = json_path
            
            # Generate PDF report (placeholder)
            self.event_bus.emit_stage_progress("Generating reports", 100)
            pdf_path = self.reports_dir / f"session_{self.session_id}_report.pdf"
            # TODO: Integrate with actual ReportGenerator
            reports["pdf"] = pdf_path
            
            # Emit completion
            # self.event_bus.reports_ready.emit(reports)
        
        except Exception as e:
            self.event_bus.emit_session_error(f"Report generation failed: {str(e)}", "reporting")
    
    def _generate_markdown_report(self, output_path: Path):
        """Generate markdown report (placeholder)."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Session {self.session_id} Report\n\n")
            f.write("Report generated.\n")
    
    def _generate_json_report(self, output_path: Path):
        """Generate JSON report (placeholder)."""
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"session_id": self.session_id, "status": "complete"}, f, indent=2)
