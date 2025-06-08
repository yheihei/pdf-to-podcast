"""Model configuration management for PDF podcast generation."""

import os
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for Gemini models used in different components."""
    pdf_model: str
    script_model: str
    tts_model: str
    
    @classmethod
    def from_args(cls, args) -> 'ModelConfig':
        """Create ModelConfig from command line arguments.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            ModelConfig instance with resolved model names
        """
        pdf_model = cls._resolve_model(
            'pdf', 
            getattr(args, 'model_pdf', None),
            'GEMINI_MODEL_PDF_PARSER',
            'gemini-2.5-flash-preview-05-20'
        )
        
        script_model = cls._resolve_model(
            'script',
            getattr(args, 'model_script', None),
            'GEMINI_MODEL_SCRIPT_BUILDER', 
            'gemini-2.5-pro-preview-06-05'
        )
        
        tts_model = cls._resolve_model(
            'tts',
            getattr(args, 'model_tts', None),
            'GEMINI_MODEL_TTS',
            'gemini-2.5-pro-preview-tts'
        )
        
        config = cls(
            pdf_model=pdf_model,
            script_model=script_model,
            tts_model=tts_model
        )
        
        logger.info(f"Model configuration resolved:")
        logger.info(f"  PDF Parser: {config.pdf_model}")
        logger.info(f"  Script Builder: {config.script_model}")
        logger.info(f"  TTS Client: {config.tts_model}")
        
        return config
    
    @staticmethod
    def _resolve_model(
        model_type: str,
        cli_value: Optional[str],
        env_var: str,
        default_value: str
    ) -> str:
        """Resolve model name using priority: CLI > ENV > Default.
        
        Args:
            model_type: Type of model (for logging)
            cli_value: Value from CLI argument
            env_var: Environment variable name
            default_value: Default model name
            
        Returns:
            Resolved model name
        """
        # Priority 1: CLI argument
        if cli_value:
            logger.debug(f"{model_type} model from CLI: {cli_value}")
            return cli_value
        
        # Priority 2: Environment variable
        env_value = os.getenv(env_var)
        if env_value:
            logger.debug(f"{model_type} model from ENV {env_var}: {env_value}")
            return env_value
        
        # Priority 3: Default value
        logger.debug(f"{model_type} model using default: {default_value}")
        return default_value
    
    def get_config_summary(self) -> dict:
        """Get configuration summary for display.
        
        Returns:
            Dictionary with configuration details
        """
        return {
            "PDF Parser Model": self.pdf_model,
            "Script Builder Model": self.script_model,
            "TTS Model": self.tts_model
        }