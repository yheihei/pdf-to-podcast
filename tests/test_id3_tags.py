"""Tests for ID3 tags module."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pdf_podcast.id3_tags import ChapterTagger


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def chapter_tagger():
    """Create ChapterTagger instance."""
    return ChapterTagger()


@pytest.fixture
def sample_chapters():
    """Create sample chapter data."""
    return [
        ("Introduction", 0.0, 120.5),
        ("Chapter 1: Getting Started", 120.5, 245.0),
        ("Chapter 2: Advanced Topics", 245.0, 380.2)
    ]


@pytest.fixture
def mock_mp3_file():
    """Create mock MP3 file."""
    with patch('pdf_podcast.id3_tags.MP3') as mock_mp3:
        # Create mock MP3 instance
        mock_instance = Mock()
        mock_instance.tags = Mock()
        mock_instance.tags.keys.return_value = []
        mock_instance.tags.setall = Mock()
        mock_instance.tags.__delitem__ = Mock()
        mock_instance.save = Mock()
        
        mock_mp3.return_value = mock_instance
        yield mock_mp3, mock_instance


class TestChapterTagger:
    """Test ChapterTagger class."""
    
    def test_initialization(self):
        """Test ChapterTagger initialization."""
        tagger = ChapterTagger()
        assert isinstance(tagger, ChapterTagger)
    
    @patch('pdf_podcast.id3_tags.MP3')
    @patch('pdf_podcast.id3_tags.ID3')
    def test_add_chapters_basic(self, mock_id3, mock_mp3, chapter_tagger, temp_dir, sample_chapters):
        """Test basic chapter addition to MP3."""
        # Setup mock MP3 file
        mock_file = Mock()
        mock_file.tags = Mock()
        mock_file.tags.keys.return_value = []
        mock_file.tags.setall = Mock()
        mock_file.save = Mock()
        mock_mp3.return_value = mock_file
        
        mp3_path = temp_dir / "test.mp3"
        mp3_path.touch()
        
        success = chapter_tagger.add_chapters_to_mp3(
            mp3_path=mp3_path,
            chapters=sample_chapters,
            album_title="Test Album",
            artist="Test Artist"
        )
        
        assert success
        
        # Verify MP3 was loaded and saved
        mock_mp3.assert_called_once()
        mock_file.save.assert_called_once_with(v2_version=4)
        
        # Verify basic metadata was set
        assert mock_file.tags.setall.call_count >= 4  # TIT2, TPE1, TALB, TCON
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_add_chapters_with_existing_tags(self, mock_mp3, chapter_tagger, temp_dir, sample_chapters):
        """Test adding chapters to MP3 with existing tags."""
        # Setup mock with existing tags
        mock_file = Mock()
        mock_tags = Mock()
        mock_tags.keys.return_value = []
        mock_tags.setall = Mock()
        
        mock_file.tags = None  # No existing tags initially
        # When add_tags is called, set tags to the mock
        def add_tags_side_effect():
            mock_file.tags = mock_tags
        mock_file.add_tags = Mock(side_effect=add_tags_side_effect)
        mock_file.save = Mock()
        mock_mp3.return_value = mock_file
        
        mp3_path = temp_dir / "test.mp3"
        mp3_path.touch()
        
        success = chapter_tagger.add_chapters_to_mp3(
            mp3_path=mp3_path,
            chapters=sample_chapters
        )
        
        assert success
        mock_file.add_tags.assert_called_once()
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_add_chapters_with_cover_image(self, mock_mp3, chapter_tagger, temp_dir, sample_chapters):
        """Test adding chapters with cover image."""
        # Setup mock
        mock_file = Mock()
        mock_file.tags = Mock()
        mock_file.tags.keys.return_value = []
        mock_file.tags.setall = Mock()
        mock_file.save = Mock()
        mock_mp3.return_value = mock_file
        
        mp3_path = temp_dir / "test.mp3"
        mp3_path.touch()
        
        # Create dummy cover image
        cover_path = temp_dir / "cover.jpg"
        cover_path.write_bytes(b"fake image data")
        
        success = chapter_tagger.add_chapters_to_mp3(
            mp3_path=mp3_path,
            chapters=sample_chapters,
            cover_image_path=cover_path
        )
        
        assert success
        # Cover image should trigger additional setall call for APIC
        assert mock_file.tags.setall.call_count >= 5
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_add_chapters_error(self, mock_mp3, chapter_tagger, temp_dir, sample_chapters):
        """Test error handling in chapter addition."""
        # Setup mock to raise exception
        mock_mp3.side_effect = Exception("Cannot read MP3 file")
        
        mp3_path = temp_dir / "bad.mp3"
        
        success = chapter_tagger.add_chapters_to_mp3(
            mp3_path=mp3_path,
            chapters=sample_chapters
        )
        
        assert not success
    
    @patch('pdf_podcast.id3_tags.MP3')
    @patch('pdf_podcast.id3_tags.ID3')
    def test_get_chapter_info(self, mock_id3, mock_mp3, chapter_tagger, temp_dir):
        """Test extracting chapter information from MP3."""
        # Setup mock with chapter tags
        mock_file = Mock()
        
        # Create mock CHAP frames
        mock_chap1 = Mock()
        mock_chap1.start_time = 0
        mock_chap1.end_time = 120500
        from pdf_podcast.id3_tags import TIT2
        mock_chap1.sub_frames = [TIT2(encoding=3, text=["Introduction"])]
        
        mock_chap2 = Mock()
        mock_chap2.start_time = 120500
        mock_chap2.end_time = 245000
        mock_chap2.sub_frames = [TIT2(encoding=3, text=["Chapter 1"])]
        
        # Setup tags
        mock_tags = Mock()
        mock_tags.__getitem__ = Mock(side_effect=lambda key: {
            'CHAP:chap001': [mock_chap1],
            'CHAP:chap002': [mock_chap2]
        }[key])
        mock_tags.keys.return_value = ['CHAP:chap001', 'CHAP:chap002']
        mock_file.tags = mock_tags
        
        mock_mp3.return_value = mock_file
        
        mp3_path = temp_dir / "test.mp3"
        mp3_path.touch()
        
        chapters = chapter_tagger.get_chapter_info(mp3_path)
        
        assert len(chapters) == 2
        assert chapters[0][0] == "Introduction"
        assert chapters[0][1] == 0.0  # Start time in seconds
        assert chapters[0][2] == 120.5  # End time in seconds
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_get_chapter_info_no_tags(self, mock_mp3, chapter_tagger, temp_dir):
        """Test extracting chapters from MP3 with no tags."""
        # Setup mock with no tags
        mock_file = Mock()
        mock_file.tags = None
        mock_mp3.return_value = mock_file
        
        mp3_path = temp_dir / "test.mp3"
        mp3_path.touch()
        
        chapters = chapter_tagger.get_chapter_info(mp3_path)
        
        assert len(chapters) == 0
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_get_chapter_info_error(self, mock_mp3, chapter_tagger, temp_dir):
        """Test error handling in chapter extraction."""
        # Setup mock to raise exception
        mock_mp3.side_effect = Exception("Cannot read file")
        
        mp3_path = temp_dir / "bad.mp3"
        
        chapters = chapter_tagger.get_chapter_info(mp3_path)
        
        assert len(chapters) == 0
    
    def test_validate_chapter_tags(self, chapter_tagger, temp_dir):
        """Test chapter tag validation."""
        with patch.object(chapter_tagger, 'get_chapter_info') as mock_get_chapters:
            # Setup mock to return valid chapters
            mock_get_chapters.return_value = [
                ("Chapter 1", 0.0, 120.0),
                ("Chapter 2", 120.0, 240.0)
            ]
            
            mp3_path = temp_dir / "test.mp3"
            mp3_path.touch()
            
            is_valid = chapter_tagger.validate_chapter_tags(mp3_path, expected_chapters=2)
            
            assert is_valid
    
    def test_validate_chapter_tags_wrong_count(self, chapter_tagger, temp_dir):
        """Test validation with wrong chapter count."""
        with patch.object(chapter_tagger, 'get_chapter_info') as mock_get_chapters:
            # Return fewer chapters than expected
            mock_get_chapters.return_value = [
                ("Chapter 1", 0.0, 120.0)
            ]
            
            mp3_path = temp_dir / "test.mp3"
            mp3_path.touch()
            
            is_valid = chapter_tagger.validate_chapter_tags(mp3_path, expected_chapters=2)
            
            assert not is_valid
    
    def test_validate_chapter_tags_overlapping(self, chapter_tagger, temp_dir):
        """Test validation with overlapping chapters."""
        with patch.object(chapter_tagger, 'get_chapter_info') as mock_get_chapters:
            # Return overlapping chapters
            mock_get_chapters.return_value = [
                ("Chapter 1", 0.0, 120.0),
                ("Chapter 2", 100.0, 240.0)  # Overlaps with Chapter 1
            ]
            
            mp3_path = temp_dir / "test.mp3"
            mp3_path.touch()
            
            is_valid = chapter_tagger.validate_chapter_tags(mp3_path, expected_chapters=2)
            
            assert not is_valid
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_remove_chapter_tags(self, mock_mp3, chapter_tagger, temp_dir):
        """Test removing chapter tags from MP3."""
        # Setup mock with chapter tags
        mock_file = Mock()
        mock_tags = Mock()
        mock_tags.keys.return_value = ['CHAP:chap001', 'CTOC:toc', 'TIT2']
        mock_tags.__delitem__ = Mock()
        mock_file.tags = mock_tags
        mock_file.save = Mock()
        mock_mp3.return_value = mock_file
        
        mp3_path = temp_dir / "test.mp3"
        mp3_path.touch()
        
        success = chapter_tagger.remove_chapter_tags(mp3_path)
        
        assert success
        # Should delete chapter-related keys only
        assert mock_tags.__delitem__.call_count == 2  # CHAP and CTOC
        mock_file.save.assert_called_once_with(v2_version=4)
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_remove_chapter_tags_no_tags(self, mock_mp3, chapter_tagger, temp_dir):
        """Test removing chapter tags from MP3 with no tags."""
        # Setup mock with no tags
        mock_file = Mock()
        mock_file.tags = None
        mock_mp3.return_value = mock_file
        
        mp3_path = temp_dir / "test.mp3"
        mp3_path.touch()
        
        success = chapter_tagger.remove_chapter_tags(mp3_path)
        
        assert success
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_get_audio_duration(self, mock_mp3, chapter_tagger, temp_dir):
        """Test getting audio duration."""
        # Setup mock
        mock_file = Mock()
        mock_file.info.length = 245.5
        mock_mp3.return_value = mock_file
        
        mp3_path = temp_dir / "test.mp3"
        mp3_path.touch()
        
        duration = chapter_tagger.get_audio_duration(mp3_path)
        
        assert duration == 245.5
    
    @patch('pdf_podcast.id3_tags.MP3')
    def test_get_audio_duration_error(self, mock_mp3, chapter_tagger, temp_dir):
        """Test getting audio duration with error."""
        # Setup mock to raise exception
        mock_mp3.side_effect = Exception("Cannot read file")
        
        mp3_path = temp_dir / "bad.mp3"
        
        duration = chapter_tagger.get_audio_duration(mp3_path)
        
        assert duration is None
    
    def test_add_cover_image(self, chapter_tagger, temp_dir):
        """Test adding cover image to MP3."""
        # Setup mock audio file
        mock_file = Mock()
        mock_file.tags = Mock()
        mock_file.tags.setall = Mock()
        
        # Create dummy cover image
        cover_path = temp_dir / "cover.png"
        cover_path.write_bytes(b"fake PNG data")
        
        # Test internal method
        chapter_tagger._add_cover_image(mock_file, cover_path)
        
        # Verify APIC tag was set
        mock_file.tags.setall.assert_called_once()
        args = mock_file.tags.setall.call_args[0]
        assert args[0] == 'APIC:'
    
    def test_add_cover_image_missing_file(self, chapter_tagger, temp_dir):
        """Test adding cover image with missing file."""
        # Setup mock audio file
        mock_file = Mock()
        mock_file.tags = Mock()
        mock_file.tags.setall = Mock()
        
        # Non-existent cover file
        cover_path = temp_dir / "missing.jpg"
        
        # Should not raise exception, just log warning
        chapter_tagger._add_cover_image(mock_file, cover_path)
        
        # APIC tag should not be set
        mock_file.tags.setall.assert_not_called()