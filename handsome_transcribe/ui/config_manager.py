"""
Configuration manager for application settings.

This module handles loading, saving, and validating application configuration
using Qt's QSettings for cross-platform persistence.
"""

import os
import sounddevice as sd
from pathlib import Path
from typing import Optional, List, Dict
from PySide6.QtCore import QSettings, QStandardPaths

from .models import SessionConfig
from .exceptions import ConfigurationError
from .constants import WHISPER_MODELS, DEFAULT_WHISPER_MODEL


class ConfigManager:
    """Manages application configuration and settings."""
    
    def __init__(self):
        """Initialize configuration manager with QSettings."""
        self.settings = QSettings("HandsomeTranscribe", "Desktop")
        self._config_dir = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
        )
        self._config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self) -> SessionConfig:
        """
        Load session configuration from settings and environment.
        
        Priority:
        1. Environment variables (for sensitive data like HF_TOKEN)
        2. Saved settings in QSettings
        3. Default values
        
        Returns:
            SessionConfig with loaded values
        """
        # Load from settings with defaults
        modelo_whisper = self.settings.value("whisper/model", DEFAULT_WHISPER_MODEL)
        habilitar_diarizacion = self.settings.value("features/diarization", False, type=bool)
        habilitar_resumen = self.settings.value("features/summarization", False, type=bool)
        dispositivo_audio = self.settings.value("audio/device", None)
        
        # Load HF_TOKEN from environment (more secure than storing in settings)
        hf_token = os.getenv("HF_TOKEN") or self.settings.value("auth/hf_token", None)
        
        # Session context is not persisted, always None on load
        session_context = None
        
        return SessionConfig(
            modelo_whisper=modelo_whisper,
            habilitar_diarizacion=habilitar_diarizacion,
            habilitar_resumen=habilitar_resumen,
            dispositivo_audio=dispositivo_audio,
            hf_token=hf_token,
            session_context=session_context
        )
    
    def save_config(self, config: SessionConfig):
        """
        Save session configuration to settings.
        
        Note: HF_TOKEN is not saved to settings for security reasons.
        It should be provided via environment variable.
        
        Args:
            config: SessionConfig to save
        """
        self.settings.setValue("whisper/model", config.modelo_whisper)
        self.settings.setValue("features/diarization", config.habilitar_diarizacion)
        self.settings.setValue("features/summarization", config.habilitar_resumen)
        
        if config.dispositivo_audio:
            self.settings.setValue("audio/device", config.dispositivo_audio)
        
        # Do NOT save HF_TOKEN to settings (security)
        # Do NOT save session_context (session-specific)
        
        self.settings.sync()
    
    def get_audio_devices(self) -> List[Dict[str, any]]:
        """
        Get list of available audio input devices.
        
        Returns:
            List of dictionaries with device information:
            [
                {
                    "index": 0,
                    "name": "Device Name",
                    "max_input_channels": 2,
                    "default_samplerate": 44100
                },
                ...
            ]
        """
        try:
            devices = sd.query_devices()
            input_devices = []
            
            for idx, device in enumerate(devices):
                # Only include devices with input channels
                if device.get("max_input_channels", 0) > 0:
                    input_devices.append({
                        "index": idx,
                        "name": device["name"],
                        "max_input_channels": device["max_input_channels"],
                        "default_samplerate": device["default_samplerate"]
                    })
            
            return input_devices
        except Exception as e:
            raise ConfigurationError(f"Failed to query audio devices: {e}") from e
    
    def get_default_audio_device(self) -> Optional[Dict[str, any]]:
        """
        Get default input audio device.
        
        Returns:
            Dictionary with default device info or None
        """
        try:
            default_idx = sd.default.device[0]  # Input device index
            devices = self.get_audio_devices()
            
            for device in devices:
                if device["index"] == default_idx:
                    return device
            
            # If default not found in input devices, return first available
            return devices[0] if devices else None
        except Exception as e:
            raise ConfigurationError(f"Failed to get default audio device: {e}") from e
    
    def validate_hf_token(self, token: Optional[str]) -> bool:
        """
        Validate Hugging Face token format.
        
        Note: This only checks format, not actual validity with HF API.
        Actual validation happens when pyannote tries to use it.
        
        Args:
            token: HF token string to validate
            
        Returns:
            True if token format is valid
        """
        if not token:
            return False
        
        # HF tokens typically start with "hf_" and are alphanumeric with underscores
        if not token.startswith("hf_"):
            return False
        
        if len(token) < 10:  # Tokens are usually much longer
            return False
        
        # Check for valid characters (alphanumeric + underscore)
        if not all(c.isalnum() or c == "_" for c in token):
            return False
        
        return True
    
    def validate_whisper_model(self, model: str) -> bool:
        """
        Validate Whisper model name.
        
        Args:
            model: Model name to validate
            
        Returns:
            True if model name is valid
        """
        return model in WHISPER_MODELS
    
    def validate_config(self, config: SessionConfig) -> tuple[bool, Optional[str]]:
        """
        Validate a session configuration.
        
        Args:
            config: SessionConfig to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if config is valid
            - error_message: None if valid, error string if invalid
        """
        # Validate Whisper model
        if not self.validate_whisper_model(config.modelo_whisper):
            return False, f"Invalid Whisper model: {config.modelo_whisper}"
        
        # Validate diarization requirements
        if config.habilitar_diarizacion:
            if not config.hf_token:
                return False, "Diarization requires HF_TOKEN to be set"
            if not self.validate_hf_token(config.hf_token):
                return False, "Invalid HF_TOKEN format"
        
        # Validate audio device if specified
        if config.dispositivo_audio:
            devices = self.get_audio_devices()
            device_names = [d["name"] for d in devices]
            if config.dispositivo_audio not in device_names:
                return False, f"Audio device not found: {config.dispositivo_audio}"
        
        return True, None
    
    def get_config_dir(self) -> Path:
        """
        Get application configuration directory path.
        
        Returns:
            Path to config directory
        """
        return self._config_dir
    
    def clear_settings(self):
        """Clear all saved settings (for testing or reset)."""
        self.settings.clear()
        self.settings.sync()
