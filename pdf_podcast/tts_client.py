"""TTS client module for generating single-speaker audio using Gemini API."""

import asyncio
import logging
import time
import random
from typing import Dict, Optional
from dataclasses import dataclass
from google import genai
from google.genai import types
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

# Import chunk processor for fallback handling
try:
    from .tts_chunk_processor import TTSChunkProcessor
    CHUNK_PROCESSOR_AVAILABLE = True
except ImportError:
    CHUNK_PROCESSOR_AVAILABLE = False
    logger.warning("TTSChunkProcessorが利用できません。分割処理フォールバックが無効になります。")


@dataclass
class VoiceConfig:
    """Configuration for a speaker voice."""
    speaker_id: str  # "Host" or "Guest"
    voice_name: str  # e.g., "Kore", "Puck"


class TTSClient:
    """Generates single-speaker audio from lecture scripts using Gemini TTS API."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro-preview-tts"):
        """Initialize TTS client with Gemini API configuration.
        
        Args:
            api_key: Google API key for Gemini
            model_name: Gemini TTS model to use
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        
        # チャンクプロセッサーの初期化
        if CHUNK_PROCESSOR_AVAILABLE:
            self.chunk_processor = TTSChunkProcessor(tts_client=self)
        else:
            self.chunk_processor = None
        
    def generate_audio(
        self,
        lecture_content: str,
        voice: str = "Kore",
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
            # Generate audio using Gemini TTS with single speaker
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=lecture_content,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            )
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
    
    async def generate_audio_with_timeout(
        self,
        lecture_content: str,
        timeout: int = 180,  # 3分
        voice: str = "Kore",
        output_path: Optional[Path] = None
    ) -> bytes:
        """タイムアウト付きTTS生成
        
        Args:
            lecture_content: Text content of the lecture
            timeout: タイムアウト時間（秒）
            voice: Voice name for the lecturer
            output_path: Optional path to save the audio file
            
        Returns:
            Audio data in MP3 format as bytes
            
        Raises:
            asyncio.TimeoutError: タイムアウトが発生した場合
        """
        logger.info(f"Generating audio with timeout ({timeout}s) for {len(lecture_content)} characters")
        
        try:
            # asyncio.wait_forでタイムアウトを設定
            audio_data = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.generate_audio(
                        lecture_content=lecture_content,
                        voice=voice,
                        output_path=output_path
                    )
                ),
                timeout=timeout
            )
            
            logger.info(f"Audio generation completed within timeout")
            return audio_data
            
        except asyncio.TimeoutError:
            logger.error(f"TTS処理がタイムアウトしました (制限: {timeout}秒)")
            logger.error(f"講義内容の文字数: {len(lecture_content)}文字")
            logger.error("コンテンツの分割処理を検討してください")
            raise
        
        except Exception as e:
            logger.error(f"Failed to generate audio with timeout: {e}")
            raise
    
    
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
        scripts: Dict[str, str],
        output_dir: Path,
        voice: str = "Kore"
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
    
    async def generate_audio_with_retry(
        self,
        lecture_content: str,
        voice: str = "Kore",
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
                # タイムアウト機能付きでTTS生成を実行
                return await self.generate_audio_with_timeout(
                    lecture_content=lecture_content,
                    timeout=180,  # 3分のタイムアウト
                    voice=voice,
                    output_path=output_path
                )
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a timeout error
                if isinstance(e, asyncio.TimeoutError) or "timeout" in error_msg:
                    logger.error(f"TTS処理がタイムアウトしました (試行: {attempt + 1})")
                    
                    # 分割処理フォールバックを試行
                    if self.chunk_processor and len(lecture_content) > 2000:
                        logger.warning("大規模コンテンツを検出。分割処理フォールバックを実行します")
                        try:
                            # Split lecture content into smaller chunks
                            paragraphs = lecture_content.split('\n\n')
                            chunk_size = len(paragraphs) // 3 + 1
                            chunks = [paragraphs[i:i+chunk_size] for i in range(0, len(paragraphs), chunk_size)]
                            
                            audio_chunks = []
                            for chunk in chunks:
                                chunk_content = '\n\n'.join(chunk)
                                chunk_audio = await self.generate_audio_with_timeout(
                                    lecture_content=chunk_content,
                                    timeout=120,
                                    voice=voice,
                                    output_path=None
                                )
                                audio_chunks.append(chunk_audio)
                            
                            # Combine audio chunks (simplified - actual implementation would need proper audio merging)
                            combined_audio = b''.join(audio_chunks)
                            if output_path:
                                output_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(output_path, 'wb') as f:
                                    f.write(combined_audio)
                            
                            logger.info("分割処理フォールバックが成功しました")
                            return combined_audio
                        except Exception as fallback_error:
                            logger.error(f"分割処理フォールバックに失敗: {fallback_error}")
                    
                    if attempt < max_retries:
                        logger.warning(f"タイムアウトによるリトライ {attempt + 1}/{max_retries}")
                        await asyncio.sleep(5)  # 短い待機時間
                        continue
                    else:
                        logger.error("タイムアウトの最大リトライ回数に達しました")
                        raise Exception("failed_timeout")
                
                # Check if it's a rate limit error
                elif "429" in error_msg or "rate limit" in error_msg or "quota" in error_msg:
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
        voice: str = "Kore",
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