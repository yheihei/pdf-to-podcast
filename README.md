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
python -m pdf_podcast --input document.pdf --output-dir ./output
```

### 詳細なオプション

```bash
python -m pdf_podcast \
  --input document.pdf \
  --output-dir ./output \
  --voice Kore \
  --bgm background_music.mp3 \
  --skip-existing
```

### コマンドラインオプション

| オプション | 説明 | デフォルト |
|------------|------|------------|
| `--input` | 入力PDFファイルのパス | 必須 |
| `--output-dir` | 出力ディレクトリ | 必須 |
| `--voice` | 講師の音声 | Kore |
| `--bgm` | BGM音楽ファイルのパス | なし |
| `--bitrate` | 音声のビットレート | 320k |
| `--max-concurrency` | 最大同時実行数 | 1 |
| `--skip-existing` | 既存ファイルをスキップ | False |
| `--model-pdf` | PDF解析用のGeminiモデル | gemini-2.5-flash-preview-05-20 |
| `--model-script` | スクリプト生成用のGeminiモデル | gemini-2.5-pro-preview-06-05 |
| `--model-tts` | 音声合成用のGeminiモデル | gemini-2.5-pro-preview-tts |
| `--verbose` | 詳細なログ出力 | False |

## 出力ファイル

実行後、以下のファイルが生成されます：

```
output/
├── episode.mp3          # 最終的なポッドキャストファイル
├── manifest.json        # 処理の進捗情報
├── scripts/            # 生成された講義スクリプト
│   └── timestamp/
│       ├── chapter1.txt
│       └── chapter2.txt
├── audio/              # 章ごとの音声ファイル
│   └── timestamp/
│       ├── 01_chapter1.mp3
│       └── 02_chapter2.mp3
└── logs/               # ログファイル
```

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

## トラブルシューティング

### タイムアウトエラー
長いコンテンツの処理でタイムアウトが発生する場合は、章の内容を短くするか、処理を分割してください。

### レート制限エラー
APIのレート制限に達した場合は、少し時間を置いてから再実行してください。

### 音声が生成されない
- Google API Keyが正しく設定されているか確認してください
- ネットワーク接続を確認してください
- ログファイルでエラーの詳細を確認してください

## ライセンス

MIT License

## 貢献

プルリクエストを歓迎します。大きな変更を行う場合は、まずIssueを作成して変更内容について議論してください。