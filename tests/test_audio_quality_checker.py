"""Tests for audio_quality_checker module."""

import pytest
import wave
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pdf_podcast.audio_quality_checker import AudioQualityChecker, AudioQualityResult


class TestAudioQualityChecker:
    """Test cases for AudioQualityChecker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.checker = AudioQualityChecker()
    
    def create_test_wav_file(self, duration: float = 5.0, sample_rate: int = 24000) -> Path:
        """Create a test WAV file for testing."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        
        # Create a simple WAV file
        with wave.open(str(temp_path), 'wb') as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            
            # Generate simple sine wave data
            import math
            num_frames = int(duration * sample_rate)
            frames = []
            for i in range(num_frames):
                # Simple sine wave at 440Hz
                value = int(32767 * 0.1 * math.sin(2 * math.pi * 440 * i / sample_rate))
                frames.extend([value & 0xFF, (value >> 8) & 0xFF])
            
            wf.writeframes(bytes(frames))
        
        return temp_path
    
    def create_empty_file(self) -> Path:
        """Create an empty file for testing."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        return temp_path
    
    def teardown_method(self):
        """Clean up test files."""
        # Clean up any temp files created during tests
        pass
    
    def test_verify_duration_valid(self):
        """Test duration verification with valid audio."""
        test_file = self.create_test_wav_file(duration=10.0)
        try:
            result = self.checker.verify_duration(test_file, expected_duration=10.0)
            assert result is True
        finally:
            test_file.unlink()
    
    def test_verify_duration_too_short(self):
        """Test duration verification with too short audio."""
        test_file = self.create_test_wav_file(duration=5.0)
        try:
            result = self.checker.verify_duration(test_file)
            assert result is False
        finally:
            test_file.unlink()
    
    def test_verify_duration_too_long(self):
        """Test duration verification with too long audio."""
        # Mock _get_audio_duration to return a very long duration
        with patch.object(self.checker, '_get_audio_duration', return_value=2000.0):
            test_file = Path("fake_file.wav")
            result = self.checker.verify_duration(test_file)
            assert result is False
    
    def test_verify_duration_expected_mismatch(self):
        """Test duration verification with expected duration mismatch."""
        test_file = self.create_test_wav_file(duration=10.0)
        try:
            # Expected 20 seconds, but file is 10 seconds (50% difference > 30% tolerance)
            result = self.checker.verify_duration(test_file, expected_duration=20.0)
            assert result is False
        finally:
            test_file.unlink()
    
    def test_check_audio_integrity_valid_file(self):
        """Test integrity check with valid audio file."""
        test_file = self.create_test_wav_file()
        try:
            result = self.checker.check_audio_integrity(test_file)
            assert result is True
        finally:
            test_file.unlink()
    
    def test_check_audio_integrity_nonexistent_file(self):
        """Test integrity check with non-existent file."""
        fake_file = Path("nonexistent_file.wav")
        result = self.checker.check_audio_integrity(fake_file)
        assert result is False
    
    def test_check_audio_integrity_empty_file(self):
        """Test integrity check with empty file."""
        empty_file = self.create_empty_file()
        try:
            result = self.checker.check_audio_integrity(empty_file)
            assert result is False
        finally:
            empty_file.unlink()
    
    def test_get_audio_duration_wav(self):
        """Test getting duration from WAV file."""
        test_file = self.create_test_wav_file(duration=15.0)
        try:
            duration = self.checker._get_audio_duration(test_file)
            assert duration is not None
            assert 14.5 <= duration <= 15.5  # Allow some tolerance
        finally:
            test_file.unlink()
    
    @patch('pdf_podcast.audio_quality_checker.AUDIO_ANALYSIS_AVAILABLE', True)
    @patch('pdf_podcast.audio_quality_checker.librosa')
    def test_detect_silence_ratio_with_librosa(self, mock_librosa):
        """Test silence detection with librosa available."""
        import numpy as np
        # Mock librosa functions
        mock_librosa.load.return_value = (np.array([0.1, 0.05, 0.0, 0.0, 0.2]), 24000)
        mock_librosa.feature.rms.return_value = np.array([[0.1, 0.05, 0.01, 0.01, 0.2]])
        
        test_file = self.create_test_wav_file()
        try:
            ratio = self.checker.detect_silence_ratio(test_file)
            assert ratio is not None
            assert 0.0 <= ratio <= 1.0
        finally:
            test_file.unlink()
    
    @patch('pdf_podcast.audio_quality_checker.AUDIO_ANALYSIS_AVAILABLE', False)
    def test_detect_silence_ratio_without_librosa(self):
        """Test silence detection without librosa."""
        test_file = self.create_test_wav_file()
        try:
            ratio = self.checker.detect_silence_ratio(test_file)
            assert ratio is None
        finally:
            test_file.unlink()
    
    def test_check_audio_quality_valid(self):
        """Test comprehensive quality check with valid audio."""
        test_file = self.create_test_wav_file(duration=15.0)
        try:
            with patch.object(self.checker, 'detect_silence_ratio', return_value=0.1):
                result = self.checker.check_audio_quality(test_file, expected_duration=15.0)
                
                assert result.is_valid
                assert not result.has_issues
                assert result.duration is not None
        finally:
            test_file.unlink()
    
    def test_check_audio_quality_with_issues(self):
        """Test comprehensive quality check with issues."""
        # Mock integrity check to fail
        with patch.object(self.checker, 'check_audio_integrity', return_value=False):
            test_file = Path("fake_file.wav")
            result = self.checker.check_audio_quality(test_file)
            
            assert not result.is_valid
            assert result.has_issues
            assert len(result.issues) > 0
    
    def test_check_audio_quality_high_silence(self):
        """Test quality check with high silence ratio."""
        test_file = self.create_test_wav_file(duration=15.0)
        try:
            with patch.object(self.checker, 'detect_silence_ratio', return_value=0.9):
                result = self.checker.check_audio_quality(test_file)
                
                assert not result.is_valid
                assert any("無音割合が高すぎます" in issue for issue in result.issues)
        finally:
            test_file.unlink()
    
    def test_check_audio_quality_moderate_silence(self):
        """Test quality check with moderate silence ratio."""
        test_file = self.create_test_wav_file(duration=15.0)
        try:
            with patch.object(self.checker, 'detect_silence_ratio', return_value=0.6):
                result = self.checker.check_audio_quality(test_file)
                
                assert result.is_valid
                assert result.has_warnings
                assert any("無音割合が多めです" in warning for warning in result.warnings)
        finally:
            test_file.unlink()
    
    def test_log_quality_results(self, caplog):
        """Test logging of quality results."""
        result = AudioQualityResult(
            is_valid=False,
            duration=10.0,
            expected_duration=15.0,
            silence_ratio=0.9,
            issues=["無音割合が高すぎます"],
            warnings=["音声長が期待値と異なります"]
        )
        
        test_file = Path("test_audio.wav")
        self.checker.log_quality_results(result, test_file)
        
        assert "エラー" in caplog.text
        assert "警告" in caplog.text
    
    def test_get_quality_improvement_suggestions(self):
        """Test improvement suggestions generation."""
        result = AudioQualityResult(
            is_valid=False,
            duration=5.0,
            expected_duration=None,
            silence_ratio=0.9,
            issues=["音声が短すぎます", "無音割合が高すぎます"],
            warnings=[]
        )
        
        suggestions = self.checker.get_quality_improvement_suggestions(result)
        
        assert len(suggestions) >= 2
        assert any("スクリプトの内容を充実" in suggestion for suggestion in suggestions)
        assert any("TTS生成パラメータを調整" in suggestion for suggestion in suggestions)


class TestAudioQualityResult:
    """Test cases for AudioQualityResult class."""
    
    def test_has_issues_property(self):
        """Test has_issues property."""
        result_with_issues = AudioQualityResult(
            is_valid=False,
            duration=10.0,
            expected_duration=None,
            silence_ratio=None,
            issues=["問題があります"],
            warnings=[]
        )
        assert result_with_issues.has_issues
        
        result_no_issues = AudioQualityResult(
            is_valid=True,
            duration=10.0,
            expected_duration=None,
            silence_ratio=None,
            issues=[],
            warnings=[]
        )
        assert not result_no_issues.has_issues
    
    def test_has_warnings_property(self):
        """Test has_warnings property."""
        result_with_warnings = AudioQualityResult(
            is_valid=True,
            duration=10.0,
            expected_duration=None,
            silence_ratio=None,
            issues=[],
            warnings=["警告があります"]
        )
        assert result_with_warnings.has_warnings
        
        result_no_warnings = AudioQualityResult(
            is_valid=True,
            duration=10.0,
            expected_duration=None,
            silence_ratio=None,
            issues=[],
            warnings=[]
        )
        assert not result_no_warnings.has_warnings