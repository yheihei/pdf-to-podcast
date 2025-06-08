"""Tests for manifest module."""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from pdf_podcast.manifest import (
    ChapterStatus, ChapterInfo, PodcastManifest, ManifestManager
)


@pytest.fixture
def temp_manifest_path():
    """Create temporary manifest file path."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()


@pytest.fixture
def sample_chapters():
    """Create sample chapter info list."""
    return [
        ChapterInfo(
            title="Chapter 1",
            start_page=1,
            end_page=10,
            text_chars=1000
        ),
        ChapterInfo(
            title="Chapter 2", 
            start_page=11,
            end_page=20,
            text_chars=1200
        )
    ]


class TestChapterInfo:
    """Test ChapterInfo dataclass."""
    
    def test_creation(self):
        """Test basic chapter info creation."""
        chapter = ChapterInfo(
            title="Test Chapter",
            start_page=1,
            end_page=5,
            text_chars=500
        )
        
        assert chapter.title == "Test Chapter"
        assert chapter.start_page == 1
        assert chapter.end_page == 5
        assert chapter.status == ChapterStatus.PENDING
        assert chapter.text_chars == 500
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        chapter = ChapterInfo(
            title="Test Chapter",
            start_page=1,
            end_page=5,
            status=ChapterStatus.COMPLETED
        )
        
        data = chapter.to_dict()
        assert data["title"] == "Test Chapter"
        assert data["status"] == "completed"
        assert data["start_page"] == 1
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "title": "Test Chapter",
            "start_page": 1,
            "end_page": 5,
            "status": "completed",
            "text_chars": 500,
            "script_path": None,
            "audio_path": None,
            "audio_duration": None,
            "error_message": None,
            "created_at": None,
            "updated_at": None
        }
        
        chapter = ChapterInfo.from_dict(data)
        assert chapter.title == "Test Chapter"
        assert chapter.status == ChapterStatus.COMPLETED
        assert chapter.text_chars == 500


class TestPodcastManifest:
    """Test PodcastManifest dataclass."""
    
    def test_creation(self, sample_chapters):
        """Test manifest creation."""
        manifest = PodcastManifest(
            pdf_path="/test/input.pdf",
            output_dir="/test/output",
            model="gemini-test",
            voice_host="TestHost",
            voice_guest="TestGuest",
            max_concurrency=2,
            skip_existing=True,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            chapters=sample_chapters
        )
        
        assert manifest.pdf_path == "/test/input.pdf"
        assert manifest.model == "gemini-test"
        assert len(manifest.chapters) == 2
        assert manifest.max_concurrency == 2
    
    def test_serialization(self, sample_chapters):
        """Test manifest serialization and deserialization."""
        manifest = PodcastManifest(
            pdf_path="/test/input.pdf",
            output_dir="/test/output",
            model="gemini-test",
            voice_host="TestHost",
            voice_guest="TestGuest",
            max_concurrency=2,
            skip_existing=False,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            chapters=sample_chapters
        )
        
        # Convert to dict and back
        data = manifest.to_dict()
        restored = PodcastManifest.from_dict(data)
        
        assert restored.pdf_path == manifest.pdf_path
        assert restored.model == manifest.model
        assert len(restored.chapters) == len(manifest.chapters)
        assert restored.chapters[0].title == manifest.chapters[0].title


class TestManifestManager:
    """Test ManifestManager class."""
    
    def test_creation(self, temp_manifest_path):
        """Test manifest manager creation."""
        manager = ManifestManager(temp_manifest_path)
        assert manager.manifest_path == temp_manifest_path
        assert manager.manifest is None
    
    def test_create_manifest(self, temp_manifest_path, sample_chapters):
        """Test manifest creation."""
        manager = ManifestManager(temp_manifest_path)
        
        manifest = manager.create_manifest(
            pdf_path="/test/input.pdf",
            output_dir="/test/output",
            chapters=sample_chapters,
            model="gemini-test"
        )
        
        assert manifest is not None
        assert manifest.pdf_path == "/test/input.pdf"
        assert len(manifest.chapters) == 2
        assert temp_manifest_path.exists()
    
    def test_load_manifest(self, temp_manifest_path, sample_chapters):
        """Test manifest loading."""
        manager = ManifestManager(temp_manifest_path)
        
        # Create manifest first
        original = manager.create_manifest(
            pdf_path="/test/input.pdf",
            output_dir="/test/output",
            chapters=sample_chapters
        )
        
        # Create new manager and load
        new_manager = ManifestManager(temp_manifest_path)
        loaded = new_manager.load_manifest()
        
        assert loaded is not None
        assert loaded.pdf_path == original.pdf_path
        assert len(loaded.chapters) == len(original.chapters)
    
    def test_update_chapter(self, temp_manifest_path, sample_chapters):
        """Test chapter update functionality."""
        manager = ManifestManager(temp_manifest_path)
        manager.create_manifest(
            pdf_path="/test/input.pdf",
            output_dir="/test/output",
            chapters=sample_chapters
        )
        
        # Update chapter
        success = manager.update_chapter(
            chapter_title="Chapter 1",
            status=ChapterStatus.COMPLETED,
            script_path="/test/script1.txt",
            audio_duration=120.5
        )
        
        assert success
        
        # Verify update
        chapter = manager.get_chapter("Chapter 1")
        assert chapter is not None
        assert chapter.status == ChapterStatus.COMPLETED
        assert chapter.script_path == "/test/script1.txt"
        assert chapter.audio_duration == 120.5
    
    def test_get_chapters_by_status(self, temp_manifest_path, sample_chapters):
        """Test filtering chapters by status."""
        manager = ManifestManager(temp_manifest_path)
        manager.create_manifest(
            pdf_path="/test/input.pdf",
            output_dir="/test/output",
            chapters=sample_chapters
        )
        
        # Update one chapter status
        manager.update_chapter("Chapter 1", status=ChapterStatus.COMPLETED)
        
        # Test filtering
        pending = manager.get_chapters_by_status(ChapterStatus.PENDING)
        completed = manager.get_chapters_by_status(ChapterStatus.COMPLETED)
        
        assert len(pending) == 1
        assert len(completed) == 1
        assert pending[0].title == "Chapter 2"
        assert completed[0].title == "Chapter 1"
    
    def test_progress_summary(self, temp_manifest_path, sample_chapters):
        """Test progress summary generation."""
        manager = ManifestManager(temp_manifest_path)
        manager.create_manifest(
            pdf_path="/test/input.pdf",
            output_dir="/test/output",
            chapters=sample_chapters
        )
        
        # Update chapter statuses
        manager.update_chapter("Chapter 1", status=ChapterStatus.COMPLETED)
        manager.update_chapter("Chapter 2", status=ChapterStatus.FAILED)
        
        summary = manager.get_progress_summary()
        
        assert summary["total_chapters"] == 2
        assert summary["completed_chapters"] == 1
        assert summary["failed_chapters"] == 1
        assert summary["progress_percent"] == 50.0
        assert not summary["episode_ready"]
    
    def test_set_episode_path(self, temp_manifest_path, sample_chapters):
        """Test setting episode path."""
        manager = ManifestManager(temp_manifest_path)
        manager.create_manifest(
            pdf_path="/test/input.pdf",
            output_dir="/test/output",
            chapters=sample_chapters
        )
        
        manager.set_episode_path("/test/episode.mp3", 300.5)
        
        assert manager.manifest.episode_path == "/test/episode.mp3"
        assert manager.manifest.total_duration == 300.5
        
        # Test progress summary with episode
        summary = manager.get_progress_summary()
        assert summary["episode_ready"]
    
    def test_nonexistent_file_load(self, temp_manifest_path):
        """Test loading non-existent manifest file."""
        manager = ManifestManager(temp_manifest_path)
        manifest = manager.load_manifest()
        assert manifest is None