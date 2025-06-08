"""TTS client module for generating multi-speaker audio using Gemini API."""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, BinaryIO
from dataclasses import dataclass
from google import genai
from google.genai import types
import wave
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
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        
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
        
        # Create multi-speaker content with voice configuration
        content = self._create_multi_speaker_content_with_voices(
            dialogue_lines, voice_host, voice_guest
        )
        
        try:
            # Generate audio using Gemini TTS with new API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=content,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=[
                                types.SpeakerVoiceConfig(
                                    speaker='Host',
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                            voice_name=voice_host,
                                        )
                                    )
                                ),
                                types.SpeakerVoiceConfig(
                                    speaker='Guest',
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                            voice_name=voice_guest,
                                        )
                                    )
                                ),
                            ]
                        )
                    ),
                    temperature=0.7,
                )
            )
            
            # Extract audio data from the new API response format
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            
            # Convert to MP3 format if needed (the API returns WAV by default)
            # For now, we'll save as WAV and change the extension later
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # Change extension to .wav since that's what we're getting
                wav_path = output_path.with_suffix('.wav')
                self._save_wav_file(wav_path, audio_data)
                # For compatibility, rename to .mp3 extension (even though it's WAV data)
                wav_path.rename(output_path)
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
    
    def _create_multi_speaker_content_with_voices(
        self, dialogue_lines: List[Dict[str, str]], voice_host: str, voice_guest: str
    ) -> str:
        """Create content with voice configuration for Gemini 2.0 TTS.
        
        Args:
            dialogue_lines: List of dialogue entries
            voice_host: Voice name for Host speaker
            voice_guest: Voice name for Guest speaker
            
        Returns:
            Formatted content with voice configuration
        """
        # Create voice mapping
        voice_mapping = {
            "Host": voice_host,
            "Guest": voice_guest
        }
        
        # Build the prompt with voice instructions
        content_parts = [
            f"Generate a podcast-style dialogue with two speakers using these voices:",
            f"- Host voice: {voice_host}",
            f"- Guest voice: {voice_guest}",
            "",
            "Dialogue:"
        ]
        
        # Add dialogue lines with voice instructions
        for line in dialogue_lines:
            speaker = line["speaker"]
            text = line["text"]
            voice = voice_mapping.get(speaker, voice_host)
            
            # Format each line with voice instruction
            content_parts.append(f"[{speaker} speaking in {voice} voice]: {text}")
        
        return '\n'.join(content_parts)
    
    def _save_wav_file(self, filename: Path, pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> None:
        """Save PCM audio data as a WAV file.
        
        Args:
            filename: Path to save the WAV file
            pcm_data: Raw PCM audio data
            channels: Number of audio channels
            rate: Sample rate in Hz
            sample_width: Sample width in bytes
        """
        with wave.open(str(filename), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)
    
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
    
    async def generate_audio_with_retry(
        self,
        dialogue_lines: List[Dict[str, str]],
        voice_host: str = "Kore",
        voice_guest: str = "Puck",
        output_path: Optional[Path] = None,
        max_retries: int = 3  # Reduced retries to avoid long wait times
    ) -> Optional[bytes]:
        """Generate audio with exponential backoff retry for rate limits.
        
        Args:
            dialogue_lines: List of dialogue entries with speaker and text
            voice_host: Voice name for Host speaker
            voice_guest: Voice name for Guest speaker
            output_path: Optional path to save the audio file
            max_retries: Maximum number of retry attempts
            
        Returns:
            Audio data in MP3 format as bytes or None if failed
        """
        for attempt in range(max_retries + 1):
            try:
                return self.generate_audio(
                    dialogue_lines=dialogue_lines,
                    voice_host=voice_host,
                    voice_guest=voice_guest,
                    output_path=output_path
                )
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a rate limit error
                if "429" in error_msg or "rate limit" in error_msg or "quota" in error_msg:
                    if attempt < max_retries:
                        # For Gemini's strict rate limit (2 requests per minute), use longer wait times
                        # Base wait time of 30 seconds + exponential backoff
                        base_wait = 30
                        wait_time = base_wait + (2 ** attempt) + random.uniform(0, 5)
                        logger.warning(f"Rate limit hit, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for rate limit")
                        raise Exception("failed_rate_limit")
                
                # Check if it's a server error (5xx)
                elif any(code in error_msg for code in ["500", "502", "503", "504"]):
                    if attempt < max_retries:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Server error, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for server error")
                        raise
                
                # For other errors, don't retry
                else:
                    logger.error(f"Non-retryable error: {e}")
                    raise
        
        return None
    
    async def generate_chapter_audios_async(
        self,
        scripts: Dict[str, List[Dict[str, str]]],
        output_dir: Path,
        voice_host: str = "Kore",
        voice_guest: str = "Puck",
        max_concurrency: int = 1,  # Reduced to 1 due to strict rate limits
        skip_existing: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Path]:
        """Generate audio files for multiple chapter scripts asynchronously.
        
        Args:
            scripts: Dictionary of chapter_title -> dialogue_lines
            output_dir: Directory to save audio files
            voice_host: Voice name for Host speaker
            voice_guest: Voice name for Guest speaker
            max_concurrency: Maximum number of concurrent requests
            skip_existing: Skip existing audio files
            max_retries: Maximum retry attempts for rate limits
            
        Returns:
            Dictionary of chapter_title -> audio_file_path
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        audio_paths = {}
        output_dir.mkdir(parents=True, exist_ok=True)
        
        async def process_chapter(idx: int, title: str, dialogue_lines: List[Dict[str, str]]) -> Optional[Path]:
            async with semaphore:
                try:
                    # Generate filename
                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
                    filename = f"{idx:02d}_{safe_title}.mp3"
                    output_path = output_dir / filename
                    
                    # Check if file already exists
                    if skip_existing and output_path.exists():
                        logger.info(f"Skipping existing audio: {title}")
                        return output_path
                    
                    # Generate audio with retry
                    audio_data = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: asyncio.run(self.generate_audio_with_retry(
                            dialogue_lines=dialogue_lines,
                            voice_host=voice_host,
                            voice_guest=voice_guest,
                            output_path=output_path,
                            max_retries=max_retries
                        ))
                    )
                    
                    if audio_data:
                        logger.info(f"Generated audio for '{title}' -> {filename}")
                        return output_path
                    else:
                        logger.error(f"Failed to generate audio for '{title}'")
                        return None
                        
                except Exception as e:
                    if "failed_rate_limit" in str(e):
                        logger.error(f"Rate limit exceeded for chapter '{title}'")
                    else:
                        logger.error(f"Failed to generate audio for chapter '{title}': {e}")
                    return None
        
        # Process chapters with rate limiting
        results = []
        for idx, (title, dialogue_lines) in enumerate(scripts.items(), 1):
            # Add delay between requests to respect rate limits (2 per minute = 30s between requests)
            if idx > 1:
                delay = 31  # 31 seconds to be safe with 2/minute limit
                logger.info(f"Waiting {delay}s before next request to respect rate limits...")
                await asyncio.sleep(delay)
            
            result = await process_chapter(idx, title, dialogue_lines)
            results.append(result)
        
        # Collect successful results
        for (title, _), result in zip(scripts.items(), results):
            if isinstance(result, Path):
                audio_paths[title] = result
            elif isinstance(result, Exception):
                logger.error(f"Exception processing chapter '{title}': {result}")
        
        return audio_paths