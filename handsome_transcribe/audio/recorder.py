"""Audio recorder module.

Records audio from the system microphone and saves it as a WAV file.
Supports configurable duration or manual start/stop via keyboard.
"""

from __future__ import annotations

import threading
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
from rich.console import Console

console = Console()

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_DTYPE = "int16"
OUTPUTS_AUDIO_DIR = Path("outputs/audio")


class AudioRecorder:
    """Records audio from the microphone and saves it to a WAV file."""

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        output_dir: Path | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.output_dir = output_dir or OUTPUTS_AUDIO_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._frames: list[np.ndarray] = []
        self._recording = False
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, duration: float | None = None, filename: str | None = None) -> Path:
        """Record audio from the microphone.

        Args:
            duration: Recording length in seconds.  When *None* the recording
                      runs until the user presses Enter.
            filename: Output file name (without extension).  Defaults to a
                      timestamp-based name.

        Returns:
            Path to the saved WAV file.
        """
        output_path = self._build_output_path(filename)
        self._frames = []
        self._stop_event.clear()

        if duration is not None:
            console.print(
                f"[bold green]Recording for {duration:.0f} seconds...[/bold green]"
            )
            self._record_fixed_duration(duration)
        else:
            console.print(
                "[bold green]Recording started. Press [bold white]Enter[/bold white] to stop.[/bold green]"
            )
            self._record_until_stop()

        self._save_wav(output_path)
        console.print(f"[bold blue]Audio saved to:[/bold blue] {output_path}")
        return output_path

    def stop(self) -> None:
        """Signal the recorder to stop (used for manual stop)."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_fixed_duration(self, duration: float) -> None:
        """Record exactly *duration* seconds of audio."""
        import sounddevice as sd  # noqa: PLC0415

        frames_needed = int(self.sample_rate * duration)
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=DEFAULT_DTYPE,
        ) as stream:
            data, _ = stream.read(frames_needed)
        self._frames = [data]

    def _record_until_stop(self) -> None:
        """Record until :meth:`stop` is called or the user presses Enter."""
        import sounddevice as sd  # noqa: PLC0415

        def _callback(indata: np.ndarray, frames: int, time, status) -> None:  # noqa: ANN001
            if status:
                console.print(f"[yellow]Audio callback status: {status}[/yellow]")
            self._frames.append(indata.copy())

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=DEFAULT_DTYPE,
            callback=_callback,
        ):
            # Wait for Enter key or external stop signal
            stop_thread = threading.Thread(target=self._wait_for_enter, daemon=True)
            stop_thread.start()
            self._stop_event.wait()

    def _wait_for_enter(self) -> None:
        """Block until the user presses Enter, then signal stop."""
        input()
        self._stop_event.set()

    def _save_wav(self, path: Path) -> None:
        """Write accumulated audio frames to a WAV file."""
        if not self._frames:
            raise RuntimeError("No audio data recorded.")

        audio_data = np.concatenate(self._frames, axis=0)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # int16 → 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())

    def _build_output_path(self, filename: str | None) -> Path:
        """Return the full output path for the WAV file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}"
        if not filename.endswith(".wav"):
            filename = f"{filename}.wav"
        return self.output_dir / filename
