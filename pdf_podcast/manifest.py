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


class SectionStatus(Enum):
    """Status of section processing."""
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
class SectionInfo:
    """Information about a single section."""
    title: str
    section_number: str  # "1.1", "2.3" など
    start_page: int
    end_page: int
    parent_chapter: str = ""
    status: SectionStatus = SectionStatus.PENDING
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
    def from_dict(cls, data: Dict[str, Any]) -> "SectionInfo":
        """Create instance from dictionary."""
        data["status"] = SectionStatus(data["status"])
        return cls(**data)


@dataclass
class PodcastManifest:
    """Manifest for tracking podcast generation progress."""
    pdf_path: str
    output_dir: str
    model: str
    voice: str
    max_concurrency: int
    skip_existing: bool
    created_at: str
    updated_at: str
    chapters: List[ChapterInfo]
    sections: List[SectionInfo] = None
    episode_path: Optional[str] = None
    total_duration: Optional[float] = None
    bgm_path: Optional[str] = None
    use_sections: bool = False  # 中項目モードかどうか

    def __post_init__(self):
        if self.sections is None:
            self.sections = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["chapters"] = [chapter.to_dict() for chapter in self.chapters]
        data["sections"] = [section.to_dict() for section in self.sections]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PodcastManifest":
        """Create instance from dictionary."""
        chapters = [ChapterInfo.from_dict(ch) for ch in data["chapters"]]
        sections = [SectionInfo.from_dict(sec) for sec in data.get("sections", [])]
        data["chapters"] = chapters
        data["sections"] = sections
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
        voice: str = "Kore",
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
            voice: Lecturer voice name
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
            voice=voice,
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
    
    def create_section_manifest(
        self,
        pdf_path: str,
        output_dir: str,
        sections: List[SectionInfo],
        model: str = "gemini-2.5-pro-preview-tts",
        voice: str = "Kore",
        max_concurrency: int = 1,
        skip_existing: bool = False,
        bgm_path: Optional[str] = None
    ) -> PodcastManifest:
        """Create a new manifest for section-based processing.
        
        Args:
            pdf_path: Path to source PDF
            output_dir: Output directory
            sections: List of section information
            model: TTS model name
            voice: Voice name
            max_concurrency: Max concurrent requests
            skip_existing: Skip existing files
            bgm_path: Optional BGM file path
            
        Returns:
            Created PodcastManifest
        """
        now = datetime.now().isoformat()
        
        self._manifest = PodcastManifest(
            pdf_path=pdf_path,
            output_dir=output_dir,
            model=model,
            voice=voice,
            max_concurrency=max_concurrency,
            skip_existing=skip_existing,
            created_at=now,
            updated_at=now,
            chapters=[],  # Empty for section mode
            sections=sections,
            bgm_path=bgm_path,
            use_sections=True
        )
        
        self.save()
        logger.info(f"Created section manifest with {len(sections)} sections")
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
    
    def update_section(
        self,
        section_number: str,
        status: Optional[SectionStatus] = None,
        script_path: Optional[str] = None,
        audio_path: Optional[str] = None,
        text_chars: Optional[int] = None,
        audio_duration: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update section information.
        
        Args:
            section_number: Section number (e.g., "1.1") to update
            status: New status
            script_path: Path to script file
            audio_path: Path to audio file
            text_chars: Number of characters in text
            audio_duration: Duration of audio in seconds
            error_message: Error message if failed
            
        Returns:
            True if section was found and updated
        """
        if not self._manifest:
            return False
            
        for section in self._manifest.sections:
            if section.section_number == section_number:
                if status is not None:
                    section.status = status
                if script_path is not None:
                    section.script_path = script_path
                if audio_path is not None:
                    section.audio_path = audio_path
                if text_chars is not None:
                    section.text_chars = text_chars
                if audio_duration is not None:
                    section.audio_duration = audio_duration
                if error_message is not None:
                    section.error_message = error_message
                    
                section.updated_at = datetime.now().isoformat()
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
    
    def get_section(self, section_number: str) -> Optional[SectionInfo]:
        """Get section information by section number.
        
        Args:
            section_number: Section number (e.g., "1.1")
            
        Returns:
            SectionInfo or None if not found
        """
        if not self._manifest:
            return None
            
        for section in self._manifest.sections:
            if section.section_number == section_number:
                return section
                
        return None
    
    def get_sections_by_status(self, status: SectionStatus) -> List[SectionInfo]:
        """Get sections by status.
        
        Args:
            status: Section status to filter by
            
        Returns:
            List of sections with specified status
        """
        if not self._manifest:
            return []
            
        return [sec for sec in self._manifest.sections if sec.status == status]

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
        
        # Check if using sections or chapters
        if self._manifest.use_sections and self._manifest.sections:
            # Section-based progress
            status_counts = {}
            for status in SectionStatus:
                status_counts[status.value] = len(self.get_sections_by_status(status))
                
            total_items = len(self._manifest.sections)
            completed_items = status_counts.get(SectionStatus.COMPLETED.value, 0)
            failed_items = (
                status_counts.get(SectionStatus.FAILED.value, 0) +
                status_counts.get(SectionStatus.FAILED_RATE_LIMIT.value, 0)
            )
            
            progress_percent = (completed_items / total_items * 100) if total_items > 0 else 0
            
            return {
                "type": "sections",
                "total_sections": total_items,
                "completed_sections": completed_items,
                "failed_sections": failed_items,
                "progress_percent": round(progress_percent, 1),
                "status_counts": status_counts,
                "use_sections": True
            }
        else:
            # Chapter-based progress (legacy)
            status_counts = {}
            for status in ChapterStatus:
                status_counts[status.value] = len(self.get_chapters_by_status(status))
                
            total_items = len(self._manifest.chapters)
            completed_items = status_counts.get(ChapterStatus.COMPLETED.value, 0)
            failed_items = (
                status_counts.get(ChapterStatus.FAILED.value, 0) +
                status_counts.get(ChapterStatus.FAILED_RATE_LIMIT.value, 0)
            )
            
            progress_percent = (completed_items / total_items * 100) if total_items > 0 else 0
        
            return {
                "type": "chapters",
                "total_chapters": total_items,
                "completed_chapters": completed_items,
                "failed_chapters": failed_items,
                "progress_percent": round(progress_percent, 1),
                "status_counts": status_counts,
                "episode_ready": self._manifest.episode_path is not None,
                "use_sections": False
            }

    @property
    def manifest(self) -> Optional[PodcastManifest]:
        """Get current manifest."""
        return self._manifest