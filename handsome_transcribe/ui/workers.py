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
from .logger import AppLogger
from .config_manager import ConfigManager


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
            logger = AppLogger.get_logger("ui.workers.recorder")
            self._recording = True
            
            # Determine device index
            device_idx = None
            if self.device_name:
                devices = ConfigManager().get_audio_devices()
                for device in devices:
                    if device["name"] == self.device_name:
                        device_idx = device["index"]
                        logger.info(
                            "Resolved audio device '%s' to index %s",
                            self.device_name,
                            device_idx
                        )
                        break
                if device_idx is None:
                    logger.warning(
                        "Audio device '%s' not found. Using default input device.",
                        self.device_name
                    )
            else:
                logger.info("No audio device selected. Using default input device.")
            
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
            logger = AppLogger.get_logger("ui.workers.recorder")
            logger.error("Recording failed: %s", e)
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
        language: Optional[str] = None,
        emit_progress: bool = True,
        emit_complete: bool = True
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
        self.emit_progress = emit_progress
        self.emit_complete = emit_complete
    
    def run(self):
        """Execute transcription in background thread."""
        try:
            logger = AppLogger.get_logger("ui.workers.transcriber")
            logger.debug(f"TranscriberWorker.run() started: audio={self.audio_path}, model={self.model_name}, lang={self.language}")
            # Import here to avoid loading Whisper at module import time
            import whisper
            
            # Load model
            if self.emit_progress:
                self.event_bus.emit_stage_progress("Transcribing", 25)
            model = whisper.load_model(self.model_name)
            logger.debug(f"Whisper model '{self.model_name}' loaded")
            
            # Transcribe audio
            if self.emit_progress:
                self.event_bus.emit_stage_progress("Transcribing", 50)
            result = model.transcribe(
                str(self.audio_path),
                language=self.language,
                verbose=False
            )
            logger.debug(f"Transcription finished: {len(result.get('segments', []))} segments")
            
            # Process segments
            if self.emit_progress:
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
            if self.emit_progress:
                self.event_bus.emit_stage_progress("Transcribing", 100)
            self.event_bus.emit_partial_transcript(segments)
            if self.emit_complete:
                self.event_bus.emit_transcription_complete(result)
        
        except Exception as e:
            logger = AppLogger.get_logger("ui.workers.transcriber")
            logger.error(f"TranscriberWorker failed: {e}")
            self.event_bus.emit_transcription_error(f"Transcription failed: {str(e)}")
    
    def _save_transcript(self, segments: List[TranscriptSegmentData]):
        """
        Save transcript to text file and JSON.
        
        Args:
            segments: List of transcript segments
        """
        # Save human-readable text format
        with open(self.output_path, "w", encoding="utf-8") as f:
            for seg in segments:
                # Format: [MM:SS-MM:SS] Text
                start_min, start_sec = divmod(int(seg.start_time), 60)
                end_min, end_sec = divmod(int(seg.end_time), 60)
                f.write(f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}] {seg.text}\n")
        
        # Save JSON format for programmatic access (used by Summarizer)
        json_path = self.output_path.with_suffix('.json')
        transcript_dict = {
            "audio_file": str(self.audio_path),
            "language": self.language or "auto",
            "segments": [
                {
                    "start": seg.start_time,
                    "end": seg.end_time,
                    "text": seg.text,
                    "speaker": str(seg.speaker_id) if seg.speaker_id is not None else "Unknown"
                }
                for seg in segments
            ]
        }
        
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(transcript_dict, f, indent=2, ensure_ascii=False)


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
            logger = AppLogger.get_logger("ui.workers.diarizer")
            logger.debug(f"DiarizerWorker.run() started: audio={self.audio_path}")
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
            logger.debug(f"Diarization finished: {len(speaker_map)} segments")
            self.event_bus.emit_speaker_update(speaker_map)
        
        except Exception as e:
            logger = AppLogger.get_logger("ui.workers.diarizer")
            logger.error(f"DiarizerWorker failed: {e}")
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
            transcript_path: Path to transcript file (.txt, will read .json)
            output_path: Path to save summary markdown
            use_transformers: Whether to use transformers (abstractive) or extractive
        """
        super().__init__()
        self.event_bus = event_bus
        # Use JSON transcript for structured data
        self.transcript_json_path = transcript_path.with_suffix('.json')
        self.output_path = output_path
        self.use_transformers = use_transformers
    
    def run(self):
        """Execute summarization in background thread."""
        try:
            logger = AppLogger.get_logger("ui.workers.summarizer")
            logger.debug(f"SummarizerWorker.run() started: transcript={self.transcript_json_path}")
            import json
            from handsome_transcribe.summarization.meeting_summarizer import MeetingSummarizer
            from handsome_transcribe.transcription.whisper_transcriber import Transcript, TranscriptSegment
            
            self.event_bus.emit_stage_progress("Summarizing", 25)
            
            # Load transcript from JSON
            with open(self.transcript_json_path, "r", encoding="utf-8") as f:
                transcript_data = json.load(f)
            
            # Construct Transcript object
            segments = [
                TranscriptSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"],
                    speaker=seg.get("speaker") or "Unknown"
                )
                for seg in transcript_data["segments"]
            ]
            transcript = Transcript(
                audio_file=transcript_data["audio_file"],
                language=transcript_data["language"],
                segments=segments
            )
            
            self.event_bus.emit_stage_progress("Summarizing", 50)
            
            # Run summarization with MeetingSummarizer
            summarizer = MeetingSummarizer(use_transformers=self.use_transformers)
            summary = summarizer.summarize(transcript)
            
            self.event_bus.emit_stage_progress("Summarizing", 75)
            
            # Format summary as markdown
            markdown_content = self._format_summary_markdown(summary)
            
            # Save summary
            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            self.event_bus.emit_stage_progress("Summarizing", 100)
            logger.debug("Summarization finished")
            # Emit completion signal with summary object
            self.event_bus.emit_summarization_complete(summary)
        
        except Exception as e:
            logger = AppLogger.get_logger("ui.workers.summarizer")
            logger.error(f"SummarizerWorker failed: {e}")
            self.event_bus.emit_session_error(f"Summarization failed: {str(e)}", "summarization")
    
    def _format_summary_markdown(self, summary) -> str:
        """
        Format MeetingSummary object as markdown.
        
        Args:
            summary: MeetingSummary object
            
        Returns:
            Markdown formatted summary
        """
        lines = ["# Meeting Summary", "", summary.summary, ""]
        
        if summary.key_topics:
            lines.append("## Key Topics")
            for topic in summary.key_topics:
                lines.append(f"- {topic}")
            lines.append("")
        
        if summary.action_items:
            lines.append("## Action Items")
            for item in summary.action_items:
                lines.append(f"- {item}")
            lines.append("")
        
        if summary.decisions:
            lines.append("## Decisions")
            for decision in summary.decisions:
                lines.append(f"- {decision}")
            lines.append("")
        
        return "\n".join(lines)


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
            logger = AppLogger.get_logger("ui.workers.reporter")
            logger.debug(f"ReporterWorker.run() started: session_dir={self.session_dir}")
            import json
            from handsome_transcribe.reporting.report_generator import ReportGenerator
            from handsome_transcribe.summarization.meeting_summarizer import MeetingSummary
            from handsome_transcribe.transcription.whisper_transcriber import Transcript, TranscriptSegment
            
            self.event_bus.emit_stage_progress("Generating reports", 20)
            
            # Load transcript from JSON
            transcript_json = self.session_dir / "transcript.json"
            with open(transcript_json, "r", encoding="utf-8") as f:
                transcript_data = json.load(f)
            
            segments = [
                TranscriptSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"],
                    speaker=seg.get("speaker") or "Unknown"
                )
                for seg in transcript_data["segments"]
            ]
            transcript = Transcript(
                audio_file=transcript_data["audio_file"],
                language=transcript_data["language"],
                segments=segments
            )
            
            self.event_bus.emit_stage_progress("Generating reports", 40)
            
            # Load summary from markdown (parse back to MeetingSummary)
            summary_md = self.session_dir / "summary.md"
            if summary_md.exists():
                summary = self._parse_summary_markdown(summary_md)
            else:
                logger.debug("No summary.md found (summarization skipped), using empty summary")
                summary = MeetingSummary(
                    summary="(Summarization was not enabled for this session)",
                    key_topics=[],
                    action_items=[],
                    decisions=[],
                )
            
            self.event_bus.emit_stage_progress("Generating reports", 60)
            
            # Generate reports using ReportGenerator
            generator = ReportGenerator(output_dir=self.reports_dir)
            title = f"Session {self.session_id}"
            
            reports = generator.generate(
                transcript=transcript,
                summary=summary,
                title=title,
                formats=["markdown", "json", "pdf"]
            )
            
            self.event_bus.emit_stage_progress("Generating reports", 100)
            logger.debug(f"Report generation finished: {list(reports.keys())}")
            # Emit completion with report paths
            self.event_bus.emit_reports_ready(reports)
        
        except Exception as e:
            logger = AppLogger.get_logger("ui.workers.reporter")
            logger.error(f"ReporterWorker failed: {e}")
            self.event_bus.emit_session_error(f"Report generation failed: {str(e)}", "reporting")
    
    def _parse_summary_markdown(self, summary_path: Path):
        """
        Parse summary markdown back to MeetingSummary object.
        
        Args:
            summary_path: Path to summary markdown file
            
        Returns:
            MeetingSummary object
        """
        from handsome_transcribe.summarization.meeting_summarizer import MeetingSummary
        
        with open(summary_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parse markdown sections
        lines = content.split("\n")
        summary_text = ""
        key_topics = []
        action_items = []
        decisions = []
        
        current_section = None
        for line in lines:
            line = line.strip()
            if line.startswith("# Meeting Summary"):
                continue
            elif line.startswith("## Key Topics"):
                current_section = "topics"
            elif line.startswith("## Action Items"):
                current_section = "actions"
            elif line.startswith("## Decisions"):
                current_section = "decisions"
            elif line.startswith("- "):
                item = line[2:]
                if current_section == "topics":
                    key_topics.append(item)
                elif current_section == "actions":
                    action_items.append(item)
                elif current_section == "decisions":
                    decisions.append(item)
            elif line and current_section is None:
                summary_text += line + " "
        
        return MeetingSummary(
            summary=summary_text.strip(),
            key_topics=key_topics,
            action_items=action_items,
            decisions=decisions
        )
