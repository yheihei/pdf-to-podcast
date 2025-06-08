"""Audio mixer module for concatenating, normalizing and adding BGM to podcast episodes."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple
from pydub import AudioSegment
from pydub.effects import normalize

logger = logging.getLogger(__name__)


class AudioMixer:
    """Handles audio mixing operations for podcast generation."""
    
    def __init__(self, bitrate: str = "128k", channels: int = 1):
        """Initialize audio mixer.
        
        Args:
            bitrate: Output audio bitrate (e.g., "128k", "192k", "320k")
            channels: Number of audio channels (1 for mono, 2 for stereo)
        """
        self.bitrate = bitrate
        self.channels = channels
        
    def concatenate_chapters(
        self,
        chapter_audio_paths: List[Path],
        output_path: Path,
        bgm_path: Optional[Path] = None,
        silence_between_chapters: float = 1.0,
        bgm_volume_db: float = -20.0,
        normalize_audio: bool = True
    ) -> Tuple[float, List[Tuple[str, float, float]]]:
        """Concatenate chapter audio files into single episode.
        
        Args:
            chapter_audio_paths: List of paths to chapter audio files
            output_path: Path to save concatenated audio
            bgm_path: Optional path to BGM file
            silence_between_chapters: Silence duration between chapters in seconds
            bgm_volume_db: BGM volume adjustment in dB
            normalize_audio: Whether to normalize the final audio
            
        Returns:
            Tuple of (total_duration_seconds, chapter_timestamps)
            chapter_timestamps format: [(title, start_time, end_time), ...]
        """
        logger.info(f"Concatenating {len(chapter_audio_paths)} chapter audio files")
        
        if not chapter_audio_paths:
            raise ValueError("No chapter audio files provided")
        
        # Load BGM if provided
        bgm = None
        if bgm_path and bgm_path.exists():
            try:
                bgm = AudioSegment.from_file(str(bgm_path))
                bgm = bgm + bgm_volume_db  # Adjust volume
                logger.info(f"Loaded BGM from {bgm_path}")
            except Exception as e:
                logger.warning(f"Failed to load BGM: {e}")
                bgm = None
        
        # Concatenate chapters
        episode = AudioSegment.empty()
        chapter_timestamps = []
        current_time = 0.0
        
        silence = AudioSegment.silent(duration=int(silence_between_chapters * 1000))
        
        for i, audio_path in enumerate(chapter_audio_paths):
            if not audio_path.exists():
                logger.warning(f"Chapter audio file not found: {audio_path}")
                continue
                
            try:
                # Load chapter audio
                chapter_audio = AudioSegment.from_file(str(audio_path))
                logger.debug(f"Loaded chapter audio: {audio_path} ({len(chapter_audio)}ms)")
                
                # Add to episode
                start_time = current_time
                episode += chapter_audio
                current_time += len(chapter_audio) / 1000.0  # Convert to seconds
                end_time = current_time
                
                # Extract chapter title from filename
                chapter_title = audio_path.stem.split('_', 1)[-1] if '_' in audio_path.stem else audio_path.stem
                chapter_timestamps.append((chapter_title, start_time, end_time))
                
                # Add silence between chapters (except after last chapter)
                if i < len(chapter_audio_paths) - 1:
                    episode += silence
                    current_time += silence_between_chapters
                    
            except Exception as e:
                logger.error(f"Failed to process chapter audio {audio_path}: {e}")
                continue
        
        if len(episode) == 0:
            raise ValueError("No valid chapter audio files found")
        
        # Add BGM if available
        if bgm:
            episode = self._add_background_music(episode, bgm)
        
        # Normalize audio
        if normalize_audio:
            episode = normalize(episode)
            logger.info("Applied audio normalization")
        
        # Export final episode
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        export_params = {
            "format": "mp3",
            "bitrate": self.bitrate,
            "parameters": ["-ac", str(self.channels)]  # Channel count based on quality setting
        }
        
        episode.export(str(output_path), **export_params)
        
        total_duration = len(episode) / 1000.0  # Convert to seconds
        logger.info(f"Episode created: {output_path} ({total_duration:.1f}s, {len(chapter_timestamps)} chapters)")
        
        return total_duration, chapter_timestamps
    
    def _add_background_music(self, audio: AudioSegment, bgm: AudioSegment) -> AudioSegment:
        """Add background music to audio.
        
        Args:
            audio: Main audio track
            bgm: Background music track
            
        Returns:
            Audio with background music mixed in
        """
        try:
            audio_length = len(audio)
            bgm_length = len(bgm)
            
            # Loop BGM if it's shorter than the audio
            if bgm_length < audio_length:
                repeats_needed = (audio_length // bgm_length) + 1
                bgm_extended = bgm * repeats_needed
                bgm_to_use = bgm_extended[:audio_length]
            else:
                bgm_to_use = bgm[:audio_length]
            
            # Mix audio with BGM
            mixed = audio.overlay(bgm_to_use)
            logger.info(f"Added background music ({len(bgm_to_use)}ms)")
            
            return mixed
            
        except Exception as e:
            logger.warning(f"Failed to add background music: {e}")
            return audio
    
    def get_audio_duration(self, audio_path: Path) -> Optional[float]:
        """Get duration of audio file in seconds.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds or None if failed
        """
        try:
            audio = AudioSegment.from_file(str(audio_path))
            return len(audio) / 1000.0
        except Exception as e:
            logger.error(f"Failed to get duration for {audio_path}: {e}")
            return None
    
    def convert_audio_format(
        self,
        input_path: Path,
        output_path: Path,
        format: str = "mp3",
        bitrate: Optional[str] = None
    ) -> bool:
        """Convert audio file to different format.
        
        Args:
            input_path: Path to input audio file
            output_path: Path to output audio file
            format: Target format (mp3, wav, etc.)
            bitrate: Target bitrate (e.g., "320k")
            
        Returns:
            True if conversion successful
        """
        try:
            audio = AudioSegment.from_file(str(input_path))
            
            export_params = {"format": format}
            if bitrate:
                export_params["bitrate"] = bitrate
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            audio.export(str(output_path), **export_params)
            
            logger.info(f"Converted audio: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to convert audio {input_path}: {e}")
            return False
    
    def apply_audio_effects(
        self,
        audio_path: Path,
        output_path: Path,
        normalize_audio: bool = True,
        fade_in_duration: float = 0.0,
        fade_out_duration: float = 0.0,
        volume_db: float = 0.0
    ) -> bool:
        """Apply audio effects to file.
        
        Args:
            audio_path: Path to input audio file
            output_path: Path to output audio file
            normalize_audio: Whether to normalize audio
            fade_in_duration: Fade in duration in seconds
            fade_out_duration: Fade out duration in seconds
            volume_db: Volume adjustment in dB
            
        Returns:
            True if processing successful
        """
        try:
            audio = AudioSegment.from_file(str(audio_path))
            
            # Apply volume adjustment
            if volume_db != 0.0:
                audio = audio + volume_db
            
            # Apply fade effects
            if fade_in_duration > 0:
                audio = audio.fade_in(int(fade_in_duration * 1000))
            
            if fade_out_duration > 0:
                audio = audio.fade_out(int(fade_out_duration * 1000))
            
            # Normalize audio
            if normalize_audio:
                audio = normalize(audio)
            
            # Export processed audio
            output_path.parent.mkdir(parents=True, exist_ok=True)
            audio.export(str(output_path), format="mp3", bitrate=self.bitrate)
            
            logger.info(f"Applied audio effects: {audio_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply audio effects to {audio_path}: {e}")
            return False
    
    def validate_audio_file(self, audio_path: Path) -> bool:
        """Validate that audio file is readable.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            True if file is valid audio
        """
        try:
            audio = AudioSegment.from_file(str(audio_path))
            return len(audio) > 0
        except Exception:
            return False