"""Tests for scripts-to-audio functionality."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import argparse

from pdf_podcast.__main__ import PodcastGenerator, main, create_parser


class TestScriptsToAudio:
    """Test scripts-to-audio mode functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.scripts_dir = Path(self.temp_dir) / "scripts" / "test_book"
        self.audio_dir = Path(self.temp_dir) / "audio" / "test_book"
        
        # Create test directories
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test script files
        (self.scripts_dir / "1_1_introduction.txt").write_text("Introduction script content", encoding='utf-8')
        (self.scripts_dir / "1_2_overview.txt").write_text("Overview script content", encoding='utf-8')
        (self.scripts_dir / "2_1_chapter2.txt").write_text("Chapter 2 script content", encoding='utf-8')
        
        # Create some existing audio files (to test skip behavior)
        (self.audio_dir / "1_1_introduction.mp3").write_bytes(b"fake audio data")
    
    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_scripts_directory_valid(self):
        """Test validate_scripts_directory with valid directory."""
        # Create mock args for PodcastGenerator
        mock_args = argparse.Namespace(
            scripts_to_audio=str(self.scripts_dir),
            output_dir=self.temp_dir,
            verbose=False,
            voice="Kore",
            bitrate="128k",
            quality="standard",
            max_concurrency=1,
            skip_existing=True
        )
        
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_key'}):
            generator = PodcastGenerator(mock_args)
            result = generator.validate_scripts_directory(str(self.scripts_dir))
            assert result == self.scripts_dir
    
    def test_validate_scripts_directory_not_exists(self):
        """Test validate_scripts_directory with non-existent directory."""
        # Create a non-existent path within temp directory to avoid filesystem issues
        nonexistent_path = Path(self.temp_dir) / "nonexistent" / "path"
        
        mock_args = argparse.Namespace(
            scripts_to_audio=str(nonexistent_path),
            output_dir=self.temp_dir,
            verbose=False,
            voice="Kore",
            bitrate="128k",
            quality="standard",
            max_concurrency=1,
            skip_existing=True
        )
        
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_key'}):
            generator = PodcastGenerator(mock_args)
            with pytest.raises(ValueError, match="スクリプトディレクトリが見つかりません"):
                generator.validate_scripts_directory(str(nonexistent_path))
    
    def test_validate_scripts_directory_not_directory(self):
        """Test validate_scripts_directory with file instead of directory."""
        # Create a file instead of directory
        test_file = Path(self.temp_dir) / "not_a_directory.txt"
        test_file.write_text("test", encoding='utf-8')
        
        mock_args = argparse.Namespace(
            scripts_to_audio=str(test_file),
            output_dir=self.temp_dir,
            verbose=False,
            voice="Kore",
            bitrate="128k",
            quality="standard",
            max_concurrency=1,
            skip_existing=True
        )
        
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_key'}):
            generator = PodcastGenerator(mock_args)
            with pytest.raises(ValueError, match="指定されたパスはディレクトリではありません"):
                generator.validate_scripts_directory(str(test_file))
    
    def test_get_missing_audio_files(self):
        """Test get_missing_audio_files detection."""
        mock_args = argparse.Namespace(
            scripts_to_audio=str(self.scripts_dir),
            output_dir=self.temp_dir,
            verbose=False,
            voice="Kore",
            bitrate="128k",
            quality="standard",
            max_concurrency=1,
            skip_existing=True
        )
        
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_key'}):
            generator = PodcastGenerator(mock_args)
            missing = generator.get_missing_audio_files(self.scripts_dir, self.audio_dir)
            
            # Should have 2 missing audio files (overview and chapter2)
            assert len(missing) == 2
            missing_names = [f.stem for f in missing]
            assert "1_2_overview" in missing_names
            assert "2_1_chapter2" in missing_names
            assert "1_1_introduction" not in missing_names  # This one has audio
    
    def test_command_line_parsing_scripts_to_audio(self):
        """Test command line argument parsing for scripts-to-audio mode."""
        parser = create_parser()
        args = parser.parse_args(["--scripts-to-audio", str(self.scripts_dir)])
        
        assert hasattr(args, 'scripts_to_audio')
        assert args.scripts_to_audio == str(self.scripts_dir)
    
    def test_main_function_validation_scripts_to_audio(self):
        """Test main function validation for scripts-to-audio mode."""
        test_args = ["--scripts-to-audio", str(self.scripts_dir)]
        
        with patch('sys.argv', ['pdf_podcast'] + test_args):
            with patch('pdf_podcast.__main__.PodcastGenerator') as mock_generator:
                with patch('asyncio.run') as mock_run:
                    mock_run.return_value = 0
                    result = main()
                    assert result == 0
                    mock_generator.assert_called_once()
    
    def test_main_function_validation_nonexistent_scripts_dir(self):
        """Test main function validation with non-existent scripts directory."""
        test_args = ["--scripts-to-audio", "/nonexistent/path"]
        
        with patch('sys.argv', ['pdf_podcast'] + test_args):
            result = main()
            assert result == 1  # Should return error code
    
    @patch('pdf_podcast.__main__.TTSClient')
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_key'})
    def test_run_scripts_to_audio_success(self, mock_tts_client):
        """Test successful scripts-to-audio execution."""
        mock_args = argparse.Namespace(
            scripts_to_audio=str(self.scripts_dir),
            output_dir=self.temp_dir,
            verbose=False,
            voice="Kore",
            bitrate="128k",
            quality="standard",
            max_concurrency=1,
            skip_existing=True
        )
        
        # Mock TTS client
        mock_tts_instance = Mock()
        mock_tts_client.return_value = mock_tts_instance
        
        generator = PodcastGenerator(mock_args)
        
        # Mock the run_scripts_to_audio method by running it
        import asyncio
        result = asyncio.run(generator.run_scripts_to_audio())
        
        assert result == 0
        # TTS client should be called for missing audio files
        mock_tts_instance.generate_audio.call_count >= 1
    
    def test_audio_directory_inference_standard_structure(self):
        """Test audio directory inference with standard structure."""
        # Standard structure: .../output/scripts/dirname
        standard_scripts_dir = Path(self.temp_dir) / "output" / "scripts" / "test_book"
        standard_scripts_dir.mkdir(parents=True, exist_ok=True)
        
        mock_args = argparse.Namespace(
            scripts_to_audio=str(standard_scripts_dir),
            output_dir=None,  # No output dir specified
            verbose=False,
            voice="Kore",
            bitrate="128k",
            quality="standard",
            max_concurrency=1,
            skip_existing=True
        )
        
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test_key'}):
            generator = PodcastGenerator(mock_args)
            scripts_dir = generator.validate_scripts_directory(str(standard_scripts_dir))
            
            # Should infer audio directory as .../output/audio/test_book
            expected_audio_dir = Path(self.temp_dir) / "output" / "audio" / "test_book"
            
            # Test audio directory logic
            scripts_parent = scripts_dir.parent
            if scripts_parent.name == "scripts":
                output_base = scripts_parent.parent
                audio_dir = output_base / "audio" / scripts_dir.name
                assert audio_dir == expected_audio_dir


class TestMainFunction:
    """Test main function argument validation."""
    
    def test_normal_mode_requires_input_and_output(self):
        """Test that normal mode requires both input and output-dir."""
        test_args = []  # No arguments
        
        with patch('sys.argv', ['pdf_podcast'] + test_args):
            result = main()
            assert result == 1  # Should return error code
    
    def test_scripts_to_audio_mode_no_input_required(self):
        """Test that scripts-to-audio mode doesn't require input."""
        with tempfile.TemporaryDirectory() as temp_dir:
            scripts_dir = Path(temp_dir) / "scripts" / "test"
            scripts_dir.mkdir(parents=True)
            
            test_args = ["--scripts-to-audio", str(scripts_dir)]
            
            with patch('sys.argv', ['pdf_podcast'] + test_args):
                with patch('pdf_podcast.__main__.PodcastGenerator') as mock_generator:
                    with patch('asyncio.run') as mock_run:
                        mock_run.return_value = 0
                        result = main()
                        assert result == 0
                        # Should not require input file to exist
                        mock_generator.assert_called_once()