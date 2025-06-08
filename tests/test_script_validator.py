"""Tests for script_validator module."""

import pytest
import logging
from pdf_podcast.script_validator import ScriptValidator, ValidationResult
from pdf_podcast.script_builder import LectureScript


class TestScriptValidator:
    """Test cases for ScriptValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ScriptValidator()
    
    def create_lecture_script(self, content: str, title="Test Chapter"):
        """Helper to create LectureScript for testing."""
        return LectureScript(
            chapter_title=title,
            content=content,
            total_chars=len(content)
        )
    
    def test_valid_script(self):
        """Test validation of a good script."""
        content = """本日は機械学習の基礎について解説します。

機械学習とは、コンピュータに明示的なプログラミングをすることなく、データから学習する能力を与える技術です。
この技術は近年急速に発展し、様々な分野で応用されています。

機械学習には主に3つのタイプがあります。
教師あり学習、教師なし学習、そして強化学習です。
それぞれの特徴を簡単に説明します。

教師あり学習は、入力と正解のペアから学習します。
教師なし学習は、データの構造を発見します。
強化学習は、試行錯誤から最適な行動を学習します。

それぞれの特徴と応用例について、今後詳しく見ていきましょう。"""
        
        script = self.create_lecture_script(content)
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert not result.has_warnings
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_too_many_chars_error(self):
        """Test error for too many characters."""
        content = "あ" * 2000  # Exceed MAX_CHARS (1800)
        script = self.create_lecture_script(content)
        
        result = self.validator.validate_script(script)
        
        assert not result.is_valid
        assert any("文字数が上限を超過" in error for error in result.errors)
    
    def test_too_many_chars_warning(self):
        """Test warning for many characters."""
        content = "あ" * 1700  # Exceed WARN_CHARS (1600) but under MAX_CHARS
        script = self.create_lecture_script(content)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("文字数が多い" in warning for warning in result.warnings)
    
    def test_empty_script_error(self):
        """Test error for empty script."""
        content = ""
        script = self.create_lecture_script(content)
        
        result = self.validator.validate_script(script)
        
        assert not result.is_valid
        assert any("講義内容が空" in error for error in result.errors)
    
    def test_too_short_script_warning(self):
        """Test warning for very short script."""
        content = "短い講義内容です。"
        script = self.create_lecture_script(content)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("文字数が少ない" in warning for warning in result.warnings)
    
    def test_few_paragraphs_warning(self):
        """Test warning for too few paragraphs."""
        content = "これは段落が少ない講義内容です。全体が一つの段落で構成されています。"
        script = self.create_lecture_script(content)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("段落数が少ない" in warning for warning in result.warnings)
    
    def test_long_paragraph_warning(self):
        """Test warning for extremely long paragraph."""
        content = f"""短い導入です。

{"あ" * 600}

まとめです。"""
        script = self.create_lecture_script(content)
        
        result = self.validator.validate_script(script)
        
        assert result.is_valid
        assert result.has_warnings
        assert any("極端に長い段落" in warning for warning in result.warnings)
    
    def test_get_improvement_suggestions(self):
        """Test improvement suggestions generation."""
        content = "短い"
        script = self.create_lecture_script(content)
        result = self.validator.validate_script(script)
        
        suggestions = self.validator.get_improvement_suggestions(result)
        
        assert len(suggestions) > 0
        assert any("内容を充実" in suggestion for suggestion in suggestions)
    
    def test_log_validation_results(self, caplog):
        """Test logging of validation results."""
        content = "あ" * 1700
        script = self.create_lecture_script(content)
        result = self.validator.validate_script(script)
        
        with caplog.at_level(logging.WARNING):
            self.validator.log_validation_results(result, "Test Chapter")
        
        assert "スクリプト検証警告" in caplog.text
        assert "文字数が多い" in caplog.text


class TestValidationResult:
    """Test cases for ValidationResult class."""
    
    def test_is_valid_property(self):
        """Test is_valid property."""
        result_with_errors = ValidationResult(
            warnings=[],
            errors=["エラーがあります"]
        )
        assert not result_with_errors.is_valid
        
        result_no_errors = ValidationResult(
            warnings=["警告があります"],
            errors=[]
        )
        assert result_no_errors.is_valid
    
    def test_has_warnings_property(self):
        """Test has_warnings property."""
        result_with_warnings = ValidationResult(
            warnings=["警告があります"],
            errors=[]
        )
        assert result_with_warnings.has_warnings
        
        result_no_warnings = ValidationResult(
            warnings=[],
            errors=["エラーがあります"]
        )
        assert not result_no_warnings.has_warnings