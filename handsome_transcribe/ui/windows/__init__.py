"""
UI windows and panels for HandsomeTranscribe desktop application.

Exports all window and panel classes for easy importing.
"""

from .session_window import SessionWindow
from .panels import (
    ConfigPanel,
    LiveSessionView,
    InterlocutoresPanel,
    SessionHistoryPanel
)

__all__ = [
    "SessionWindow",
    "ConfigPanel",
    "LiveSessionView",
    "InterlocutoresPanel",
    "SessionHistoryPanel"
]
