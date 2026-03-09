"""
Panels and widgets for HandsomeTranscribe tabs.

Contains:
- ConfigPanel: Configuration settings tab
- LiveSessionView: Live recording and transcription tab (principal)
- InterlocutoresPanel: Speaker library management tab
- SessionHistoryPanel: Session history and results tab
"""

from typing import Optional, List
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QLineEdit, QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QDialog, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QFont

from ..config_manager import ConfigManager
from ..event_bus import EventBus
from ..speaker_manager import SpeakerManager
from ..database import Database
from ..models import SessionConfig, SessionState


class ConfigPanel(QWidget):
    """Configuration tab for session settings."""
    
    def __init__(self, config_manager: ConfigManager, event_bus: EventBus):
        super().__init__()
        self.config_manager = config_manager
        self.event_bus = event_bus
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Create configuration UI components."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Session Configuration")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Whisper Model
        layout.addWidget(QLabel("Whisper Model:"))
        self.whisper_combo = QComboBox()
        whisper_models = ["tiny", "base", "small", "medium", "large"]
        self.whisper_combo.addItems(whisper_models)
        layout.addWidget(self.whisper_combo)
        
        # Diarization
        self.diarization_check = QCheckBox("Enable Diarization (requires HF_TOKEN)")
        layout.addWidget(self.diarization_check)
        
        layout.addWidget(QLabel("HF_TOKEN:"))
        self.hf_token_input = QLineEdit()
        self.hf_token_input.setReadOnly(True)
        self.hf_token_input.setPlaceholderText("Set via environment variable HF_TOKEN")
        layout.addWidget(self.hf_token_input)
        
        # Summarization
        self.summarization_check = QCheckBox("Enable Summarization")
        layout.addWidget(self.summarization_check)
        
        # Audio Device
        layout.addWidget(QLabel("Audio Device:"))
        self.device_combo = QComboBox()
        self._load_audio_devices()
        layout.addWidget(self.device_combo)
        
        # Session Context
        layout.addWidget(QLabel("Session Context (optional):"))
        layout.addWidget(QLabel("Contexto de la sesión o tema a tratar..."))
        self.context_text = QTextEdit()
        self.context_text.setPlaceholderText("Hoy hablaremos sobre...\n\nEste contexto puede mejorar transcripción/resumen (funcionalidad futura)")
        self.context_text.setMaximumHeight(100)
        layout.addWidget(self.context_text)
        
        # Status
        layout.addWidget(QLabel("Mode: Free/Local"))
        
        # Load current config
        self._load_current_config()
        
        # Start Session button
        layout.addStretch()
        self.start_button = QPushButton("Start Session")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        self.start_button.clicked.connect(self._on_start_session)
        layout.addWidget(self.start_button)
        
        self.setLayout(layout)
    
    def _load_audio_devices(self):
        """Load audio devices into combo box."""
        try:
            devices = self.config_manager.get_audio_devices()
            self.device_combo.addItems(devices)
        except Exception as e:
            self.device_combo.addItem(f"Error loading devices: {str(e)}")
    
    def _load_current_config(self):
        """Load current configuration into form."""
        config = self.config_manager.load_config()
        
        # Set Whisper model
        index = self.whisper_combo.findText(config.modelo_whisper)
        if index >= 0:
            self.whisper_combo.setCurrentIndex(index)
        
        # Set diarization checkbox
        self.diarization_check.setChecked(config.habilitar_diarizacion)
        
        # Set HF token
        if config.hf_token:
            self.hf_token_input.setText(config.hf_token[:20] + "...")
        
        # Set summarization checkbox
        self.summarization_check.setChecked(config.habilitar_resumen)
        
        # Set audio device
        if config.dispositivo_audio:
            index = self.device_combo.findText(config.dispositivo_audio)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)
    
    @Slot()
    def _on_start_session(self):
        """Slot: start session button clicked."""
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
            QMessageBox.warning(self, "Configuration Invalid", error)
            return
        
        # Emit signal to start session
        self.event_bus.emit_start_session_requested(config)


