"""Audio quality checker module for validating generated TTS audio."""

import logging
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Import audio analysis libraries with graceful fallbacks
try:
    import librosa
    import soundfile as sf
    AUDIO_ANALYSIS_AVAILABLE = True
except ImportError:
    AUDIO_ANALYSIS_AVAILABLE = False
    logger.warning("音声解析ライブラリ（librosa, soundfile）が利用できません。基本的な検証のみ実行されます。")


@dataclass
class AudioQualityResult:
    """Results of audio quality check."""
    is_valid: bool
    duration: Optional[float]
    expected_duration: Optional[float]
    silence_ratio: Optional[float]
    issues: List[str]
    warnings: List[str]
    
    @property
    def has_issues(self) -> bool:
        """Check if audio has quality issues."""
        return len(self.issues) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if audio has warnings."""
        return len(self.warnings) > 0


class AudioQualityChecker:
    """Validates TTS-generated audio quality and integrity."""
    
    # Quality thresholds
    SILENCE_RATIO_THRESHOLD = 0.8  # 80%以上が無音の場合は問題
    SILENCE_RATIO_WARNING = 0.5    # 50%以上が無音の場合は警告
    DURATION_TOLERANCE = 0.3       # 期待時間の30%の誤差まで許容
    MIN_DURATION = 10.0            # 最低10秒
    MAX_DURATION = 1800.0          # 最大30分
    
    def verify_duration(
        self, 
        audio_path: Path, 
        expected_duration: Optional[float] = None
    ) -> bool:
        """音声長の検証
        
        Args:
            audio_path: 検証対象の音声ファイルパス
            expected_duration: 期待される音声長（秒）
            
        Returns:
            音声長が適切かどうか
        """
        try:
            duration = self._get_audio_duration(audio_path)
            
            if duration is None:
                logger.error(f"音声ファイルの長さを取得できませんでした: {audio_path}")
                return False
            
            # 基本的な長さチェック
            if duration < self.MIN_DURATION:
                logger.error(f"音声が短すぎます: {duration:.1f}秒 (最低: {self.MIN_DURATION}秒)")
                return False
            
            if duration > self.MAX_DURATION:
                logger.error(f"音声が長すぎます: {duration:.1f}秒 (最大: {self.MAX_DURATION}秒)")
                return False
            
            # 期待時間との比較
            if expected_duration:
                diff_ratio = abs(duration - expected_duration) / expected_duration
                if diff_ratio > self.DURATION_TOLERANCE:
                    logger.warning(f"音声長が期待値と大きく異なります: {duration:.1f}秒 (期待: {expected_duration:.1f}秒)")
                    return False
            
            logger.info(f"音声長検証: OK ({duration:.1f}秒)")
            return True
            
        except Exception as e:
            logger.error(f"音声長検証中にエラーが発生しました: {e}")
            return False
    
    def detect_silence_ratio(self, audio_path: Path) -> Optional[float]:
        """無音割合の検出
        
        Args:
            audio_path: 検証対象の音声ファイルパス
            
        Returns:
            無音割合（0.0-1.0）、検出できない場合はNone
        """
        if not AUDIO_ANALYSIS_AVAILABLE:
            logger.warning("音声解析ライブラリが利用できないため、無音検出をスキップします")
            return None
        
        try:
            # 音声ファイルを読み込み
            audio_data, sample_rate = librosa.load(str(audio_path), sr=None)
            
            if len(audio_data) == 0:
                logger.error(f"音声データが空です: {audio_path}")
                return 1.0  # 完全に無音
            
            # RMS（Root Mean Square）を計算して無音区間を検出
            frame_length = 2048
            hop_length = 512
            rms = librosa.feature.rms(
                y=audio_data, 
                frame_length=frame_length, 
                hop_length=hop_length
            )[0]
            
            # 無音閾値を設定（RMSの最大値の5%以下を無音とする）
            silence_threshold = max(rms) * 0.05
            silence_frames = rms < silence_threshold
            silence_ratio = silence_frames.sum() / len(silence_frames)
            
            logger.info(f"無音割合: {silence_ratio:.2%}")
            return float(silence_ratio)
            
        except Exception as e:
            logger.error(f"無音検出中にエラーが発生しました: {e}")
            return None
    
    def check_audio_integrity(self, audio_path: Path) -> bool:
        """音声ファイルの完整性チェック
        
        Args:
            audio_path: 検証対象の音声ファイルパス
            
        Returns:
            ファイルが完整かどうか
        """
        try:
            # ファイルの存在確認
            if not audio_path.exists():
                logger.error(f"音声ファイルが存在しません: {audio_path}")
                return False
            
            # ファイルサイズ確認
            file_size = audio_path.stat().st_size
            if file_size == 0:
                logger.error(f"音声ファイルのサイズが0バイトです: {audio_path}")
                return False
            
            if file_size < 1000:  # 1KB未満は異常
                logger.warning(f"音声ファイルのサイズが小さすぎます: {file_size} bytes")
                return False
            
            # ファイル形式の確認
            try:
                if audio_path.suffix.lower() in ['.wav']:
                    # WAVファイルの場合、waveモジュールで読み込み確認
                    with wave.open(str(audio_path), 'rb') as wf:
                        frames = wf.getnframes()
                        if frames == 0:
                            logger.error(f"音声ファイルにフレームデータがありません: {audio_path}")
                            return False
                
                elif AUDIO_ANALYSIS_AVAILABLE:
                    # その他の形式の場合、librosaで読み込み確認
                    audio_data, _ = librosa.load(str(audio_path), sr=None, duration=1.0)
                    if len(audio_data) == 0:
                        logger.error(f"音声データを読み込めませんでした: {audio_path}")
                        return False
                
            except Exception as e:
                logger.error(f"音声ファイルの読み込みに失敗しました: {audio_path} - {e}")
                return False
            
            logger.info(f"音声ファイル完整性: OK ({file_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"音声ファイル完整性チェック中にエラーが発生しました: {e}")
            return False
    
    def _get_audio_duration(self, audio_path: Path) -> Optional[float]:
        """音声ファイルの長さを取得
        
        Args:
            audio_path: 音声ファイルパス
            
        Returns:
            音声の長さ（秒）、取得できない場合はNone
        """
        try:
            if audio_path.suffix.lower() in ['.wav']:
                # WAVファイルの場合
                with wave.open(str(audio_path), 'rb') as wf:
                    frames = wf.getnframes()
                    sample_rate = wf.getframerate()
                    duration = frames / sample_rate
                    return duration
            
            elif AUDIO_ANALYSIS_AVAILABLE:
                # その他の形式の場合
                duration = librosa.get_duration(path=str(audio_path))
                return duration
            
            else:
                logger.warning(f"音声解析ライブラリが利用できないため、{audio_path.suffix}ファイルの長さを取得できません")
                return None
                
        except Exception as e:
            logger.error(f"音声長取得中にエラーが発生しました: {e}")
            return None
    
    def check_audio_quality(
        self,
        audio_path: Path,
        expected_duration: Optional[float] = None
    ) -> AudioQualityResult:
        """総合的な音声品質チェック
        
        Args:
            audio_path: 検証対象の音声ファイルパス
            expected_duration: 期待される音声長（秒）
            
        Returns:
            AudioQualityResult containing all check results
        """
        issues = []
        warnings = []
        duration = None
        silence_ratio = None
        
        # ファイル完整性チェック
        if not self.check_audio_integrity(audio_path):
            issues.append("音声ファイルの完整性に問題があります")
            return AudioQualityResult(
                is_valid=False,
                duration=duration,
                expected_duration=expected_duration,
                silence_ratio=silence_ratio,
                issues=issues,
                warnings=warnings
            )
        
        # 音声長チェック
        duration = self._get_audio_duration(audio_path)
        if duration is None:
            issues.append("音声長を取得できませんでした")
        else:
            if duration < self.MIN_DURATION:
                issues.append(f"音声が短すぎます: {duration:.1f}秒")
            elif duration > self.MAX_DURATION:
                issues.append(f"音声が長すぎます: {duration:.1f}秒")
            
            if expected_duration:
                diff_ratio = abs(duration - expected_duration) / expected_duration
                if diff_ratio > self.DURATION_TOLERANCE:
                    warnings.append(f"音声長が期待値と異なります: {duration:.1f}秒 (期待: {expected_duration:.1f}秒)")
        
        # 無音割合チェック
        silence_ratio = self.detect_silence_ratio(audio_path)
        if silence_ratio is not None:
            if silence_ratio >= self.SILENCE_RATIO_THRESHOLD:
                issues.append(f"無音割合が高すぎます: {silence_ratio:.1%}")
            elif silence_ratio >= self.SILENCE_RATIO_WARNING:
                warnings.append(f"無音割合が多めです: {silence_ratio:.1%}")
        
        is_valid = len(issues) == 0
        
        return AudioQualityResult(
            is_valid=is_valid,
            duration=duration,
            expected_duration=expected_duration,
            silence_ratio=silence_ratio,
            issues=issues,
            warnings=warnings
        )
    
    def log_quality_results(self, result: AudioQualityResult, audio_path: Path) -> None:
        """品質チェック結果をログに出力
        
        Args:
            result: 品質チェック結果
            audio_path: 音声ファイルパス
        """
        if result.issues:
            logger.error(f"音声品質チェック - エラー '{audio_path.name}':")
            for issue in result.issues:
                logger.error(f"  - {issue}")
        
        if result.warnings:
            logger.warning(f"音声品質チェック - 警告 '{audio_path.name}':")
            for warning in result.warnings:
                logger.warning(f"  - {warning}")
        
        if result.is_valid and not result.has_warnings:
            logger.info(f"音声品質チェック: OK '{audio_path.name}' ({result.duration:.1f}秒)")
    
    def get_quality_improvement_suggestions(self, result: AudioQualityResult) -> List[str]:
        """品質改善提案を生成
        
        Args:
            result: 品質チェック結果
            
        Returns:
            改善提案のリスト
        """
        suggestions = []
        
        for issue in result.issues:
            if "音声が短すぎます" in issue:
                suggestions.append("スクリプトの内容を充実させて音声を長くしてください")
            elif "音声が長すぎます" in issue:
                suggestions.append("スクリプトを短縮するか、分割処理を検討してください")
            elif "無音割合が高すぎます" in issue:
                suggestions.append("TTS生成パラメータを調整するか、スクリプトを見直してください")
            elif "完整性に問題" in issue:
                suggestions.append("TTS生成を再実行してください")
        
        for warning in result.warnings:
            if "音声長が期待値と異なります" in warning:
                suggestions.append("スクリプトの文字数を調整して期待される長さに近づけてください")
            elif "無音割合が多めです" in warning:
                suggestions.append("スクリプトの対話内容を見直して、より自然な発話にしてください")
        
        return suggestions