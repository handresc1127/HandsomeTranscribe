"""Speech-to-text transcription using local Whisper.

Converts a WAV/MP3 audio file into a timestamped transcript.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console

console = Console()

OUTPUTS_TRANSCRIPTS_DIR = Path("outputs/transcripts")


@dataclass
class TranscriptSegment:
    """A single segment of the transcript with timing information."""

    start: float
    end: float
    text: str
    speaker: str = "Unknown"


@dataclass
class Transcript:
    """Full transcript produced from an audio file."""

    audio_file: str
    language: str
    segments: list[TranscriptSegment]

    @property
    def full_text(self) -> str:
        """Return the full transcript as a single string."""
        return " ".join(seg.text.strip() for seg in self.segments)

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return asdict(self)


class WhisperTranscriber:
    """Transcribes audio files using local Whisper."""

    def __init__(self, model_name: str = "base", output_dir: Path | None = None) -> None:
        """Initialise the transcriber.

        Args:
            model_name: Whisper model size (tiny/base/small/medium/large).
            output_dir: Directory where transcript JSON files are saved.
        """
        self.model_name = model_name
        self.output_dir = output_dir or OUTPUTS_TRANSCRIPTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._model = None  # Lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(self, audio_path: Path | str, save: bool = True) -> Transcript:
        """Transcribe *audio_path* and return a :class:`Transcript`.

        Args:
            audio_path: Path to the WAV or MP3 file.
            save: When *True* the transcript is also saved to ``output_dir``.

        Returns:
            A :class:`Transcript` object.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        console.print(
            f"[bold green]Transcribing[/bold green] [bold white]{audio_path.name}[/bold white] "
            f"using Whisper model '[bold cyan]{self.model_name}[/bold cyan]'…"
        )

        model = self._get_model()
        result = model.transcribe(str(audio_path), verbose=False)

        segments = [
            TranscriptSegment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"],
            )
            for seg in result.get("segments", [])
        ]

        transcript = Transcript(
            audio_file=str(audio_path),
            language=result.get("language", "unknown"),
            segments=segments,
        )

        if save:
            out_path = self._save_transcript(transcript, audio_path.stem)
            console.print(f"[bold blue]Transcript saved to:[/bold blue] {out_path}")

        return transcript

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model(self):
        """Lazy-load the Whisper model."""
        if self._model is None:
            import whisper  # noqa: PLC0415

            console.print(
                f"[dim]Loading Whisper model '{self.model_name}'…[/dim]"
            )
            self._model = whisper.load_model(self.model_name)
        return self._model

    def _save_transcript(self, transcript: Transcript, stem: str) -> Path:
        """Save the transcript as a JSON file and return the path."""
        out_path = self.output_dir / f"{stem}_transcript.json"
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(transcript.to_dict(), fh, indent=2, ensure_ascii=False)
        return out_path

    @staticmethod
    def load_transcript(path: Path | str) -> Transcript:
        """Load a previously saved transcript JSON file.

        Args:
            path: Path to the transcript JSON file.

        Returns:
            A reconstructed :class:`Transcript` object.
        """
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        segments = [TranscriptSegment(**seg) for seg in data.get("segments", [])]
        return Transcript(
            audio_file=data["audio_file"],
            language=data["language"],
            segments=segments,
        )
