"""ID3 tags module for adding chapter information to MP3 files."""

import logging
import struct
from pathlib import Path
from typing import List, Tuple, Optional
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, APIC, CHAP, CTOC

logger = logging.getLogger(__name__)


class ChapterTagger:
    """Handles adding ID3v2 chapter tags to MP3 files."""
    
    def __init__(self):
        """Initialize chapter tagger."""
        pass
    
    def add_chapters_to_mp3(
        self,
        mp3_path: Path,
        chapters: List[Tuple[str, float, float]],
        album_title: str = "PDF Podcast",
        artist: str = "PDF Podcast Generator",
        year: Optional[str] = None,
        genre: str = "Podcast",
        cover_image_path: Optional[Path] = None
    ) -> bool:
        """Add chapter information to MP3 file using ID3v2 tags.
        
        Args:
            mp3_path: Path to MP3 file
            chapters: List of (title, start_time_seconds, end_time_seconds)
            album_title: Album title for metadata
            artist: Artist name for metadata
            year: Release year
            genre: Genre for metadata
            cover_image_path: Optional path to cover image
            
        Returns:
            True if successful
        """
        try:
            # Load MP3 file
            audio_file = MP3(str(mp3_path), ID3=ID3)
            
            # Add or update ID3 tags
            if audio_file.tags is None:
                audio_file.add_tags()
            
            # Add basic metadata
            audio_file.tags.setall('TIT2', [TIT2(encoding=3, text=album_title)])
            audio_file.tags.setall('TPE1', [TPE1(encoding=3, text=artist)])
            audio_file.tags.setall('TALB', [TALB(encoding=3, text=album_title)])
            audio_file.tags.setall('TCON', [TCON(encoding=3, text=genre)])
            
            if year:
                audio_file.tags.setall('TDRC', [TDRC(encoding=3, text=year)])
            
            # Add cover image if provided
            if cover_image_path and cover_image_path.exists():
                self._add_cover_image(audio_file, cover_image_path)
            
            # Add chapter information
            self._add_chapter_tags(audio_file, chapters)
            
            # Save file
            audio_file.save(v2_version=4)
            
            logger.info(f"Added {len(chapters)} chapters to {mp3_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add chapters to {mp3_path}: {e}")
            return False
    
    def _add_chapter_tags(self, audio_file: MP3, chapters: List[Tuple[str, float, float]]) -> None:
        """Add CHAP and CTOC tags to MP3 file.
        
        Args:
            audio_file: MP3 file object
            chapters: List of chapter information
        """
        if not chapters:
            return
        
        # Remove existing chapter tags
        chapter_keys = [key for key in audio_file.tags.keys() if key.startswith('CHAP:') or key.startswith('CTOC:')]
        for key in chapter_keys:
            del audio_file.tags[key]
        
        # Create chapter IDs
        chapter_ids = []
        
        # Add individual chapter tags (CHAP)
        for i, (title, start_time, end_time) in enumerate(chapters):
            chapter_id = f"chap{i:03d}"
            chapter_ids.append(chapter_id)
            
            # Convert times to milliseconds
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            # Create CHAP frame
            chap_frame = CHAP(
                encoding=3,
                element_id=chapter_id,
                start_time=start_ms,
                end_time=end_ms,
                start_offset=0xFFFFFFFF,  # Not used
                end_offset=0xFFFFFFFF,    # Not used
                sub_frames=[
                    TIT2(encoding=3, text=title)
                ]
            )
            
            audio_file.tags.setall(f'CHAP:{chapter_id}', [chap_frame])
            logger.debug(f"Added chapter: {title} ({start_time:.1f}s - {end_time:.1f}s)")
        
        # Add table of contents (CTOC)
        if chapter_ids:
            ctoc_frame = CTOC(
                encoding=3,
                element_id="toc",
                flags=CTOC.TOP_LEVEL | CTOC.ORDERED,
                child_element_ids=chapter_ids,
                sub_frames=[
                    TIT2(encoding=3, text="Table of Contents")
                ]
            )
            
            audio_file.tags.setall('CTOC:toc', [ctoc_frame])
            logger.debug(f"Added table of contents with {len(chapter_ids)} chapters")
    
    def _add_cover_image(self, audio_file: MP3, image_path: Path) -> None:
        """Add cover image to MP3 file.
        
        Args:
            audio_file: MP3 file object
            image_path: Path to cover image
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Determine image type
            image_mime = 'image/jpeg'
            if image_path.suffix.lower() == '.png':
                image_mime = 'image/png'
            elif image_path.suffix.lower() in ['.jpg', '.jpeg']:
                image_mime = 'image/jpeg'
            
            # Add cover image
            apic_frame = APIC(
                encoding=3,
                mime=image_mime,
                type=3,  # Cover (front)
                desc='Cover',
                data=image_data
            )
            
            audio_file.tags.setall('APIC:', [apic_frame])
            logger.debug(f"Added cover image: {image_path}")
            
        except Exception as e:
            logger.warning(f"Failed to add cover image: {e}")
    
    def get_chapter_info(self, mp3_path: Path) -> List[Tuple[str, float, float]]:
        """Extract chapter information from MP3 file.
        
        Args:
            mp3_path: Path to MP3 file
            
        Returns:
            List of (title, start_time_seconds, end_time_seconds)
        """
        try:
            audio_file = MP3(str(mp3_path), ID3=ID3)
            
            if not audio_file.tags:
                return []
            
            chapters = []
            
            # Find all CHAP frames
            chap_frames = []
            for key in audio_file.tags.keys():
                if key.startswith('CHAP:'):
                    chap_frames.append(audio_file.tags[key])
            
            # Sort by start time and extract info
            for chap_frame in chap_frames:
                if chap_frame:
                    frame = chap_frame[0]  # Get first frame
                    title = "Unknown"
                    
                    # Extract title from sub-frames
                    for sub_frame in frame.sub_frames:
                        if isinstance(sub_frame, TIT2):
                            title = str(sub_frame.text[0])
                            break
                    
                    start_time = frame.start_time / 1000.0  # Convert to seconds
                    end_time = frame.end_time / 1000.0
                    
                    chapters.append((title, start_time, end_time))
            
            # Sort by start time
            chapters.sort(key=lambda x: x[1])
            
            logger.info(f"Extracted {len(chapters)} chapters from {mp3_path}")
            return chapters
            
        except Exception as e:
            logger.error(f"Failed to extract chapters from {mp3_path}: {e}")
            return []
    
    def validate_chapter_tags(self, mp3_path: Path, expected_chapters: int) -> bool:
        """Validate that MP3 file has correct chapter tags.
        
        Args:
            mp3_path: Path to MP3 file
            expected_chapters: Expected number of chapters
            
        Returns:
            True if validation passes
        """
        try:
            chapters = self.get_chapter_info(mp3_path)
            
            if len(chapters) != expected_chapters:
                logger.warning(f"Chapter count mismatch: expected {expected_chapters}, found {len(chapters)}")
                return False
            
            # Check for overlapping chapters
            for i in range(len(chapters) - 1):
                current_end = chapters[i][2]
                next_start = chapters[i + 1][1]
                
                if current_end > next_start:
                    logger.warning(f"Overlapping chapters detected: {chapters[i][0]} and {chapters[i + 1][0]}")
                    return False
            
            logger.info(f"Chapter validation passed for {mp3_path}")
            return True
            
        except Exception as e:
            logger.error(f"Chapter validation failed for {mp3_path}: {e}")
            return False
    
    def remove_chapter_tags(self, mp3_path: Path) -> bool:
        """Remove all chapter tags from MP3 file.
        
        Args:
            mp3_path: Path to MP3 file
            
        Returns:
            True if successful
        """
        try:
            audio_file = MP3(str(mp3_path), ID3=ID3)
            
            if not audio_file.tags:
                return True
            
            # Remove chapter-related tags
            chapter_keys = [key for key in audio_file.tags.keys() 
                          if key.startswith('CHAP:') or key.startswith('CTOC:')]
            
            for key in chapter_keys:
                del audio_file.tags[key]
            
            audio_file.save(v2_version=4)
            
            logger.info(f"Removed chapter tags from {mp3_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove chapter tags from {mp3_path}: {e}")
            return False
    
    def get_audio_duration(self, mp3_path: Path) -> Optional[float]:
        """Get duration of MP3 file in seconds.
        
        Args:
            mp3_path: Path to MP3 file
            
        Returns:
            Duration in seconds or None if failed
        """
        try:
            audio_file = MP3(str(mp3_path))
            return audio_file.info.length
        except Exception as e:
            logger.error(f"Failed to get duration for {mp3_path}: {e}")
            return None