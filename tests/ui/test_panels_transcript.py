"""Unit tests for LiveSessionView transcript rendering."""

from handsome_transcribe.ui.event_bus import EventBus
from handsome_transcribe.ui.models import TranscriptSegmentData
from handsome_transcribe.ui.windows.panels import LiveSessionView


def test_live_session_transcript_accepts_dataclass_and_dict(qtbot, qapp):
    """Verify LiveSessionView renders transcript from dataclass and dict inputs."""
    event_bus = EventBus()
    view = LiveSessionView(event_bus)
    qtbot.addWidget(view)

    segments = [
        TranscriptSegmentData(
            start_time=0.0,
            end_time=1.0,
            text="Hello world",
            confidence=0.0,
        ),
        {"text": "Second line", "speaker_id": None},
    ]

    event_bus.emit_partial_transcript(segments)
    qapp.processEvents()

    text = view.transcript_view.toPlainText()
    assert "Hello world" in text
    assert "Second line" in text
