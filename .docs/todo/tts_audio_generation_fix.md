# 実装プラン: TTS音声生成の品質向上と安定化

## 現在の問題分析

### 確認された問題
1. **長時間TTS処理**: 6分のAPI処理時間（正常：1-2分）
2. **不完全な音声**: 22分中2分以降無音
3. **過大なスクリプト**: 35行（3400文字）の対話
4. **検証機能不足**: 音声品質チェックなし

### 根本原因
- **Gemini TTS APIの処理限界**: 35行は処理しきれない
- **タイムアウト未設定**: 長時間処理の中断検出なし
- **品質管理不足**: 生成音声の検証なし

## Phase 1: スクリプト最適化

### 1.1 プロンプト要件の変更
**ファイル**: `pdf_podcast/script_builder.py`

**変更箇所**: `_create_dialogue_prompt()` メソッド
- 10分 → **5分**
- 2800-3000文字 → **1500-2000文字**
- 対話行数の目安追加

**実装済み**: ✅ 完了

### 1.2 スクリプト事前検証機能
**新規機能**: `ScriptValidator` クラス

```python
class ScriptValidator:
    MAX_LINES = 25
    MAX_CHARS = 2000
    WARN_LINES = 20
    
    def validate_script(self, script: DialogueScript) -> ValidationResult:
        """スクリプトの適正性を検証"""
        warnings = []
        errors = []
        
        if len(script.lines) > self.WARN_LINES:
            warnings.append(f"対話行数が多い: {len(script.lines)}行 (推奨: {self.WARN_LINES}行以下)")
        
        if len(script.lines) > self.MAX_LINES:
            errors.append(f"対話行数が上限を超過: {len(script.lines)}行 (上限: {self.MAX_LINES}行)")
        
        if script.total_chars > self.MAX_CHARS:
            errors.append(f"文字数が上限を超過: {script.total_chars}文字 (上限: {self.MAX_CHARS}文字)")
        
        return ValidationResult(warnings=warnings, errors=errors)
```

### 1.3 自動警告システム
**統合箇所**: `ScriptBuilder.generate_dialogue_script()`

## Phase 2: TTS処理改善

### 2.1 タイムアウト設定
**ファイル**: `pdf_podcast/tts_client.py`

**追加メソッド**:
```python
async def generate_audio_with_timeout(
    self,
    dialogue_lines: List[Dict[str, str]], 
    timeout: int = 180  # 3分
) -> bytes:
    """タイムアウト付きTTS生成"""
```

### 2.2 分割処理機能
**新規クラス**: `TTSChunkProcessor`

```python
class TTSChunkProcessor:
    def split_dialogue_for_tts(self, dialogue_lines: List[Dict]) -> List[List[Dict]]:
        """TTS用に対話を分割"""
        
    async def process_chunks_sequentially(self, chunks: List[List[Dict]]) -> List[bytes]:
        """分割された音声を順次処理"""
        
    def merge_audio_chunks(self, audio_chunks: List[bytes]) -> bytes:
        """分割音声をマージ"""
```

### 2.3 リトライ機能強化
**拡張**: 既存の `generate_audio_with_retry()` メソッド
- タイムアウトエラーの処理追加
- 分割処理の自動フォールバック

## Phase 3: 品質検証

### 3.1 音声品質チェッカー
**新規クラス**: `AudioQualityChecker`

```python
class AudioQualityChecker:
    def verify_duration(self, audio_path: Path, expected_duration: float) -> bool:
        """音声長の検証"""
        
    def detect_silence_ratio(self, audio_path: Path) -> float:
        """無音割合の検出"""
        
    def check_audio_integrity(self, audio_path: Path) -> bool:
        """音声ファイルの完整性チェック"""
```

### 3.2 検証の統合
**統合箇所**: 
- `TTSClient.generate_audio()` - 生成後の即座検証
- `PodcastGenerator._generate_audio()` - 全体検証

