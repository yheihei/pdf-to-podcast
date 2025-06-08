"""Script validation module for checking lecture script quality and limits."""

import logging
from typing import List, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from .script_builder import LectureScript

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Results of script validation."""
    warnings: List[str]
    errors: List[str]
    
    @property
    def is_valid(self) -> bool:
        """Check if validation passed without errors."""
        return len(self.errors) == 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0


class ScriptValidator:
    """Validates lecture scripts for TTS generation quality and limits."""
    
    MAX_CHARS = 1800
    WARN_CHARS = 1600
    MIN_CHARS = 200
    
    def validate_script(self, script) -> ValidationResult:
        """スクリプトの適正性を検証
        
        Args:
            script: 検証対象のLectureScript
            
        Returns:
            ValidationResult containing warnings and errors
        """
        warnings = []
        errors = []
        
        # 文字数のチェック
        if script.total_chars > self.WARN_CHARS:
            warnings.append(f"文字数が多い: {script.total_chars}文字 (推奨: {self.WARN_CHARS}文字以下)")
            
        if script.total_chars > self.MAX_CHARS:
            errors.append(f"文字数が上限を超過: {script.total_chars}文字 (上限: {self.MAX_CHARS}文字)")
        
        # 空のスクリプトチェック
        if not script.content or script.content.strip() == "":
            errors.append("講義内容が空です")
            
        # 極端に短いスクリプトチェック
        if script.total_chars < self.MIN_CHARS:
            warnings.append(f"文字数が少ない: {script.total_chars}文字 (推奨: {self.MIN_CHARS}文字以上)")
        
        # 段落数のチェック
        paragraphs = [p for p in script.content.split('\n\n') if p.strip()]
        if len(paragraphs) < 3:
            warnings.append(f"段落数が少ない: {len(paragraphs)}段落 (推奨: 3段落以上で構造化)")
        
        # 極端に長い段落チェック
        if paragraphs:
            max_paragraph_length = max(len(p) for p in paragraphs)
            if max_paragraph_length > 500:
                warnings.append(f"極端に長い段落があります: {max_paragraph_length}文字 (推奨: 500文字以下)")
        
        return ValidationResult(warnings=warnings, errors=errors)
    
    def log_validation_results(self, validation_result: ValidationResult, chapter_title: str) -> None:
        """検証結果をログに出力
        
        Args:
            validation_result: 検証結果
            chapter_title: 章のタイトル
        """
        if validation_result.errors:
            logger.error(f"章 '{chapter_title}' のスクリプト検証エラー:")
            for error in validation_result.errors:
                logger.error(f"  - {error}")
        
        if validation_result.warnings:
            logger.warning(f"章 '{chapter_title}' のスクリプト検証警告:")
            for warning in validation_result.warnings:
                logger.warning(f"  - {warning}")
        
        if validation_result.is_valid and not validation_result.has_warnings:
            logger.info(f"章 '{chapter_title}' のスクリプト検証: 問題なし")
    
    def get_improvement_suggestions(self, validation_result: ValidationResult) -> List[str]:
        """検証結果に基づく改善提案を生成
        
        Args:
            validation_result: 検証結果
            
        Returns:
            改善提案のリスト
        """
        suggestions = []
        
        # エラーに対する提案
        for error in validation_result.errors:
            if "文字数が上限を超過" in error:
                suggestions.append("講義内容を簡潔にし、要点を絞ってください")
            elif "講義内容が空" in error:
                suggestions.append("講義内容を生成してください")
        
        # 警告に対する提案
        for warning in validation_result.warnings:
            if "文字数が多い" in warning:
                suggestions.append("音声品質向上のため、1600文字以下に調整することを推奨します")
            elif "段落数が少ない" in warning:
                suggestions.append("導入、本論、まとめの構造で段落を構成してください")
            elif "極端に長い段落" in warning:
                suggestions.append("長い段落を複数の短い段落に分割してください")
            elif "文字数が少ない" in warning:
                suggestions.append("内容を充実させて、より詳細な講義にしてください")
        
        return suggestions