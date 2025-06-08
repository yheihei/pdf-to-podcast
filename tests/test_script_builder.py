"""Tests for script_builder module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pdf_podcast.script_builder import ScriptBuilder, DialogueScript


class TestScriptBuilder:
    """Test cases for ScriptBuilder class."""
    
    @pytest.fixture
    def mock_genai(self):
        """Mock google.generativeai module."""
        with patch('pdf_podcast.script_builder.genai') as mock:
            yield mock
    
    @pytest.fixture
    def script_builder(self, mock_genai):
        """Create ScriptBuilder instance with mocked API."""
        return ScriptBuilder(api_key="test-api-key", model_name="test-model")
    
    def test_init(self, mock_genai):
        """Test ScriptBuilder initialization."""
        builder = ScriptBuilder(api_key="test-key", model_name="custom-model")
        
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        mock_genai.GenerativeModel.assert_called_once_with("custom-model")
    
    def test_generate_dialogue_script_success(self, script_builder, mock_genai):
        """Test successful dialogue script generation."""
        # Mock response
        mock_response = Mock()
        mock_response.text = """Host: こんにちは、今日は第1章について話しましょう。
Guest: はい、とても興味深い内容ですね。
Host: 特に重要なポイントは何でしょうか？
Guest: 3つの主要な概念があります。"""
        
        script_builder.model.generate_content.return_value = mock_response
        
        # Generate script
        result = script_builder.generate_dialogue_script(
            chapter_title="第1章: 導入",
            chapter_content="これは第1章の内容です。"
        )
        
        # Assertions
        assert isinstance(result, DialogueScript)
        assert result.chapter_title == "第1章: 導入"
        assert len(result.lines) == 4
        assert result.lines[0]["speaker"] == "Host"
        assert result.lines[1]["speaker"] == "Guest"
        assert result.total_chars > 0
    
    def test_generate_dialogue_script_api_error(self, script_builder, mock_genai):
        """Test handling of API errors."""
        script_builder.model.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(Exception) as exc_info:
            script_builder.generate_dialogue_script(
                chapter_title="第1章",
                chapter_content="内容"
            )
        
        assert "API Error" in str(exc_info.value)
    
    def test_parse_dialogue_response(self, script_builder):
        """Test dialogue response parsing."""
        response_text = """Host: これはホストの発言です。
とても長い発言で
複数行にわたります。

Guest: これはゲストの返答です。

Host: 再びホストが話します。"""
        
        lines = script_builder._parse_dialogue_response(response_text)
        
        assert len(lines) == 3
        assert lines[0]["speaker"] == "Host"
        assert "複数行にわたります" in lines[0]["text"]
        assert lines[1]["speaker"] == "Guest"
        assert lines[2]["speaker"] == "Host"
    
    def test_parse_dialogue_response_empty(self, script_builder):
        """Test parsing empty response."""
        lines = script_builder._parse_dialogue_response("")
        assert lines == []
    
    def test_parse_dialogue_response_malformed(self, script_builder):
        """Test parsing malformed response."""
        response_text = """これは正しくない形式です。
Speaker: 誰かの発言
Random text"""
        
        lines = script_builder._parse_dialogue_response(response_text)
        # Should handle gracefully, may return empty or partial results
        assert isinstance(lines, list)
    
    def test_create_dialogue_prompt(self, script_builder):
        """Test dialogue prompt creation."""
        prompt = script_builder._create_dialogue_prompt(
            chapter_title="テスト章",
            chapter_content="章の内容"
        )
        
        assert "テスト章" in prompt
        assert "章の内容" in prompt
        assert "Host:" in prompt
        assert "Guest:" in prompt
        assert "10分で聴ける長さ" in prompt
    
    def test_generate_scripts_for_chapters(self, script_builder, mock_genai):
        """Test batch script generation for multiple chapters."""
        # Mock responses
        mock_response1 = Mock()
        mock_response1.text = "Host: 第1章の話\nGuest: そうですね"
        
        mock_response2 = Mock()
        mock_response2.text = "Host: 第2章の話\nGuest: なるほど"
        
        script_builder.model.generate_content.side_effect = [
            mock_response1,
            mock_response2
        ]
        
        chapters = {
            "第1章": "内容1",
            "第2章": "内容2"
        }
        
        scripts = script_builder.generate_scripts_for_chapters(chapters)
        
        assert len(scripts) == 2
        assert "第1章" in scripts
        assert "第2章" in scripts
        assert isinstance(scripts["第1章"], DialogueScript)
        assert isinstance(scripts["第2章"], DialogueScript)
    
    def test_generate_scripts_partial_failure(self, script_builder, mock_genai):
        """Test handling of partial failures in batch generation."""
        # First call succeeds, second fails
        mock_response = Mock()
        mock_response.text = "Host: 成功\nGuest: OK"
        
        script_builder.model.generate_content.side_effect = [
            mock_response,
            Exception("API Error")
        ]
        
        chapters = {
            "第1章": "内容1",
            "第2章": "内容2"
        }
        
        scripts = script_builder.generate_scripts_for_chapters(chapters)
        
        # Should complete successfully for first chapter
        assert len(scripts) == 1
        assert "第1章" in scripts
        assert "第2章" not in scripts