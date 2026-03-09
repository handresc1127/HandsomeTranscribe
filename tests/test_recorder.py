"""Tests for the audio recorder module."""

from __future__ import annotations

import sys
import types
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from handsome_transcribe.audio.recorder import AudioRecorder


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    return tmp_path / "audio"


def _make_audio_data(sample_rate: int = 16000, duration: float = 1.0) -> np.ndarray:
    """Generate a simple sine-wave audio array."""
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, dtype=np.float32)
    return (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16).reshape(-1, 1)


class TestAudioRecorder:
    def test_output_path_default_timestamp(self, tmp_output_dir: Path) -> None:
        recorder = AudioRecorder(output_dir=tmp_output_dir)
        path = recorder._build_output_path(None)
        assert path.suffix == ".wav"
        assert "recording_" in path.name
        assert path.parent == tmp_output_dir

    def test_output_path_custom_name(self, tmp_output_dir: Path) -> None:
        recorder = AudioRecorder(output_dir=tmp_output_dir)
        path = recorder._build_output_path("my_meeting")
        assert path.name == "my_meeting.wav"

    def test_output_path_already_has_extension(self, tmp_output_dir: Path) -> None:
        recorder = AudioRecorder(output_dir=tmp_output_dir)
        path = recorder._build_output_path("my_meeting.wav")
        assert path.name == "my_meeting.wav"

    def test_save_wav_creates_valid_file(self, tmp_output_dir: Path) -> None:
        tmp_output_dir.mkdir(parents=True, exist_ok=True)
        recorder = AudioRecorder(output_dir=tmp_output_dir)
        recorder._frames = [_make_audio_data()]

        out = tmp_output_dir / "test.wav"
        recorder._save_wav(out)

        assert out.exists()
        with wave.open(str(out), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000

    def test_save_wav_raises_when_no_frames(self, tmp_output_dir: Path) -> None:
        tmp_output_dir.mkdir(parents=True, exist_ok=True)
        recorder = AudioRecorder(output_dir=tmp_output_dir)
        recorder._frames = []
        with pytest.raises(RuntimeError, match="No audio data recorded"):
            recorder._save_wav(tmp_output_dir / "empty.wav")

    def test_record_fixed_duration(self, tmp_output_dir: Path) -> None:
        """record() with a duration writes a WAV file and returns its path."""
        audio_data = _make_audio_data(duration=1.0)

        # Build a minimal fake sounddevice module so that the lazy import succeeds
        fake_sd = types.ModuleType("sounddevice")
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.read = MagicMock(return_value=(audio_data, None))
        fake_sd.InputStream = MagicMock(return_value=mock_stream)

        with patch.dict(sys.modules, {"sounddevice": fake_sd}):
            recorder = AudioRecorder(output_dir=tmp_output_dir)
            path = recorder.record(duration=1.0, filename="test_rec")

        assert path.exists()
        assert path.suffix == ".wav"

