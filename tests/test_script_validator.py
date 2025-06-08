"""Tests for script_validator module."""

import pytest
from pdf_podcast.script_validator import ScriptValidator, ValidationResult
from pdf_podcast.script_builder import DialogueScript


class TestScriptValidator:
    """Test cases for ScriptValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ScriptValidator()
    
    def create_dialogue_script(self, lines_data, title="Test Chapter"):
        """Helper to create DialogueScript for testing."""
        total_chars = sum(len(line["text"]) for line in lines_data)
        return DialogueScript(
            chapter_title=title,
            lines=lines_data,
            total_chars=total_chars
        )
    
    def test_valid_script(self):
        """Test validation of a good script."""
        lines = [
            {"speaker": "Host", "text": "こんにちは、今日は素晴らしい話題について話しましょう。"},
            {"speaker": "Guest", "text": "はい、とても興味深いトピックですね。詳しく教えてください。"},
            {"speaker": "Host", "text": "まず最初に基本的な概念から始めましょう。"},
            {"speaker": "Guest", "text": "それは良いアイデアですね。よろしくお願いします。"}
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert not result.has_warnings
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_too_many_lines_error(self):
        """Test error for too many dialogue lines."""
        lines = []
        for i in range(30):  # Exceed MAX_LINES (25)
            lines.append({
                "speaker": "Host" if i % 2 == 0 else "Guest",
                "text": f"これは {i+1} 番目の発言です。"
            })
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert not result.is_valid
        assert any("対話行数が上限を超過" in error for error in result.errors)
    
    def test_too_many_lines_warning(self):
        """Test warning for many dialogue lines."""
        lines = []
        for i in range(22):  # Exceed WARN_LINES (20) but under MAX_LINES
            lines.append({
                "speaker": "Host" if i % 2 == 0 else "Guest",
                "text": f"発言 {i+1}"
            })
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("対話行数が多い" in warning for warning in result.warnings)
    
    def test_too_many_chars_error(self):
        """Test error for too many characters."""
        lines = [
            {"speaker": "Host", "text": "あ" * 1500},  # Very long text
            {"speaker": "Guest", "text": "い" * 600}   # Total > MAX_CHARS (2000)
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert not result.is_valid
        assert any("文字数が上限を超過" in error for error in result.errors)
    
    def test_too_many_chars_warning(self):
        """Test warning for many characters."""
        lines = [
            {"speaker": "Host", "text": "あ" * 1000},
            {"speaker": "Guest", "text": "い" * 900}  # Total > WARN_CHARS (1800)
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("文字数が多い" in warning for warning in result.warnings)
    
    def test_empty_script_error(self):
        """Test error for empty script."""
        lines = []
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert not result.is_valid
        assert any("対話行が空" in error for error in result.errors)
    
    def test_too_short_script_warning(self):
        """Test warning for very short script."""
        lines = [
            {"speaker": "Host", "text": "短い"},
            {"speaker": "Guest", "text": "はい"}
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("文字数が少ない" in warning for warning in result.warnings)
    
    def test_missing_host_error(self):
        """Test error for missing Host speaker."""
        lines = [
            {"speaker": "Guest", "text": "ゲストの発言です。"},
            {"speaker": "Guest", "text": "もう一つのゲストの発言です。"}
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert not result.is_valid
        assert any("Hostの発言がありません" in error for error in result.errors)
    
    def test_missing_guest_error(self):
        """Test error for missing Guest speaker."""
        lines = [
            {"speaker": "Host", "text": "ホストの発言です。"},
            {"speaker": "Host", "text": "もう一つのホストの発言です。"}
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert not result.is_valid
        assert any("Guestの発言がありません" in error for error in result.errors)
    
    def test_imbalanced_speakers_warning(self):
        """Test warning for imbalanced speaker distribution."""
        lines = [
            {"speaker": "Host", "text": "ホストの発言1"},
            {"speaker": "Host", "text": "ホストの発言2"},
            {"speaker": "Host", "text": "ホストの発言3"},
            {"speaker": "Host", "text": "ホストの発言4"},
            {"speaker": "Host", "text": "ホストの発言5"},
            {"speaker": "Host", "text": "ホストの発言6"},
            {"speaker": "Host", "text": "ホストの発言7"},
            {"speaker": "Host", "text": "ホストの発言8"},
            {"speaker": "Host", "text": "ホストの発言9"},
            {"speaker": "Host", "text": "ホストの発言10"},
            {"speaker": "Guest", "text": "ゲストの発言1"},
            {"speaker": "Guest", "text": "ゲストの発言2"}
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("発言のバランスが偏っています" in warning for warning in result.warnings)
    
    def test_very_long_line_warning(self):
        """Test warning for very long individual lines."""
        lines = [
            {"speaker": "Host", "text": "これはとても長い発言です。" + "あ" * 350},
            {"speaker": "Guest", "text": "普通の長さの発言です。"}
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("極端に長い発言があります" in warning for warning in result.warnings)
    
    def test_get_improvement_suggestions(self):
        """Test improvement suggestions generation."""
        lines = []
        for i in range(30):  # Too many lines
            lines.append({
                "speaker": "Host",
                "text": "あ" * 100
            })
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        suggestions = self.validator.get_improvement_suggestions(result)
        
        assert len(suggestions) > 0
        assert any("対話を短縮" in suggestion or "重要なポイントに絞って" in suggestion 
                  for suggestion in suggestions)
    
    def test_log_validation_results(self, caplog):
        """Test logging of validation results."""
        lines = [
            {"speaker": "Host", "text": "テスト発言"},
            {"speaker": "Guest", "text": "テスト応答"}
        ]
        script = self.create_dialogue_script(lines)
        
        result = self.validator.validate_script(script)
        self.validator.log_validation_results(result, "Test Chapter")
        
        assert "問題なし" in caplog.text or "Test Chapter" in caplog.text


class TestValidationResult:
    """Test cases for ValidationResult class."""
    
    def test_is_valid_with_no_errors(self):
        """Test is_valid property with no errors."""
        result = ValidationResult(warnings=["warning"], errors=[])
        assert result.is_valid
    
    def test_is_valid_with_errors(self):
        """Test is_valid property with errors."""
        result = ValidationResult(warnings=[], errors=["error"])
        assert not result.is_valid
    
    def test_has_warnings(self):
        """Test has_warnings property."""
        result = ValidationResult(warnings=["warning"], errors=[])
        assert result.has_warnings
        
        result_no_warnings = ValidationResult(warnings=[], errors=[])
        assert not result_no_warnings.has_warnings