"""Tests for logging system module."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import logging

from pdf_podcast.logging_system import PodcastLogger, setup_logger


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_console():
    """Create mock rich console."""
    with patch('pdf_podcast.logging_system.Console') as mock:
        console_instance = Mock()
        mock.return_value = console_instance
        yield console_instance


class TestPodcastLogger:
    """Test PodcastLogger class."""
    
    def test_initialization_default(self, temp_dir, mock_console):
        """Test default initialization."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir, verbose=False)
            
            assert logger.log_dir == temp_dir
            assert not logger.verbose
            assert logger.progress is None
            assert len(logger.task_ids) == 0
    
    def test_initialization_verbose(self, temp_dir, mock_console):
        """Test verbose initialization."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir, verbose=True)
            
            assert logger.verbose
    
    def test_initialization_default_log_dir(self, mock_console):
        """Test initialization with default log directory."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(verbose=False)
            
            assert logger.log_dir == Path("./logs")
    
    @patch('pdf_podcast.logging_system.logging.basicConfig')
    @patch('pdf_podcast.logging_system.logging.FileHandler')
    @patch('pdf_podcast.logging_system.logging.getLogger')
    def test_setup_logging(self, mock_get_logger, mock_file_handler, mock_basic_config, temp_dir, mock_console):
        """Test logging setup."""
        # Setup mocks
        mock_root_logger = Mock()
        mock_get_logger.return_value = mock_root_logger
        mock_handler = Mock()
        mock_file_handler.return_value = mock_handler
        
        logger = PodcastLogger(log_dir=temp_dir, verbose=False)
        
        # Verify basic config was called
        mock_basic_config.assert_called_once()
        
        # Verify file handler was added
        mock_root_logger.addHandler.assert_called_once_with(mock_handler)
    
    def test_print_header(self, temp_dir, mock_console):
        """Test printing header."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            logger.print_header("Test Title", "Test Subtitle")
            
            # Verify console.print was called
            mock_console.print.assert_called()
    
    def test_print_header_no_subtitle(self, temp_dir, mock_console):
        """Test printing header without subtitle."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            logger.print_header("Test Title")
            
            mock_console.print.assert_called()
    
    def test_print_summary(self, temp_dir, mock_console):
        """Test printing summary table."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            data = {
                "Setting 1": "Value 1",
                "Setting 2": "Value 2"
            }
            
            logger.print_summary(data)
            
            mock_console.print.assert_called()
    
    def test_print_progress_summary(self, temp_dir, mock_console):
        """Test printing progress summary."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            summary = {
                "total_chapters": 5,
                "completed_chapters": 3,
                "failed_chapters": 1,
                "progress_percent": 60.0,
                "episode_ready": True,
                "status_counts": {
                    "completed": 3,
                    "failed": 1,
                    "pending": 1
                }
            }
            
            logger.print_progress_summary(summary)
            
            # Should print main table and status breakdown
            assert mock_console.print.call_count >= 2
    
    @patch('pdf_podcast.logging_system.Progress')
    def test_start_progress(self, mock_progress_class, temp_dir, mock_console):
        """Test starting progress tracking."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            # Setup mock progress
            mock_progress_instance = Mock()
            mock_progress_class.return_value = mock_progress_instance
            
            logger = PodcastLogger(log_dir=temp_dir)
            
            progress = logger.start_progress(total_tasks=5)
            
            assert progress == mock_progress_instance
            assert logger.progress == mock_progress_instance
            mock_progress_instance.start.assert_called_once()
    
    def test_add_task(self, temp_dir, mock_console):
        """Test adding task to progress."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            # Mock progress
            mock_progress = Mock()
            mock_progress.add_task.return_value = "task_id_123"
            logger.progress = mock_progress
            
            task_id = logger.add_task("Test Task", total=10)
            
            assert task_id == "task_id_123"
            assert logger.task_ids["Test Task"] == "task_id_123"
            mock_progress.add_task.assert_called_once_with("Test Task", total=10)
    
    def test_add_task_no_progress(self, temp_dir, mock_console):
        """Test adding task when no progress is started."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            with patch.object(PodcastLogger, 'start_progress') as mock_start:
                mock_progress = Mock()
                mock_progress.add_task.return_value = "task_id_123"
                mock_start.return_value = mock_progress
                
                logger = PodcastLogger(log_dir=temp_dir)
                
                task_id = logger.add_task("Test Task")
                
                # Should start progress automatically
                mock_start.assert_called_once()
    
    def test_update_task(self, temp_dir, mock_console):
        """Test updating task progress."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            # Mock progress
            mock_progress = Mock()
            logger.progress = mock_progress
            
            logger.update_task("task_id", advance=2, description="New description")
            
            mock_progress.update.assert_called_once_with(
                "task_id", 
                advance=2, 
                description="New description"
            )
    
    def test_complete_task(self, temp_dir, mock_console):
        """Test completing task."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            # Mock progress
            mock_progress = Mock()
            logger.progress = mock_progress
            
            logger.complete_task("task_id", "Custom completion message")
            
            mock_progress.update.assert_called_once_with(
                "task_id", 
                description="✅ Custom completion message"
            )
    
    def test_complete_task_default_message(self, temp_dir, mock_console):
        """Test completing task with default message."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            # Mock progress
            mock_progress = Mock()
            logger.progress = mock_progress
            
            logger.complete_task("task_id")
            
            mock_progress.update.assert_called_once_with(
                "task_id", 
                description="✅ Completed"
            )
    
    def test_stop_progress(self, temp_dir, mock_console):
        """Test stopping progress."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            # Mock progress
            mock_progress = Mock()
            logger.progress = mock_progress
            logger.task_ids = {"task1": "id1", "task2": "id2"}
            
            logger.stop_progress()
            
            mock_progress.stop.assert_called_once()
            assert logger.progress is None
            assert len(logger.task_ids) == 0
    
    def test_print_error(self, temp_dir, mock_console):
        """Test printing error message."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir, verbose=False)
            
            logger.print_error("Test error message")
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "❌ Error:" in call_args
            assert "Test error message" in call_args
    
    def test_print_error_with_exception(self, temp_dir, mock_console):
        """Test printing error with exception in verbose mode."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir, verbose=True)
            
            exception = ValueError("Test exception")
            logger.print_error("Test error", exception)
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "Test error" in call_args
            assert "Test exception" in call_args
    
    def test_print_warning(self, temp_dir, mock_console):
        """Test printing warning message."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            logger.print_warning("Test warning")
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "⚠️  Warning:" in call_args
            assert "Test warning" in call_args
    
    def test_print_success(self, temp_dir, mock_console):
        """Test printing success message."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            logger.print_success("Test success")
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "✅ Success:" in call_args
            assert "Test success" in call_args
    
    def test_print_info(self, temp_dir, mock_console):
        """Test printing info message."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            logger.print_info("Test info")
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "ℹ️  Info:" in call_args
            assert "Test info" in call_args
    
    def test_print_chapter_status(self, temp_dir, mock_console):
        """Test printing chapter status."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            logger.print_chapter_status("Chapter 1", "completed", "Additional details")
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "✅" in call_args  # completed icon
            assert "Chapter 1" in call_args
            assert "Completed" in call_args
            assert "Additional details" in call_args
    
    def test_print_chapter_status_no_details(self, temp_dir, mock_console):
        """Test printing chapter status without details."""
        with patch('pdf_podcast.logging_system.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            logger.print_chapter_status("Chapter 2", "failed")
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "❌" in call_args  # failed icon
            assert "Chapter 2" in call_args
            assert "Failed" in call_args
    
    @patch('pdf_podcast.logging_system.tqdm')
    def test_create_simple_progress_bar(self, mock_tqdm, temp_dir, mock_console):
        """Test creating simple progress bar."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            mock_tqdm_instance = Mock()
            mock_tqdm.return_value = mock_tqdm_instance
            
            pbar = logger.create_simple_progress_bar(10, "Processing items")
            
            assert pbar == mock_tqdm_instance
            mock_tqdm.assert_called_once_with(
                total=10,
                desc="Processing items",
                unit="item",
                ncols=80,
                file=mock_tqdm.call_args[1]['file']
            )
    
    def test_print_file_info_existing(self, temp_dir, mock_console):
        """Test printing info for existing file."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            # Create test file
            test_file = temp_dir / "test.txt"
            test_file.write_text("test content")
            
            logger.print_file_info(test_file, "Test File")
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "📁 Test File:" in call_args
            assert str(test_file) in call_args
            assert "MB)" in call_args
    
    def test_print_file_info_missing(self, temp_dir, mock_console):
        """Test printing info for missing file."""
        with patch('pdf_podcast.logging_system.logging.basicConfig'):
            logger = PodcastLogger(log_dir=temp_dir)
            
            # Non-existent file
            missing_file = temp_dir / "missing.txt"
            
            logger.print_file_info(missing_file, "Missing File")
            
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "📁 Missing File:" in call_args
            assert str(missing_file) in call_args
            assert "(not found)" in call_args


class TestSetupLogger:
    """Test setup_logger function."""
    
    def test_setup_logger_default(self, temp_dir):
        """Test setup_logger with default parameters."""
        with patch('pdf_podcast.logging_system.PodcastLogger') as mock_logger_class:
            mock_instance = Mock()
            mock_logger_class.return_value = mock_instance
            
            logger = setup_logger(log_dir=temp_dir, verbose=False)
            
            assert logger == mock_instance
            mock_logger_class.assert_called_once_with(log_dir=temp_dir, verbose=False)
    
    def test_setup_logger_verbose(self, temp_dir):
        """Test setup_logger with verbose enabled."""
        with patch('pdf_podcast.logging_system.PodcastLogger') as mock_logger_class:
            mock_instance = Mock()
            mock_logger_class.return_value = mock_instance
            
            logger = setup_logger(log_dir=temp_dir, verbose=True)
            
            assert logger == mock_instance
            mock_logger_class.assert_called_once_with(log_dir=temp_dir, verbose=True)
    
    def test_setup_logger_no_args(self):
        """Test setup_logger with no arguments."""
        with patch('pdf_podcast.logging_system.PodcastLogger') as mock_logger_class:
            mock_instance = Mock()
            mock_logger_class.return_value = mock_instance
            
            logger = setup_logger()
            
            assert logger == mock_instance
            mock_logger_class.assert_called_once_with(log_dir=None, verbose=False)