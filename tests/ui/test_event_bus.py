"""
Unit tests for EventBus.

Tests signal emission and connection.
"""

import pytest
from PySide6.QtCore import QObject, Slot

from handsome_transcribe.ui.event_bus import EventBus


class SignalReceiver(QObject):
    """Helper class to receive and test signals."""
    
    def __init__(self):
        super().__init__()
        self.received_signals = []
    
    @Slot(int, float)
    def on_recording_frame(self, frames, duration):
        self.received_signals.append(("recording_frame", frames, duration))
    
    @Slot(list)
    def on_partial_transcript(self, segments):
        self.received_signals.append(("partial_transcript", segments))
    
    @Slot(int, str, float)
    def on_speaker_identified(self, speaker_id, name, confidence):
        self.received_signals.append(("speaker_identified", speaker_id, name, confidence))
    
    @Slot(str)
    def on_session_state_changed(self, state):
        self.received_signals.append(("state_changed", state))


class TestEventBus:
    """Tests for EventBus."""
    
    def test_create_event_bus(self, event_bus):
        """Test creating an EventBus instance."""
        assert event_bus is not None
    
    def test_recording_frame_signal(self, event_bus):
        """Test recording frame signal emission."""
        receiver = SignalReceiver()
        event_bus.recording_frame_ready.connect(receiver.on_recording_frame)
        
        event_bus.emit_recording_frame(100, 5.0)
        
        assert len(receiver.received_signals) == 1
        assert receiver.received_signals[0] == ("recording_frame", 100, 5.0)
    
    def test_partial_transcript_signal(self, event_bus):
        """Test partial transcript signal emission."""
        receiver = SignalReceiver()
        event_bus.partial_transcript_ready.connect(receiver.on_partial_transcript)
        
        segments = [{"text": "Hello"}, {"text": "World"}]
        event_bus.emit_partial_transcript(segments)
        
        assert len(receiver.received_signals) == 1
        assert receiver.received_signals[0][0] == "partial_transcript"
        assert receiver.received_signals[0][1] == segments
    
    def test_speaker_identified_signal(self, event_bus):
        """Test speaker identified signal emission."""
        receiver = SignalReceiver()
        event_bus.speaker_identified.connect(receiver.on_speaker_identified)
        
        event_bus.emit_speaker_identified(1, "John Doe", 0.95)
        
        assert len(receiver.received_signals) == 1
        assert receiver.received_signals[0] == ("speaker_identified", 1, "John Doe", 0.95)
    
    def test_session_state_changed_signal(self, event_bus):
        """Test session state changed signal emission."""
        receiver = SignalReceiver()
        event_bus.session_state_changed.connect(receiver.on_session_state_changed)
        
        event_bus.emit_session_state_changed("recording")
        
        assert len(receiver.received_signals) == 1
        assert receiver.received_signals[0] == ("state_changed", "recording")
    
    def test_multiple_signals(self, event_bus):
        """Test emitting multiple different signals."""
        receiver = SignalReceiver()
        event_bus.recording_frame_ready.connect(receiver.on_recording_frame)
        event_bus.speaker_identified.connect(receiver.on_speaker_identified)
        
        event_bus.emit_recording_frame(50, 2.5)
        event_bus.emit_speaker_identified(2, "Jane Doe", 0.98)
        
        assert len(receiver.received_signals) == 2
        assert receiver.received_signals[0][0] == "recording_frame"
        assert receiver.received_signals[1][0] == "speaker_identified"
