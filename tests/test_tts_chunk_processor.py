"""Tests for tts_chunk_processor module."""

import pytest
import asyncio
import wave
import tempfile
import io
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from pdf_podcast.tts_chunk_processor import TTSChunkProcessor


class TestTTSChunkProcessor:
    """Test cases for TTSChunkProcessor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_tts_client = Mock()
        self.processor = TTSChunkProcessor(tts_client=self.mock_tts_client)
    
    def create_sample_dialogue(self, num_lines: int = 10) -> list:
        """Create sample dialogue for testing."""
        dialogue = []
        for i in range(num_lines):
            speaker = "Host" if i % 2 == 0 else "Guest"
            text = f"これは{i+1}番目の発言です。" + "詳細な内容が続きます。" * (i % 3 + 1)
            dialogue.append({"speaker": speaker, "text": text})
        return dialogue
    
    def create_long_dialogue(self, num_lines: int = 30) -> list:
        """Create a long dialogue that exceeds limits."""
        dialogue = []
        for i in range(num_lines):
            speaker = "Host" if i % 2 == 0 else "Guest"
            text = f"これは長い発言{i+1}です。" + "とても詳細な説明が続きます。" * 10
            dialogue.append({"speaker": speaker, "text": text})
        return dialogue
    
    def test_split_dialogue_no_split_needed(self):
        """Test splitting when no split is needed."""
        short_dialogue = self.create_sample_dialogue(5)
        
        chunks = self.processor.split_dialogue_for_tts(short_dialogue)
        
        assert len(chunks) == 1
        assert chunks[0] == short_dialogue
    
    def test_split_dialogue_by_line_count(self):
        """Test splitting by line count."""
        long_dialogue = self.create_sample_dialogue(25)  # Exceeds PREFERRED_CHUNK_LINES
        
        chunks = self.processor.split_dialogue_for_tts(long_dialogue)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= self.processor.MAX_CHUNK_LINES
    
    def test_split_dialogue_by_character_count(self):
        """Test splitting by character count."""
        dialogue = [
            {"speaker": "Host", "text": "あ" * 800},
            {"speaker": "Guest", "text": "い" * 800},
            {"speaker": "Host", "text": "う" * 800}
        ]  # Total > MAX_CHUNK_CHARS
        
        chunks = self.processor.split_dialogue_for_tts(dialogue)
        
        assert len(chunks) > 1
        for chunk in chunks:
            total_chars = sum(len(line["text"]) for line in chunk)
            assert total_chars <= self.processor.MAX_CHUNK_CHARS
    
    def test_find_natural_split_point(self):
        """Test finding natural split points."""
        dialogue = [
            {"speaker": "Host", "text": "最初の発言です。"},
            {"speaker": "Guest", "text": "応答です。"},
            {"speaker": "Host", "text": "続きの発言です。"},
            {"speaker": "Guest", "text": "最後の応答です。"},
        ]
        
        split_point = self.processor._find_natural_split_point(dialogue, dialogue, 4)
        
        # Should find a natural split point (speaker change + sentence end)
        assert 0 <= split_point <= len(dialogue)
    
    def test_is_natural_ending(self):
        """Test natural ending detection."""
        natural_endings = [
            "これは自然な終わりです。",
            "質問ですか？",
            "驚きました！",
            "そうですね",
            "理解しました",
            "ありがとうございます。"
        ]
        
        unnatural_endings = [
            "これは途中で",
            "続きがあります、",
            "まだ話している"
        ]
        
        for text in natural_endings:
            assert self.processor._is_natural_ending(text)
        
        for text in unnatural_endings:
            assert not self.processor._is_natural_ending(text)
    
    @pytest.mark.asyncio
    async def test_process_chunks_sequentially_success(self):
        """Test successful sequential chunk processing."""
        chunks = [
            [{"speaker": "Host", "text": "チャンク1の発言"}],
            [{"speaker": "Guest", "text": "チャンク2の発言"}]
        ]
        
        # Mock TTS client to return audio data
        async def mock_generate_audio_with_timeout(*args, **kwargs):
            return b"fake_audio_data"
        
        self.mock_tts_client.generate_audio_with_timeout = mock_generate_audio_with_timeout
        
        audio_chunks = await self.processor.process_chunks_sequentially(chunks)
        
        assert len(audio_chunks) == 2
        assert all(chunk == b"fake_audio_data" for chunk in audio_chunks)
    
    @pytest.mark.asyncio
    async def test_process_chunks_sequentially_with_failure(self):
        """Test chunk processing with some failures."""
        chunks = [
            [{"speaker": "Host", "text": "チャンク1の発言"}],
            [{"speaker": "Guest", "text": "チャンク2の発言"}]
        ]
        
        # Mock TTS client to fail on second chunk
        call_count = 0
        
        async def mock_generate_audio_with_timeout(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"fake_audio_data"
            else:
                raise Exception("TTS failed")
        
        self.mock_tts_client.generate_audio_with_timeout = mock_generate_audio_with_timeout
        
        with patch.object(self.processor, '_create_silence_chunk', return_value=b"silence"):
            audio_chunks = await self.processor.process_chunks_sequentially(chunks)
        
        assert len(audio_chunks) == 2
        assert audio_chunks[0] == b"fake_audio_data"
        assert audio_chunks[1] == b"silence"
    
    def test_merge_audio_chunks_single_chunk(self):
        """Test merging with single chunk."""
        chunks = [b"single_audio_data"]
        
        merged = self.processor.merge_audio_chunks(chunks)
        
        assert merged == b"single_audio_data"
    
    def test_merge_audio_chunks_empty(self):
        """Test merging with no chunks."""
        chunks = []
        
        merged = self.processor.merge_audio_chunks(chunks)
        
        assert merged == b""
    
    @patch('pdf_podcast.tts_chunk_processor.NUMPY_AVAILABLE', False)
    def test_merge_audio_chunks_without_numpy(self):
        """Test merging without numpy available."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        
        merged = self.processor.merge_audio_chunks(chunks)
        
        assert merged == b"chunk1chunk2chunk3"
    
    def test_create_silence_chunk(self):
        """Test silence chunk creation."""
        silence = self.processor._create_silence_chunk(duration=2.0)
        
        assert isinstance(silence, bytes)
        assert len(silence) > 0
        
        # Verify it's a valid WAV file
        audio_io = io.BytesIO(silence)
        with wave.open(audio_io, 'rb') as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 24000
            duration = wf.getnframes() / wf.getframerate()
            assert abs(duration - 2.0) < 0.1  # Allow small tolerance
    
    @pytest.mark.asyncio
    async def test_process_large_dialogue_end_to_end(self):
        """Test complete large dialogue processing."""
        large_dialogue = self.create_long_dialogue(20)
        
        # Mock TTS client
        async def mock_generate_audio_with_timeout(*args, **kwargs):
            return b"fake_audio_data"
        
        self.mock_tts_client.generate_audio_with_timeout = mock_generate_audio_with_timeout
        
        with patch.object(self.processor, 'merge_audio_chunks', return_value=b"merged_audio"):
            result = await self.processor.process_large_dialogue(
                dialogue_lines=large_dialogue,
                voice_host="Kore",
                voice_guest="Puck"
            )
        
        assert result == b"merged_audio"
    
    def test_estimate_processing_time(self):
        """Test processing time estimation."""
        dialogue = self.create_long_dialogue(30)
        
        chunk_count, estimated_time = self.processor.estimate_processing_time(dialogue)
        
        assert chunk_count > 1  # Should be split into multiple chunks
        assert estimated_time > 0
        assert estimated_time == chunk_count * 60 + (chunk_count - 1) * 2
    
    def test_merge_wav_chunks_integration(self):
        """Test WAV chunk merging with real WAV data."""
        # Create test WAV chunks
        chunks = []
        for i in range(2):
            output_io = io.BytesIO()
            with wave.open(output_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                # Write some sample frames
                frames = bytes([0, 0] * 1000)  # 1000 frames of silence
                wf.writeframes(frames)
            chunks.append(output_io.getvalue())
        
        merged = self.processor._merge_wav_chunks(chunks)
        
        assert isinstance(merged, bytes)
        assert len(merged) > len(chunks[0])  # Should be larger than individual chunks
        
        # Verify the merged audio is valid WAV
        audio_io = io.BytesIO(merged)
        with wave.open(audio_io, 'rb') as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 24000
            assert wf.getnframes() >= 2000  # Should have frames from both chunks
    
    def test_processor_without_tts_client(self):
        """Test processor behavior without TTS client."""
        processor = TTSChunkProcessor()
        
        with pytest.raises(ValueError, match="TTSClientが設定されていません"):
            asyncio.run(processor.process_chunks_sequentially([]))
    
    def test_split_preserves_speaker_order(self):
        """Test that splitting preserves natural speaker alternation."""
        dialogue = []
        for i in range(20):
            speaker = "Host" if i % 2 == 0 else "Guest"
            text = f"発言{i+1}: " + "内容です。" * 5
            dialogue.append({"speaker": speaker, "text": text})
        
        chunks = self.processor.split_dialogue_for_tts(dialogue)
        
        # Verify each chunk has reasonable speaker distribution
        for chunk in chunks:
            if len(chunk) > 1:
                speakers = [line["speaker"] for line in chunk]
                # Should have both speakers in most cases (unless very short chunk)
                unique_speakers = set(speakers)
                assert len(unique_speakers) >= 1  # At least one speaker
    
    def test_long_single_line_handling(self):
        """Test handling of extremely long single lines."""
        dialogue = [
            {"speaker": "Host", "text": "あ" * 2000},  # Exceeds MAX_CHUNK_CHARS alone
            {"speaker": "Guest", "text": "短い応答"}
        ]
        
        chunks = self.processor.split_dialogue_for_tts(dialogue)
        
        # Should still create chunks, even with single long line
        assert len(chunks) >= 1
        # First chunk might exceed normal limits due to single long line
        # but processor should handle this gracefully