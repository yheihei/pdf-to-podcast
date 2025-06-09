# PDF Podcast Generator

PDFドキュメントをオンライン講義形式の音声コンテンツに変換するツールです。

## 概要

PDF Podcast Generatorは、PDFファイルから章を抽出し、AIを使用して講義形式のスクリプトを生成し、自然な音声に変換します。生成された音声は、講師が視聴者に向けて説明するオンライン講義のような形式になります。

## 特徴

- 📚 PDFから自動的に章を抽出
- 🎓 講義形式のスクリプト生成（導入・本論・まとめの構造）
- 🎙️ 高品質な音声合成（Gemini TTS使用）
- 📊 進捗管理とマニフェスト機能
- 🎵 BGM付き音声生成のサポート
- 📝 チャプター情報付きMP3ファイル生成
- 🗜️ 音声ファイルサイズ最適化（最大70%削減）
- 📄 **NEW** PDFページ番号オフセット対応（前付け対応）

## 必要要件

- Python 3.8以上
- Google API Key（Gemini API用）
- ffmpeg（音声処理用）

## インストール

```bash
# リポジトリのクローン
git clone https://github.com/yourusername/pdf-podcast.git
cd pdf-podcast

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数の設定
# .env.exampleをコピーして.envファイルを作成
cp .env.example .env

# .envファイルを編集してAPIキーを設定
# お好みのエディタで.envを開き、以下の値を設定してください：
#   GOOGLE_API_KEY=your_actual_api_key_here
# 
# 必要に応じて、他の設定も変更できます：
#   GEMINI_MODEL_PDF_PARSER: PDF解析用モデル
#   GEMINI_MODEL_SCRIPT_BUILDER: スクリプト生成用モデル  
#   GEMINI_MODEL_TTS: 音声合成用モデル
```

## 使い方

### 基本的な使い方

```bash
# 新規PDF処理
python -m pdf_podcast --input document.pdf --output-dir ./output
```

### Scripts-to-Audio機能（新機能）

音声生成が途中で止まった場合や、既存のスクリプトから音声のみを再生成したい場合に使用：

```bash
# 既存スクリプトから音声のみ生成
python -m pdf_podcast --scripts-to-audio ./output/scripts/document

# 相対パスでも指定可能
python -m pdf_podcast --scripts-to-audio scripts/document

# 出力先を指定（オプション）
python -m pdf_podcast --scripts-to-audio ./scripts/document --output-dir ./output
```

**特徴:**
- PDF解析とスクリプト生成をスキップして高速処理
- 既存の音声ファイルを自動でスキップ
- レート制限エラー時の再開が簡単
- 429エラー発生時に適切な再開コマンドを表示

### 詳細なオプション

```bash
python -m pdf_podcast \
  --input document.pdf \
  --output-dir ./output \
  --voice Kore \
  --quality standard \
  --bgm background_music.mp3 \
  --skip-existing
```

### 音声品質設定

ファイルサイズと音質のバランスを調整できます：

```bash
# 標準品質（推奨、70%サイズ削減）
python -m pdf_podcast --input document.pdf --output-dir ./output --quality standard

# 高品質（従来品質、大きなファイルサイズ）
python -m pdf_podcast --input document.pdf --output-dir ./output --quality high

# コンパクト（最大圧縮、80%サイズ削減）
python -m pdf_podcast --input document.pdf --output-dir ./output --quality compact
```

### PDFページ番号オフセット対応（新機能）

前付け（序文、目次など）があるPDFでも正しい内容を抽出できます：

```bash
# 自動オフセット検出（推奨）
python -m pdf_podcast --input document.pdf --output-dir ./output

# 手動オフセット指定（前付けが5ページの場合）
python -m pdf_podcast --input document.pdf --output-dir ./output --page-offset 5
```

**前付け対応の特徴:**
- PDFから自動的にページ番号オフセットを検出
- 手動オフセット指定によるフォールバック機能
- 既存PDFとの完全な互換性
- 論理ページ番号と物理ページ番号の自動変換

### コマンドラインオプション

| オプション | 説明 | デフォルト |
|------------|------|------------|
| `--input` | 入力PDFファイルのパス | 通常モードで必須 |
| `--output-dir` | 出力ディレクトリ | 通常モードで必須 |
| `--scripts-to-audio` | スクリプトディレクトリから音声のみ生成 | なし |
| `--voice` | 講師の音声 | Kore |
| `--quality` | 音声品質プリセット（high/standard/compact） | standard |
| `--bitrate` | 音声のビットレート（qualityより優先） | 128k |
| `--bgm` | BGM音楽ファイルのパス | なし |
| `--max-concurrency` | 最大同時実行数 | 1 |
| `--skip-existing` | 既存ファイルをスキップ | False |
| `--model-pdf` | PDF解析用のGeminiモデル | gemini-2.5-flash-preview-05-20 |
| `--model-script` | スクリプト生成用のGeminiモデル | gemini-2.5-pro-preview-06-05 |
| `--model-tts` | 音声合成用のGeminiモデル | gemini-2.5-pro-preview-tts |
| `--page-offset` | 手動ページオフセット指定 | 自動検出 |
| `--verbose` | 詳細なログ出力 | False |

