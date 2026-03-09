"""
Panels and widgets for HandsomeTranscribe tabs.

Contains:
- ConfigPanel: Configuration settings tab
- LiveSessionView: Live recording and transcription tab (principal)
- InterlocutoresPanel: Speaker library management tab
- SessionHistoryPanel: Session history and results tab
"""

import json
from typing import Optional, List
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QLineEdit, QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QDialog, QScrollArea, QFrame, QGroupBox, QSpinBox
)
from PySide6.QtCore import Qt, Slot, QTimer, Signal
from PySide6.QtGui import QFont, QIcon, QColor

from ..config_manager import ConfigManager
from ..event_bus import EventBus
from ..speaker_manager import SpeakerManager
from ..database import Database
from ..models import SessionConfig, SessionState


class ConfigPanel(QWidget):
    """Configuration tab for session settings."""
    
    # Signal: emitted when user wants to start a session
    session_requested = Signal(SessionConfig)
    
    def __init__(self, config_manager: ConfigManager, event_bus: EventBus, database: Database = None):
        super().__init__()
        self.config_manager = config_manager
        self.event_bus = event_bus
        self.database = database
        
        # State
        self._current_config = None
        self._has_active_session = False
        
        self._setup_ui()
        self._load_saved_config()
        
        # Connect to EventBus for session state updates
        self.event_bus.session_state_changed.connect(self._on_session_state_changed)
    
    def _setup_ui(self):
        """Create configuration UI components."""
        main_layout = QVBoxLayout()
        
        # Title
        title = QLabel("Session Configuration")
        title_font = QFont("Arial", 14, QFont.Bold)
        title.setFont(title_font)
        main_layout.addWidget(title)
        
        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        
        # === MODEL SETTINGS ===
        model_group = QGroupBox("Transcription Model")
        model_layout = QVBoxLayout()
        
        model_layout.addWidget(QLabel("Whisper Model:"))
        self.whisper_combo = QComboBox()
        whisper_models = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
        self.whisper_combo.addItems(whisper_models)
        self.whisper_combo.setToolTip("Larger models are more accurate but slower")
        model_layout.addWidget(self.whisper_combo)
        
        model_layout.addWidget(QLabel("Language: (optional, auto-detect if empty)"))
        self.language_input = QLineEdit()
        self.language_input.setPlaceholderText("e.g., es for Spanish, en for English (leave empty for auto-detect)")
        model_layout.addWidget(self.language_input)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # === AUDIO SETTINGS ===
        audio_group = QGroupBox("Audio Settings")
        audio_layout = QVBoxLayout()
        
        audio_layout.addWidget(QLabel("Audio Device:"))
        self.device_combo = QComboBox()
        self._load_audio_devices()
        audio_layout.addWidget(self.device_combo)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)
        
        # === PROCESSING OPTIONS ===
        processing_group = QGroupBox("Processing Options")
        processing_layout = QVBoxLayout()
        
        self.diarization_check = QCheckBox("Enable Speaker Diarization (requires HF_TOKEN)")
        self.diarization_check.setToolTip("Identifies different speakers in the audio")
        self.diarization_check.toggled.connect(self._on_diarization_toggled)
        processing_layout.addWidget(self.diarization_check)
        
        processing_layout.addWidget(QLabel("HF_TOKEN (for Diarization):"))
        self.hf_token_input = QLineEdit()
        self.hf_token_input.setReadOnly(True)
        self.hf_token_input.setPlaceholderText("Set via environment variable HF_TOKEN")
        self.hf_token_input.setEchoMode(QLineEdit.Password)
        processing_layout.addWidget(self.hf_token_input)
        
        self.summarization_check = QCheckBox("Enable Automatic Summarization")
        self.summarization_check.setToolTip("Generates summary of transcribed content")
        processing_layout.addWidget(self.summarization_check)
        
        processing_group.setLayout(processing_layout)
        layout.addWidget(processing_group)
        
        # === SESSION CONTEXT ===
        context_group = QGroupBox("Session Context (Optional)")
        context_layout = QVBoxLayout()
        
        context_help = QLabel(
            "Provide context about this meeting or conversation. "
            "This can help improve transcription and summarization (future feature)."
        )
        context_help.setStyleSheet("color: #666; font-size: 11px;")
        context_help.setWordWrap(True)
        context_layout.addWidget(context_help)
        
        self.context_text = QTextEdit()
        self.context_text.setPlaceholderText(
            "Example:\n"
            "Hoy discutimos el proyecto X en detalle.\n"
            "Asistentes: Juan, María, Carlos\n"
            "Temas: presupuesto, cronograma, recursos"
        )
        self.context_text.setMaximumHeight(100)
        self.context_text.setMinimumHeight(80)
        context_layout.addWidget(self.context_text)
        
        context_group.setLayout(context_layout)
        layout.addWidget(context_group)
        
        # === STATUS ===
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Mode:"))
        self.mode_label = QLabel("Free/Local")
        self.mode_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        status_layout.addWidget(self.mode_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # === BUTTONS ===
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self._on_reset_config)
        buttons_layout.addWidget(self.reset_button)
        
        self.start_button = QPushButton("Start Session")
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.start_button.clicked.connect(self._on_start_session)
        buttons_layout.addWidget(self.start_button)
        
        main_layout.addLayout(buttons_layout)
        self.setLayout(main_layout)
    
    def _load_audio_devices(self):
        """Load audio devices into combo box."""
        try:
            devices = self.config_manager.get_audio_devices()
            if devices:
                self.device_combo.addItems(devices)
            else:
                self.device_combo.addItem("Default Device")
        except Exception as e:
            self.device_combo.addItem(f"Error: {str(e)[:50]}")
    
    def _load_saved_config(self):
        """Load saved configuration into form."""
        try:
            config = self.config_manager.load_config()
            self._current_config = config
            
            # Set Whisper model
            index = self.whisper_combo.findText(config.modelo_whisper)
            if index >= 0:
                self.whisper_combo.setCurrentIndex(index)
            
            # Set diarization checkbox
            self.diarization_check.setChecked(config.habilitar_diarizacion)
            
            # Set HF token (masked)
            if config.hf_token:
                masked_token = config.hf_token[:10] + "..." if len(config.hf_token) > 10 else config.hf_token
                self.hf_token_input.setText(f"✓ Token configured")
            
            # Set summarization checkbox
            self.summarization_check.setChecked(config.habilitar_resumen)
            
            # Set audio device
            if config.dispositivo_audio:
                index = self.device_combo.findText(config.dispositivo_audio)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
            
            # Set session context
            if config.session_context:
                self.context_text.setPlainText(config.session_context)
        
        except Exception as e:
            print(f"Error loading config: {e}")
    
    @Slot()
    def _on_diarization_toggled(self):
        """Slot: diarization checkbox toggled."""
        is_checked = self.diarization_check.isChecked()
        self.hf_token_input.setEnabled(is_checked)
        if is_checked and not self.hf_token_input.text():
            QMessageBox.information(
                self,
                "HF_TOKEN Required",
                "To use speaker diarization, set the HF_TOKEN environment variable.\n\n"
                "You can obtain a token from: https://huggingface.co/settings/tokens"
            )
    
    @Slot()
    def _on_reset_config(self):
        """Slot: reset to default configuration."""
        reply = QMessageBox.question(
            self,
            "Reset Configuration",
            "Reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.whisper_combo.setCurrentText("base")
            self.language_input.clear()
            self.diarization_check.setChecked(False)
            self.summarization_check.setChecked(False)
            self.context_text.clear()
            self._load_audio_devices()
    
    @Slot()
    def _on_start_session(self):
        """Slot: start session button clicked."""
        # Check for active session
        if self._has_active_session:
            QMessageBox.warning(
                self,
                "Active Session",
                "A session is already active. Finish or pause it before starting a new one."
            )
            return
        
        # Collect configuration
        config = SessionConfig(
            modelo_whisper=self.whisper_combo.currentText(),
            habilitar_diarizacion=self.diarization_check.isChecked(),
            habilitar_resumen=self.summarization_check.isChecked(),
            dispositivo_audio=self.device_combo.currentText(),
            hf_token=self.config_manager.load_config().hf_token,
            session_context=self.context_text.toPlainText() or None
        )
        
        # Validate
        is_valid, error = self.config_manager.validate_config(config)
        if not is_valid:
            QMessageBox.warning(self, "Configuration Invalid", f"Please fix the following:\n\n{error}")
            return
        
        # Save configuration
        self.config_manager.save_config(config)
        self._current_config = config
        
        # Disable start button and controls during session
        self.start_button.setEnabled(False)
        self._set_panel_enabled(False)
        
        # Emit signal to start session
        self.session_requested.emit(config)
        self.event_bus.emit_start_session_requested(config)
    
    @Slot(str)
    def _on_session_state_changed(self, state: str):
        """Slot: session state changed."""
        try:
            session_state = SessionState[state]
            is_active = session_state in [SessionState.RECORDING, SessionState.PAUSED]
            self._has_active_session = is_active
            
            if not is_active:
                # Re-enable controls when session ends
                self.start_button.setEnabled(True)
                self._set_panel_enabled(True)
        except (KeyError, ValueError):
            pass
    
    def _set_panel_enabled(self, enabled: bool):
        """Enable or disable all configuration controls."""
        self.whisper_combo.setEnabled(enabled)
        self.language_input.setEnabled(enabled)
        self.device_combo.setEnabled(enabled)
        self.diarization_check.setEnabled(enabled)
        self.summarization_check.setEnabled(enabled)
        self.context_text.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)


