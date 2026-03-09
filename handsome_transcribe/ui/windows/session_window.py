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
from .panels import (
    ConfigPanel,
    LiveSessionView,
    InterlocutoresPanel,
    SessionHistoryPanel
)


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
        
        # Initialize backend services
        self.db = Database()
        self.event_bus = EventBus()
        self.speaker_manager = SpeakerManager(self.db)
        self.config_manager = ConfigManager()
        self.session_manager = None  # Created when session starts
        
        # Setup UI
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
        
        # Add tabs to widget
        self.tab_widget.addTab(self.live_session_view, "Session")
        self.tab_widget.addTab(self.config_panel, "Configuration")
        self.tab_widget.addTab(self.interlocutores_panel, "Interlocutores")
        self.tab_widget.addTab(self.session_history_panel, "Sesiones")
        
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
    def _on_about(self):
        """Slot: show about dialog."""
        QMessageBox.information(
            self,
            "About HandsomeTranscribe",
            "HandsomeTranscribe Desktop v0.1.0\n\n"
            "Desktop application for transcription, speaker identification, and summarization.\n\n"
            "Built with PySide6 and powered by Whisper, pyannote.audio, and transformers."
        )
    
    @Slot(str)
    def _on_session_started(self, session_info_json: str):
        """Slot: session started, update status bar."""
        self.update_status("RECORDING")
    
    @Slot(str, str)
    def _on_session_completed(self, session_info_json: str, result_json: str):
        """Slot: session completed, update status bar."""
        self.update_status("COMPLETED")
        # Switch to session history to view results
        self.tab_widget.setCurrentWidget(self.session_history_panel)
    
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
