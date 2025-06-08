# PRD: TTS音声生成の品質向上と安定化

## 概要

現在のTTS音声生成において、長いスクリプトに対して途中で無音になる問題が発生している。6分間のAPI処理時間と22分の最終音声のうち2分以降が無音となる現象を解決し、安定した音声生成を実現する。

## 背景と課題

### 現在の問題

1. **TTS処理の長時間化**
   - API処理時間：約6分（通常は1-2分以内が期待値）
   - 35行の対話処理で約3400文字のスクリプト
   - 最終音声：22分のうち2分以降無音

2. **スクリプト長の問題**
   - 現在の要件：10分（2800-3000文字）
   - 実際の生成：35-44行の対話（3400-3800文字）
   - TTS APIの処理限界を超えている可能性

3. **エラーハンドリング不足**
   - 長時間処理のタイムアウト対策なし
   - 部分的失敗時の検出機能なし
   - ユーザーへの警告表示なし

4. **品質管理の欠如**
   - 生成音声の長さ検証なし
   - 無音部分の検出なし
   - スクリプト適正サイズの事前チェックなし

## 要件

### 機能要件

#### 1. スクリプト長の最適化
- 目標音声長：**3-5分**（従来の10分から短縮）
- 文字数制限：**1500-2000文字**（従来の2800-3000文字から削減）
- 対話行数制限：**最大25行**（警告閾値：20行）

#### 2. TTS処理の改善
- **タイムアウト設定**：3分（180秒）
- **分割処理**：20行を超える場合は自動分割
- **リトライ機能**：失敗時の自動再試行（最大2回）
- **進行状況表示**：長時間処理の進捗可視化

#### 3. 品質検証機能
- **音声長チェック**：期待値との比較（±20%以内）
- **無音検出**：生成音声の無音部分検出
- **完整性検証**：スクリプト行数と音声内容の対応確認

#### 4. エラーハンドリング強化
- **事前チェック**：スクリプト長の適正性判定
- **処理中断検出**：API応答の不完全性検出
- **ユーザー通知**：問題発生時の分かりやすいメッセージ

### 非機能要件

#### 1. パフォーマンス
- TTS処理時間：**3分以内**（従来の6分から半減）
- レスポンス性：進行状況の1秒間隔更新
- メモリ効率：大容量音声データの適切な処理

#### 2. 安定性
- 成功率：**95%以上**（現在は不明、50%程度と推測）
- 部分失敗の検出：**100%**
- エラー復旧率：**80%以上**

#### 3. ユーザビリティ
- 問題の早期検出と通知
- 修正提案の自動表示
- 処理時間の事前予測表示

## 実装計画

### Phase 1: スクリプト最適化
1. プロンプトの要件変更（10分→5分、文字数削減）
2. 生成スクリプトの事前検証機能
3. 長すぎるスクリプトの自動警告

### Phase 2: TTS処理改善
1. タイムアウト設定の実装
2. 分割処理機能の追加
3. リトライ機能の強化

### Phase 3: 品質検証
1. 音声長検証機能の実装
2. 無音検出機能の追加
3. 完整性チェック機能

### Phase 4: UX向上
1. 進行状況表示の改善
2. エラーメッセージの改良
3. 修正提案機能の追加

## 技術詳細

### スクリプト分割処理

```python
class TTSProcessor:
    MAX_LINES_PER_CHUNK = 20
    MAX_CHARS_PER_CHUNK = 2000
    
    def split_dialogue(self, dialogue_lines: List[Dict]) -> List[List[Dict]]:
        """対話を適切なサイズに分割"""
        chunks = []
        current_chunk = []
        current_chars = 0
        
        for line in dialogue_lines:
            line_chars = len(line["text"])
            
            if (len(current_chunk) >= self.MAX_LINES_PER_CHUNK or 
                current_chars + line_chars > self.MAX_CHARS_PER_CHUNK):
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_chars = 0
            
            current_chunk.append(line)
            current_chars += line_chars
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
```

### 音声品質検証

```python
class AudioQualityChecker:
    def verify_audio_quality(self, audio_path: Path, expected_duration: float) -> bool:
        """音声品質を検証"""
        actual_duration = self.get_audio_duration(audio_path)
        
        # 長さの検証（±20%）
        if not (0.8 * expected_duration <= actual_duration <= 1.2 * expected_duration):
            return False
        
        # 無音検出
        if self.detect_silence_ratio(audio_path) > 0.3:  # 30%以上無音
            return False
        
        return True
    
    def detect_silence_ratio(self, audio_path: Path) -> float:
        """無音の割合を検出"""
        # 音声解析ライブラリを使用して無音部分を検出
        pass
```

### タイムアウト処理

```python
async def generate_audio_with_timeout(self, dialogue_lines: List[Dict], timeout: int = 180):
    """タイムアウト付きTTS生成"""
    try:
        audio_data = await asyncio.wait_for(
            self.generate_audio(dialogue_lines),
            timeout=timeout
        )
        return audio_data
    except asyncio.TimeoutError:
        logger.error(f"TTS generation timed out after {timeout}s")
        raise TTSTimeoutError("Audio generation exceeded time limit")
```

## 受け入れ基準

### 機能テスト
1. スクリプト長が1500-2000文字に制限されること
2. 20行を超える対話で警告が表示されること
3. 3分以内にTTS処理が完了すること
4. 生成音声に無音部分がないこと

### 性能テスト
1. TTS処理時間が3分以内であること
2. 成功率が95%以上であること
3. メモリ使用量が適正範囲内であること

### UXテスト
1. 進行状況が適切に表示されること
2. エラー時に分かりやすいメッセージが表示されること
3. 修正提案が適切に提示されること

## リスク要因

### 技術リスク
- **高**: Gemini TTS APIの内部制限変更
- **中**: 分割処理による音声品質の劣化
- **低**: タイムアウト設定による処理中断

### 運用リスク
- **中**: ユーザーの期待値調整（10分→5分）
- **低**: 既存コンテンツの再処理需要

## 成功指標

1. **TTS処理時間**: 平均3分以内（現在6分）
2. **音声品質**: 無音問題発生率5%以下
3. **成功率**: 95%以上の正常完了
4. **ユーザー満足度**: エラー関連問い合わせ50%削減

## 制約条件

1. **API制限**: Gemini TTS APIの仕様内での実装
2. **後方互換性**: 既存のマニフェストファイル形式維持
3. **処理時間**: 全体処理時間の大幅延長は避ける

## スケジュール

- **Week 1**: Phase 1実装（スクリプト最適化）
- **Week 2**: Phase 2実装（TTS処理改善） 
- **Week 3**: Phase 3実装（品質検証）
- **Week 4**: Phase 4実装（UX向上）とテスト