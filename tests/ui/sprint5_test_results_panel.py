"""
Sprint 5 Tests: Results Panel
Test ResultsPanel display, media playback, and file opening.
"""

import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer

from handsome_transcribe.ui.windows.panels import ResultsPanel, TranscriptViewDialog, SummaryViewDialog
from handsome_transcribe.ui.event_bus import EventBus
from handsome_transcribe.ui.database import Database


@pytest.fixture
def app(qapp):
    """Fixture: QApplication instance."""
    return qapp


@pytest.fixture
def event_bus():
    """Fixture: EventBus instance."""
    return EventBus()


@pytest.fixture
def results_panel(event_bus):
    """Fixture: ResultsPanel instance."""
    return ResultsPanel(event_bus)


# Test 1: ResultsPanel initialization
def test_results_panel_init(results_panel, event_bus):
    """Test ResultsPanel initializes correctly."""
    assert results_panel is not None
    assert results_panel.event_bus == event_bus
    assert results_panel.results_tree is not None
    assert results_panel.media_player is not None
    assert results_panel.audio_output is not None
    assert results_panel.new_session_btn is not None


# Test 2: ResultsPanel UI components exist
def test_results_panel_ui_components(results_panel):
    """Test ResultsPanel has all required UI components."""
    # Tree widget
    assert results_panel.results_tree is not None
    assert results_panel.results_tree.columnCount() == 3
    
    # Media controls
    assert results_panel.media_controls is not None
    assert results_panel.play_btn is not None
    assert results_panel.pause_btn is not None
    assert results_panel.stop_btn is not None
    assert results_panel.volume_slider is not None
    assert results_panel.volume_label is not None
    assert results_panel.time_label is not None
    
    # New Session button
    assert results_panel.new_session_btn is not None
    assert not results_panel.new_session_btn.isEnabled()  # Initially disabled


# Test 3: Media player initialization
def test_media_player_init(results_panel):
    """Test QMediaPlayer is initialized correctly."""
    assert results_panel.media_player is not None
    assert results_panel.audio_output is not None
    assert results_panel.media_player.audioOutput() == results_panel.audio_output


# Test 4: Volume control updates
def test_volume_control(results_panel):
    """Test volume slider updates audio output volume."""
    # Set volume to 50%
    results_panel.volume_slider.setValue(50)
    assert results_panel.audio_output.volume() == 0.5
    assert results_panel.volume_label.text() == "50%"
    
    # Set volume to 100%
    results_panel.volume_slider.setValue(100)
    assert results_panel.audio_output.volume() == 1.0
    assert results_panel.volume_label.text() == "100%"
    
    # Set volume to 0%
    results_panel.volume_slider.setValue(0)
    assert results_panel.audio_output.volume() == 0.0
    assert results_panel.volume_label.text() == "0%"


# Test 5: session_completed signal connection
def test_session_completed_signal(results_panel, event_bus):
    """Test ResultsPanel connects to session_completed signal."""
    # Emit session_completed with mock results
    mock_results = {
        "session_data": {
            "id": 123,
            "fecha_inicio": "2026-03-09 12:00:00",
            "duracion_segundos": 120,
            "directorio_sesion": str(Path.cwd() / "outputs" / "sessions" / "session_123")
        },
        "reports": {}
    }
    
    # Emit signal (should not crash)
    event_bus.session_completed.emit(mock_results)
    
    # Check that results were set
    assert results_panel._results == mock_results
    assert results_panel._session_data == mock_results["session_data"]


# Test 6: New session button signal
def test_new_session_button_signal(results_panel, qtbot):
    """Test new session button emits signal when clicked."""
    # Enable button
    results_panel.new_session_btn.setEnabled(True)
    
    # Connect signal recorder
    with qtbot.waitSignal(results_panel.new_session_requested, timeout=1000):
        # Simulate button click (will show QMessageBox)
        # We need to mock QMessageBox.question to return Yes
        from unittest.mock import patch
        with patch('handsome_transcribe.ui.windows.panels.QMessageBox.question', return_value=2):  # QMessageBox.Yes
            results_panel._on_new_session_clicked()


# Test 7: TranscriptViewDialog initialization
def test_transcript_view_dialog():
    """Test TranscriptViewDialog initializes with content."""
    content = "Speaker 1: Hello world\nSpeaker 2: Hi there"
    filename = "transcript.txt"
    
    dialog = TranscriptViewDialog(content, filename)
    
    assert dialog is not None
    assert dialog.windowTitle() == f"Transcript - {filename}"
    assert dialog.text_view is not None
    assert dialog.text_view.toPlainText() == content
    assert dialog.text_view.isReadOnly()


# Test 8: SummaryViewDialog initialization
def test_summary_view_dialog():
    """Test SummaryViewDialog initializes with markdown content."""
    content = "# Meeting Summary\n\n## Key Points\n- Point 1\n- Point 2"
    filename = "summary.md"
    
    dialog = SummaryViewDialog(content, filename)
    
    assert dialog is not None
    assert dialog.windowTitle() == f"Summary - {filename}"
    assert dialog.text_view is not None
    assert dialog.text_view.isReadOnly()


# Test 9: Media controls initially hidden
def test_media_controls_initially_hidden(results_panel):
    """Test media controls are hidden until audio is loaded."""
    assert results_panel.media_controls.isHidden()


# Test 10: New session button initially disabled
def test_new_session_button_initially_disabled(results_panel):
    """Test new session button is disabled until session completes."""
    assert not results_panel.new_session_btn.isEnabled()


# Test 11: Playback state changes update buttons
def test_playback_state_changes(results_panel):
    """Test playback state changes update button enabled states."""
    # Initially all controls should be in stopped state
    assert results_panel.play_btn.isEnabled()
    assert not results_panel.pause_btn.isEnabled()
    assert not results_panel.stop_btn.isEnabled()


# Test 12: ResultsPanel clears on new session
def test_results_panel_clear(results_panel, event_bus):
    """Test ResultsPanel clears data when starting new session."""
    # Set some mock data
    mock_results = {
        "session_data": {
            "id": 123,
            "fecha_inicio": "2026-03-09 12:00:00",
            "duracion_segundos": 120,
            "directorio_sesion": str(Path.cwd() / "outputs" / "sessions" / "session_123")
        },
        "reports": {}
    }
    results_panel._results = mock_results
    results_panel._session_data = mock_results["session_data"]
    
    # Clear results
    results_panel._clear_results()
    
    # Verify cleared
    assert results_panel._results is None
    assert results_panel._session_data is None
    assert results_panel.results_tree.topLevelItemCount() == 0
    assert not results_panel.new_session_btn.isEnabled()
