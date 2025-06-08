"""Tests for audio mixer module."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pdf_podcast.audio_mixer import AudioMixer


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def audio_mixer():
    """Create AudioMixer instance."""
    return AudioMixer(bitrate="128k")


@pytest.fixture
def mock_audio_segment():
    """Create mock AudioSegment."""
    with patch('pdf_podcast.audio_mixer.AudioSegment') as mock:
        # Configure mock audio segment
        mock_segment = Mock()
        mock_segment.__len__ = Mock(return_value=10000)  # 10 seconds
        mock_segment.__add__ = Mock(return_value=mock_segment)
        mock_segment.overlay = Mock(return_value=mock_segment)
        mock_segment.export = Mock()
        # Add attributes needed for normalize effect
        mock_segment.max = 32767  # Maximum sample value for 16-bit audio
        mock_segment.max_possible_amplitude = 32767  # Maximum possible amplitude
        
        mock.empty.return_value = mock_segment
        mock.silent.return_value = mock_segment
        mock.from_file.return_value = mock_segment
        
        yield mock


class TestAudioMixer:
    """Test AudioMixer class."""
    
    def test_initialization(self):
        """Test AudioMixer initialization."""
        mixer = AudioMixer(bitrate="320k")
        assert mixer.bitrate == "320k"
        
        # Test default bitrate
        default_mixer = AudioMixer()
        assert default_mixer.bitrate == "320k"
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    @patch('pdf_podcast.audio_mixer.normalize')
    def test_concatenate_chapters_basic(self, mock_normalize, mock_audio_segment, audio_mixer, temp_dir):
        """Test basic chapter concatenation."""
        # Setup mock audio segments
        mock_segment = Mock()
        mock_segment.__len__ = Mock(return_value=10000)  # 10 seconds
        mock_segment.__add__ = Mock(return_value=mock_segment)
        mock_normalize.return_value = mock_segment
        
        mock_audio_segment.empty.return_value = mock_segment
        mock_audio_segment.silent.return_value = mock_segment
        mock_audio_segment.from_file.return_value = mock_segment
        
        # Create test audio files
        audio_files = [
            temp_dir / "chapter1.mp3",
            temp_dir / "chapter2.mp3"
        ]
        
        # Create dummy files
        for audio_file in audio_files:
            audio_file.touch()
        
        output_path = temp_dir / "episode.mp3"
        
        # Test concatenation
        duration, timestamps = audio_mixer.concatenate_chapters(
            chapter_audio_paths=audio_files,
            output_path=output_path,
            normalize_audio=True
        )
        
        # Verify results
        assert duration > 0
        assert len(timestamps) == 2
        assert timestamps[0][0] == "chapter1"  # Chapter title extracted from filename
        assert timestamps[1][0] == "chapter2"
        
        # Verify normalize was called
        mock_normalize.assert_called_once()
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    @patch('pdf_podcast.audio_mixer.normalize')
    def test_concatenate_with_bgm(self, mock_normalize, mock_audio_segment, audio_mixer, temp_dir):
        """Test concatenation with background music."""
        # Setup mocks
        mock_segment = Mock()
        mock_segment.__len__ = Mock(return_value=10000)
        mock_segment.__add__ = Mock(return_value=mock_segment)
        mock_segment.overlay = Mock(return_value=mock_segment)
        mock_segment.__getitem__ = Mock(return_value=mock_segment)  # For BGM slicing
        mock_segment.__mul__ = Mock(return_value=mock_segment)  # For BGM repeating
        mock_segment.export = Mock()  # For export method
        # Add attributes needed for normalize effect
        mock_segment.max = 32767
        mock_segment.max_possible_amplitude = 32767
        
        mock_audio_segment.empty.return_value = mock_segment
        mock_audio_segment.silent.return_value = mock_segment
        mock_audio_segment.from_file.return_value = mock_segment
        mock_normalize.return_value = mock_segment
        
        # Create test files
        audio_files = [temp_dir / "chapter1.mp3"]
        audio_files[0].touch()
        
        bgm_file = temp_dir / "bgm.mp3"
        bgm_file.touch()
        
        output_path = temp_dir / "episode.mp3"
        
        # Test with BGM
        duration, timestamps = audio_mixer.concatenate_chapters(
            chapter_audio_paths=audio_files,
            output_path=output_path,
            bgm_path=bgm_file,
            bgm_volume_db=-15.0
        )
        
        # Verify BGM was loaded and processed
        assert mock_segment.overlay.called
    
    def test_concatenate_empty_list(self, audio_mixer, temp_dir):
        """Test concatenation with empty audio file list."""
        output_path = temp_dir / "episode.mp3"
        
        with pytest.raises(ValueError, match="No chapter audio files provided"):
            audio_mixer.concatenate_chapters(
                chapter_audio_paths=[],
                output_path=output_path
            )
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    @patch('pdf_podcast.audio_mixer.normalize')
    def test_concatenate_missing_files(self, mock_normalize, mock_audio_segment, audio_mixer, temp_dir):
        """Test concatenation with missing audio files."""
        # Setup mock that raises exception for missing files
        def from_file_side_effect(path):
            if "missing" in str(path):
                raise FileNotFoundError("File not found")
            mock_segment = Mock()
            mock_segment.__len__ = Mock(return_value=10000)
            return mock_segment
        
        mock_audio_segment.from_file.side_effect = from_file_side_effect
        
        # Create mocks that work with the actual implementation
        empty_mock = Mock()
        empty_mock.__len__ = Mock(return_value=0)
        empty_mock.__add__ = Mock(side_effect=lambda x: x)  # Return the added segment
        empty_mock.export = Mock()
        empty_mock.max = 32767
        empty_mock.max_possible_amplitude = 32767
        
        silent_mock = Mock()
        silent_mock.__len__ = Mock(return_value=1000)
        silent_mock.__add__ = Mock(return_value=silent_mock)
        
        # Create a chapter mock that will be returned by from_file for existing files
        chapter_mock = Mock()
        chapter_mock.__len__ = Mock(return_value=10000)
        chapter_mock.__add__ = Mock(return_value=chapter_mock)
        chapter_mock.export = Mock()
        
        mock_audio_segment.empty.return_value = empty_mock
        mock_audio_segment.silent.return_value = silent_mock
        
        # For the existing file, empty_mock + chapter_mock should return chapter_mock 
        empty_mock.__add__ = Mock(return_value=chapter_mock)
        
        mock_normalize.return_value = chapter_mock
        
        # Create test files (some missing)
        audio_files = [
            temp_dir / "existing.mp3",
            temp_dir / "missing.mp3"
        ]
        audio_files[0].touch()  # Only create first file
        
        output_path = temp_dir / "episode.mp3"
        
        # Should handle missing files gracefully
        duration, timestamps = audio_mixer.concatenate_chapters(
            chapter_audio_paths=audio_files,
            output_path=output_path
        )
        
        # Should process only existing files
        assert len(timestamps) == 1
        assert timestamps[0][0] == "existing"
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    def test_get_audio_duration(self, mock_audio_segment, audio_mixer, temp_dir):
        """Test getting audio duration."""
        # Setup mock
        mock_segment = Mock()
        mock_segment.__len__ = Mock(return_value=15000)  # 15 seconds
        mock_audio_segment.from_file.return_value = mock_segment
        
        audio_file = temp_dir / "test.mp3"
        audio_file.touch()
        
        duration = audio_mixer.get_audio_duration(audio_file)
        
        assert duration == 15.0  # 15000ms = 15s
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    def test_get_audio_duration_error(self, mock_audio_segment, audio_mixer, temp_dir):
        """Test getting audio duration with error."""
        # Setup mock to raise exception
        mock_audio_segment.from_file.side_effect = Exception("Cannot read file")
        
        audio_file = temp_dir / "bad.mp3"
        
        duration = audio_mixer.get_audio_duration(audio_file)
        
        assert duration is None
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    def test_convert_audio_format(self, mock_audio_segment, audio_mixer, temp_dir):
        """Test audio format conversion."""
        # Setup mock
        mock_segment = Mock()
        mock_audio_segment.from_file.return_value = mock_segment
        
        input_file = temp_dir / "input.wav"
        output_file = temp_dir / "output.mp3"
        input_file.touch()
        
        success = audio_mixer.convert_audio_format(
            input_path=input_file,
            output_path=output_file,
            format="mp3",
            bitrate="192k"
        )
        
        assert success
        mock_segment.export.assert_called_once()
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    @patch('pdf_podcast.audio_mixer.normalize')
    def test_apply_audio_effects(self, mock_normalize, mock_audio_segment, audio_mixer, temp_dir):
        """Test applying audio effects."""
        # Setup mock
        mock_segment = Mock()
        mock_segment.__add__ = Mock(return_value=mock_segment)
        mock_segment.fade_in = Mock(return_value=mock_segment)
        mock_segment.fade_out = Mock(return_value=mock_segment)
        mock_segment.export = Mock()
        # Add attributes needed for normalize effect
        mock_segment.max = 32767
        mock_segment.max_possible_amplitude = 32767
        
        mock_audio_segment.from_file.return_value = mock_segment
        mock_normalize.return_value = mock_segment
        
        input_file = temp_dir / "input.mp3"
        output_file = temp_dir / "output.mp3"
        input_file.touch()
        
        success = audio_mixer.apply_audio_effects(
            audio_path=input_file,
            output_path=output_file,
            volume_db=5.0,
            fade_in_duration=1.0,
            fade_out_duration=2.0
        )
        
        assert success
        mock_segment.__add__.assert_called_with(5.0)
        mock_segment.fade_in.assert_called_with(1000)  # 1s = 1000ms
        mock_segment.fade_out.assert_called_with(2000)  # 2s = 2000ms
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    def test_validate_audio_file(self, mock_audio_segment, audio_mixer, temp_dir):
        """Test audio file validation."""
        # Setup mock for valid file
        mock_segment = Mock()
        mock_segment.__len__ = Mock(return_value=5000)
        mock_audio_segment.from_file.return_value = mock_segment
        
        audio_file = temp_dir / "valid.mp3"
        audio_file.touch()
        
        is_valid = audio_mixer.validate_audio_file(audio_file)
        assert is_valid
    
    @patch('pdf_podcast.audio_mixer.AudioSegment')
    def test_validate_invalid_audio_file(self, mock_audio_segment, audio_mixer, temp_dir):
        """Test validation of invalid audio file."""
        # Setup mock to raise exception
        mock_audio_segment.from_file.side_effect = Exception("Invalid audio")
        
        audio_file = temp_dir / "invalid.mp3"
        
        is_valid = audio_mixer.validate_audio_file(audio_file)
        assert not is_valid
    
    def test_add_background_music_shorter_bgm(self, audio_mixer):
        """Test adding BGM that's shorter than main audio."""
        with patch('pdf_podcast.audio_mixer.AudioSegment') as mock_audio_segment:
            # Setup mocks
            main_audio = Mock()
            main_audio.__len__ = Mock(return_value=20000)  # 20 seconds
            
            bgm = Mock()
            bgm.__len__ = Mock(return_value=8000)  # 8 seconds
            bgm.__mul__ = Mock(return_value=bgm)  # For repeating BGM
            bgm.__getitem__ = Mock(return_value=bgm)  # For slicing
            
            main_audio.overlay = Mock(return_value=main_audio)
            
            # Test internal method
            result = audio_mixer._add_background_music(main_audio, bgm)
            
            # Verify BGM was repeated and overlayed
            bgm.__mul__.assert_called_once()
            main_audio.overlay.assert_called_once()
            assert result == main_audio
    
    def test_add_background_music_longer_bgm(self, audio_mixer):
        """Test adding BGM that's longer than main audio."""
        with patch('pdf_podcast.audio_mixer.AudioSegment') as mock_audio_segment:
            # Setup mocks
            main_audio = Mock()
            main_audio.__len__ = Mock(return_value=10000)  # 10 seconds
            
            bgm = Mock()
            bgm.__len__ = Mock(return_value=20000)  # 20 seconds
            bgm.__getitem__ = Mock(return_value=bgm)  # For slicing
            
            main_audio.overlay = Mock(return_value=main_audio)
            
            # Test internal method
            result = audio_mixer._add_background_music(main_audio, bgm)
            
            # Verify BGM was sliced and overlayed
            bgm.__getitem__.assert_called_with(slice(None, 10000))
            main_audio.overlay.assert_called_once()
            assert result == main_audio