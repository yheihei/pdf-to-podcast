"""TTS client module for generating single-speaker audio using Gemini API."""

import asyncio
import logging
import time
import random
from typing import Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass
from google import genai
from google.genai import types
import wave
from pathlib import Path
from pydub import AudioSegment

if TYPE_CHECKING:
    from .script_builder import SectionScript

logger = logging.getLogger(__name__)



@dataclass
class VoiceConfig:
    """Configuration for a speaker voice."""
    speaker_id: str  # "Host" or "Guest"
    voice_name: str  # e.g., "Zephyr", "Puck"


class TTSClient:
    """Generates single-speaker audio from lecture scripts using Gemini TTS API."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro-preview-tts", 
                 sample_rate: int = 22050, channels: int = 1, bitrate: str = "128k",
                 temperature: float = 1.0, style_instructions: str = None):
        """Initialize TTS client with Gemini API configuration.
        
        Args:
            api_key: Google API key for Gemini
            model_name: Gemini TTS model to use
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels (1=mono, 2=stereo)
            bitrate: Output MP3 bitrate
            temperature: TTS temperature for voice variability (0.1-1.0)
            style_instructions: Style instructions for voice (e.g., 'read in anime-style voice')
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.bitrate = bitrate
        self.temperature = temperature
        self.style_instructions = style_instructions
        
    def generate_audio(
        self,
        lecture_content: str,
        voice: str = "Zephyr",
        output_path: Optional[Path] = None
    ) -> bytes:
        """Generate single-speaker audio from lecture content.
        
        Args:
            lecture_content: Text content of the lecture
            voice: Voice name for the lecturer
            output_path: Optional path to save the audio file
            
        Returns:
            Audio data in MP3 format as bytes
        """
        logger.info(f"Generating audio with {len(lecture_content)} characters")
        
        # Warning for long content
        if len(lecture_content) > 3000:
            logger.warning(f"Large lecture content ({len(lecture_content)} chars). This may cause TTS timeouts.")
        
        try:
            # Prepare content with style instructions embedded
            if self.style_instructions:
                # Embed style instructions directly in the content as natural language prompt
                content_with_style = f"{self.style_instructions}: {lecture_content}"
                logger.info(f"Using style instructions: {self.style_instructions}")
            else:
                content_with_style = lecture_content
                logger.info("No style instructions provided")
            
            # Generate audio using Gemini TTS with single speaker
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=content_with_style,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            )
                        )
                    ),
                    temperature=self.temperature,
                )
            )
            
            # Extract audio data from the new API response format
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            
            # Save and convert to MP3 with proper encoding
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # Save as temporary WAV file first
                temp_wav_path = output_path.with_suffix('.wav')
                self._save_wav_file(temp_wav_path, audio_data)
                
                # Convert WAV to MP3 with proper bitrate and channel settings
                self._convert_wav_to_mp3(temp_wav_path, output_path)
                
                # Clean up temporary WAV file
                temp_wav_path.unlink()
                logger.info(f"Audio saved to {output_path} ({self.bitrate}, {self.channels}ch)")
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Failed to generate audio: {e}")
            raise
    
    
    
    def _save_wav_file(self, filename: Path, pcm_data: bytes, channels: int = None, rate: int = None, sample_width: int = 2) -> None:
        """Save PCM audio data as a WAV file.
        
        Args:
            filename: Path to save the WAV file
            pcm_data: Raw PCM audio data
            channels: Number of audio channels (uses instance default if None)
            rate: Sample rate in Hz (uses instance default if None)
            sample_width: Sample width in bytes
        """
        # Use instance defaults if not specified
        channels = channels or self.channels
        rate = rate or self.sample_rate
        
        with wave.open(str(filename), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)
    
    def _convert_wav_to_mp3(self, wav_path: Path, mp3_path: Path) -> None:
        """Convert WAV file to MP3 with quality settings.
        
        Args:
            wav_path: Path to input WAV file
            mp3_path: Path to output MP3 file
        """
        try:
            # Load WAV file
            audio = AudioSegment.from_wav(str(wav_path))
            
            # Apply channel conversion if needed
            if self.channels == 1 and audio.channels > 1:
                audio = audio.set_channels(1)  # Convert to mono
            elif self.channels == 2 and audio.channels == 1:
                audio = audio.set_channels(2)  # Convert to stereo
            
            # Export as MP3 with specified bitrate
            audio.export(
                str(mp3_path),
                format="mp3",
                bitrate=self.bitrate,
                parameters=["-ac", str(self.channels)]
            )
            logger.debug(f"Converted {wav_path} to {mp3_path} (bitrate: {self.bitrate})")
            
        except Exception as e:
            logger.error(f"Failed to convert WAV to MP3: {e}")
            # Fallback: just rename the file
            wav_path.rename(mp3_path)
    
    def generate_chapter_audios(
        self,
        scripts: Dict[str, str],
        output_dir: Path,
        voice: str = "Zephyr"
    ) -> Dict[str, Path]:
        """Generate audio files for multiple chapter scripts.
        
        Args:
            scripts: Dictionary of chapter_title -> lecture_content
            output_dir: Directory to save audio files
            voice: Voice name for the lecturer
            
        Returns:
            Dictionary of chapter_title -> audio_file_path
        """
        audio_paths = {}
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for idx, (title, lecture_content) in enumerate(scripts.items(), 1):
            try:
                # Generate filename
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
                filename = f"{idx:02d}_{safe_title}.mp3"
                output_path = output_dir / filename
                
                # Generate audio
                self.generate_audio(
                    lecture_content=lecture_content,
                    voice=voice,
                    output_path=output_path
                )
                
                audio_paths[title] = output_path
                logger.info(f"Generated audio for '{title}' -> {filename}")
                
            except Exception as e:
                logger.error(f"Failed to generate audio for chapter '{title}': {e}")
                # Continue with other chapters
        
        return audio_paths
    
    def generate_section_audios(
        self,
        section_scripts: Dict[str, 'SectionScript'],
        output_dir: Path,
        voice: str = "Zephyr"
    ) -> Dict[str, Path]:
        """Generate audio files for multiple section scripts.
        
        Args:
            section_scripts: Dictionary of section_key -> SectionScript object
            output_dir: Directory to save audio files
            voice: Voice name for the lecturer
            
        Returns:
            Dictionary of section_key -> audio_file_path
        """
        audio_paths = {}
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for section_key, section_script in section_scripts.items():
            try:
                # Generate filename based on section number and title
                safe_title = "".join(c for c in section_script.section_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title.replace(' ', '_')[:30]  # Limit length
                filename = f"{section_script.section_number.replace('.', '_')}_{safe_title}.mp3"
                output_path = output_dir / filename
                
                # Generate audio
                self.generate_audio(
                    lecture_content=section_script.content,
                    voice=voice,
                    output_path=output_path
                )
                
                audio_paths[section_key] = output_path
                logger.info(f"Generated audio for '{section_script.section_number} {section_script.section_title}' -> {filename}")
                
            except Exception as e:
                logger.error(f"Failed to generate audio for section '{section_script.section_number} {section_script.section_title}': {e}")
                # Continue with other sections
        
        return audio_paths
    
    async def generate_audio_with_retry(
        self,
        lecture_content: str,
        voice: str = "Zephyr",
        output_path: Optional[Path] = None,
        max_retries: int = 3  # Reduced retries to avoid long wait times
    ) -> Optional[bytes]:
        """Generate audio with exponential backoff retry for rate limits.
        
        Args:
            lecture_content: Text content of the lecture
            voice: Voice name for the lecturer
            output_path: Optional path to save the audio file
            max_retries: Maximum number of retry attempts
            
        Returns:
            Audio data in MP3 format as bytes or None if failed
        """
        for attempt in range(max_retries + 1):
            try:
                # 直接TTS生成を実行
                return await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.generate_audio(
                        lecture_content=lecture_content,
                        voice=voice,
                        output_path=output_path
                    )
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
        scripts: Dict[str, str],
        output_dir: Path,
        voice: str = "Zephyr",
        max_concurrency: int = 1,  # Fixed to 1 for Free tier rate limit compliance
        skip_existing: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Path]:
        """Generate audio files for multiple chapter scripts asynchronously.
        
        Args:
            scripts: Dictionary of chapter_title -> lecture_content
            output_dir: Directory to save audio files
            voice: Voice name for the lecturer
            max_concurrency: Maximum number of concurrent requests
            skip_existing: Skip existing audio files
            max_retries: Maximum retry attempts for rate limits
            
        Returns:
            Dictionary of chapter_title -> audio_file_path
        """
        # Force max_concurrency to 1 for Free tier compliance
        actual_concurrency = 1
        semaphore = asyncio.Semaphore(actual_concurrency)
        
        if max_concurrency > 1:
            logger.warning(f"max_concurrency reduced from {max_concurrency} to 1 for Free tier rate limit compliance")
        audio_paths = {}
        output_dir.mkdir(parents=True, exist_ok=True)
        
        async def process_chapter(idx: int, title: str, lecture_content: str) -> Optional[Path]:
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
                            lecture_content=lecture_content,
                            voice=voice,
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
        for idx, (title, lecture_content) in enumerate(scripts.items(), 1):
            # Add delay between requests to respect rate limits (2 per minute = 30s between requests)
            if idx > 1:
                delay = 31  # 31 seconds to be safe with 2/minute limit
                logger.info(f"Waiting {delay}s before next request to respect rate limits...")
                await asyncio.sleep(delay)
            
            result = await process_chapter(idx, title, lecture_content)
            results.append(result)
        
        # Collect successful results
        for (title, _), result in zip(scripts.items(), results):
            if isinstance(result, Path):
                audio_paths[title] = result
            elif isinstance(result, Exception):
                logger.error(f"Exception processing chapter '{title}': {result}")
        
        return audio_paths
    
    async def generate_section_audios_async(
        self,
        section_scripts: Dict[str, 'SectionScript'],
        output_dir: Path,
        voice: str = "Zephyr",
        max_concurrency: int = 1,  # Fixed to 1 for Free tier rate limit compliance
        skip_existing: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Path]:
        """Generate audio files for multiple section scripts asynchronously.
        
        Args:
            section_scripts: Dictionary of section_key -> SectionScript object
            output_dir: Directory to save audio files
            voice: Voice name for the lecturer
            max_concurrency: Maximum number of concurrent requests
            skip_existing: Skip existing audio files
            max_retries: Maximum retry attempts for rate limits
            
        Returns:
            Dictionary of section_key -> audio_file_path
        """
        # Force max_concurrency to 1 for Free tier compliance
        actual_concurrency = 1
        semaphore = asyncio.Semaphore(actual_concurrency)
        
        if max_concurrency > 1:
            logger.warning(f"max_concurrency reduced from {max_concurrency} to 1 for Free tier rate limit compliance")
        audio_paths = {}
        output_dir.mkdir(parents=True, exist_ok=True)
        
        async def process_section(section_key: str, section_script: 'SectionScript') -> Optional[Path]:
            async with semaphore:
                try:
                    # Generate filename based on section number and title
                    safe_title = "".join(c for c in section_script.section_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    safe_title = safe_title.replace(' ', '_')[:30]  # Limit length
                    filename = f"{section_script.section_number.replace('.', '_')}_{safe_title}.mp3"
                    output_path = output_dir / filename
                    
                    # Check if file already exists and skip if requested
                    if skip_existing and output_path.exists():
                        logger.info(f"Skipping existing audio file: {filename}")
                        return output_path
                    
                    # Generate audio with retry logic
                    audio_data = await self.generate_audio_with_retry(
                        lecture_content=section_script.content,
                        voice=voice,
                        output_path=output_path,
                        max_retries=max_retries
                    )
                    
                    if audio_data is not None:
                        logger.info(f"Generated audio for '{section_script.section_number} {section_script.section_title}' -> {filename}")
                        return output_path
                    else:
                        logger.error(f"Failed to generate audio for section '{section_script.section_number} {section_script.section_title}'")
                        return None
                        
                except Exception as e:
                    logger.error(f"Error processing section '{section_script.section_number} {section_script.section_title}': {e}")
                    return None
        
        # Process sections with rate limiting (sequential with delays)
        results = []
        section_items = list(section_scripts.items())
        for idx, (section_key, section_script) in enumerate(section_items):
            # Add delay between requests to respect rate limits (2 per minute = 30s between requests)
            if idx > 0:
                delay = 31  # 31 seconds to be safe with 2/minute limit
                logger.info(f"Waiting {delay}s before next request to respect rate limits...")
                await asyncio.sleep(delay)
            
            result = await process_section(section_key, section_script)
            results.append(result)
        
        # Collect successful results
        for (section_key, _), result in zip(section_items, results):
            if isinstance(result, Path):
                audio_paths[section_key] = result
            elif isinstance(result, Exception):
                logger.error(f"Exception processing section '{section_key}': {result}")
        
        return audio_paths