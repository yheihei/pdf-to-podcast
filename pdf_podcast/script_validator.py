"""Script validation module for checking dialogue script quality and limits."""

import logging
from typing import List, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from .script_builder import DialogueScript

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
    """Validates dialogue scripts for TTS generation quality and limits."""
    
    MAX_LINES = 25
    MAX_CHARS = 2000
    WARN_LINES = 20
    WARN_CHARS = 1800
    
    def validate_script(self, script) -> ValidationResult:
        """スクリプトの適正性を検証
        
        Args:
            script: 検証対象のDialogueScript
            
        Returns:
            ValidationResult containing warnings and errors
        """
        warnings = []
        errors = []
        
        # 対話行数のチェック
        if len(script.lines) > self.WARN_LINES:
            warnings.append(f"対話行数が多い: {len(script.lines)}行 (推奨: {self.WARN_LINES}行以下)")
        
        if len(script.lines) > self.MAX_LINES:
            errors.append(f"対話行数が上限を超過: {len(script.lines)}行 (上限: {self.MAX_LINES}行)")
        
        # 文字数のチェック
        if script.total_chars > self.WARN_CHARS:
            warnings.append(f"文字数が多い: {script.total_chars}文字 (推奨: {self.WARN_CHARS}文字以下)")
            
        if script.total_chars > self.MAX_CHARS:
            errors.append(f"文字数が上限を超過: {script.total_chars}文字 (上限: {self.MAX_CHARS}文字)")
        
        # 空のスクリプトチェック
        if len(script.lines) == 0:
            errors.append("対話行が空です")
            
        # 極端に短いスクリプトチェック
        if script.total_chars < 200:
            warnings.append(f"文字数が少ない: {script.total_chars}文字 (推奨: 200文字以上)")
        
        # 発言のバランスチェック
        host_lines = sum(1 for line in script.lines if line["speaker"] == "Host")
        guest_lines = sum(1 for line in script.lines if line["speaker"] == "Guest")
        
        if host_lines == 0:
            errors.append("Hostの発言がありません")
        elif guest_lines == 0:
            errors.append("Guestの発言がありません")
        else:
            ratio = min(host_lines, guest_lines) / max(host_lines, guest_lines)
            if ratio < 0.3:  # 一方の発言が3割未満
                warnings.append(f"発言のバランスが偏っています (Host: {host_lines}行, Guest: {guest_lines}行)")
        
        # 極端に長い発言チェック
        max_line_length = max(len(line["text"]) for line in script.lines) if script.lines else 0
        if max_line_length > 300:
            warnings.append(f"極端に長い発言があります: {max_line_length}文字 (推奨: 300文字以下)")
        
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
            if "対話行数が上限を超過" in error:
                suggestions.append("対話を短縮するか、重要なポイントに絞ってください")
            elif "文字数が上限を超過" in error:
                suggestions.append("各発言を簡潔にし、要点を絞ってください")
            elif "対話行が空" in error:
                suggestions.append("対話内容を生成してください")
            elif "発言がありません" in error:
                suggestions.append("HostとGuestの両方の発言を含めてください")
        
        # 警告に対する提案
        for warning in validation_result.warnings:
            if "対話行数が多い" in warning:
                suggestions.append("TTS処理時間短縮のため、対話を20行以下に調整することを推奨します")
            elif "文字数が多い" in warning:
                suggestions.append("音声品質向上のため、1800文字以下に調整することを推奨します")
            elif "発言のバランスが偏っています" in warning:
                suggestions.append("HostとGuestの発言回数のバランスを調整してください")
            elif "極端に長い発言" in warning:
                suggestions.append("長い発言を複数の短い発言に分割してください")
            elif "文字数が少ない" in warning:
                suggestions.append("内容を充実させて、より詳細な対話にしてください")
        
        return suggestions