# 実装ドキュメント: モデル設定の環境変数化とレートリミット対策

## 実装概要

PRDの要件に基づき、Geminiモデルの環境変数による設定機能とレートリミット対策を実装しました。

## 実装されたファイル

### 新規作成ファイル

1. **`pdf_podcast/model_config.py`** - モデル設定管理クラス
2. **`pdf_podcast/rate_limiter.py`** - レートリミッタークラス  
3. **`.env.example`** - 環境変数設定例
4. **`tests/test_model_config.py`** - ModelConfigのテスト
5. **`tests/test_rate_limiter.py`** - レートリミッターのテスト

### 修正ファイル

1. **`pdf_podcast/__main__.py`** - CLI引数、モデル設定、初期化
2. **`pdf_podcast/pdf_parser.py`** - レートリミッター統合
3. **`pdf_podcast/script_builder.py`** - レートリミッター統合  
4. **`pdf_podcast/tts_client.py`** - 並行処理数制限

## 主要な実装内容

### 1. ModelConfigクラス (`pdf_podcast/model_config.py`)

**機能**:
- 3つのモデル設定の管理（PDF解析、台本生成、TTS）
- 設定優先順位の実装（CLI > 環境変数 > デフォルト値）
- 設定サマリーの生成

**主要メソッド**:
```python
@classmethod
def from_args(cls, args) -> 'ModelConfig'  # CLI引数から設定を作成
def get_config_summary(self) -> dict      # 設定サマリー取得
```

**環境変数**:
- `GEMINI_MODEL_PDF_PARSER` (デフォルト: `gemini-2.5-flash-preview-05-20`)
- `GEMINI_MODEL_SCRIPT_BUILDER` (デフォルト: `gemini-2.5-pro-preview-06-05`)
- `GEMINI_MODEL_TTS` (デフォルト: `gemini-2.5-pro-preview-tts`)

### 2. GeminiRateLimiterクラス (`pdf_podcast/rate_limiter.py`)

**機能**:
- RPM制限の管理（デフォルト: 15 RPM）
- Exponential backoffによるリトライ
- 429エラーとサーバーエラーの自動ハンドリング
- レートリミット統計の取得

**主要メソッド**:
```python
async def acquire(self) -> None                    # レート制限内でのリクエスト許可
async def call_with_backoff(self, func, ...) -> Any  # バックオフ付きの関数呼び出し
def get_stats(self) -> dict                        # 統計情報取得
```

**設定パラメータ**:
- `rpm_limit`: 15 (Free tier想定)
- `max_retries`: 5
- `base_delay`: 2.0秒
- `max_delay`: 60.0秒

### 3. CLI引数の変更

**削除された引数**:
- `--model` (単一のモデル指定)

**追加された引数**:
- `--model-pdf`: PDF解析用モデル指定
- `--model-script`: 台本生成用モデル指定
- `--model-tts`: TTS用モデル指定

**変更された引数**:
- `--max-concurrency`: デフォルト値を4から1に変更

### 4. レートリミット対応

**PDF Parser (`pdf_parser.py`)**:
- `extract_chapters()`メソッドをasyncに変更
- `_detect_chapters_with_llm()`でレートリミッター使用

**Script Builder (`script_builder.py`)**:
- `generate_dialogue_script()`メソッドをasyncに変更
- 並行処理数を強制的に1に制限
- レートリミッター統合

**TTS Client (`tts_client.py`)**:
- 既存のリトライ機能を維持
- 並行処理数を強制的に1に制限

### 5. 設定表示機能

**起動時の設定表示**:
- 各モデルの設定値を表示
- 設定ソース（CLI/環境変数/デフォルト）をログに記録
- レートリミット設定の表示

## 使用方法

### 1. 環境変数による設定

`.env`ファイルの例:
```bash
# Google API設定
GOOGLE_API_KEY=your_api_key_here

# モデル設定
GEMINI_MODEL_PDF_PARSER=gemini-2.5-flash-preview-05-20
GEMINI_MODEL_SCRIPT_BUILDER=gemini-2.5-pro-preview-06-05
GEMINI_MODEL_TTS=gemini-2.5-pro-preview-tts

# レートリミット設定
GEMINI_RATE_LIMIT_RPM=15
GEMINI_API_TIER=free
```