### 3.3 必要なライブラリ
**追加依存関係**:
```python
# requirements.txtに追加
librosa>=0.10.0  # 音声解析
soundfile>=0.12.0  # 音声ファイル操作
```

## Phase 4: UX向上

### 4.1 進行状況表示の改善
**拡張**: `LoggingSystem` クラス
- TTS処理の詳細進捗表示
- 推定残り時間の計算

### 4.2 エラーメッセージの改良
**改善箇所**: 
- `TTSClient` - 具体的なエラー原因表示
- `ScriptBuilder` - 修正提案の自動生成

### 4.3 修正提案機能
**新規機能**: `FixSuggestionGenerator`

```python
class FixSuggestionGenerator:
    def suggest_script_fixes(self, validation_result: ValidationResult) -> List[str]:
        """スクリプト修正提案を生成"""
        
    def suggest_tts_alternatives(self, error_type: str) -> List[str]:
        """TTS代替手段を提案"""
```

## 実装の優先順位と詳細手順

### Step 1: 即効性のある修正（High Priority）
1. **スクリプト長制限** ✅ 実装済み
2. **基本的な警告追加**
3. **タイムアウト設定**

### Step 2: 安定性向上（High Priority）
1. **音声長検証**
2. **分割処理**
3. **エラーハンドリング強化**

### Step 3: 品質管理（Medium Priority）  
1. **無音検出**
2. **完整性チェック**
3. **リトライ機能拡張**

### Step 4: UX改善（Low Priority）
1. **進行状況表示**
2. **修正提案**
3. **詳細ログ**

## ファイル変更一覧

### 既存ファイルの修正
- `pdf_podcast/script_builder.py` - プロンプト修正、検証追加
- `pdf_podcast/tts_client.py` - タイムアウト、分割処理
- `pdf_podcast/__main__.py` - 品質チェック統合
- `requirements.txt` - 新規依存関係追加

### 新規ファイル作成
- `pdf_podcast/script_validator.py` - スクリプト検証
- `pdf_podcast/audio_quality_checker.py` - 音声品質チェック
- `pdf_podcast/tts_chunk_processor.py` - 分割処理
- `pdf_podcast/fix_suggestion.py` - 修正提案

### テストファイル
- `tests/test_script_validator.py`
- `tests/test_audio_quality_checker.py`
- `tests/test_tts_chunk_processor.py`

## 検証計画

### Step 1: 短縮スクリプトのテスト
```bash
python -m pdf_podcast --input test/test.pdf --output-dir ./test_short
```
**期待結果**: 
- スクリプト行数: 20行以下
- TTS処理時間: 3分以内
- 音声長: 5分程度、無音なし

### Step 2: 長いコンテンツでの分割テスト
**テストケース**: 意図的に長いスクリプトを生成
**期待結果**: 自動分割と警告表示

### Step 3: エラー処理のテスト
**テストケース**: ネットワーク遅延、API制限のシミュレート
**期待結果**: 適切なエラーメッセージと復旧提案

## リスク管理

### 技術リスク
1. **音声品質劣化**: 分割処理による境界部分の不自然さ
   - **対策**: 自然な分割点の検出（文の終わり）
   
2. **処理時間増加**: 品質チェックによるオーバーヘッド
   - **対策**: 軽量な検証アルゴリズム

3. **依存関係増加**: 新しいライブラリの追加
   - **対策**: オプション機能として実装

### 運用リスク
1. **既存ユーザーの混乱**: 音声長の変更
   - **対策**: 段階的移行とドキュメント整備

## 成功基準

### 定量的指標
- TTS処理時間: **3分以内** (現在6分)
- 無音問題発生率: **5%以下** (現在100%)
- 成功率: **95%以上** (現在推定50%)

### 定性的指標
- ユーザーからのエラー報告減少
- 音声品質の一貫性向上
- 処理の予測可能性向上

この実装プランにより、TTS音声生成の安定性と品質を大幅に改善できる見込みです。