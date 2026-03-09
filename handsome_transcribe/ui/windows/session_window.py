"""
Main application window for HandsomeTranscribe.

SessionWindow is the primary UI container with 4 tabs:
- Session: live recording and transcription
- Configuration: audio/model settings
- Interlocutores: speaker library management
- Sesiones: session history

Enforces single active session constraint.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QMenuBar, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QIcon, QAction

from ..database import Database
from ..event_bus import EventBus
from ..speaker_manager import SpeakerManager
from ..session_manager import SessionManager
from ..config_manager import ConfigManager
from ..models import SessionConfig
from ..constants import SESSIONS_DIR
from ..logger import get_logger
from .panels import (
    ConfigPanel,
    LiveSessionView,
    InterlocutoresPanel,
    SessionHistoryPanel,
    ResultsPanel
)

# Create logger for session window
logger = get_logger('ui.session_window')


class SessionWindow(QMainWindow):
    """
    Main application window with session management and 4 tabs.
    
    Responsibilities:
    - Create and manage 4 tabs (Session, Configuration, Interlocutores, Sesiones)
    - Initialize backend services (Database, SessionManager, SpeakerManager)
    - Enforce single active session constraint
    - Connect signals from EventBus to panel slots
    - Display status bar with current session state and auto-save timestamp
    """
    
    def __init__(self):
        super().__init__()
        logger.info("Initializing SessionWindow")
        
        # Initialize backend services
        logger.debug("Initializing backend services")
        self.db = Database()
        self.event_bus = EventBus()
        self.speaker_manager = SpeakerManager(self.db)
        self.config_manager = ConfigManager()
        self.session_manager = None  # Created when session starts
        
        # Setup UI
        logger.debug("Setting up UI components")
        self._setup_ui()
        self._connect_signals()
        
        # Window properties
        self.setWindowTitle("HandsomeTranscribe - Desktop")
        self.setGeometry(100, 100, 1200, 800)
        self.move(
            (self.screen().availableGeometry().width() - 1200) // 2,
            (self.screen().availableGeometry().height() - 800) // 2
        )
        
        # State
        self._last_autosave_time = None
        
        logger.info("SessionWindow initialized successfully")
    
    def _setup_ui(self):
        """Create UI components: menu bar, tabs, status bar."""
        # Menu bar
        self._setup_menu_bar()
        
        # Central widget with tab widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 8px 20px; }
        """)
        
        # Create tabs
        self.config_panel = ConfigPanel(
            self.config_manager,
            self.event_bus,
            self.db
        )
        self.config_panel.session_requested.connect(self._on_session_requested)
        self.live_session_view = LiveSessionView(self.event_bus)
        self.interlocutores_panel = InterlocutoresPanel(
            self.speaker_manager,
            self.event_bus
        )
        self.session_history_panel = SessionHistoryPanel(
            self.db,
            self.event_bus
        )
        self.results_panel = ResultsPanel(self.event_bus)
        
        # Connect ResultsPanel signals
        self.results_panel.new_session_requested.connect(self._on_new_session)
        
        # Add tabs to widget
        self.tab_widget.addTab(self.live_session_view, "Session")
        self.tab_widget.addTab(self.config_panel, "Configuration")
        self.tab_widget.addTab(self.interlocutores_panel, "Interlocutores")
        self.tab_widget.addTab(self.session_history_panel, "Sesiones")
        self.tab_widget.addTab(self.results_panel, "Results")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("IDLE")
    
    def _setup_menu_bar(self):
        """Create menu bar with File and Help menus."""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        new_action = QAction("New Session", self)
        new_action.triggered.connect(self._on_new_session)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        
        user_guide_action = QAction("User Guide", self)
        user_guide_action.triggered.connect(self._on_user_guide)
        help_menu.addAction(user_guide_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _connect_signals(self):
        """Connect EventBus signals to slots."""
        # Session lifecycle
        self.event_bus.session_started.connect(self._on_session_started)
        self.event_bus.session_completed.connect(self._on_session_completed)
        self.event_bus.session_error.connect(self._on_session_error)
        self.event_bus.session_state_changed.connect(self._on_session_state_changed)
        
        # Auto-save
        self.event_bus.autosave_complete.connect(self._on_autosave_complete)
    
    @Slot()
    def _on_new_session(self):
        """Slot: new session initiated from menu."""
        # Verify no active session
        active_session = self.db.get_active_session()
        if active_session is not None and active_session.state.name in ["RECORDING", "PAUSED"]:
            QMessageBox.warning(
                self,
                "Active Session",
                "Una sesión activa está en progreso. Finalízala antes de iniciar una nueva."
            )
            return
        
        # Switch to Configuration tab to select settings
        self.tab_widget.setCurrentWidget(self.config_panel)
    
    @Slot()
    def _on_user_guide(self):
        """Slot: show user guide dialog."""
        guide_text = """
<h2>HandsomeTranscribe User Guide</h2>

<h3>🎤 Getting Started</h3>
<ol>
<li><b>Configure Settings:</b> Go to the 'Configuration' tab to set audio device, transcription model, and output preferences.</li>
<li><b>Add Speakers (optional):</b> Use 'Interlocutores' tab to add speaker profiles for better diarization accuracy.</li>
<li><b>Start Recording:</b> Click 'Start Recording' in the 'Session' tab or use File → New Session.</li>
<li><b>View Results:</b> After processing completes, the 'Results' tab will show all artifacts.</li>
</ol>

<h3>📋 Session Workflow</h3>
<ul>
<li><b>Recording:</b> Audio is captured in 30-60 second blocks with auto-save.</li>
<li><b>Transcription:</b> Whisper model processes audio and generates text with timestamps.</li>
<li><b>Diarization:</b> pyannote.audio identifies speakers and assigns labels (Speaker 1, Speaker 2, etc.).</li>
<li><b>Summarization:</b> Transformer model creates a concise summary of the conversation (optional).</li>
<li><b>Reporting:</b> Generates PDF, Markdown, and JSON reports with all information.</li>
</ul>

<h3>🔧 Configuration Options</h3>
<ul>
<li><b>Audio Device:</b> Select microphone input (default or specific device).</li>
<li><b>Sample Rate:</b> 16000 Hz (recommended for Whisper) or 44100 Hz (high quality).</li>
<li><b>Whisper Model:</b> tiny, base, small, medium, large (larger = more accurate, slower).</li>
<li><b>Language:</b> Auto-detect or specify language code (es, en, etc.).</li>
<li><b>Enable Diarization:</b> Speaker identification (requires HuggingFace token).</li>
<li><b>Enable Summary:</b> Generate meeting summary (optional).</li>
<li><b>Output Formats:</b> Select Markdown, JSON, PDF reports.</li>
</ul>

<h3>🎯 Tips & Best Practices</h3>
<ul>
<li><b>Quiet Environment:</b> Background noise affects transcription quality.</li>
<li><b>Clear Speech:</b> Speak clearly and at moderate pace for best results.</li>
<li><b>Speaker Profiles:</b> Adding speaker audio samples improves diarization accuracy.</li>
<li><b>Auto-Save:</b> Sessions are automatically saved every 30-60 seconds - safe to close app.</li>
<li><b>Review Results:</b> Use 'Results' tab to play audio, view transcripts, and access reports.</li>
</ul>

<h3>📁 Output Directory</h3>
<p>Session files are saved to: <code>outputs/sessions/session_&lt;id&gt;/</code></p>
<ul>
<li><b>recording.wav:</b> Full audio recording</li>
<li><b>transcript.txt / .json:</b> Transcription with timestamps</li>
<li><b>summary.md:</b> Meeting summary (if enabled)</li>
<li><b>session_&lt;id&gt;_report.{md,json,pdf}:</b> Comprehensive reports</li>
<li><b>temp/:</b> Partial recordings (30-60 sec blocks)</li>
</ul>

<h3>⚙️ Troubleshooting</h3>
<ul>
<li><b>No audio:</b> Check microphone permissions and device selection.</li>
<li><b>Poor transcription:</b> Try a larger Whisper model or specify language manually.</li>
<li><b>Diarization not working:</b> Verify HuggingFace token is set (requires authentication).</li>
<li><b>Slow processing:</b> Use smaller Whisper model (tiny/base) or disable summarization.</li>
</ul>

<hr>
<p><i>For more information, visit the project README or GitHub repository.</i></p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("User Guide - HandsomeTranscribe")
        msg.setTextFormat(Qt.RichText)
        msg.setText(guide_text)
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setMinimumWidth(700)
        msg.exec()
    
    @Slot()
    def _on_about(self):
        """Slot: show about dialog."""
        about_text = """
<h2>HandsomeTranscribe Desktop</h2>
<p><b>Version:</b> 0.1.0 (Sprint 5 MVP)</p>
<p><b>Author:</b> handresc1127</p>

<h3>Description</h3>
<p>Desktop application for audio transcription, speaker diarization, and meeting summarization.</p>

<h3>Technology Stack</h3>
<ul>
<li><b>UI Framework:</b> PySide6 (Qt for Python)</li>
<li><b>Transcription:</b> OpenAI Whisper</li>
<li><b>Diarization:</b> pyannote.audio (Hugging Face)</li>
<li><b>Summarization:</b> Hugging Face Transformers</li>
<li><b>Reporting:</b> ReportLab (PDF generation)</li>
<li><b>Database:</b> SQLite 3</li>
</ul>

<h3>Features</h3>
<ul>
<li>✅ Real-time audio recording with live transcription</li>
<li>✅ Multi-speaker diarization with speaker identification</li>
<li>✅ AI-powered meeting summarization</li>
<li>✅ PDF, Markdown, and JSON report generation</li>
<li>✅ Session history and playback</li>
<li>✅ Speaker library management</li>
<li>✅ Auto-save and crash recovery</li>
</ul>

<h3>License</h3>
<p>MIT License - Open Source</p>

<h3>Links</h3>
<p>
📂 Project: HandsomeTranscribe<br>
🐙 GitHub: <a href="https://github.com/handresc1127/HandsomeTranscribe">github.com/handresc1127/HandsomeTranscribe</a><br>
📧 Contact: handresc1127@github.com
</p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("About - HandsomeTranscribe")
        msg.setTextFormat(Qt.RichText)
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setMinimumWidth(600)
        msg.exec()
    
    @Slot(str)
    def _on_session_started(self, session_info_json: str):
        """Slot: session started, update status bar."""
        self.update_status("RECORDING")
    
    @Slot(str, str)
    def _on_session_completed(self, session_info_json: str, result_json: str):
        """Slot: session completed, update status bar and switch to results."""
        self.update_status("COMPLETED")
        # Switch to results panel to view session artifacts
        self.tab_widget.setCurrentWidget(self.results_panel)
    
    @Slot(str, str)
    def _on_session_error(self, error_title: str, error_message: str):
        """Slot: session error occurred."""
        self.update_status("ERROR")
        QMessageBox.critical(self, error_title, error_message)
    
    @Slot(str)
    def _on_session_state_changed(self, state: str):
        """Slot: session state changed."""
        self.update_status(state)
    
    @Slot(object)
    def _on_session_requested(self, config):
        """Slot: session start requested from ConfigPanel."""
        try:
            # Create or update session manager
            self.session_manager = SessionManager(
                config,
                self.event_bus,
                self.db,
                self.speaker_manager
            )
            
            # Switch to live session tab
            self.tab_widget.setCurrentWidget(self.live_session_view)
        except Exception as e:
            self.event_bus.emit_session_error("Failed to Start Session", str(e))
    
    
    def update_status(self, state: Optional[str] = None):
        """
        Update status bar with current state and auto-save timestamp.
        
        Args:
            state: Current session state (IDLE, RECORDING, PAUSED, etc.)
        """
        status_parts = []
        
        if state:
            status_parts.append(f"State: {state}")
        
        if self._last_autosave_time:
            time_str = self._last_autosave_time.strftime("%H:%M:%S")
            status_parts.append(f"Last auto-save: {time_str}")
        
        status_text = " | ".join(status_parts) if status_parts else "Ready"
        self.status_bar.showMessage(status_text)
    
    def closeEvent(self, event):
        """
        Handle window close event.
        
        Warn if session is active (RECORDING or PAUSED).
        """
        if self.session_manager:
            from ..models import SessionState
            if self.session_manager.state in [SessionState.RECORDING, SessionState.PAUSED]:
                reply = QMessageBox.warning(
                    self,
                    "Active Session",
                    "¿Estás seguro que deseas cerrar?\n\n"
                    "La sesión está en progreso. Aunque auto-guardado está habilitado, "
                    "el procesamiento pendiente (transcripción, diarizacion, resumen) se detendrá.\n\n"
                    "¿Deseas continuar?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    event.ignore()
                    return
        
        event.accept()
