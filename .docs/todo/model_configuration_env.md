# 実装プラン: モデル設定の環境変数化とレートリミット対策

## 現在のコード分析結果

### 問題点の確認

1. **CLI引数の不整合**:
   - `__main__.py:456行目`: 単一の`--model`引数（デフォルト: `gemini-2.0-flash-exp`）
   - 実際の各クラスのデフォルト値と異なる

2. **クラス別デフォルト値**:
   - `PDFParser:28行目`: `gemini-2.5-flash-preview-05-20`
   - `ScriptBuilder:24行目`: `gemini-2.5-pro-preview-06-05`
   - `TTSClient:27行目`: `gemini-2.5-pro-preview-tts`

3. **現在の初期化パターン**:
   - `__main__.py:153行目`: `PDFParser(self.args.input, self.args.model, self.api_key)`
   - `__main__.py:231行目`: `ScriptBuilder(self.api_key, self.args.model)`
   - `__main__.py:285行目`: `TTSClient(self.api_key, tts_model)` (ハードコード)

4. **環境変数サポート**: なし
5. **レートリミット対策**: TTSClientに部分的にあり、他は未実装

## Phase 1: 環境変数設定機能

### 1.1 環境変数設定ファイルの更新
- `.env`ファイルに新しい環境変数追加
- デフォルト値をPRDに合わせて定義

### 1.2 CLI引数の拡張
- `__main__.py`の`create_parser()`を修正:
  - `--model` → 3つの個別引数に分割
  - `--model-pdf` (デフォルト: 環境変数またはクラス内デフォルト)
  - `--model-script` (デフォルト: 環境変数またはクラス内デフォルト)
  - `--model-tts` (デフォルト: 環境変数またはクラス内デフォルト)

### 1.3 モデル設定管理クラスの作成
- `pdf_podcast/model_config.py`を新規作成
- 設定優先順位の実装:
  1. CLI引数
  2. 環境変数
  3. クラス内デフォルト値
- 設定値の検証機能

### 1.4 各クラスの初期化パラメータ修正
- `PDFParser.__init__()`：モデル引数の受け取り方を統一
- `ScriptBuilder.__init__()`：同様に修正
- `TTSClient.__init__()`：同様に修正
- `PodcastGenerator.__init__()`：設定管理クラスの利用

### 1.5 設定表示機能の追加
- `PodcastGenerator._print_configuration()`を拡張
- 各モデルの設定値を表示

## Phase 2: レートリミット対策

### 2.1 レートリミッタークラスの実装
- `pdf_podcast/rate_limiter.py`を新規作成
- `GeminiRateLimiter`クラス:
  - RPM制限管理
  - Exponential backoff
  - 429エラーハンドリング
  - 並行処理数の動的調整

### 2.2 各クラスへのレートリミット統合
- `PDFParser`：API呼び出し前にレートリミッター適用
- `ScriptBuilder`：非同期処理でのレートリミッター統合
- `TTSClient`：既存のリトライ機能をレートリミッターに統合

### 2.3 並行処理の最適化
- デフォルトの`max_concurrency`を調整
- Free tier/Paid tierの自動判定またはユーザー設定
- 動的な並行処理数調整

## Phase 3: ログとUX改善

### 3.1 ログ出力の拡張
- レートリミット状況の詳細ログ
- 設定情報の起動時ログ
- 進行状況でのレートリミット待機表示

### 3.2 エラーハンドリングの改善
- レートリミットエラーの分かりやすいメッセージ
- 部分的処理完了状態の保持・復旧

### 3.3 UX向上
- レートリミット待機時の進行状況表示
- 設定ミスの検出と警告

## 実装の詳細ステップ

### Step 1.1: 環境変数の定義
```bash
# .envファイルに追加
GEMINI_MODEL_PDF_PARSER=gemini-2.5-flash-preview-05-20
GEMINI_MODEL_SCRIPT_BUILDER=gemini-2.5-pro-preview-06-05
GEMINI_MODEL_TTS=gemini-2.5-pro-preview-tts
GEMINI_RATE_LIMIT_RPM=15
GEMINI_API_TIER=free
```

### Step 1.2: ModelConfigクラスの設計
```python
class ModelConfig:
    def __init__(self, cli_args):
        # 優先順位に従って設定を決定
        self.pdf_model = self._resolve_model('pdf', cli_args.model_pdf)
        self.script_model = self._resolve_model('script', cli_args.model_script)
        self.tts_model = self._resolve_model('tts', cli_args.model_tts)
    
    def _resolve_model(self, model_type, cli_value):
        # 1. CLI引数 > 2. 環境変数 > 3. デフォルト値
```

### Step 1.3: CLI引数の更新
```python
# __main__.py内のcreate_parser()に追加
parser.add_argument("--model-pdf", help="PDF解析用モデル")
parser.add_argument("--model-script", help="台本生成用モデル")  
parser.add_argument("--model-tts", help="TTS用モデル")
```

### Step 2.1: レートリミッタークラス
```python
class GeminiRateLimiter:
    def __init__(self, rpm_limit=15):
        self.rpm_limit = rpm_limit
        self.request_times = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        # RPM制限内でのリクエスト許可
    
    async def backoff_retry(self, func, max_retries=5):
        # Exponential backoffでのリトライ
```

## ファイル変更一覧

### 新規作成
- `pdf_podcast/model_config.py` - モデル設定管理クラス
- `pdf_podcast/rate_limiter.py` - レートリミッタークラス

### 修正ファイル
- `pdf_podcast/__main__.py` - CLI引数、初期化、設定表示
- `pdf_podcast/pdf_parser.py` - 初期化とレートリミット対応
- `pdf_podcast/script_builder.py` - 初期化とレートリミット対応
- `pdf_podcast/tts_client.py` - レートリミッター統合
- `.env` - 新しい環境変数追加

### テストファイル
- `tests/test_model_config.py` - ModelConfigクラスのテスト
- `tests/test_rate_limiter.py` - レートリミッタークラスのテスト
- 既存テストファイルの更新

## 不明点・確認事項

1. **後方互換性**: 既存の`--model`引数を残すか？削除するか？
2. **レートリミット設定**: ユーザーがFree/Paid tierを手動設定するか、自動検出を試みるか？
3. **並行処理数**: Free tierでmax_concurrency=1に強制するか、ユーザー設定を尊重するか？
4. **エラー時の挙動**: レートリミット超過時にプロセス停止するか、警告のみで続行するか？

## リスク・注意点

1. **API仕様変更リスク**: Gemini APIのレートリミット仕様が変更される可能性
2. **設定複雑化**: 3つのモデル設定でユーザーの混乱を招く可能性  
3. **既存ワークフローへの影響**: CLIインターフェースの変更による既存ユーザーへの影響

## 成功基準

- [ ] 環境変数でモデルが正しく設定される
- [ ] CLI引数が環境変数より優先される  
- [ ] レートリミットエラーが自動で回復する
- [ ] 設定情報が起動時に正しく表示される
- [ ] 既存の機能が正常に動作する
- [ ] テストが全て通る