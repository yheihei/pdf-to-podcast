# PRD: モデル設定の環境変数化とレートリミット対策

## 概要

現在、PDF解析と台本生成で使用するGeminiモデルがCLI引数でしか変更できず、デフォルト値もクラス間で不統一になっている。また、Gemini APIのレートリミットによる制限が発生する可能性がある。これらの問題を解決するため、モデル設定を環境変数で制御可能にし、レートリミット対策を実装する。

## 背景と課題

### 現在の問題
1. **モデル設定の不整合**
   - CLI引数デフォルト: `gemini-2.0-flash-exp`
   - PDFParserクラス内デフォルト: `gemini-2.5-flash-preview-05-20`
   - ScriptBuilderクラス内デフォルト: `gemini-2.5-pro-preview-06-05`
   - CLI引数が優先されるため、各クラスの適切なデフォルト値が使われない

2. **設定の柔軟性不足**
   - 環境変数でモデルを設定できない
   - 用途別（PDF解析/台本生成）に異なるモデルを指定できない

3. **レートリミットの問題**
   - Gemini API の制限: Free tier は 2-15 RPM、Paid tier は 360 RPM
   - 同時実行時に429エラー（quota exceeded）が発生する可能性
   - 現在のmax_concurrency=4でもレートリミットに抵触する恐れ

## 要件

### 機能要件

#### 1. 環境変数による設定
- `GEMINI_MODEL_PDF_PARSER`: PDF解析用モデル（デフォルト: `gemini-2.5-flash-preview-05-20`）
- `GEMINI_MODEL_SCRIPT_BUILDER`: 台本生成用モデル（デフォルト: `gemini-2.5-pro-preview-06-05`）
- `GEMINI_MODEL_TTS`: TTS用モデル（デフォルト: `gemini-2.5-pro-preview-tts`）

#### 2. 設定優先順位
1. CLI引数（`--model-pdf`、`--model-script`、`--model-tts`）
2. 環境変数
3. クラス内デフォルト値

#### 3. レートリミット対策
- APIリクエスト間隔の自動調整
- Exponential backoffによるリトライ機能
- 429エラー時の自動待機・再試行
- レートリミット対応ログ出力

### 非機能要件

#### 1. 後方互換性
- 環境変数が未設定の場合は各クラスのデフォルト値を使用
- 既存のマニフェストファイルとの互換性を保持

#### 2. ユーザビリティ
- 設定内容を起動時に表示
- レートリミット発生時の分かりやすいメッセージ
- 進行状況に影響するレートリミット待機の表示

#### 3. 安定性
- レートリミットエラーによるプロセス停止の回避
- 部分的な処理完了状態の保持

## 実装計画

### Phase 1: 環境変数設定機能
1. `.env`ファイルへの新しい環境変数追加
2. CLI引数に新しいモデル指定オプション追加
3. 各クラス（PDFParser、ScriptBuilder、TTSClient）の初期化パラメータ修正
4. 設定優先順位の実装

### Phase 2: レートリミット対策
1. レートリミッター クラスの実装
2. Exponential backoff機能の追加
3. 429エラーハンドリングの統一化
4. 並行処理数の動的調整機能

### Phase 3: ログとUX改善
1. 設定情報の起動時表示
2. レートリミット状況のログ出力
3. 進行状況表示の改善
4. エラーメッセージの多言語化

## 技術詳細

### レートリミット対策の実装

#### 1. Rate Limiter クラス
```python
class GeminiRateLimiter:
    def __init__(self, rpm_limit: int = 15):
        self.rpm_limit = rpm_limit
        self.request_times = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        # RPM制限内でのリクエスト許可
        pass
    
    async def backoff_retry(self, func, max_retries: int = 5):
        # Exponential backoffでのリトライ
        pass
```

#### 2. エラーハンドリング強化
- 429エラーの検出と自動リトライ
- API応答時間の監視
- レート制限情報の抽出と活用

#### 3. 並行処理の最適化
- free tier: max_concurrency を 1-2 に制限
- paid tier: max_concurrency を動的に調整
- tier の自動検出またはユーザー設定

### 設定ファイルの更新

#### `.env` ファイル例
```env
# Google API設定
GOOGLE_API_KEY=your_api_key_here

# モデル設定
GEMINI_MODEL_PDF_PARSER=gemini-2.5-flash-preview-05-20
GEMINI_MODEL_SCRIPT_BUILDER=gemini-2.5-pro-preview-06-05
GEMINI_MODEL_TTS=gemini-2.5-pro-preview-tts

# レートリミット設定
GEMINI_RATE_LIMIT_RPM=15
GEMINI_API_TIER=free  # free または paid
```

## 受け入れ基準

### 機能テスト
1. 環境変数でモデルが正しく設定されること
2. CLI引数が環境変数より優先されること
3. レートリミットエラーが自動で回復すること
4. 設定情報が起動時に正しく表示されること

### 性能テスト
1. レートリミット制限内で安定動作すること
2. 429エラー時のbackoffが適切に機能すること
3. 並行処理数の動的調整が機能すること

### 互換性テスト
1. 環境変数未設定時にデフォルト値が使用されること
2. 既存のマニフェストファイルが読み込めること
3. 新しいCLI引数が正しく動作すること

## リスク要因

### 技術リスク
- **高**: Gemini APIの仕様変更によるレートリミット制限の変化
- **中**: 新しいモデル名の互換性問題
- **低**: Exponential backoffの実装複雑性

### 運用リスク
- **中**: ユーザーによる不適切なレートリミット設定
- **低**: 環境変数設定の誤り

## 成功指標

1. **レートリミットエラーの削減**: 429エラーの発生率を90%以上削減
2. **設定の柔軟性向上**: 用途別モデル指定の利用率向上
3. **ユーザー体験の改善**: レートリミット関連の問い合わせ削減
4. **処理安定性の向上**: プロセス途中停止の発生率削減

## スケジュール

- **Week 1**: Phase 1 実装（環境変数設定機能）
- **Week 2**: Phase 2 実装（レートリミット対策）
- **Week 3**: Phase 3 実装（ログとUX改善）
- **Week 4**: テスト・デバッグ・ドキュメント更新