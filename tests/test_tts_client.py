"""Tests for tts_client module."""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import base64
from pdf_podcast.tts_client import TTSClient, VoiceConfig


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
        return TTSClient(api_key="test-api-key", model_name="test-tts-model")
    
    def test_init(self, mock_genai):
        """Test TTSClient initialization."""
        client = TTSClient(api_key="test-key", model_name="custom-tts-model")
        
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        mock_genai.GenerativeModel.assert_called_once_with("custom-tts-model")
    
    def test_create_multi_speaker_content(self, tts_client):
        """Test multi-speaker content creation."""
        dialogue_lines = [
            {"speaker": "Host", "text": "こんにちは"},
            {"speaker": "Guest", "text": "よろしくお願いします"},
            {"speaker": "Host", "text": "今日のテーマは"}
        ]
        
        content = tts_client._create_multi_speaker_content(dialogue_lines)
        
        expected = '<speaker id="Host">こんにちは</speaker>\n' \
                  '<speaker id="Guest">よろしくお願いします</speaker>\n' \
                  '<speaker id="Host">今日のテーマは</speaker>'
        
        assert content == expected
    
    def test_extract_audio_data_success(self, tts_client):
        """Test successful audio data extraction."""
        # Mock audio data
        audio_bytes = b"fake audio data"
        encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Mock response with audio part
        mock_part = Mock()
        mock_part.inline_data.mime_type = "audio/mp3"
        mock_part.inline_data.data = encoded_audio
        
        mock_response = Mock()
        mock_response.parts = [mock_part]
        
        result = tts_client._extract_audio_data(mock_response)
        
        assert result == audio_bytes
    
    def test_extract_audio_data_no_parts(self, tts_client):
        """Test extraction with no parts in response."""
        mock_response = Mock()
        mock_response.parts = []
        
        with pytest.raises(ValueError) as exc_info:
            tts_client._extract_audio_data(mock_response)
        
        assert "No audio data in response" in str(exc_info.value)
    
    def test_extract_audio_data_no_audio_part(self, tts_client):
        """Test extraction with no audio part."""
        # Mock part without audio
        mock_part = Mock()
        mock_part.inline_data.mime_type = "text/plain"
        
        mock_response = Mock()
        mock_response.parts = [mock_part]
        
        with pytest.raises(ValueError) as exc_info:
            tts_client._extract_audio_data(mock_response)
        
        assert "No audio data found" in str(exc_info.value)
    
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_audio_success(self, mock_file, tts_client, mock_genai):
        """Test successful audio generation."""
        dialogue_lines = [
            {"speaker": "Host", "text": "テスト"},
            {"speaker": "Guest", "text": "音声生成"}
        ]
        
        # Mock audio response
        audio_bytes = b"test audio content"
        encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
        
        mock_part = Mock()
        mock_part.inline_data.mime_type = "audio/mp3"
        mock_part.inline_data.data = encoded_audio
        
        mock_response = Mock()
        mock_response.parts = [mock_part]
        
        tts_client.model.generate_content.return_value = mock_response
        
        # Generate audio without saving
        result = tts_client.generate_audio(dialogue_lines)
        
        assert result == audio_bytes
        
        # Verify API call
        tts_client.model.generate_content.assert_called_once()
        call_args = tts_client.model.generate_content.call_args
        
        # Check content
        content_arg = call_args[0][0][0]  # First element of the list passed to generate_content
        assert '<speaker id="Host">テスト</speaker>' in content_arg
        assert '<speaker id="Guest">音声生成</speaker>' in content_arg
        
        # Check generation config
        gen_config = call_args[1]['generation_config']
        assert gen_config['response_modalities'] == ["AUDIO"]
        assert gen_config['response_mime_type'] == "audio/mp3"
        assert 'multiSpeakerVoiceConfig' in gen_config
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_generate_audio_with_output_path(self, mock_mkdir, mock_file, tts_client, mock_genai):
        """Test audio generation with file output."""
        dialogue_lines = [{"speaker": "Host", "text": "Test"}]
        output_path = Path("/tmp/test.mp3")
        
        # Mock audio response
        audio_bytes = b"audio data"
        encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
        
        mock_part = Mock()
        mock_part.inline_data.mime_type = "audio/mp3"
        mock_part.inline_data.data = encoded_audio
        
        mock_response = Mock()
        mock_response.parts = [mock_part]
        
        tts_client.model.generate_content.return_value = mock_response
        
        # Generate audio with saving
        result = tts_client.generate_audio(dialogue_lines, output_path=output_path)
        
        # Verify file operations
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file.assert_called_once_with(output_path, 'wb')
        mock_file().write.assert_called_once_with(audio_bytes)
    
    def test_generate_audio_api_error(self, tts_client, mock_genai):
        """Test handling of API errors."""
        dialogue_lines = [{"speaker": "Host", "text": "Test"}]
        
        tts_client.model.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(Exception) as exc_info:
            tts_client.generate_audio(dialogue_lines)
        
        assert "API Error" in str(exc_info.value)
    
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_chapter_audios(self, mock_file, mock_mkdir, tts_client, mock_genai):
        """Test batch audio generation for chapters."""
        scripts = {
            "第1章: 導入": [
                {"speaker": "Host", "text": "第1章の内容"},
                {"speaker": "Guest", "text": "興味深い"}
            ],
            "第2章: 詳細": [
                {"speaker": "Host", "text": "第2章の内容"}
            ]
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
        
        tts_client.model.generate_content.return_value = mock_response
        
        # Generate audios
        result = tts_client.generate_chapter_audios(scripts, output_dir)
        
        # Verify results
        assert len(result) == 2
        assert "第1章: 導入" in result
        assert "第2章: 詳細" in result
        
        # Check file paths
        path1 = result["第1章: 導入"]
        path2 = result["第2章: 詳細"]
        
        assert path1.suffix == ".mp3"
        assert path2.suffix == ".mp3"
        assert "01_" in str(path1)
        assert "02_" in str(path2)
    
    @patch('pathlib.Path.mkdir')
    def test_generate_chapter_audios_partial_failure(self, mock_mkdir, tts_client, mock_genai):
        """Test handling of partial failures in batch generation."""
        scripts = {
            "第1章": [{"speaker": "Host", "text": "内容1"}],
            "第2章": [{"speaker": "Host", "text": "内容2"}]
        }
        
        output_dir = Path("/tmp/output")
        
        # First succeeds, second fails
        audio_bytes = b"audio"
        encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
        
        mock_part = Mock()
        mock_part.inline_data.mime_type = "audio/mp3"
        mock_part.inline_data.data = encoded_audio
        
        mock_response = Mock()
        mock_response.parts = [mock_part]
        
        tts_client.model.generate_content.side_effect = [
            mock_response,
            Exception("API Error")
        ]
        
        with patch('builtins.open', mock_open()):
            result = tts_client.generate_chapter_audios(scripts, output_dir)
        
        # Should complete for first chapter only
        assert len(result) == 1
        assert "第1章" in result
        assert "第2章" not in result