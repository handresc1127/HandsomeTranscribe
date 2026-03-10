"""Tests for the WhisperTranscriber module."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from handsome_transcribe.transcription.whisper_transcriber import (
    Transcript,
    TranscriptSegment,
    WhisperTranscriber,
)


@pytest.fixture
def sample_transcript() -> Transcript:
    return Transcript(
        audio_file="test.wav",
        language="en",
        segments=[
            TranscriptSegment(start=0.0, end=2.0, text="Hello world."),
            TranscriptSegment(start=2.0, end=4.0, text="This is a test."),
        ],
    )


class TestTranscriptDataClass:
    def test_full_text(self, sample_transcript: Transcript) -> None:
        assert "Hello world." in sample_transcript.full_text
        assert "This is a test." in sample_transcript.full_text

    def test_to_dict(self, sample_transcript: Transcript) -> None:
        d = sample_transcript.to_dict()
        assert d["audio_file"] == "test.wav"
        assert d["language"] == "en"
        assert len(d["segments"]) == 2
        assert d["segments"][0]["text"] == "Hello world."


class TestWhisperTranscriber:
    def test_transcribe_missing_file_raises(self, tmp_path: Path) -> None:
        transcriber = WhisperTranscriber(output_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            transcriber.transcribe(tmp_path / "nonexistent.wav", save=False)

    def test_transcribe_uses_whisper(self, tmp_path: Path) -> None:
        """Verify that WhisperTranscriber calls whisper.load_model and transcribe."""
        import sys
        import types

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)  # minimal fake WAV

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 1.5, "text": " Hello."},
                {"start": 1.5, "end": 3.0, "text": " World."},
            ],
        }

        # Inject a fake 'whisper' module so the lazy import succeeds
        fake_whisper = types.ModuleType("whisper")
        fake_whisper.load_model = MagicMock(return_value=mock_model)

        with patch.dict(sys.modules, {"whisper": fake_whisper}):
            transcriber = WhisperTranscriber(model_name="base", output_dir=tmp_path)
            transcript = transcriber.transcribe(audio_file, save=False)

        assert transcript.language == "en"
        assert len(transcript.segments) == 2
        assert transcript.segments[0].text == " Hello."

    def test_save_and_load_transcript(
        self, tmp_path: Path, sample_transcript: Transcript
    ) -> None:
        """Round-trip: save then reload a transcript."""
        transcriber = WhisperTranscriber(output_dir=tmp_path)
        saved_path = transcriber._save_transcript(sample_transcript, "test")

        loaded = WhisperTranscriber.load_transcript(saved_path)
        assert loaded.audio_file == sample_transcript.audio_file
        assert loaded.language == sample_transcript.language
        assert len(loaded.segments) == len(sample_transcript.segments)
        assert loaded.segments[0].text == sample_transcript.segments[0].text

    def test_transcribe_real_recording(self) -> None:
        """Transcribe a real recording.wav when explicitly enabled."""
        if os.environ.get("HT_RUN_REAL_AUDIO_TEST") != "1":
            pytest.skip("Set HT_RUN_REAL_AUDIO_TEST=1 to run this test")

        if shutil.which("ffmpeg") is None:
            pytest.skip("ffmpeg not found in PATH")

        audio_path = Path("outputs/sessions/session_20260309_233252/recording.wav")
        if not audio_path.exists():
            pytest.skip("Sample recording.wav not found in outputs/sessions")

        output_dir = Path("outputs/transcripts")
        transcriber = WhisperTranscriber(model_name="tiny", output_dir=output_dir)
        transcript = transcriber.transcribe(audio_path, save=True)

        assert transcript.full_text.strip()