class LiveSessionView(QWidget):
    """Live recording and transcription view (main Session tab)."""
    
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self._current_speakers = {}  # {speaker_id: (name, confidence, avatar_path)}
        self._session_active = False
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Create live session UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Live Recording Session")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # === SPEAKER SECTION ===
        speakers_group = QGroupBox("Active Speakers")
        speakers_layout = QVBoxLayout()
        
        self.speakers_scroll = QScrollArea()
        self.speakers_scroll.setWidgetResizable(True)
        self.speakers_scroll.setStyleSheet("QScrollArea { border: 1px solid #bdc3c7; }")
        
        self.speakers_widget = QWidget()
        self.speakers_h_layout = QHBoxLayout(self.speakers_widget)
        self.speakers_h_layout.addStretch()
        self.speakers_scroll.setWidget(self.speakers_widget)
        
        speakers_layout.addWidget(self.speakers_scroll)
        speakers_group.setLayout(speakers_layout)
        speakers_group.setMaximumHeight(100)
        layout.addWidget(speakers_group)
        
        # === TRANSCRIPT SECTION ===
        transcript_group = QGroupBox("Transcription (Live)")
        transcript_layout = QVBoxLayout()
        
        self.transcript_view = QPlainTextEdit()
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                padding: 5px;
                background-color: #ecf0f1;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        transcript_layout.addWidget(self.transcript_view)
        transcript_group.setLayout(transcript_layout)
        layout.addWidget(transcript_group, 1)  # Give it stretch priority
        
        # === PROGRESS SECTION ===
        progress_group = QGroupBox("Session Progress")
        progress_layout = QVBoxLayout()
        
        progress_layout.addWidget(QLabel("Duration:"))
        self.duration_progress = QProgressBar()
        self.duration_progress.setFormat("%p% (%m:%s/%M:%S)")
        self.duration_progress.setMaximum(3600)  # 1 hour max by default
        progress_layout.addWidget(self.duration_progress)
        
        self.stage_label = QLabel("Waiting for session to start...")
        self.stage_label.setStyleSheet("color: #555; font-style: italic;")
        progress_layout.addWidget(self.stage_label)
        
        progress_group.setLayout(progress_layout)
        progress_group.setMaximumHeight(100)
        layout.addWidget(progress_group)
        
        # === CONTROLS SECTION ===
        controls_group = QGroupBox("Recording Controls")
        controls_layout = QHBoxLayout()
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setMinimumWidth(100)
        self.pause_button.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e67e22; }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.pause_button.clicked.connect(self._on_pause_resume)
        self.pause_button.setEnabled(False)
        controls_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("Stop Recording")
        self.stop_button.setMinimumWidth(100)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.stop_button.clicked.connect(self._on_stop)
        self.stop_button.setEnabled(False)
        controls_layout.addWidget(self.stop_button)
        
        controls_layout.addStretch()
        controls_group.setLayout(controls_layout)
        controls_group.setMaximumHeight(70)
        layout.addWidget(controls_group)
        
        self.setLayout(layout)
        self._is_paused = False
    
    def _connect_signals(self):
        """Connect EventBus signals."""
        self.event_bus.partial_transcript_ready.connect(self._on_partial_transcript)
        self.event_bus.speaker_identified.connect(self._on_speaker_identified)
        self.event_bus.session_state_changed.connect(self._on_state_changed)
        self.event_bus.stage_progress.connect(self._on_stage_progress)
        self.event_bus.recording_frame_ready.connect(self._on_recording_progress)
    
    @Slot(list)
    def _on_partial_transcript(self, segments: list):
        """Slot: partial transcript ready."""
        for segment in segments:
            text = segment.get("text", "")
            speaker_id = segment.get("speaker_id")
            
            if text:
                if speaker_id and speaker_id in self._current_speakers:
                    speaker_name = self._current_speakers[speaker_id][0]
                    formatted_text = f"[{speaker_name}] {text}"
                else:
                    formatted_text = text
                
                self.transcript_view.appendPlainText(formatted_text)
    
    @Slot(int, str, float)
    def _on_speaker_identified(self, speaker_id: int, name: str, confidence: float):
        """Slot: speaker identified."""
        self._current_speakers[speaker_id] = (name, confidence, None)
        self.stage_label.setText(f"Speaking: {name} ({confidence*100:.0f}% confidence)")
        self._update_speakers_display()
    
    @Slot(str, int)
    def _on_stage_progress(self, stage: str, percent: int):
        """Slot: stage progress update."""
        if percent > 0:
            self.stage_label.setText(f"{stage}... {percent}%")
        else:
            self.stage_label.setText(stage)
    
    @Slot(str)
    def _on_state_changed(self, state: str):
        """Slot: session state changed."""
        try:
            session_state = SessionState[state]
            
            if session_state == SessionState.RECORDING:
                self.pause_button.setText("Pause")
                self.pause_button.setEnabled(True)
                self.stop_button.setEnabled(True)
                self._is_paused = False
                self.stage_label.setText("Recording in progress...")
                self.transcript_view.clear()
                self._session_active = True
            
            elif session_state == SessionState.PAUSED:
                self.pause_button.setText("Resume")
                self._is_paused = True
                self.stage_label.setText("Recording paused")
            
            elif session_state == SessionState.TRANSCRIBING:
                self.pause_button.setEnabled(False)
                self.stop_button.setEnabled(False)
                self.stage_label.setText("Transcribing...")
            
            elif session_state == SessionState.DIARIZING:
                self.stage_label.setText("Identifying speakers...")
            
            elif session_state == SessionState.SUMMARIZING:
                self.stage_label.setText("Generating summary...")
            
            elif session_state == SessionState.COMPLETED:
                self.pause_button.setEnabled(False)
                self.stop_button.setEnabled(False)
                self.stage_label.setText("Session completed")
                self._session_active = False
            
            elif session_state == SessionState.ERROR:
                self.pause_button.setEnabled(False)
                self.stop_button.setEnabled(False)
                self.stage_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                self.stage_label.setText("Error occurred")
                self._session_active = False
        
        except (KeyError, ValueError):
            pass
    
    def _update_speakers_display(self):
        """Update speakers display with current speakers."""
        # Clear existing layout (except stretch)
        while self.speakers_h_layout.count() > 1:
            item = self.speakers_h_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add speaker labels
        for speaker_id, (name, confidence, avatar) in self._current_speakers.items():
            speaker_frame = QFrame()
            speaker_frame.setStyleSheet("""
                QFrame {
                    border: 2px solid #3498db;
                    border-radius: 5px;
                    padding: 5px;
                    background-color: #ecf0f1;
                }
            """)
            speaker_layout = QVBoxLayout(speaker_frame)
            speaker_layout.setContentsMargins(5, 5, 5, 5)
            
            name_label = QLabel(name)
            name_label.setFont(QFont("Arial", 10, QFont.Bold))
            name_label.setAlignment(Qt.AlignCenter)
            speaker_layout.addWidget(name_label)
            
            confidence_label = QLabel(f"{confidence*100:.0f}%")
            confidence_label.setAlignment(Qt.AlignCenter)
            confidence_label.setStyleSheet("color: #7f8c8d; font-size: 9px;")
            speaker_layout.addWidget(confidence_label)
            
            self.speakers_h_layout.insertWidget(self.speakers_h_layout.count() - 1, speaker_frame)
    
    @Slot()
    def _on_pause_resume(self):
        """Slot: pause/resume button clicked."""
        if self._is_paused:
            self.event_bus.emit_resume_recording()
        else:
            self.event_bus.emit_pause_recording()
    
    @Slot()
    def _on_stop(self):
        """Slot: stop button clicked."""
        reply = QMessageBox.question(
            self,
            "Stop Recording",
            "¿Detener la grabación?\n\n"
            "Se iniciará el procesamiento de transcripción, diarización y resumen.\n"
            "Este proceso puede tomar varios minutos.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.event_bus.emit_stop_recording()
    
    @Slot(int, float)
    def _on_recording_progress(self, frames_count: int, duration_sec: float):
        """
        Slot: recording progress update.
        
        Args:
            frames_count: Total frames recorded
            duration_sec: Total duration in seconds
        """
        # Update progress bar with duration
        self.duration_progress.setValue(int(duration_sec))
        
        # Format time as MM:SS
        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)
        self.duration_progress.setFormat(f"{minutes:02d}:{seconds:02d}")



