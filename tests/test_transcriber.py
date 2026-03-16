"""Tests for the WhisperTranscriber module."""

from __future__ import annotations

import json
import os
import shutil
import struct
import sys
import types
import wave
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(path: Path, sample_rate: int = 16000, duration_sec: float = 0.5) -> None:
    """Write a minimal valid PCM-16 mono WAV file (silence) to *path*."""
    n_frames = int(sample_rate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


def _fake_whisper_module(mock_model: MagicMock) -> types.ModuleType:
    """Return a fake 'whisper' module that returns *mock_model* from load_model."""
    fake = types.ModuleType("whisper")
    fake.load_model = MagicMock(return_value=mock_model)
    return fake


# ---------------------------------------------------------------------------
# Language parameter tests
# ---------------------------------------------------------------------------

class TestWhisperTranscriberLanguage:
    """Tests that verify the language parameter is stored and forwarded correctly."""

    def test_language_defaults_to_none(self) -> None:
        transcriber = WhisperTranscriber.__new__(WhisperTranscriber)
        transcriber.model_name = "base"
        transcriber.output_dir = Path(".")
        transcriber.language = None
        transcriber._model = None
        assert transcriber.language is None

    def test_language_stored_from_init(self, tmp_path: Path) -> None:
        transcriber = WhisperTranscriber(output_dir=tmp_path, language="es")
        assert transcriber.language == "es"

    def test_language_none_by_default_in_init(self, tmp_path: Path) -> None:
        transcriber = WhisperTranscriber(output_dir=tmp_path)
        assert transcriber.language is None

    def test_language_passed_to_model_transcribe(self, tmp_path: Path) -> None:
        """The language kwarg must be forwarded to model.transcribe()."""
        audio_file = tmp_path / "audio.wav"
        _make_wav(audio_file)

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "language": "es",
            "segments": [{"start": 0.0, "end": 2.0, "text": " dos, tres, cuatro"}],
        }

        with patch.dict(sys.modules, {"whisper": _fake_whisper_module(mock_model)}):
            transcriber = WhisperTranscriber(output_dir=tmp_path, language="es")
            transcriber.transcribe(audio_file, save=False)

        mock_model.transcribe.assert_called_once_with(
            str(audio_file), verbose=False, language="es"
        )

    def test_language_none_forwarded_as_none(self, tmp_path: Path) -> None:
        """When language=None, Whisper receives language=None (auto-detect)."""
        audio_file = tmp_path / "audio.wav"
        _make_wav(audio_file)

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "language": "en",
            "segments": [{"start": 0.0, "end": 1.0, "text": " hello"}],
        }

        with patch.dict(sys.modules, {"whisper": _fake_whisper_module(mock_model)}):
            transcriber = WhisperTranscriber(output_dir=tmp_path, language=None)
            transcriber.transcribe(audio_file, save=False)

        mock_model.transcribe.assert_called_once_with(
            str(audio_file), verbose=False, language=None
        )


# ---------------------------------------------------------------------------
# Spanish transcription tests ("dos, tres, cuatro")
# ---------------------------------------------------------------------------

class TestSpanishTranscription:
    """Tests modelling the part1.wav scenario: Spanish audio 'dos, tres, cuatro'."""

    @pytest.fixture
    def spanish_mock_model(self) -> MagicMock:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "language": "es",
            "segments": [
                {"start": 0.0, "end": 1.2, "text": " dos, tres, cuatro"},
            ],
        }
        return mock_model

    def test_transcript_language_is_es(
        self, tmp_path: Path, spanish_mock_model: MagicMock
    ) -> None:
        audio_file = tmp_path / "part1.wav"
        _make_wav(audio_file)

        with patch.dict(sys.modules, {"whisper": _fake_whisper_module(spanish_mock_model)}):
            transcriber = WhisperTranscriber(output_dir=tmp_path, language="es")
            transcript = transcriber.transcribe(audio_file, save=False)

        assert transcript.language == "es"

    def test_transcript_text_contains_dos_tres_cuatro(
        self, tmp_path: Path, spanish_mock_model: MagicMock
    ) -> None:
        audio_file = tmp_path / "part1.wav"
        _make_wav(audio_file)

        with patch.dict(sys.modules, {"whisper": _fake_whisper_module(spanish_mock_model)}):
            transcriber = WhisperTranscriber(output_dir=tmp_path, language="es")
            transcript = transcriber.transcribe(audio_file, save=False)

        assert "dos" in transcript.full_text.lower()
        assert "tres" in transcript.full_text.lower()
        assert "cuatro" in transcript.full_text.lower()

    def test_segment_count_and_timing(
        self, tmp_path: Path, spanish_mock_model: MagicMock
    ) -> None:
        audio_file = tmp_path / "part1.wav"
        _make_wav(audio_file)

        with patch.dict(sys.modules, {"whisper": _fake_whisper_module(spanish_mock_model)}):
            transcriber = WhisperTranscriber(output_dir=tmp_path, language="es")
            transcript = transcriber.transcribe(audio_file, save=False)

        assert len(transcript.segments) == 1
        seg = transcript.segments[0]
        assert seg.start == pytest.approx(0.0)
        assert seg.end == pytest.approx(1.2)

    def test_without_language_hint_auto_detects(
        self, tmp_path: Path
    ) -> None:
        """Without language='es', Whisper auto-detects — may produce wrong result."""
        audio_file = tmp_path / "part1.wav"
        _make_wav(audio_file)

        mock_model = MagicMock()
        # Simulate Whisper mis-detecting the language when no hint is given
        mock_model.transcribe.return_value = {
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 1.2, "text": " dose dress quatro"},
            ],
        }

        with patch.dict(sys.modules, {"whisper": _fake_whisper_module(mock_model)}):
            transcriber = WhisperTranscriber(output_dir=tmp_path, language=None)
            transcript = transcriber.transcribe(audio_file, save=False)

        # Demonstrates auto-detect failure — language hint is required for Spanish
        assert transcript.language != "es"
        assert "tres" not in transcript.full_text.lower()

    def test_part1_wav_real_transcription(self, tmp_path: Path) -> None:
        """Integration test: transcribe the actual part1.wav file.

        Set ``HT_RUN_REAL_AUDIO_TEST=1`` and place ``part1.wav`` next to this
        file (tests/fixtures/part1.wav) before running.
        """
        if os.environ.get("HT_RUN_REAL_AUDIO_TEST") != "1":
            pytest.skip("Set HT_RUN_REAL_AUDIO_TEST=1 to run this test")

        fixture_path = Path(__file__).parent / "fixtures" / "part1.wav"
        if not fixture_path.exists():
            pytest.skip(f"Audio fixture not found: {fixture_path}")

        transcriber = WhisperTranscriber(
            model_name="tiny", output_dir=tmp_path, language="es"
        )
        transcript = transcriber.transcribe(fixture_path, save=False)

        text = transcript.full_text.lower()
        assert "dos" in text, f"Expected 'dos' in transcript, got: {text!r}"
        assert "tres" in text, f"Expected 'tres' in transcript, got: {text!r}"
        assert "cuatro" in text, f"Expected 'cuatro' in transcript, got: {text!r}"
