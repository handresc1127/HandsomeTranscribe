"""
Unit tests for ConfigManager.

Tests configuration loading/saving and validation.
"""

import pytest
from unittest.mock import patch

from handsome_transcribe.ui.config_manager import ConfigManager
from handsome_transcribe.ui.models import SessionConfig


class TestConfigManager:
    """Tests for ConfigManager."""
    
    def test_create_config_manager(self, config_manager):
        """Test creating a ConfigManager instance."""
        assert config_manager is not None
    
    def test_save_and_load_config(self, config_manager):
        """Test saving and loading configuration."""
        config = SessionConfig(
            modelo_whisper="large",
            habilitar_diarizacion=True,
            habilitar_resumen=True,
            dispositivo_audio="Test Device"
        )
        
        config_manager.save_config(config)
        loaded_config = config_manager.load_config()
        
        assert loaded_config.modelo_whisper == "large"
        assert loaded_config.habilitar_diarizacion is True
        assert loaded_config.habilitar_resumen is True
        assert loaded_config.dispositivo_audio == "Test Device"
    
    def test_load_default_config(self, config_manager):
        """Test loading default config when none exists."""
        config = config_manager.load_config()
        
        assert config.modelo_whisper == "base"
        assert config.habilitar_diarizacion is False
        assert config.habilitar_resumen is False
    
    @patch.dict('os.environ', {'HF_TOKEN': 'hf_test_token_from_env'})
    def test_load_config_with_env_token(self, config_manager):
        """Test loading config with HF_TOKEN from environment."""
        config = config_manager.load_config()
        
        assert config.hf_token == "hf_test_token_from_env"
    
    def test_validate_hf_token_valid(self, config_manager):
        """Test validating a valid HF token."""
        valid_token = "hf_abcdefghijklmnopqrstuvwxyz123456"
        
        is_valid = config_manager.validate_hf_token(valid_token)
        
        assert is_valid is True
    
    def test_validate_hf_token_invalid(self, config_manager):
        """Test validating an invalid HF token."""
        invalid_token = "invalid_token"
        
        is_valid = config_manager.validate_hf_token(invalid_token)
        
        assert is_valid is False
    
    def test_validate_hf_token_none(self, config_manager):
        """Test validating None token."""
        is_valid = config_manager.validate_hf_token(None)

        assert is_valid is False
    
    def test_validate_whisper_model_valid(self, config_manager):
        """Test validating valid Whisper model."""
        valid_models = ["tiny", "base", "small", "medium", "large"]
        
        for model in valid_models:
            is_valid = config_manager.validate_whisper_model(model)
            assert is_valid is True, f"Model {model} should be valid"
    
    def test_validate_whisper_model_invalid(self, config_manager):
        """Test validating invalid Whisper model."""
        invalid_model = "nonexistent-model"
        
        is_valid = config_manager.validate_whisper_model(invalid_model)
        
        assert is_valid is False
    
    def test_validate_config_complete_valid(self, config_manager):
        """Test validating a complete valid configuration."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=False,
            habilitar_resumen=False,
            dispositivo_audio=None,
            hf_token=None
        )
        
        is_valid, error = config_manager.validate_config(config)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_config_invalid_whisper_model(self, config_manager):
        """Test validating config with invalid Whisper model."""
        config = SessionConfig(
            modelo_whisper="invalid_model",
            habilitar_diarizacion=False,
            habilitar_resumen=False
        )
        
        is_valid, error = config_manager.validate_config(config)
        
        assert is_valid is False
        assert "Whisper" in error
    
    def test_validate_config_diarization_without_token(self, config_manager):
        """Test validating config with diarization enabled but no HF token."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=True,
            habilitar_resumen=False,
            hf_token=None
        )
        
        is_valid, error = config_manager.validate_config(config)
        
        assert is_valid is False
        assert "HF_TOKEN" in error or "token" in error.lower()
    
    def test_validate_config_diarization_with_valid_token(self, config_manager):
        """Test validating config with diarization and valid token."""
        config = SessionConfig(
            modelo_whisper="base",
            habilitar_diarizacion=True,
            habilitar_resumen=False,
            hf_token="hf_abcdefghijklmnopqrstuvwxyz123456"
        )
        
        is_valid, error = config_manager.validate_config(config)
        
        assert is_valid is True
        assert error is None
    
    @patch('sounddevice.query_devices')
    def test_get_audio_devices(self, mock_query_devices, config_manager):
        """Test retrieving audio devices."""
        # Mock sounddevice response
        mock_query_devices.return_value = [
            {'name': 'Device 1', 'max_input_channels': 2},
            {'name': 'Device 2', 'max_input_channels': 1},
            {'name': 'Device 3', 'max_input_channels': 0}
        ]
        
        devices = config_manager.get_audio_devices()

        # Should only include devices with input channels
        assert len(devices) == 2
        names = [d["name"] for d in devices]
        assert "Device 1" in names
        assert "Device 2" in names
        assert "Device 3" not in names
