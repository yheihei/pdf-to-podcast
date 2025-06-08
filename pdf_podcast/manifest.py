"""Manifest module for tracking podcast generation progress and metadata."""

import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ChapterStatus(Enum):
    """Status of chapter processing."""
    PENDING = "pending"
    SCRIPT_GENERATED = "script_generated"
    AUDIO_GENERATED = "audio_generated" 
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_RATE_LIMIT = "failed_rate_limit"


@dataclass
class ChapterInfo:
    """Information about a single chapter."""
    title: str
    start_page: int
    end_page: int
    status: ChapterStatus = ChapterStatus.PENDING
    script_path: Optional[str] = None
    audio_path: Optional[str] = None
    text_chars: Optional[int] = None
    audio_duration: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterInfo":
        """Create instance from dictionary."""
        data["status"] = ChapterStatus(data["status"])
        return cls(**data)


@dataclass
class PodcastManifest:
    """Manifest for tracking podcast generation progress."""
    pdf_path: str
    output_dir: str
    model: str
    voice_host: str
    voice_guest: str
    max_concurrency: int
    skip_existing: bool
    created_at: str
    updated_at: str
    chapters: List[ChapterInfo]
    episode_path: Optional[str] = None
    total_duration: Optional[float] = None
    bgm_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["chapters"] = [chapter.to_dict() for chapter in self.chapters]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PodcastManifest":
        """Create instance from dictionary."""
        chapters = [ChapterInfo.from_dict(ch) for ch in data["chapters"]]
        data["chapters"] = chapters
        return cls(**data)


class ManifestManager:
    """Manages podcast manifest file operations."""
    
    def __init__(self, manifest_path: Path):
        """Initialize manifest manager.
        
        Args:
            manifest_path: Path to manifest.json file
        """
        self.manifest_path = manifest_path
        self._manifest: Optional[PodcastManifest] = None

    def create_manifest(
        self,
        pdf_path: str,
        output_dir: str,
        chapters: List[ChapterInfo],
        model: str = "gemini-2.5-pro-preview-tts",
        voice_host: str = "Kore",
        voice_guest: str = "Puck",
        max_concurrency: int = 4,
        skip_existing: bool = False,
        bgm_path: Optional[str] = None
    ) -> PodcastManifest:
        """Create new manifest.
        
        Args:
            pdf_path: Path to input PDF
            output_dir: Output directory path
            chapters: List of chapter information
            model: Gemini model name
            voice_host: Host voice name
            voice_guest: Guest voice name
            max_concurrency: Maximum concurrent processes
            skip_existing: Skip existing files flag
            bgm_path: Optional BGM file path
            
        Returns:
            Created PodcastManifest
        """
        now = datetime.now().isoformat()
        
        self._manifest = PodcastManifest(
            pdf_path=pdf_path,
            output_dir=output_dir,
            model=model,
            voice_host=voice_host,
            voice_guest=voice_guest,
            max_concurrency=max_concurrency,
            skip_existing=skip_existing,
            created_at=now,
            updated_at=now,
            chapters=chapters,
            bgm_path=bgm_path
        )
        
        self.save()
        logger.info(f"Created manifest with {len(chapters)} chapters")
        return self._manifest

    def load_manifest(self) -> Optional[PodcastManifest]:
        """Load manifest from file.
        
        Returns:
            Loaded PodcastManifest or None if file doesn't exist
        """
        if not self.manifest_path.exists():
            return None
            
        try:
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._manifest = PodcastManifest.from_dict(data)
            logger.info(f"Loaded manifest with {len(self._manifest.chapters)} chapters")
            return self._manifest
            
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return None

    def save(self) -> None:
        """Save manifest to file."""
        if not self._manifest:
            return
            
        # Update timestamp
        self._manifest.updated_at = datetime.now().isoformat()
        
        try:
            # Ensure directory exists
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump(self._manifest.to_dict(), f, indent=2, ensure_ascii=False)
                
            logger.debug(f"Saved manifest to {self.manifest_path}")
            
        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")

    def update_chapter(
        self,
        chapter_title: str,
        status: Optional[ChapterStatus] = None,
        script_path: Optional[str] = None,
        audio_path: Optional[str] = None,
        text_chars: Optional[int] = None,
        audio_duration: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update chapter information.
        
        Args:
            chapter_title: Title of chapter to update
            status: New status
            script_path: Path to script file
            audio_path: Path to audio file
            text_chars: Number of characters in text
            audio_duration: Duration of audio in seconds
            error_message: Error message if failed
            
        Returns:
            True if chapter was found and updated
        """
        if not self._manifest:
            return False
            
        for chapter in self._manifest.chapters:
            if chapter.title == chapter_title:
                if status is not None:
                    chapter.status = status
                if script_path is not None:
                    chapter.script_path = script_path
                if audio_path is not None:
                    chapter.audio_path = audio_path
                if text_chars is not None:
                    chapter.text_chars = text_chars
                if audio_duration is not None:
                    chapter.audio_duration = audio_duration
                if error_message is not None:
                    chapter.error_message = error_message
                    
                chapter.updated_at = datetime.now().isoformat()
                self.save()
                return True
                
        return False

    def get_chapter(self, chapter_title: str) -> Optional[ChapterInfo]:
        """Get chapter information by title.
        
        Args:
            chapter_title: Title of chapter
            
        Returns:
            ChapterInfo or None if not found
        """
        if not self._manifest:
            return None
            
        for chapter in self._manifest.chapters:
            if chapter.title == chapter_title:
                return chapter
                
        return None

    def get_chapters_by_status(self, status: ChapterStatus) -> List[ChapterInfo]:
        """Get chapters by status.
        
        Args:
            status: Chapter status to filter by
            
        Returns:
            List of chapters with specified status
        """
        if not self._manifest:
            return []
            
        return [ch for ch in self._manifest.chapters if ch.status == status]

    def set_episode_path(self, episode_path: str, total_duration: Optional[float] = None) -> None:
        """Set episode file path and duration.
        
        Args:
            episode_path: Path to episode MP3 file
            total_duration: Total duration in seconds
        """
        if self._manifest:
            self._manifest.episode_path = episode_path
            if total_duration is not None:
                self._manifest.total_duration = total_duration
            self.save()

    def get_progress_summary(self) -> Dict[str, Any]:
        """Get progress summary.
        
        Returns:
            Dictionary with progress statistics
        """
        if not self._manifest:
            return {}
            
        status_counts = {}
        for status in ChapterStatus:
            status_counts[status.value] = len(self.get_chapters_by_status(status))
            
        total_chapters = len(self._manifest.chapters)
        completed_chapters = status_counts.get(ChapterStatus.COMPLETED.value, 0)
        failed_chapters = (
            status_counts.get(ChapterStatus.FAILED.value, 0) +
            status_counts.get(ChapterStatus.FAILED_RATE_LIMIT.value, 0)
        )
        
        progress_percent = (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
        
        return {
            "total_chapters": total_chapters,
            "completed_chapters": completed_chapters,
            "failed_chapters": failed_chapters,
            "progress_percent": progress_percent,
            "status_counts": status_counts,
            "episode_ready": self._manifest.episode_path is not None
        }

    @property
    def manifest(self) -> Optional[PodcastManifest]:
        """Get current manifest."""
        return self._manifest