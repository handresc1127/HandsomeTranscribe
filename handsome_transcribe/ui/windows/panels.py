"""
Panels and widgets for HandsomeTranscribe tabs.

Contains:
- ConfigPanel: Configuration settings tab
- LiveSessionView: Live recording and transcription tab (principal)
- InterlocutoresPanel: Speaker library management tab
- SessionHistoryPanel: Session history and results tab
"""

import json
import os
import subprocess
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QLineEdit, QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QDialog, QScrollArea, QFrame, QGroupBox, QSpinBox,
    QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, Slot, QTimer, Signal, QUrl
from PySide6.QtGui import QFont, QIcon, QColor, QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..config_manager import ConfigManager
from ..event_bus import EventBus
from ..logger import get_logger
from ..models import SpeakerProfile

# Create logger for panels module
logger = get_logger('ui.panels')
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
        
        model_layout.addWidget(QLabel("Language:"))
        self.language_input = QComboBox()
        self.language_input.setToolTip("Language for transcription. 'Auto-detect' lets Whisper guess (may fail on short clips)")
        _languages = [
            ("Spanish", "es"),
            ("English", "en"),
            ("Auto-detect", None),
        ]
        for display, code in _languages:
            self.language_input.addItem(display, code)
        # Default to Spanish
        self.language_input.setCurrentIndex(0)
        model_layout.addWidget(self.language_input)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)
        
        # === AUDIO SETTINGS ===
        audio_group = QGroupBox("Audio Settings")
        audio_layout = QVBoxLayout()
        
        audio_layout.addWidget(QLabel("Audio Device:"))
        self.device_combo = QComboBox()
        self._device_info = []
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
            default_device = self.config_manager.get_default_audio_device()

            logger.info("Audio devices debug start")
            logger.info("Total devices detected: %s", len(devices))
            logger.info(
                "Default device: %s",
                default_device.get("name") if default_device else "None",
            )

            if devices:
                if default_device and default_device.get("hostapi") is not None:
                    logger.info(
                        "Filtering by hostapi: %s",
                        default_device.get("hostapi"),
                    )
                    filtered_devices = [
                        device for device in devices
                        if device.get("hostapi") == default_device["hostapi"]
                    ]
                    logger.info("Devices after filtering: %s", len(filtered_devices))
                    if filtered_devices:
                        devices = filtered_devices

                logger.info("Devices to show in combo:")
                for idx, device in enumerate(devices):
                    logger.info(
                        "  [%s] %s (hostapi: %s)",
                        idx,
                        device.get("name"),
                        device.get("hostapi"),
                    )

                device_names = [device["name"] for device in devices]
                self.device_combo.clear()
                self.device_combo.addItems(device_names)
                self._device_info = devices

                if default_device:
                    selected_name = default_device.get("name")
                else:
                    selected_name = None

                if selected_name:
                    default_index = self.device_combo.findText(selected_name)
                    if default_index >= 0:
                        self.device_combo.setCurrentIndex(default_index)
                        logger.info(
                            "Selected device at index %s: %s",
                            default_index,
                            selected_name,
                        )
                    elif device_names:
                        self.device_combo.setCurrentIndex(0)
                        logger.info(
                            "Selected first device as fallback: %s",
                            device_names[0],
                        )
                logger.info("Audio devices debug end")
            else:
                self.device_combo.clear()
                self.device_combo.addItem("Default Device")
                self._device_info = []
        except Exception as e:
            self.device_combo.clear()
            self.device_combo.addItem(f"Error: {str(e)[:50]}")
            self._device_info = []
    
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
            
            # Set language
            if config.idioma_transcripcion:
                idx = self.language_input.findData(config.idioma_transcripcion)
                if idx >= 0:
                    self.language_input.setCurrentIndex(idx)
        
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
            self.language_input.setCurrentIndex(0)  # Reset to Spanish
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
            session_context=self.context_text.toPlainText() or None,
            idioma_transcripcion=self.language_input.currentData()
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
            session_state = SessionState(state)
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
            if isinstance(segment, dict):
                text = segment.get("text", "")
                speaker_id = segment.get("speaker_id")
            else:
                text = getattr(segment, "text", "")
                speaker_id = getattr(segment, "speaker_id", None)
            
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
            session_state = SessionState(state)
            
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
            speakers = self.speaker_manager.database.get_all_speakers()
            if not speakers:
                placeholder = QListWidgetItem("No speakers registered yet.\n\nClick 'Add Speaker' to create one.")
                placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsSelectable)
                self.speaker_list.addItem(placeholder)
                self.speaker_count_label.setText("0")
                return

            for speaker in speakers:
                tags_str = f"  [{', '.join(speaker.tags)}]" if speaker.tags else ""
                last_seen = speaker.last_seen.strftime("%Y-%m-%d") if speaker.last_seen else "Never"
                item = QListWidgetItem(
                    f"{speaker.name}{tags_str}\n"
                    f"  Created: {speaker.created_at.strftime('%Y-%m-%d')}  |  Last seen: {last_seen}"
                )
                item.setData(Qt.UserRole, speaker.id)
                self.speaker_list.addItem(item)

            self.speaker_count_label.setText(str(len(speakers)))
        
        except Exception as e:
            error_item = QListWidgetItem(f"Error loading speakers: {str(e)}")
            self.speaker_list.addItem(error_item)
    
    @Slot()
    def _on_selection_changed(self):
        """Slot: selection in speaker list changed."""
        current = self.speaker_list.currentItem()
        has_real_item = current is not None and current.data(Qt.UserRole) is not None
        
        self.edit_button.setEnabled(has_real_item)
        self.delete_button.setEnabled(has_real_item)
    
    @Slot()
    def _on_add_speaker(self):
        """Slot: add speaker button clicked."""
        dialog = AddSpeakerDialog(self)
        if dialog.exec():
            name, tags = dialog.get_data()
            try:
                speaker = SpeakerProfile(id=0, name=name, tags=tags)
                self.speaker_manager.database.create_speaker(speaker)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create speaker: {e}")
                return
            self._load_speakers()
    
    @Slot()
    def _on_edit_speaker(self):
        """Slot: edit speaker button clicked."""
        current_item = self.speaker_list.currentItem()
        if not current_item:
            return
        
        speaker_id = current_item.data(Qt.UserRole)
        if speaker_id is None:
            return

        dialog = AddSpeakerDialog(self)
        dialog.setWindowTitle("Edit Speaker")
        # Pre-populate from current item text (name is first line before tags)
        current_name = current_item.text().split("\n")[0].split("  [")[0].strip()
        dialog.name_input.setText(current_name)
        if dialog.exec():
            name, tags = dialog.get_data()
            try:
                self.speaker_manager.database.update_speaker(
                    speaker_id, name=name, tags=tags
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not update speaker: {e}")
                return
            self._load_speakers()
    
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
            speaker_id = current_item.data(Qt.UserRole)
            if speaker_id is not None:
                try:
                    self.speaker_manager.database.delete_speaker(speaker_id)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not delete speaker: {e}")
                    return
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
            sessions = self.database.get_all_sessions()

            # Apply filter
            filter_text = self.filter_combo.currentText()
            if filter_text != "All":
                sessions = [s for s in sessions if s.state.value.upper() == filter_text]

            if not sessions:
                self.session_table.insertRow(0)
                item = QTableWidgetItem("No sessions found.")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.session_table.setItem(0, 0, item)
                self.total_sessions_label.setText("0")
                self.total_duration_label.setText("0h 0m")
                return

            total_size = 0
            for row_idx, session in enumerate(sessions):
                self.session_table.insertRow(row_idx)

                # Date
                date_item = QTableWidgetItem(
                    session.created_at.strftime("%Y-%m-%d %H:%M")
                )
                date_item.setData(Qt.UserRole, session.id)
                date_item.setData(Qt.UserRole + 1, str(session.session_dir))
                self.session_table.setItem(row_idx, 0, date_item)

                # Duration — estimate from recording file size if available
                dur_text = "—"
                rec_path = session.recording_path
                if rec_path and rec_path.exists():
                    file_size = rec_path.stat().st_size
                    # PCM-16 mono 16 kHz ≈ 32 KB/s
                    secs = file_size / 32000
                    mins = int(secs // 60)
                    secs_r = int(secs % 60)
                    dur_text = f"{mins}m {secs_r}s"
                    total_size += file_size
                self.session_table.setItem(row_idx, 1, QTableWidgetItem(dur_text))

                # Speakers
                self.session_table.setItem(row_idx, 2, QTableWidgetItem("—"))

                # Status
                self.session_table.setItem(
                    row_idx, 3, QTableWidgetItem(session.state.value.capitalize())
                )

                # File size
                size_text = "—"
                if session.session_dir and session.session_dir.exists():
                    dir_size = sum(
                        f.stat().st_size
                        for f in session.session_dir.rglob("*")
                        if f.is_file()
                    )
                    if dir_size > 1_048_576:
                        size_text = f"{dir_size / 1_048_576:.1f} MB"
                    else:
                        size_text = f"{dir_size / 1024:.0f} KB"
                self.session_table.setItem(row_idx, 4, QTableWidgetItem(size_text))

            self.total_sessions_label.setText(str(len(sessions)))
            total_mb = total_size / 1_048_576
            self.total_duration_label.setText(f"{total_mb:.1f} MB total audio")
        
        except Exception as e:
            self.session_table.insertRow(0)
            item = QTableWidgetItem(f"Error: {str(e)}")
            self.session_table.setItem(0, 0, item)
    
    @Slot()
    def _on_selection_changed(self):
        """Slot: selection in table changed."""
        row = self.session_table.currentRow()
        has_real = (
            row >= 0
            and self.session_table.item(row, 0) is not None
            and self.session_table.item(row, 0).data(Qt.UserRole) is not None
        )
        self.open_button.setEnabled(has_real)
        self.delete_button.setEnabled(has_real)
    
    @Slot()
    def _on_filter_changed(self):
        """Slot: filter combo changed."""
        self._load_sessions()
    
    @Slot()
    def _on_open_session(self):
        """Slot: open session button clicked — open session folder in file explorer."""
        row = self.session_table.currentRow()
        if row < 0:
            return
        
        session_dir = self.session_table.item(row, 0).data(Qt.UserRole + 1)
        if session_dir and Path(session_dir).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(session_dir))
        else:
            QMessageBox.warning(self, "Not Found", "Session directory not found on disk.")
    
    @Slot()
    def _on_delete_session(self):
        """Slot: delete session button clicked."""
        row = self.session_table.currentRow()
        if row < 0:
            return
        
        session_id = self.session_table.item(row, 0).data(Qt.UserRole)
        session_dir = self.session_table.item(row, 0).data(Qt.UserRole + 1)
        reply = QMessageBox.question(
            self,
            "Delete Session",
            "¿Eliminar la sesión de manera permanente?\n\n"
            "Se eliminarán la transcripción, audio, y reporte PDF.\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                if session_id is not None:
                    self.database.delete_session(session_id)
                # Remove session directory from disk
                if session_dir:
                    import shutil
                    dir_path = Path(session_dir)
                    if dir_path.exists():
                        shutil.rmtree(dir_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete session: {e}")
                return
            self._load_sessions()
    
    @Slot()
    def _on_autosave_complete(self):
        """Slot: auto-save event triggered."""
        # Reload sessions to show new/updated entries
        self._load_sessions()


class ResultsPanel(QWidget):
    """Results viewer with media playback and file access."""
    
    # Signal: request to start a new session
    new_session_requested = Signal()
    
    def __init__(self, event_bus: EventBus):
        super().__init__()
        logger.info("Initializing ResultsPanel")
        self.event_bus = event_bus
        self._session_data = None
        self._results = None
        
        self._setup_ui()
        
        # Connect to EventBus
        self.event_bus.session_completed.connect(self._on_session_completed)
        logger.debug("ResultsPanel initialized successfully")
    
    def _setup_ui(self):
        """Create results UI components."""
        main_layout = QVBoxLayout()
        
        # Title
        title = QLabel("Session Results")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        main_layout.addWidget(title)
        
        # Results tree widget
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Item", "Value", "Actions"])
        self.results_tree.setColumnWidth(0, 250)
        self.results_tree.setColumnWidth(1, 300)
        self.results_tree.setAlternatingRowColors(True)
        self.results_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QTreeWidget::item {
                padding: 8px;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        main_layout.addWidget(self.results_tree, 1)
        
        # Media player controls (initially hidden)
        self.media_controls = self._create_media_controls()
        main_layout.addWidget(self.media_controls)
        self.media_controls.hide()
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.new_session_btn = QPushButton("Nueva Sesión")
        self.new_session_btn.clicked.connect(self._on_new_session_clicked)
        self.new_session_btn.setEnabled(False)
        self.new_session_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
            QPushButton:hover:enabled {
                background-color: #2980b9;
            }
        """)
        button_layout.addWidget(self.new_session_btn)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def _create_media_controls(self) -> QGroupBox:
        """Create media player control widgets."""
        group = QGroupBox("Audio Player")
        layout = QVBoxLayout()
        
        # Initialize media player
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        # Playback controls
        controls_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._on_play_clicked)
        controls_layout.addWidget(self.play_btn)
        
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        self.pause_btn.setEnabled(False)
        controls_layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)
        
        controls_layout.addSpacing(20)
        controls_layout.addWidget(QLabel("Volume:"))
        
        # Volume control (0-100)
        from PySide6.QtWidgets import QSlider
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(150)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        controls_layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("70%")
        self.volume_label.setMinimumWidth(40)
        controls_layout.addWidget(self.volume_label)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Time display
        time_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-family: 'Courier New', monospace; font-size: 11px;")
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        layout.addLayout(time_layout)
        
        # Connect player signals
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        
        group.setLayout(layout)
        return group
    
    @Slot(str, str)
    def _on_session_completed(self, session_info_json: str, result_json: str):
        """Slot: session processing completed, display results."""
        try:
            result = json.loads(result_json)
        except (json.JSONDecodeError, TypeError):
            result = {}

        session_dir = result.get("session_dir", "")
        results = {
            "session_data": {
                "id": result.get("session_id", "N/A"),
                "directorio_sesion": session_dir,
                "recording_path": result.get("recording_path"),
                "transcript_path": result.get("transcript_path"),
                "summary_path": result.get("summary_path"),
            },
        }
        logger.info(f"Session completed, displaying results for session {result.get('session_id', 'N/A')}")
        self._results = results
        self._session_data = results["session_data"]
        
        self._populate_results_tree(results)
        self.new_session_btn.setEnabled(True)
        logger.debug("Results tree populated successfully")
    
    def _populate_results_tree(self, results: Dict):
        """Populate tree with session artifacts."""
        self.results_tree.clear()
        
        session_data = results.get("session_data")
        if not session_data:
            return
        
        session_dir = Path(session_data["directorio_sesion"])
        
        # Session info (root item)
        session_item = QTreeWidgetItem(["Session Information", "", ""])
        session_item.setFont(0, QFont("Arial", 10, QFont.Bold))
        self.results_tree.addTopLevelItem(session_item)
        
        # Session details (children)
        details = [
            ("Session ID", str(session_data.get("id", "N/A"))),
            ("Directory", str(session_dir))
        ]
        # Estimate duration from recording file if available
        audio_path_str = session_data.get("recording_path")
        if audio_path_str:
            rec = Path(audio_path_str)
            if rec.exists():
                secs = rec.stat().st_size / 32000  # PCM-16 mono 16 kHz
                details.insert(1, ("Duration", f"{int(secs // 60)}m {int(secs % 60)}s"))
        for key, value in details:
            child = QTreeWidgetItem([key, value, ""])
            session_item.addChild(child)
        
        # Add "Open Folder" button to directory row (last child)
        folder_btn = QPushButton("📁 Open Folder")
        folder_btn.clicked.connect(lambda: self._open_folder(session_dir))
        folder_btn.setMaximumWidth(120)
        dir_child_idx = session_item.childCount() - 1
        self.results_tree.setItemWidget(session_item.child(dir_child_idx), 2, folder_btn)
        
        session_item.setExpanded(True)
        
        # Audio file
        audio_path = session_dir / "recording.wav"
        if audio_path.exists():
            audio_item = QTreeWidgetItem(["Audio Recording", str(audio_path), ""])
            audio_item.setFont(0, QFont("Arial", 10, QFont.Bold))
            self.results_tree.addTopLevelItem(audio_item)
            
            play_btn = QPushButton("▶ Play Audio")
            play_btn.clicked.connect(lambda: self._load_audio(audio_path))
            play_btn.setMaximumWidth(120)
            self.results_tree.setItemWidget(audio_item, 2, play_btn)
        
        # Transcript files
        transcript_txt = session_dir / "transcript.txt"
        transcript_json = session_dir / "transcript.json"
        if transcript_txt.exists() or transcript_json.exists():
            transcript_item = QTreeWidgetItem(["Transcription", "", ""])
            transcript_item.setFont(0, QFont("Arial", 10, QFont.Bold))
            self.results_tree.addTopLevelItem(transcript_item)
            
            if transcript_txt.exists():
                txt_child = QTreeWidgetItem(["Transcript (Text)", str(transcript_txt), ""])
                transcript_item.addChild(txt_child)
                
                view_btn = QPushButton("👁 View")
                view_btn.clicked.connect(lambda: self._view_transcript(transcript_txt))
                view_btn.setMaximumWidth(120)
                self.results_tree.setItemWidget(txt_child, 2, view_btn)
            
            if transcript_json.exists():
                json_child = QTreeWidgetItem(["Transcript (JSON)", str(transcript_json), ""])
                transcript_item.addChild(json_child)
                
                open_btn = QPushButton("📄 Open")
                open_btn.clicked.connect(lambda: self._open_file(transcript_json))
                open_btn.setMaximumWidth(120)
                self.results_tree.setItemWidget(json_child, 2, open_btn)
            
            transcript_item.setExpanded(True)
        
        # Summary file
        summary_path = session_dir / "summary.md"
        if summary_path.exists():
            summary_item = QTreeWidgetItem(["Summary", str(summary_path), ""])
            summary_item.setFont(0, QFont("Arial", 10, QFont.Bold))
            self.results_tree.addTopLevelItem(summary_item)
            
            view_btn = QPushButton("👁 View Summary")
            view_btn.clicked.connect(lambda: self._view_summary(summary_path))
            view_btn.setMaximumWidth(120)
            self.results_tree.setItemWidget(summary_item, 2, view_btn)
        
        # Reports
        reports = results.get("reports", {})
        if reports:
            reports_item = QTreeWidgetItem(["Reports", "", ""])
            reports_item.setFont(0, QFont("Arial", 10, QFont.Bold))
            self.results_tree.addTopLevelItem(reports_item)
            
            for format_type, report_path in reports.items():
                report_path = Path(report_path)
                if report_path.exists():
                    format_label = format_type.upper()
                    report_child = QTreeWidgetItem([f"Report ({format_label})", str(report_path), ""])
                    reports_item.addChild(report_child)
                    
                    open_btn = QPushButton("📄 Open")
                    open_btn.clicked.connect(lambda p=report_path: self._open_file(p))
                    open_btn.setMaximumWidth(120)
                    self.results_tree.setItemWidget(report_child, 2, open_btn)
            
            reports_item.setExpanded(True)
        
        # Temp files (partial recordings)
        temp_dir = session_dir / "temp"
        if temp_dir.exists() and any(temp_dir.iterdir()):
            temp_item = QTreeWidgetItem(["Partial Recordings (temp/)", str(temp_dir), ""])
            temp_item.setFont(0, QFont("Arial", 10, QFont.Bold))
            temp_item.setForeground(0, QColor("#95a5a6"))
            self.results_tree.addTopLevelItem(temp_item)
            
            folder_btn = QPushButton("📁 Open Folder")
            folder_btn.clicked.connect(lambda: self._open_folder(temp_dir))
            folder_btn.setMaximumWidth(120)
            self.results_tree.setItemWidget(temp_item, 2, folder_btn)
    
    def _load_audio(self, audio_path: Path):
        """Load audio file into media player."""
        logger.info(f"Loading audio file: {audio_path}")
        self.media_player.setSource(QUrl.fromLocalFile(str(audio_path)))
        self.media_controls.show()
        self.play_btn.setEnabled(True)
        self._on_volume_changed(self.volume_slider.value())
        
        logger.debug(f"Audio loaded successfully, duration: {self.media_player.duration() // 1000}s")
        
        QMessageBox.information(
            self,
            "Audio Loaded",
            f"Audio file loaded:\n{audio_path.name}\n\nClick Play to start playback."
        )
    
    def _view_transcript(self, transcript_path: Path):
        """Open transcript in a dialog."""
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            dialog = TranscriptViewDialog(content, transcript_path.name, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to read transcript:\n{e}"
            )
    
    def _view_summary(self, summary_path: Path):
        """Open summary in a dialog."""
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            dialog = SummaryViewDialog(content, summary_path.name, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to read summary:\n{e}"
            )
    
    def _open_file(self, file_path: Path):
        """Open file with system default application."""
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open file:\n{e}"
            )
    
    def _open_folder(self, folder_path: Path):
        """Open folder in system file explorer."""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(str(folder_path))
            elif os.name == 'posix':  # Linux/macOS
                subprocess.run(['xdg-open' if os.uname().sysname == 'Linux' else 'open', str(folder_path)])
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open folder:\n{e}"
            )
    
    @Slot()
    def _on_play_clicked(self):
        """Slot: play button clicked."""
        self.media_player.play()
    
    @Slot()
    def _on_pause_clicked(self):
        """Slot: pause button clicked."""
        self.media_player.pause()
    
    @Slot()
    def _on_stop_clicked(self):
        """Slot: stop button clicked."""
        self.media_player.stop()
    
    @Slot(int)
    def _on_volume_changed(self, value: int):
        """Slot: volume slider changed."""
        self.audio_output.setVolume(value / 100.0)
        self.volume_label.setText(f"{value}%")
    
    @Slot(int)
    def _on_position_changed(self, position: int):
        """Slot: playback position changed."""
        self._update_time_label()
    
    @Slot(int)
    def _on_duration_changed(self, duration: int):
        """Slot: media duration available."""
        self._update_time_label()
    
    def _update_time_label(self):
        """Update time display label."""
        position = self.media_player.position() // 1000  # ms to seconds
        duration = self.media_player.duration() // 1000
        
        pos_min, pos_sec = divmod(position, 60)
        dur_min, dur_sec = divmod(duration, 60)
        
        self.time_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")
    
    @Slot()
    def _on_playback_state_changed(self):
        """Slot: playback state changed."""
        state = self.media_player.playbackState()
        
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
        elif state == QMediaPlayer.PausedState:
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:  # Stopped
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
    
    @Slot()
    def _on_new_session_clicked(self):
        """Slot: new session button clicked."""
        logger.info("New session requested by user")
        reply = QMessageBox.question(
            self,
            "Nueva Sesión",
            "¿Desea iniciar una nueva sesión?\n\n"
            "Esto cerrará los resultados actuales y volverá a la configuración.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            logger.info("User confirmed new session, clearing results")
            self._clear_results()
            self.new_session_requested.emit()
        else:
            logger.debug("User cancelled new session request")
    
    def _clear_results(self):
        """Clear current results and reset UI."""
        self.results_tree.clear()
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.media_controls.hide()
        self.new_session_btn.setEnabled(False)
        self._session_data = None
        self._results = None


class TranscriptViewDialog(QDialog):
    """Dialog for viewing transcript content."""
    
    def __init__(self, content: str, filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Transcript - {filename}")
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # Content area
        self.text_view = QPlainTextEdit()
        self.text_view.setPlainText(content)
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFont("Courier New", 10))
        self.text_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: #f9f9f9;
                border: 1px solid #bdc3c7;
                padding: 10px;
            }
        """)
        layout.addWidget(self.text_view)
        
        # Button row
        button_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy All")
        copy_btn.clicked.connect(self._on_copy_all)
        button_layout.addWidget(copy_btn)
        
        save_btn = QPushButton("💾 Save As...")
        save_btn.clicked.connect(self._on_save_as)
        button_layout.addWidget(save_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self._content = content
        self._filename = filename
    
    @Slot()
    def _on_copy_all(self):
        """Copy all text to clipboard."""
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._content)
        QMessageBox.information(self, "Copied", "Transcript copied to clipboard.")
    
    @Slot()
    def _on_save_as(self):
        """Save transcript to a new file."""
        from PySide6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Transcript As",
            self._filename,
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self._content)
                QMessageBox.information(self, "Saved", f"Transcript saved to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")


class SummaryViewDialog(QDialog):
    """Dialog for viewing summary with markdown rendering."""
    
    def __init__(self, content: str, filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Summary - {filename}")
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # Content area with QTextBrowser for markdown rendering
        from PySide6.QtWidgets import QTextBrowser
        self.text_view = QTextBrowser()
        self.text_view.setMarkdown(content)
        self.text_view.setReadOnly(True)
        self.text_view.setOpenExternalLinks(False)
        self.text_view.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #bdc3c7;
                padding: 15px;
            }
        """)
        layout.addWidget(self.text_view)
        
        # Button row
        button_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy (Markdown)")
        copy_btn.clicked.connect(self._on_copy_all)
        button_layout.addWidget(copy_btn)
        
        save_btn = QPushButton("💾 Save As...")
        save_btn.clicked.connect(self._on_save_as)
        button_layout.addWidget(save_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self._content = content
        self._filename = filename
    
    @Slot()
    def _on_copy_all(self):
        """Copy raw markdown to clipboard."""
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._content)
        QMessageBox.information(self, "Copied", "Summary markdown copied to clipboard.")
    
    @Slot()
    def _on_save_as(self):
        """Save summary to a new file."""
        from PySide6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Summary As",
            self._filename,
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*.*)"
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self._content)
                QMessageBox.information(self, "Saved", f"Summary saved to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