#### 音声品質プリセット詳細

| 品質設定 | ビットレート | サンプルレート | チャンネル | ファイルサイズ | 用途 |
|----------|-------------|---------------|-----------|------------|------|
| `high` | 320kbps | 24kHz | ステレオ | 大（従来サイズ） | 最高音質が必要な場合 |
| `standard` | 128kbps | 22.05kHz | モノラル | 小（70%削減） | **推奨**：音声コンテンツに最適 |
| `compact` | 96kbps | 16kHz | モノラル | 最小（80%削減） | ストレージ節約が最優先 |

## 出力ファイル

実行後、以下のファイルが生成されます：

```
output/
├── episode.mp3          # 最終的なポッドキャストファイル
├── manifest.json        # 処理の進捗情報
├── scripts/            # 生成された講義スクリプト
│   └── filename/       # PDFファイル名ベースのディレクトリ
│       ├── chapter1.txt
│       └── chapter2.txt
├── audio/              # 章ごとの音声ファイル
│   └── filename/       # PDFファイル名ベースのディレクトリ
│       ├── 01_chapter1.mp3
│       └── 02_chapter2.mp3
└── logs/               # ログファイル
```

**注意**: ディレクトリ名は入力PDFファイル名（拡張子なし）から生成されます。同名のファイルが複数回処理される場合は、自動的に連番が付与されます（例：`document`, `document_2`, `document_3`）。

## 講義形式について

生成されるコンテンツは以下の特徴を持ちます：

- **構造化された内容**: 導入、本論、まとめの明確な構造
- **視聴者への語りかけ**: 「みなさん」「〜ですね」などの親しみやすい表現
- **適切な長さ**: 各章5分程度（1500〜2000文字）で聴きやすい
- **専門用語の説明**: 難しい用語には適切な説明を追加

## 制限事項

- Gemini APIの無料枠では、1分間に2リクエストまでの制限があります
- 大きなPDFファイルの処理には時間がかかる場合があります
- 生成される音声ファイルは実際にはWAV形式ですが、互換性のため.mp3拡張子で保存されます
- ページ番号オフセット自動検出は、ヘッダー・フッターにページ番号があるPDFのみ対応

## パフォーマンス情報

### ファイルサイズの目安

| 音声長 | high品質 | standard品質 | compact品質 |
|--------|----------|-------------|-------------|
| 1分 | 約2.4MB | 約1.0MB | 約0.7MB |
| 5分 | 約12MB | 約5MB | 約3.5MB |
| 10分 | 約24MB | 約10MB | 約7MB |

**standard品質（推奨）**は、音声コンテンツに十分な品質を保ちながら、ファイルサイズを大幅に削減します。

## トラブルシューティング

### タイムアウトエラー
長いコンテンツの処理でタイムアウトが発生する場合は、章の内容を短くするか、処理を分割してください。

### レート制限エラー（429エラー）
APIのレート制限に達した場合：

1. **自動ガイダンス**: エラー発生時に処理状況と再開コマンドが表示されます
2. **Scripts-to-Audio機能を使用**: 推奨待機時間（2-5分）後に表示されたコマンドで再開
3. **既存ファイルは自動スキップ**: 重複処理を避けて効率的に再開

```bash
# 例：429エラー後の再開
python -m pdf_podcast --scripts-to-audio ./output/scripts/document
```

### 音声が生成されない
- Google API Keyが正しく設定されているか確認してください
- ネットワーク接続を確認してください
- ログファイルでエラーの詳細を確認してください

### ページ番号オフセットの問題
前付けがあるPDFで間違った内容が抽出される場合：

```bash
# 手動でオフセットを指定（前付けページ数分）
python -m pdf_podcast --input document.pdf --output-dir ./output --page-offset 5

# ログでオフセット検出状況を確認
python -m pdf_podcast --input document.pdf --output-dir ./output --verbose
```

**オフセット値の確認方法:**
1. PDFビューアーで実際の1ページ目（本文開始）の物理ページ番号を確認
2. オフセット = 物理ページ番号 - 1
3. 例：本文が物理6ページ目から始まる場合、オフセットは5

## ライセンス

MIT License

## 貢献

プルリクエストを歓迎します。大きな変更を行う場合は、まずIssueを作成して変更内容について議論してください。