class InterlocutoresPanel(QWidget):
    """Speaker library management tab."""
    
    def __init__(self, speaker_manager: SpeakerManager, event_bus: EventBus):
        super().__init__()
        self.speaker_manager = speaker_manager
        self.event_bus = event_bus
        self._setup_ui()
        self._load_speakers()
    
    def _setup_ui(self):
        """Create speaker management UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Speaker Library (Interlocutores)")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Help text
        help_text = QLabel(
            "Manage your speakers and their voice profiles. "
            "Speakers are automatically identified during recording."
        )
        help_text.setStyleSheet("color: #666; font-size: 11px;")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        # Speaker list
        self.speaker_list = QListWidget()
        self.speaker_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        layout.addWidget(self.speaker_list, 1)
        
        # Statistics
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("Total speakers:"))
        self.speaker_count_label = QLabel("0")
        self.speaker_count_label.setFont(QFont("Arial", 10, QFont.Bold))
        stats_layout.addWidget(self.speaker_count_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        # Control buttons
        buttons_layout = QHBoxLayout()
        
        add_button = QPushButton("+ Add Speaker")
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #229954; }
        """)
        add_button.clicked.connect(self._on_add_speaker)
        buttons_layout.addWidget(add_button)
        
        edit_button = QPushButton("✎ Edit Speaker")
        edit_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        edit_button.clicked.connect(self._on_edit_speaker)
        buttons_layout.addWidget(edit_button)
        
        delete_button = QPushButton("✕ Delete Speaker")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        delete_button.clicked.connect(self._on_delete_speaker)
        buttons_layout.addWidget(delete_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Store references
        self.edit_button = edit_button
        self.delete_button = delete_button
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        
        # Enable/disable edit/delete on selection
        self.speaker_list.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_speakers(self):
        """Load speakers from database."""
        self.speaker_list.clear()
        
        try:
            # TODO: Load from database using speaker_manager
            # For now, show placeholder
            placeholder = QListWidgetItem("No speakers registered yet.\n\nSpeakers are automatically created during recording.")
            self.speaker_list.addItem(placeholder)
            self.speaker_count_label.setText("0")
        
        except Exception as e:
            error_item = QListWidgetItem(f"Error loading speakers: {str(e)}")
            self.speaker_list.addItem(error_item)
    
    @Slot()
    def _on_selection_changed(self):
        """Slot: selection in speaker list changed."""
        has_selection = self.speaker_list.currentItem() is not None
        # Don't enable if placeholder is selected
        is_placeholder = has_selection and "No speakers" in self.speaker_list.currentItem().text()
        
        self.edit_button.setEnabled(has_selection and not is_placeholder)
        self.delete_button.setEnabled(has_selection and not is_placeholder)
    
    @Slot()
    def _on_add_speaker(self):
        """Slot: add speaker button clicked."""
        dialog = AddSpeakerDialog(self)
        if dialog.exec():
            name, tags = dialog.get_data()
            QMessageBox.information(
                self,
                "Speaker Added",
                f"Speaker '{name}' added to library.\n\n"
                f"This speaker will be automatically identified during recording\n"
                f"if their voice embedding matches with >98% confidence."
            )
            self._load_speakers()
    
    @Slot()
    def _on_edit_speaker(self):
        """Slot: edit speaker button clicked."""
        current_item = self.speaker_list.currentItem()
        if not current_item:
            return
        
        QMessageBox.information(self, "Edit Speaker", "Edit speaker dialog - TBD")
    
    @Slot()
    def _on_delete_speaker(self):
        """Slot: delete speaker button clicked."""
        current_item = self.speaker_list.currentItem()
        if not current_item:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Speaker",
            f"¿Eliminar este interlocutor permanentemente?\n\n"
            f"Su perfil y voice embedding serán removidos.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "Deleted", "Speaker deleted - TBD")
            self._load_speakers()


class AddSpeakerDialog(QDialog):
    """Dialog for adding a new speaker."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Speaker")
        self.setModal(True)
        self.setGeometry(200, 200, 400, 250)
        self._setup_ui()
    
    def _setup_ui(self):
        """Create dialog UI."""
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Speaker Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Juan Perez")
        layout.addWidget(self.name_input)
        
        layout.addWidget(QLabel("Tags (optional, comma-separated):"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("e.g., manager, team lead, CEO")
        layout.addWidget(self.tags_input)
        
        layout.addWidget(QLabel("Notes (optional):"))
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        layout.addWidget(self.notes_input)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Add Speaker")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px 15px;
            }
            QPushButton:hover { background-color: #229954; }
        """)
        ok_btn.clicked.connect(self._on_ok)
        buttons_layout.addWidget(ok_btn)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
    
    @Slot()
    def _on_ok(self):
        """Slot: OK button clicked."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Required", "Please enter a speaker name")
            return
        
        self.accept()
    
    def get_data(self):
        """Get dialog data."""
        name = self.name_input.text().strip()
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        return name, tags


class SessionHistoryPanel(QWidget):
    """Session history browser and manager."""
    
    def __init__(self, database: Database, event_bus: EventBus):
        super().__init__()
        self.database = database
        self.event_bus = event_bus
        self._setup_ui()
        self._load_sessions()
        
        # Connect to auto-save signal
        self.event_bus.autosave_complete.connect(self._on_autosave_complete)
    
    def _setup_ui(self):
        """Create session history UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Session History (Sesiones)")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Help text
        help_text = QLabel(
            "Browse your past transcription sessions. "
            "View transcripts, speaker information, and summaries."
        )
        help_text.setStyleSheet("color: #666; font-size: 11px;")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by status:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "COMPLETED", "ERROR", "PAUSED"])
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Session table
        self.session_table = QTableWidget()
        self.session_table.setColumnCount(5)
        self.session_table.setHorizontalHeaderLabels(
            ["Date", "Duration", "Speakers", "Status", "File Size"]
        )
        self.session_table.setColumnWidth(0, 150)
        self.session_table.setColumnWidth(1, 100)
        self.session_table.setColumnWidth(2, 150)
        self.session_table.setColumnWidth(3, 80)
        self.session_table.setColumnWidth(4, 100)
        self.session_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.session_table.setSelectionMode(QTableWidget.SingleSelection)
        self.session_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #ecf0f1;
                padding: 5px;
            }
        """)
        layout.addWidget(self.session_table, 1)
        
        # Statistics
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("Total sessions:"))
        self.total_sessions_label = QLabel("0")
        self.total_sessions_label.setFont(QFont("Arial", 10, QFont.Bold))
        stats_layout.addWidget(self.total_sessions_label)
        stats_layout.addSpacing(20)
        stats_layout.addWidget(QLabel("Total duration:"))
        self.total_duration_label = QLabel("0h 0m")
        self.total_duration_label.setFont(QFont("Arial", 10, QFont.Bold))
        stats_layout.addWidget(self.total_duration_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        # Control buttons
        buttons_layout = QHBoxLayout()
        
        refresh_button = QPushButton("🔄 Refresh")
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        refresh_button.clicked.connect(self._load_sessions)
        buttons_layout.addWidget(refresh_button)
        
        open_button = QPushButton("📂 Open Session")
        open_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        open_button.clicked.connect(self._on_open_session)
        buttons_layout.addWidget(open_button)
        
        delete_button = QPushButton("✕ Delete Session")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        delete_button.clicked.connect(self._on_delete_session)
        buttons_layout.addWidget(delete_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
        # Store refs
        self.open_button = open_button
        self.delete_button = delete_button
        self.open_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        
        # Enable/disable on selection
        self.session_table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_sessions(self):
        """Load sessions from database."""
        self.session_table.setRowCount(0)
        
        try:
            # TODO: Query database for all sessions
            # For now, show placeholder
            placeholder_row = 0
            self.session_table.insertRow(placeholder_row)
            item = QTableWidgetItem("No sessions recorded yet.")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.session_table.setItem(placeholder_row, 0, item)
            
            self.total_sessions_label.setText("0")
            self.total_duration_label.setText("0h 0m")
        
        except Exception as e:
            error_row = 0
            self.session_table.insertRow(error_row)
            item = QTableWidgetItem(f"Error: {str(e)}")
            self.session_table.setItem(error_row, 0, item)
    
    @Slot()
    def _on_selection_changed(self):
        """Slot: selection in table changed."""
        has_selection = len(self.session_table.selectedIndexes()) > 0
        # Don't enable if placeholder row is selected
        if has_selection:
            row = self.session_table.currentRow()
            first_cell = self.session_table.item(row, 0)
            is_placeholder = first_cell and ("No sessions" in first_cell.text() or "Error" in first_cell.text())
            has_selection = not is_placeholder
        
        self.open_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
    
    @Slot()
    def _on_filter_changed(self):
        """Slot: filter combo changed."""
        # TODO: Implement filtering
        self._load_sessions()
    
    @Slot()
    def _on_open_session(self):
        """Slot: open session button clicked."""
        row = self.session_table.currentRow()
        if row < 0:
            return
        
        session_id = self.session_table.item(row, 0).text()
        QMessageBox.information(
            self,
            "Open Session",
            f"Open session {session_id} - TBD\n\n"
            f"This will display the transcript, speakers, and summary."
        )
    
    @Slot()
    def _on_delete_session(self):
        """Slot: delete session button clicked."""
        row = self.session_table.currentRow()
        if row < 0:
            return
        
        session_id = self.session_table.item(row, 0).text()
        reply = QMessageBox.question(
            self,
            "Delete Session",
            f"¿Eliminar la sesión de manera permanente?\n\n"
            f"Se eliminarán la transcripción, audio, y reporte PDF.\n"
            f"Esta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "Deleted", f"Session {session_id} deleted - TBD")
            self._load_sessions()
    
    @Slot()
    def _on_autosave_complete(self):
        """Slot: auto-save event triggered."""
        # Reload sessions to show new/updated entries
        self._load_sessions()
