"""TTS chunk processor module for handling large dialogue scripts."""

import asyncio
import logging
import io
import wave
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Import audio processing libraries with graceful fallbacks
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPyが利用できません。音声マージ機能が制限されます。")


class TTSChunkProcessor:
    """Processes large dialogue scripts by splitting and merging TTS audio."""
    
    # Chunking parameters based on TTS API limits
    MAX_CHUNK_LINES = 15      # 1チャンクあたりの最大行数
    MAX_CHUNK_CHARS = 1200    # 1チャンクあたりの最大文字数
    PREFERRED_CHUNK_LINES = 12 # 推奨行数
    PREFERRED_CHUNK_CHARS = 1000 # 推奨文字数
    
    def __init__(self, tts_client=None):
        """Initialize TTSChunkProcessor.
        
        Args:
            tts_client: TTSClient instance for audio generation
        """
        self.tts_client = tts_client
    
    def split_dialogue_for_tts(self, dialogue_lines: List[Dict[str, str]]) -> List[List[Dict[str, str]]]:
        """TTS用に対話を分割
        
        長いスクリプトを適切なサイズのチャンクに分割し、
        自然な分割点を見つけて音声品質を保つ。
        
        Args:
            dialogue_lines: 対話行のリスト
            
        Returns:
            分割されたチャンクのリスト
        """
        if len(dialogue_lines) <= self.PREFERRED_CHUNK_LINES:
            total_chars = sum(len(line["text"]) for line in dialogue_lines)
            if total_chars <= self.PREFERRED_CHUNK_CHARS:
                logger.info(f"分割不要: {len(dialogue_lines)}行, {total_chars}文字")
                return [dialogue_lines]
        
        chunks = []
        current_chunk = []
        current_chars = 0
        
        for i, line in enumerate(dialogue_lines):
            line_chars = len(line["text"])
            
            # チャンクサイズをチェック
            will_exceed_lines = len(current_chunk) + 1 > self.MAX_CHUNK_LINES
            will_exceed_chars = current_chars + line_chars > self.MAX_CHUNK_CHARS
            
            # 分割判定
            if current_chunk and (will_exceed_lines or will_exceed_chars):
                # 自然な分割点を探す
                split_point = self._find_natural_split_point(current_chunk, dialogue_lines, i)
                
                if split_point != len(current_chunk):
                    # より適切な分割点が見つかった場合
                    final_chunk = current_chunk[:split_point]
                    remaining_lines = current_chunk[split_point:]
                    
                    if final_chunk:
                        chunks.append(final_chunk)
                        logger.info(f"チャンク作成: {len(final_chunk)}行, {sum(len(l['text']) for l in final_chunk)}文字")
                    
                    # 残りの行から新しいチャンクを開始
                    current_chunk = remaining_lines + [line]
                    current_chars = sum(len(l["text"]) for l in current_chunk)
                else:
                    # 現在のチャンクを確定
                    chunks.append(current_chunk)
                    logger.info(f"チャンク作成: {len(current_chunk)}行, {current_chars}文字")
                    current_chunk = [line]
                    current_chars = line_chars
            else:
                # 現在のチャンクに追加
                current_chunk.append(line)
                current_chars += line_chars
        
        # 最後のチャンクを追加
        if current_chunk:
            chunks.append(current_chunk)
            logger.info(f"最終チャンク: {len(current_chunk)}行, {current_chars}文字")
        
        logger.info(f"分割完了: {len(dialogue_lines)}行 → {len(chunks)}チャンク")
        return chunks
    
    def _find_natural_split_point(
        self, 
        current_chunk: List[Dict[str, str]], 
        all_lines: List[Dict[str, str]], 
        next_index: int
    ) -> int:
        """自然な分割点を探す
        
        Args:
            current_chunk: 現在のチャンク
            all_lines: 全対話行
            next_index: 次に追加する行のインデックス
            
        Returns:
            最適な分割点のインデックス
        """
        # 話者の変わり目を優先
        best_split = len(current_chunk)
        
        # 後半の発言を確認（最後の数行）
        check_range = min(5, len(current_chunk))
        for i in range(len(current_chunk) - check_range, len(current_chunk)):
            if i <= 0:
                continue
                
            current_speaker = current_chunk[i]["speaker"]
            prev_speaker = current_chunk[i-1]["speaker"]
            
            # 話者が変わる点
            if current_speaker != prev_speaker:
                # 文が終わる形（句点、感嘆符など）で終わっているかチェック
                prev_text = current_chunk[i-1]["text"].strip()
                if self._is_natural_ending(prev_text):
                    best_split = i
                    logger.debug(f"自然な分割点を発見: {i}行目 (話者変更 + 文終了)")
                    break
        
        return best_split
    
    def _is_natural_ending(self, text: str) -> bool:
        """テキストが自然な終わり方をしているかチェック
        
        Args:
            text: チェック対象のテキスト
            
        Returns:
            自然な終わり方かどうか
        """
        natural_endings = ["。", "！", "？", ".", "!", "?", "ですね", "ですが", "ました", "ます"]
        return any(text.endswith(ending) for ending in natural_endings)
    
    async def process_chunks_sequentially(
        self, 
        chunks: List[List[Dict[str, str]]],
        voice_host: str = "Kore",
        voice_guest: str = "Puck",
        timeout: int = 180
    ) -> List[bytes]:
        """分割された音声を順次処理
        
        Args:
            chunks: 分割されたチャンクのリスト
            voice_host: ホストの音声
            voice_guest: ゲストの音声
            timeout: 各チャンクのタイムアウト時間
            
        Returns:
            生成された音声データのリスト
        """
        if not self.tts_client:
            raise ValueError("TTSClientが設定されていません")
        
        audio_chunks = []
        
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"チャンク {i}/{len(chunks)} を処理中... ({len(chunk)}行)")
            
            try:
                # チャンクの音声生成
                audio_data = await self.tts_client.generate_audio_with_timeout(
                    dialogue_lines=chunk,
                    timeout=timeout,
                    voice_host=voice_host,
                    voice_guest=voice_guest
                )
                
                audio_chunks.append(audio_data)
                logger.info(f"チャンク {i} 完了: {len(audio_data)} bytes")
                
                # 連続リクエスト制限のため小休止
                if i < len(chunks):
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"チャンク {i} の処理に失敗: {e}")
                # 失敗したチャンクは無音データで代替
                silence_data = self._create_silence_chunk(duration=1.0)
                audio_chunks.append(silence_data)
                logger.warning(f"チャンク {i} を無音で代替しました")
        
        logger.info(f"全チャンク処理完了: {len(audio_chunks)}個")
        return audio_chunks
    
    def merge_audio_chunks(self, audio_chunks: List[bytes]) -> bytes:
        """分割音声をマージ
        
        Args:
            audio_chunks: 音声データのリスト
            
        Returns:
            マージされた音声データ
        """
        if not audio_chunks:
            logger.warning("マージする音声チャンクがありません")
            return b""
        
        if len(audio_chunks) == 1:
            logger.info("チャンクが1つのため、マージ処理をスキップ")
            return audio_chunks[0]
        
        try:
            # WAVフォーマットの場合のマージ処理
            merged_audio = self._merge_wav_chunks(audio_chunks)
            logger.info(f"音声マージ完了: {len(merged_audio)} bytes")
            return merged_audio
            
        except Exception as e:
            logger.error(f"音声マージに失敗: {e}")
            # フォールバック: 単純な結合
            return b"".join(audio_chunks)
    
    def _merge_wav_chunks(self, audio_chunks: List[bytes]) -> bytes:
        """WAV音声チャンクをマージ
        
        Args:
            audio_chunks: WAV音声データのリスト
            
        Returns:
            マージされたWAV音声データ
        """
        if not NUMPY_AVAILABLE:
            logger.warning("NumPyが利用できないため、簡易マージを実行")
            return b"".join(audio_chunks)
        
        merged_frames = []
        sample_rate = None
        channels = None
        sample_width = None
        
        for i, chunk_data in enumerate(audio_chunks):
            try:
                # WAVデータをメモリ上で読み込み
                audio_io = io.BytesIO(chunk_data)
                with wave.open(audio_io, 'rb') as wf:
                    if sample_rate is None:
                        sample_rate = wf.getframerate()
                        channels = wf.getnchannels()
                        sample_width = wf.getsampwidth()
                    
                    # フォーマットの整合性チェック
                    if (wf.getframerate() != sample_rate or 
                        wf.getnchannels() != channels or 
                        wf.getsampwidth() != sample_width):
                        logger.warning(f"チャンク {i+1} の音声フォーマットが異なります")
                    
                    # フレームデータを読み込み
                    frames = wf.readframes(wf.getnframes())
                    merged_frames.append(frames)
                    
            except Exception as e:
                logger.error(f"チャンク {i+1} の読み込みに失敗: {e}")
                continue
        
        if not merged_frames:
            logger.error("有効な音声チャンクがありません")
            return b""
        
        # マージされた音声データを作成
        merged_data = b"".join(merged_frames)
        
        # 新しいWAVファイルを作成
        output_io = io.BytesIO()
        with wave.open(output_io, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(merged_data)
        
        return output_io.getvalue()
    
    def _create_silence_chunk(self, duration: float = 1.0) -> bytes:
        """無音チャンクを作成
        
        Args:
            duration: 無音の長さ（秒）
            
        Returns:
            無音の音声データ
        """
        sample_rate = 24000
        channels = 1
        sample_width = 2
        
        # 無音フレームを生成
        num_frames = int(duration * sample_rate)
        silence_frames = b'\x00' * (num_frames * channels * sample_width)
        
        # WAVファイルとして出力
        output_io = io.BytesIO()
        with wave.open(output_io, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(silence_frames)
        
        return output_io.getvalue()
    
    async def process_large_dialogue(
        self,
        dialogue_lines: List[Dict[str, str]],
        voice_host: str = "Kore",
        voice_guest: str = "Puck",
        output_path: Optional[Path] = None,
        timeout: int = 180
    ) -> bytes:
        """大きな対話スクリプトを分割処理
        
        Args:
            dialogue_lines: 対話行のリスト
            voice_host: ホストの音声
            voice_guest: ゲストの音声
            output_path: 出力パス
            timeout: 各チャンクのタイムアウト時間
            
        Returns:
            マージされた音声データ
        """
        logger.info(f"大規模対話処理を開始: {len(dialogue_lines)}行")
        
        # スクリプトを分割
        chunks = self.split_dialogue_for_tts(dialogue_lines)
        
        # 各チャンクを順次処理
        audio_chunks = await self.process_chunks_sequentially(
            chunks=chunks,
            voice_host=voice_host,
            voice_guest=voice_guest,
            timeout=timeout
        )
        
        # 音声をマージ
        merged_audio = self.merge_audio_chunks(audio_chunks)
        
        # ファイルに保存
        if output_path and merged_audio:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(merged_audio)
            logger.info(f"マージされた音声を保存: {output_path}")
        
        return merged_audio
    
    def estimate_processing_time(self, dialogue_lines: List[Dict[str, str]]) -> Tuple[int, int]:
        """処理時間を推定
        
        Args:
            dialogue_lines: 対話行のリスト
            
        Returns:
            (推定チャンク数, 推定処理時間(秒))
        """
        chunks = self.split_dialogue_for_tts(dialogue_lines)
        chunk_count = len(chunks)
        
        # 1チャンクあたり約60秒 + チャンク間の待機時間
        estimated_time = chunk_count * 60 + (chunk_count - 1) * 2
        
        return chunk_count, estimated_time