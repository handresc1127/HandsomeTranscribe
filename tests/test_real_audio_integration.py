"""
Integration tests with real audio files.

These tests require actual Whisper processing and are gated by:
    HT_RUN_REAL_AUDIO_TEST=1

Run with:
    $env:HT_RUN_REAL_AUDIO_TEST="1"; python -m pytest tests/test_real_audio_integration.py -v
"""

import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import MagicMock

REAL_AUDIO = os.environ.get("HT_RUN_REAL_AUDIO_TEST") == "1"


def _ffmpeg_available():
    """Check if ffmpeg is available directly or via imageio-ffmpeg."""
    if shutil.which("ffmpeg"):
        return True
    try:
        import imageio_ffmpeg  # noqa: F401
        return True  # conftest.py will shim it onto PATH
    except ImportError:
        return False


skip_unless_real = pytest.mark.skipif(
    not REAL_AUDIO or not _ffmpeg_available(),
    reason="Set HT_RUN_REAL_AUDIO_TEST=1 and install ffmpeg (or imageio-ffmpeg) to run real audio integration tests",
)
FIXTURES = Path(__file__).parent / "fixtures"


@skip_unless_real
def test_whisper_transcribes_recording1_spanish():
    """Whisper transcribes recording1.wav and returns non-empty segments."""
    import whisper

    path = FIXTURES / "recording1.wav"
    assert path.exists(), f"Fixture not found: {path}"

    model = whisper.load_model("base")
    result = model.transcribe(str(path), language="es", verbose=False)

    assert "segments" in result
    assert len(result["segments"]) > 0


@skip_unless_real
def test_whisper_transcribes_recording2_spanish():
    """Whisper transcribes recording2.wav and returns non-empty segments."""
    import whisper

    path = FIXTURES / "recording2.wav"
    assert path.exists(), f"Fixture not found: {path}"

    model = whisper.load_model("base")
    result = model.transcribe(str(path), language="es", verbose=False)

    assert "segments" in result
    assert len(result["segments"]) > 0


@skip_unless_real
def test_transcriber_worker_emits_complete(tmp_path):
    """TranscriberWorker emits emit_transcription_complete after processing a real audio file."""
    from PySide6.QtWidgets import QApplication
    from handsome_transcribe.ui.event_bus import EventBus
    from handsome_transcribe.ui.workers import TranscriberWorker

    app = QApplication.instance() or QApplication([])

    event_bus = EventBus()
    completed_results = []
    event_bus.transcription_complete.connect(lambda r: completed_results.append(r))

    audio_path = FIXTURES / "recording1.wav"
    output_path = tmp_path / "transcript.txt"

    worker = TranscriberWorker(
        event_bus=event_bus,
        audio_path=audio_path,
        output_path=output_path,
        model_name="base",
        language="es",
    )
    worker.run()
    QApplication.processEvents()

    assert len(completed_results) == 1
    result = completed_results[0]
    assert "segments" in result


@skip_unless_real
def test_transcriber_worker_emits_error_on_bad_file(tmp_path):
    """TranscriberWorker emits emit_transcription_error when audio file does not exist."""
    from PySide6.QtWidgets import QApplication
    from handsome_transcribe.ui.event_bus import EventBus
    from handsome_transcribe.ui.workers import TranscriberWorker

    app = QApplication.instance() or QApplication([])

    event_bus = EventBus()
    errors = []
    event_bus.transcription_error.connect(lambda msg: errors.append(msg))

    worker = TranscriberWorker(
        event_bus=event_bus,
        audio_path=tmp_path / "nonexistent.wav",
        output_path=tmp_path / "transcript.txt",
        model_name="base",
        language="es",
    )
    worker.run()
    QApplication.processEvents()

    assert len(errors) == 1
    assert "Transcription failed" in errors[0]
