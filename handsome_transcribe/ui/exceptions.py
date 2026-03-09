"""
Custom exceptions for the UI layer.
"""


class UIError(Exception):
    """Base exception for UI-related errors."""
    pass


class SessionError(UIError):
    """Raised when session operations fail."""
    pass


class ActiveSessionError(SessionError):
    """Raised when attempting to start a new session while one is already active."""
    pass


class ConfigurationError(UIError):
    """Raised when configuration is invalid."""
    pass


class WorkerError(UIError):
    """Raised when a worker operation fails."""
    pass


class DatabaseError(UIError):
    """Raised when database operations fail."""
    pass


class SpeakerError(UIError):
    """Raised when speaker management operations fail."""
    pass
