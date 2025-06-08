"""Tests for tts_client module."""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open, AsyncMock
from pathlib import Path
import base64
from pdf_podcast.tts_client import TTSClient, VoiceConfig
from pdf_podcast.script_builder import SectionScript


class TestTTSClient:
    """Test cases for TTSClient class."""
    
    @pytest.fixture
    def mock_genai(self):
        """Mock google.generativeai module."""
        with patch('pdf_podcast.tts_client.genai') as mock:
            yield mock
    
    @pytest.fixture
    def tts_client(self, mock_genai):
        """Create TTSClient instance with mocked API."""
        return TTSClient(api_key="test-api-key", model_name="test-tts-model", 
                        sample_rate=22050, channels=1, bitrate="128k")
    
    def test_init(self, mock_genai):
        """Test TTSClient initialization."""
        client = TTSClient(api_key="test-key", model_name="custom-tts-model", 
                          sample_rate=16000, channels=2, bitrate="320k")
        
        mock_genai.Client.assert_called_once_with(api_key="test-key")
        assert client.model_name == "custom-tts-model"
        assert client.sample_rate == 16000
        assert client.channels == 2
        assert client.bitrate == "320k"
        
        # Test defaults
        default_client = TTSClient(api_key="test-key")
        assert default_client.sample_rate == 22050
        assert default_client.channels == 1
        assert default_client.bitrate == "128k"
    
    
    def test_generate_audio_success(self, tts_client, mock_genai):
        """Test successful audio generation."""
        lecture_content = "みなさん、こんにちは。今日は講義を行います。"
        
        # Mock audio response with correct structure
        audio_data = b"test audio content"
        
        mock_inline_data = Mock()
        mock_inline_data.data = audio_data
        
        mock_part = Mock()
        mock_part.inline_data = mock_inline_data
        
        mock_content = Mock()
        mock_content.parts = [mock_part]
        
        mock_candidate = Mock()
        mock_candidate.content = mock_content
        
        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        
        tts_client.client.models.generate_content.return_value = mock_response
        
        # Generate audio without saving
        result = tts_client.generate_audio(lecture_content)
        
        assert result == audio_data
        
        # Verify API call
        tts_client.client.models.generate_content.assert_called_once()
    
    @patch('pdf_podcast.tts_client.Path')
    def test_generate_audio_with_output_path(self, mock_path_class, tts_client, mock_genai):
        """Test audio generation with file output."""
        lecture_content = "講義内容です。"
        output_path = Mock()
        output_path.parent.mkdir = Mock()
        
        # Mock audio response with correct structure
        audio_data = b"audio data"
        
        mock_inline_data = Mock()
        mock_inline_data.data = audio_data
        
        mock_part = Mock()
        mock_part.inline_data = mock_inline_data
        
        mock_content = Mock()
        mock_content.parts = [mock_part]
        
        mock_candidate = Mock()
        mock_candidate.content = mock_content
        
        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        
        tts_client.client.models.generate_content.return_value = mock_response
        
        # Mock file operations
        wav_path = Mock()
        output_path.with_suffix = Mock(return_value=wav_path)
        wav_path.rename = Mock()
        
        with patch.object(tts_client, '_save_wav_file') as mock_save_wav:
            # Generate audio with output path
            result = tts_client.generate_audio(
                lecture_content=lecture_content,
                output_path=output_path
            )
        
        assert result == audio_data
        mock_save_wav.assert_called_once_with(wav_path, audio_data)
        wav_path.rename.assert_called_once_with(output_path)
    
    def test_generate_audio_api_error(self, tts_client, mock_genai):
        """Test handling of API errors."""
        lecture_content = "Test content"
        
        tts_client.client.models.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(Exception) as exc_info:
            tts_client.generate_audio(lecture_content)
        
        assert "API Error" in str(exc_info.value)
    
    @patch('pdf_podcast.tts_client.Path.mkdir')
    def test_generate_chapter_audios(self, mock_mkdir, tts_client, mock_genai):
        """Test batch audio generation for chapters."""
        scripts = {
            "第1章: 導入": "第1章の講義内容です。",
            "第2章: 詳細": "第2章の講義内容です。"
        }
        
        output_dir = Path("/tmp/output")
        
        # Mock audio responses
        audio_bytes = b"audio data"
        encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
        
        mock_part = Mock()
        mock_part.inline_data.mime_type = "audio/mp3"
        mock_part.inline_data.data = encoded_audio
        
        mock_response = Mock()
        mock_response.parts = [mock_part]
        
        tts_client.client.models.generate_content.return_value = mock_response
        
        with patch.object(tts_client, 'generate_audio', return_value=audio_bytes) as mock_generate:
            audio_paths = tts_client.generate_chapter_audios(scripts, output_dir)
        
        assert len(audio_paths) == 2
        assert "第1章: 導入" in audio_paths
        assert "第2章: 詳細" in audio_paths
        
        # Verify generate_audio was called for each script
        assert mock_generate.call_count == 2
    
    @patch('pdf_podcast.tts_client.Path.mkdir')
    def test_generate_chapter_audios_partial_failure(self, mock_mkdir, tts_client, mock_genai):
        """Test handling of partial failures in batch generation."""
        scripts = {
            "第1章": "内容1",
            "第2章": "内容2"
        }
        
        output_dir = Path("/tmp/output")
        
        # First succeeds, second fails
        with patch.object(tts_client, 'generate_audio', side_effect=[b"audio", Exception("API Error")]):
            audio_paths = tts_client.generate_chapter_audios(scripts, output_dir)
        
        # Should complete successfully for first chapter only
        assert len(audio_paths) == 1
        assert "第1章" in audio_paths
        assert "第2章" not in audio_paths
    
    @patch('pdf_podcast.tts_client.Path.mkdir')
    def test_generate_section_audios(self, mock_mkdir, tts_client, mock_genai):
        """Test batch audio generation for sections."""
        section1 = SectionScript(
            section_title="データ構造",
            section_number="1.1",
            content="データ構造についての講義内容です。",
            total_chars=100,
            parent_chapter="第1章"
        )
        
        section2 = SectionScript(
            section_title="アルゴリズム",
            section_number="1.2",
            content="アルゴリズムについての講義内容です。",
            total_chars=120,
            parent_chapter="第1章"
        )
        
        section_scripts = {
            "1.1_データ構造": section1,
            "1.2_アルゴリズム": section2
        }
        
        output_dir = Path("/tmp/output")
        
        # Mock audio responses
        audio_bytes = b"audio data"
        
        with patch.object(tts_client, 'generate_audio', return_value=audio_bytes) as mock_generate:
            audio_paths = tts_client.generate_section_audios(section_scripts, output_dir)
        
        assert len(audio_paths) == 2
        assert "1.1_データ構造" in audio_paths
        assert "1.2_アルゴリズム" in audio_paths
        
        # Verify generate_audio was called for each section
        assert mock_generate.call_count == 2
        
        # Verify filename format
        for path in audio_paths.values():
            assert "1_1_" in str(path) or "1_2_" in str(path)  # Section number format
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_retry_success(self, tts_client):
        """Test successful audio generation with retry."""
        lecture_content = "講義内容です。"
        
        # Mock successful generation
        with patch.object(tts_client, 'generate_audio', return_value=b"audio data") as mock_generate:
            result = await tts_client.generate_audio_with_retry(lecture_content)
        
        assert result == b"audio data"
        mock_generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_audio_with_retry_rate_limit(self, tts_client):
        """Test retry behavior with rate limit errors."""
        lecture_content = "講義内容です。"
        
        # Mock rate limit error followed by success
        with patch.object(tts_client, 'generate_audio', side_effect=[
            Exception("429 rate limit exceeded"),
            b"audio data"
        ]) as mock_generate:
            with patch('asyncio.sleep') as mock_sleep:
                result = await tts_client.generate_audio_with_retry(lecture_content, max_retries=1)
        
        assert result == b"audio data"
        assert mock_generate.call_count == 2
        mock_sleep.assert_called_once()  # Should sleep between retries
    
    @pytest.mark.asyncio
    async def test_generate_section_audios_async(self, tts_client):
        """Test async section audio generation."""
        section1 = SectionScript(
            section_title="データ構造",
            section_number="1.1",
            content="データ構造についての講義内容です。",
            total_chars=100,
            parent_chapter="第1章"
        )
        
        section_scripts = {
            "1.1_データ構造": section1
        }
        
        output_dir = Path("/tmp/output")
        
        # Mock successful generation
        with patch.object(tts_client, 'generate_audio_with_retry', return_value=b"audio data") as mock_generate:
            audio_paths = await tts_client.generate_section_audios_async(section_scripts, output_dir)
        
        assert len(audio_paths) == 1
        assert "1.1_データ構造" in audio_paths
        mock_generate.assert_called_once()