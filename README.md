# PDF Podcast Generator

PDFファイルから対話形式のポッドキャスト音声を自動生成するPython CLIツールです。

## 📖 概要

このツールは以下の処理を自動化します：

1. **PDF解析**: PDFファイルから章ごとにテキストを抽出
2. **対話スクリプト生成**: Gemini AIを使って各章を2人の対話形式に変換
3. **音声生成**: Gemini TTSのマルチスピーカー機能で自然な対話音声を作成
4. **音声編集**: 章別音声の連結、BGM追加、チャプター情報の埋め込み

## ✨ 主な機能

- 🤖 **AIベースの章検出**: Gemini AIが文書構造を理解して章を自動分割
- 🎭 **マルチスピーカー対話**: ホストとゲストによる自然な掛け合い
- 🎵 **高品質音声生成**: Gemini 2.5 Pro TTS Preview による24言語対応
- 📑 **チャプター機能**: 再生アプリでスキップ可能なチャプター情報を埋め込み
- ⚡ **並列処理**: 複数章を同時処理して高速化
- 🔄 **再実行制御**: 既存ファイルをスキップして効率的な部分実行
- 📊 **豊富なログ**: プログレスバーと詳細ログで進行状況を把握

## 🛠 インストール

### 前提条件

- Python 3.10以上
- FFmpeg（音声処理用）
- Google Gemini API キー

### Python環境の準備

```bash
# リポジトリをクローン
git clone https://https://github.com/yheihei/pdf-to-podcast
cd pdf-to-podcast

# 依存関係をインストール
pip install -r requirements.txt
```

### FFmpegのインストール

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
[FFmpeg公式サイト](https://ffmpeg.org/download.html)からダウンロード

### API キーの設定

Google AI Studio で Gemini API キーを取得し、環境変数に設定：

```bash
# .envファイルを作成
echo "GOOGLE_API_KEY=your_api_key_here" > .env

# または環境変数で設定
export GOOGLE_API_KEY="your_api_key_here"
```

## 🚀 使い方

### 基本的な使用方法

```bash
# 最小限の実行
python -m pdf_podcast --input book.pdf --output-dir ./output

# 詳細オプション付きの実行
python -m pdf_podcast \
    --input book.pdf \
    --output-dir ./output \
    --model gemini-2.5-pro-preview-tts \
    --voice-host Kore \
    --voice-guest Puck \
    --bitrate 320k \
    --max-concurrency 4 \
    --skip-existing \
    --verbose
```

### コマンドオプション

| オプション | 説明 | デフォルト値 |
|-----------|------|-------------|
| `--input` | 入力PDFファイル（必須） | - |
| `--output-dir` | 出力ディレクトリ（必須） | - |
| `--model` | Gemini TTSモデル | `gemini-2.5-pro-preview-tts` |
| `--voice-host` | ホストの音声 | `Kore` |
| `--voice-guest` | ゲストの音声 | `Puck` |
| `--bitrate` | 音声ビットレート | `192k` |
| `--bgm` | BGMファイル（MP3） | なし |
| `--max-concurrency` | 並列処理数 | `3` |
| `--skip-existing` | 既存ファイルをスキップ | `False` |
| `--verbose` | 詳細ログ表示 | `False` |

### 使用例

**基本実行:**
```bash
python -m pdf_podcast --input "技術書.pdf" --output-dir ./output
```

**高品質+BGM付き:**
```bash
python -m pdf_podcast \
    --input "技術書.pdf" \
    --output-dir ./output \
    --bitrate 320k \
    --bgm ./music/intro.mp3 \
    --verbose
```

**高速処理（並列度アップ）:**
```bash
python -m pdf_podcast \
    --input "技術書.pdf" \
    --output-dir ./output \
    --max-concurrency 8 \
    --skip-existing
```

## 📁 出力ファイル構成

```
output/
├── manifest.json              # 処理状況とメタデータ
├── episode.mp3               # 最終ポッドキャスト（チャプター付き）
├── scripts/                  # 生成されたスクリプト
│   ├── 01_序章.txt
│   ├── 02_第1章_概要.txt
│   └── 03_第2章_実装.txt
├── audio/                    # 章別音声ファイル
│   ├── 01_序章.mp3
│   ├── 02_第1章_概要.mp3
│   └── 03_第2章_実装.mp3
└── logs/                     # 詳細ログ
    └── tool_20250608_120000.log
```

### メインファイル

- **`episode.mp3`**: 全章を連結した最終ポッドキャスト
  - ID3v2チャプター情報付き
  - 再生アプリでチャプタースキップ可能
  - BGM付き（指定時）

- **`manifest.json`**: 処理進行状況
  ```json
  {
    "pdf_path": "book.pdf",
    "total_chapters": 5,
    "completed_chapters": 3,
    "chapters": [
      {
        "title": "序章",
        "status": "completed",
        "script_file": "scripts/01_序章.txt",
        "audio_file": "audio/01_序章.mp3"
      }
    ]
  }
  ```

## 🎵 対応音声設定

### 利用可能な音声

Gemini TTSが対応する音声名（一部）:
- `Kore`, `Puck`, `Sage`, `Vale` (英語)
- `Echo`, `Felix`, `Nova`, `Zen` (多言語対応)

### 音声の選び方

```bash
# 異なる性別の組み合わせ例
--voice-host Sage --voice-guest Echo  # 男性 + 女性
--voice-host Nova --voice-guest Felix # 女性 + 男性
```

## 🔧 トラブルシューティング

### よくある問題

**1. API キーエラー**
```
Error: API key not found
```
→ `GOOGLE_API_KEY` 環境変数が設定されているか確認

**2. FFmpegエラー**
```
FFmpeg not found
```
→ FFmpegがインストールされ、PATHに追加されているか確認

**3. メモリ不足**
```
MemoryError during audio processing
```
→ `--max-concurrency` を下げて実行

**4. API制限エラー**
```
Rate limit exceeded
```
→ しばらく待ってから `--skip-existing` で再実行

### デバッグ方法

**詳細ログの確認:**
```bash
python -m pdf_podcast --input book.pdf --output-dir ./output --verbose
```

**ログファイルの確認:**
```bash
tail -f ./output/logs/tool_*.log
```

**マニフェストの確認:**
```bash
cat ./output/manifest.json | python -m json.tool
```

## 🧪 開発・テスト

### テストの実行

```bash
# 全テストを実行
pytest

# 特定モジュールのテスト
pytest tests/test_pdf_parser.py -v

# カバレッジ付きテスト
pytest --cov=pdf_podcast tests/
```

### 開発環境のセットアップ

```bash
# 開発用依存関係のインストール
pip install -e .
pip install pytest pytest-cov black flake8

# コードフォーマット
black pdf_podcast/
flake8 pdf_podcast/
```

## 📋 制限事項

- **PDF形式**: テキスト抽出可能なPDFのみ対応（画像PDFは非対応）
- **言語**: 日本語と英語で最適化（他言語は実験的）
- **ファイルサイズ**: 大きなPDF（500ページ超）は処理時間が長くなる可能性
- **API制限**: Gemini APIの利用制限に依存

## 🔗 関連リンク

- [Gemini API Documentation](https://ai.google.dev/docs)
- [Google AI Studio](https://aistudio.google.com/)
- [FFmpeg公式サイト](https://ffmpeg.org/)

## 📄 ライセンス

MIT License