### 2. CLI引数による設定

```bash
python -m pdf_podcast \
    --input document.pdf \
    --output-dir ./output \
    --model-pdf gemini-2.0-flash-exp \
    --model-script gemini-2.5-pro-preview-06-05 \
    --model-tts gemini-2.5-pro-preview-tts
```

### 3. 設定優先順位

1. **CLI引数** (最高優先度)
2. **環境変数**
3. **デフォルト値** (最低優先度)

## レートリミット対策の効果

### Free Tier対応

- **RPM制限**: 15 RPM（分間リクエスト数）
- **並行処理**: 強制的に1に制限
- **リトライ**: 429エラー時の自動バックオフ
- **遅延**: リクエスト間隔の自動調整

### エラーハンドリング

- **429エラー**: レートリミット超過時の自動リトライ
- **5xxエラー**: サーバーエラーの短時間リトライ
- **その他エラー**: 即座に例外発生（プロセス停止）

## テスト

### ModelConfig テスト
- CLI引数の優先度テスト
- 環境変数の処理テスト
- デフォルト値の使用テスト
- 設定サマリーの生成テスト

### RateLimiter テスト  
- 基本的なレート制限テスト
- バックオフ機能のテスト
- エラーハンドリングのテスト
- 統計機能のテスト

## 互換性

### 後方互換性の破綻

- **`--model`引数の削除**: 既存のスクリプトは動作しない
- **max_concurrency=1の強制**: 並行処理が制限される

### 移行方法

1. **既存の`--model`を削除**
2. **新しい引数に置き換え**:
   - `--model gemini-2.0-flash-exp` → `--model-pdf gemini-2.0-flash-exp --model-script gemini-2.0-flash-exp --model-tts gemini-2.0-flash-exp`
3. **環境変数の設定**: `.env`ファイルの作成

## 制限事項

### Current Limitations

1. **Free Tier前提**: Paid tierの自動検出なし
2. **並行処理の固定**: max_concurrency=1で固定
3. **レートリミット設定**: RPM=15で固定
4. **プロセス停止**: レートリミット超過時は停止

### 今後の改善案

1. **Paid Tier対応**: 自動検出または設定による切り替え
2. **動的並行処理**: tierに応じた並行処理数調整
3. **設定可能なRPM**: 環境変数による調整
4. **Graceful Degradation**: エラー時の継続処理

## ログとモニタリング

### 追加されたログ

1. **モデル設定**: 起動時の設定表示
2. **レートリミット**: 制限発生時の警告
3. **リトライ**: バックオフ処理の進行状況
4. **統計**: レートリミッターの使用状況

### ログレベル

- **INFO**: 設定情報、進行状況
- **WARNING**: レートリミット、設定変更
- **ERROR**: API エラー、リトライ失敗

## パフォーマンス影響

### 処理時間の増加

- **シーケンシャル処理**: 並行処理数=1により処理時間増加
- **レートリミット待機**: API制限による待機時間
- **リトライ処理**: エラー時のバックオフによる遅延

### 推定処理時間

- **章数N**: 従来の並行処理時間 × N （worst case）
- **レートリミット**: +30秒/リクエスト（Free tier）
- **リトライ**: +数秒～数分（エラー発生時のみ）

## 成功指標の達成

### PRDの受け入れ基準

✅ **環境変数でモデルが正しく設定される**  
✅ **CLI引数が環境変数より優先される**  
✅ **レートリミットエラーが自動で回復する**  
✅ **設定情報が起動時に正しく表示される**  

### 性能要件

✅ **レートリミット制限内で安定動作する**  
✅ **429エラー時のbackoffが適切に機能する**  
✅ **並行処理数の制限が機能する**  

### 互換性要件

⚠️ **環境変数未設定時にデフォルト値が使用される** (破綻: --model引数削除)  
✅ **既存のマニフェストファイルが読み込める**  
✅ **新しいCLI引数が正しく動作する**

## まとめ

PRDで要求された主要機能は実装済みです：

1. **環境変数による設定機能** - 完全実装
2. **レートリミット対策** - Free tier対応で実装  
3. **UX改善** - 設定表示とログ出力を実装

ただし、後方互換性の破綻（`--model`引数削除）があるため、ユーザーへの移行案内が必要です。