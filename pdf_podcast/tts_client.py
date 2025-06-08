"""TTS client module for generating multi-speaker audio using Gemini API."""

import logging
import base64
from typing import Dict, List, Optional, BinaryIO
from dataclasses import dataclass
import google.generativeai as genai
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """Configuration for a speaker voice."""
    speaker_id: str  # "Host" or "Guest"
    voice_name: str  # e.g., "Kore", "Puck"


class TTSClient:
    """Generates multi-speaker audio from dialogue scripts using Gemini TTS API."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro-preview-tts"):
        """Initialize TTS client with Gemini API configuration.
        
        Args:
            api_key: Google API key for Gemini
            model_name: Gemini TTS model to use
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
    def generate_audio(
        self,
        dialogue_lines: List[Dict[str, str]],
        voice_host: str = "Kore",
        voice_guest: str = "Puck",
        output_path: Optional[Path] = None
    ) -> bytes:
        """Generate multi-speaker audio from dialogue lines.
        
        Args:
            dialogue_lines: List of dialogue entries with speaker and text
            voice_host: Voice name for Host speaker
            voice_guest: Voice name for Guest speaker
            output_path: Optional path to save the audio file
            
        Returns:
            Audio data in MP3 format as bytes
        """
        logger.info(f"Generating audio with {len(dialogue_lines)} dialogue lines")
        
        # Create multi-speaker content
        content = self._create_multi_speaker_content(dialogue_lines)
        
        # Create voice configuration
        multi_speaker_config = {
            "multiSpeakerVoiceConfig": {
                "speakers": [
                    {
                        "speakerId": "Host",
                        "voiceName": voice_host
                    },
                    {
                        "speakerId": "Guest", 
                        "voiceName": voice_guest
                    }
                ]
            }
        }
        
        try:
            # Generate audio using Gemini TTS
            response = self.model.generate_content(
                [content],
                generation_config={
                    **multi_speaker_config,
                    "response_modalities": ["AUDIO"],
                    "response_mime_type": "audio/mp3",
                    "temperature": 0.7,
                }
            )
            
            # Extract audio data
            audio_data = self._extract_audio_data(response)
            
            # Save to file if path provided
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
                logger.info(f"Audio saved to {output_path}")
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Failed to generate audio: {e}")
            raise
    
    def _create_multi_speaker_content(self, dialogue_lines: List[Dict[str, str]]) -> str:
        """Create content with speaker tags for multi-speaker synthesis.
        
        Args:
            dialogue_lines: List of dialogue entries
            
        Returns:
            Formatted content with speaker tags
        """
        content_parts = []
        
        for line in dialogue_lines:
            speaker_id = line["speaker"]  # "Host" or "Guest"
            text = line["text"]
            
            # Format with speaker tags
            content_parts.append(f'<speaker id="{speaker_id}">{text}</speaker>')
        
        return '\n'.join(content_parts)
    
    def _extract_audio_data(self, response) -> bytes:
        """Extract audio data from Gemini response.
        
        Args:
            response: Response from Gemini API
            
        Returns:
            Audio data as bytes
        """
        # Check if response contains audio
        if not response.parts:
            raise ValueError("No audio data in response")
        
        # Find audio part
        for part in response.parts:
            if hasattr(part, 'inline_data') and part.inline_data.mime_type.startswith('audio/'):
                # Decode base64 audio data
                return base64.b64decode(part.inline_data.data)
        
        raise ValueError("No audio data found in response parts")
    
    def generate_chapter_audios(
        self,
        scripts: Dict[str, List[Dict[str, str]]],
        output_dir: Path,
        voice_host: str = "Kore",
        voice_guest: str = "Puck"
    ) -> Dict[str, Path]:
        """Generate audio files for multiple chapter scripts.
        
        Args:
            scripts: Dictionary of chapter_title -> dialogue_lines
            output_dir: Directory to save audio files
            voice_host: Voice name for Host speaker
            voice_guest: Voice name for Guest speaker
            
        Returns:
            Dictionary of chapter_title -> audio_file_path
        """
        audio_paths = {}
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for idx, (title, dialogue_lines) in enumerate(scripts.items(), 1):
            try:
                # Generate filename
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
                filename = f"{idx:02d}_{safe_title}.mp3"
                output_path = output_dir / filename
                
                # Generate audio
                self.generate_audio(
                    dialogue_lines=dialogue_lines,
                    voice_host=voice_host,
                    voice_guest=voice_guest,
                    output_path=output_path
                )
                
                audio_paths[title] = output_path
                logger.info(f"Generated audio for '{title}' -> {filename}")
                
            except Exception as e:
                logger.error(f"Failed to generate audio for chapter '{title}': {e}")
                # Continue with other chapters
        
        return audio_paths