class LiveSessionView(QWidget):
    """Live recording and transcription view (main Session tab)."""
    
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Create live session UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Live Session")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Speaker avatars (placeholder for now)
        speakers_layout = QHBoxLayout()
        speakers_label = QLabel("Active Speakers:")
        speakers_layout.addWidget(speakers_label)
        speakers_layout.addStretch()
        layout.addLayout(speakers_layout)
        self.speakers_frame = QFrame()
        self.speakers_frame.setMaximumHeight(60)
        layout.addWidget(self.speakers_frame)
        
        # Transcript view
        layout.addWidget(QLabel("Transcript:"))
        self.transcript_view = QPlainTextEdit()
        self.transcript_view.setReadOnly(True)
        layout.addWidget(self.transcript_view)
        
        # Progress bar
        layout.addWidget(QLabel("Duration:"))
        self.duration_progress = QProgressBar()
        self.duration_progress.setFormat("%m:%s")
        layout.addWidget(self.duration_progress)
        
        # Stage label
        self.stage_label = QLabel("Waiting to start...")
        layout.addWidget(self.stage_label)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._on_pause_resume)
        controls_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet("""
            QPushButton { background-color: #e74c3c; color: white; padding: 10px; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.stop_button.clicked.connect(self._on_stop)
        controls_layout.addWidget(self.stop_button)
        
        layout.addLayout(controls_layout)
        self.setLayout(layout)
        
        self._is_paused = False
    
    def _connect_signals(self):
        """Connect EventBus signals."""
        self.event_bus.partial_transcript_ready.connect(self._on_partial_transcript)
        self.event_bus.speaker_identified.connect(self._on_speaker_identified)
        self.event_bus.session_state_changed.connect(self._on_state_changed)
    
    @Slot(list)
    def _on_partial_transcript(self, segments: list):
        """Slot: partial transcript ready."""
        for segment in segments:
            text = segment.get("text", "")
            if text:
                self.transcript_view.appendPlainText(text)
    
    @Slot(int, str, float)
    def _on_speaker_identified(self, speaker_id: int, name: str, confidence: float):
        """Slot: speaker identified."""
        self.stage_label.setText(f"Speaking: {name} ({confidence:.0%})")
    
    @Slot(str)
    def _on_state_changed(self, state: str):
        """Slot: session state changed."""
        if state == "PAUSED":
            self.pause_button.setText("Resume")
            self._is_paused = True
        elif state == "RECORDING":
            self.pause_button.setText("Pause")
            self._is_paused = False
        elif state == "COMPLETED":
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(False)
    
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
            "¿Detener la grabación actual? Se iniciará el procesamiento de transcripción.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.event_bus.emit_stop_recording()


class InterlocutoresPanel(QWidget):
    """Speaker library management tab."""
    
    def __init__(self, speaker_manager: SpeakerManager, event_bus: EventBus):
        super().__init__()
        self.speaker_manager = speaker_manager
        self.event_bus = event_bus
        self._setup_ui()
    
    def _setup_ui(self):
        """Create speaker management UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Speaker Library (Interlocutores)")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Speaker list
        self.speaker_list = QListWidget()
        layout.addWidget(self.speaker_list)
        
        # Control buttons
        buttons_layout = QHBoxLayout()
        
        add_button = QPushButton("Add Speaker")
        add_button.clicked.connect(self._on_add_speaker)
        buttons_layout.addWidget(add_button)
        
        edit_button = QPushButton("Edit Speaker")
        edit_button.clicked.connect(self._on_edit_speaker)
        buttons_layout.addWidget(edit_button)
        
        delete_button = QPushButton("Delete Speaker")
        delete_button.setStyleSheet("""
            QPushButton { background-color: #e74c3c; color: white; padding: 10px; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        delete_button.clicked.connect(self._on_delete_speaker)
        buttons_layout.addWidget(delete_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Load speakers
        self._load_speakers()
    
    def _load_speakers(self):
        """Load speakers from database."""
        self.speaker_list.clear()
        # TODO: Load from database
        placeholder = QListWidgetItem("No speakers yet. Add one to get started.")
        self.speaker_list.addItem(placeholder)
    
    @Slot()
    def _on_add_speaker(self):
        """Slot: add speaker button clicked."""
        QMessageBox.information(self, "Add Speaker", "Add speaker dialog - TBD")
    
    @Slot()
    def _on_edit_speaker(self):
        """Slot: edit speaker button clicked."""
        if not self.speaker_list.currentItem():
            QMessageBox.warning(self, "No Selection", "Select a speaker to edit")
            return
        QMessageBox.information(self, "Edit Speaker", "Edit speaker dialog - TBD")
    
    @Slot()
    def _on_delete_speaker(self):
        """Slot: delete speaker button clicked."""
        if not self.speaker_list.currentItem():
            QMessageBox.warning(self, "No Selection", "Select a speaker to delete")
            return
        reply = QMessageBox.question(
            self,
            "Delete Speaker",
            "¿Eliminar este interlocutor permanentemente?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "Deleted", "Speaker deleted - TBD")


class SessionHistoryPanel(QWidget):
    """Session history and results tab (placeholder)."""
    
    def __init__(self, database: Database):
        super().__init__()
        self.database = database
        self._setup_ui()
    
    def _setup_ui(self):
        """Create session history UI."""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Session History (Sesiones)")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)
        
        # Table
        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(5)
        self.sessions_table.setHorizontalHeaderLabels([
            "ID", "Date", "Duration", "Speakers", "Status"
        ])
        layout.addWidget(self.sessions_table)
        
        # Control buttons
        buttons_layout = QHBoxLayout()
        
        open_button = QPushButton("Open Session")
        open_button.clicked.connect(self._on_open_session)
        buttons_layout.addWidget(open_button)
        
        delete_button = QPushButton("Delete Session")
        delete_button.setStyleSheet("""
            QPushButton { background-color: #e74c3c; color: white; padding: 10px; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        delete_button.clicked.connect(self._on_delete_session)
        buttons_layout.addWidget(delete_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Load sessions
        self._load_sessions()
    
    def _load_sessions(self):
        """Load sessions from database."""
        # TODO: Load from database
        self.sessions_table.setRowCount(0)
    
    @Slot()
    def _on_open_session(self):
        """Slot: open session button clicked."""
        QMessageBox.information(self, "Open Session", "Open session dialog - TBD")
    
    @Slot()
    def _on_delete_session(self):
        """Slot: delete session button clicked."""
        reply = QMessageBox.question(
            self,
            "Delete Session",
            "¿Eliminar esta sesión permanentemente?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "Deleted", "Session deleted - TBD")
