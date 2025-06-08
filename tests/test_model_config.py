"""Tests for ModelConfig class."""

import os
import pytest
from unittest.mock import patch
from argparse import Namespace

from pdf_podcast.model_config import ModelConfig


class TestModelConfig:
    """Test cases for ModelConfig class."""
    
    def test_from_args_with_cli_values(self):
        """Test ModelConfig creation with CLI arguments."""
        args = Namespace(
            model_pdf="custom-pdf-model",
            model_script="custom-script-model", 
            model_tts="custom-tts-model"
        )
        
        config = ModelConfig.from_args(args)
        
        assert config.pdf_model == "custom-pdf-model"
        assert config.script_model == "custom-script-model"
        assert config.tts_model == "custom-tts-model"
    
    def test_from_args_with_env_vars(self):
        """Test ModelConfig creation with environment variables."""
        args = Namespace()
        
        with patch.dict(os.environ, {
            'GEMINI_MODEL_PDF_PARSER': 'env-pdf-model',
            'GEMINI_MODEL_SCRIPT_BUILDER': 'env-script-model',
            'GEMINI_MODEL_TTS': 'env-tts-model'
        }):
            config = ModelConfig.from_args(args)
            
            assert config.pdf_model == "env-pdf-model"
            assert config.script_model == "env-script-model"
            assert config.tts_model == "env-tts-model"
    
    def test_from_args_with_defaults(self):
        """Test ModelConfig creation with default values."""
        args = Namespace()
        
        with patch.dict(os.environ, {}, clear=True):
            config = ModelConfig.from_args(args)
            
            assert config.pdf_model == "gemini-2.5-flash-preview-05-20"
            assert config.script_model == "gemini-2.5-pro-preview-06-05"
            assert config.tts_model == "gemini-2.5-pro-preview-tts"
    
    def test_priority_cli_over_env(self):
        """Test that CLI arguments take priority over environment variables."""
        args = Namespace(
            model_pdf="cli-pdf-model",
            model_script=None,
            model_tts="cli-tts-model"
        )
        
        with patch.dict(os.environ, {
            'GEMINI_MODEL_PDF_PARSER': 'env-pdf-model',
            'GEMINI_MODEL_SCRIPT_BUILDER': 'env-script-model',
            'GEMINI_MODEL_TTS': 'env-tts-model'
        }):
            config = ModelConfig.from_args(args)
            
            # CLI values should override env
            assert config.pdf_model == "cli-pdf-model"
            assert config.tts_model == "cli-tts-model"
            # No CLI value, should use env
            assert config.script_model == "env-script-model"
    
    def test_get_config_summary(self):
        """Test configuration summary generation."""
        config = ModelConfig(
            pdf_model="test-pdf",
            script_model="test-script",
            tts_model="test-tts"
        )
        
        summary = config.get_config_summary()
        
        expected = {
            "PDF Parser Model": "test-pdf",
            "Script Builder Model": "test-script", 
            "TTS Model": "test-tts"
        }
        
        assert summary == expected
    
    def test_resolve_model_priority(self):
        """Test _resolve_model method with different priorities."""
        # CLI value takes priority
        result = ModelConfig._resolve_model(
            "test", "cli-value", "TEST_ENV", "default-value"
        )
        assert result == "cli-value"
        
        # Env value when no CLI
        with patch.dict(os.environ, {'TEST_ENV': 'env-value'}):
            result = ModelConfig._resolve_model(
                "test", None, "TEST_ENV", "default-value"
            )
            assert result == "env-value"
        
        # Default value when no CLI or env
        with patch.dict(os.environ, {}, clear=True):
            result = ModelConfig._resolve_model(
                "test", None, "TEST_ENV", "default-value"
            )
            assert result == "default-value"