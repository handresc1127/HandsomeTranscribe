"""Speaker diarization module using pyannote.audio.

Identifies and labels different speakers in an audio file, then merges
the speaker labels into an existing :class:`Transcript`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from handsome_transcribe.transcription.whisper_transcriber import Transcript, TranscriptSegment

console = Console()


@dataclass
class DiarizedSegment:
    """An audio segment with start/end time and assigned speaker label."""

    start: float
    end: float
    speaker: str


class SpeakerIdentifier:
    """Diarizes an audio file using pyannote.audio and assigns speaker
    labels to transcript segments.

    A Hugging Face auth token is required to download the pyannote models.
    Set the ``HF_TOKEN`` environment variable or pass *hf_token* explicitly.
    """

    def __init__(self, hf_token: str | None = None) -> None:
        """Initialise the identifier.

        Args:
            hf_token: Hugging Face API token.  Falls back to the ``HF_TOKEN``
                      environment variable when *None*.
        """
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self._pipeline = None  # Lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def diarize(self, audio_path: Path | str) -> list[DiarizedSegment]:
        """Run diarization on *audio_path*.

        Args:
            audio_path: Path to the WAV or MP3 audio file.

        Returns:
            A list of :class:`DiarizedSegment` objects sorted by start time.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        console.print(
            f"[bold green]Running speaker diarization on[/bold green] "
            f"[bold white]{audio_path.name}[/bold white]…"
        )

        pipeline = self._get_pipeline()
        diarization = pipeline(str(audio_path))

        segments: list[DiarizedSegment] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(
                DiarizedSegment(
                    start=turn.start,
                    end=turn.end,
                    speaker=speaker,
                )
            )

        segments.sort(key=lambda s: s.start)
        console.print(
            f"[bold blue]Detected {len({s.speaker for s in segments})} speaker(s).[/bold blue]"
        )
        return segments

    def assign_speakers(
        self,
        transcript: Transcript,
        diarized_segments: list[DiarizedSegment],
    ) -> Transcript:
        """Assign speaker labels to transcript segments using diarization results.

        Each transcript segment is labelled with the speaker whose diarized
        window has the greatest overlap with the segment's time range.

        Args:
            transcript: The original :class:`Transcript` (will not be mutated).
            diarized_segments: Output of :meth:`diarize`.

        Returns:
            A new :class:`Transcript` with speaker labels populated.
        """
        labelled: list[TranscriptSegment] = []
        for seg in transcript.segments:
            speaker = self._find_speaker(seg.start, seg.end, diarized_segments)
            labelled.append(
                TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                    speaker=speaker,
                )
            )

        return Transcript(
            audio_file=transcript.audio_file,
            language=transcript.language,
            segments=labelled,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_pipeline(self):
        """Lazy-load the pyannote diarization pipeline."""
        if self._pipeline is None:
            from pyannote.audio import Pipeline  # noqa: PLC0415

            if not self.hf_token:
                raise EnvironmentError(
                    "A Hugging Face token is required for pyannote.audio. "
                    "Set the HF_TOKEN environment variable or pass hf_token= "
                    "when constructing SpeakerIdentifier."
                )
            console.print("[dim]Loading pyannote diarization pipeline…[/dim]")
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token,
            )
        return self._pipeline

    @staticmethod
    def _find_speaker(
        start: float,
        end: float,
        diarized: list[DiarizedSegment],
    ) -> str:
        """Return the speaker with the largest overlap with [start, end]."""
        overlap: dict[str, float] = {}
        for seg in diarized:
            ov_start = max(start, seg.start)
            ov_end = min(end, seg.end)
            if ov_end > ov_start:
                overlap[seg.speaker] = overlap.get(seg.speaker, 0.0) + (ov_end - ov_start)

        if not overlap:
            return "Unknown"
        return max(overlap, key=overlap.get)  # type: ignore[arg-type]
