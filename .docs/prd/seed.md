# 入力されたコンテンツを自動でポッドキャスト形式にしするプログラム

以下は **「PDF → 章ごとに対話脚本生成 → Gemini TTS （マルチスピーカー）で Podcast 音声化」** に特化した **CLI ツール要件定義（Markdown 版）** です。
“Summary モード”は完全に削除し、機能は **Podcast 生成のみ** に絞りました。

---

## 1. 目的

1. 入力 PDF を章単位で抽出し、各章を **ホスト／ゲストの掛け合い**スクリプトへ要約変換。
2. スクリプトを **Gemini 2.5 Pro／Flash Preview TTS** に渡し、**multi-speaker** 音声（最大 2 人）を生成する。
   * `multiSpeakerVoiceConfig` と `<speaker id="…">` で声を分離。([ai.google.dev][1])
   * 同モデルは 24 言語・複数声色をサポートし、自然な対話を生成できる。([developers.googleblog.com][2])
3. 章別 MP3 と、章を連結した **episode.mp3** を出力し、チャプターマーカー付き RSS もオプション生成。

---

## 2. 機能要件

| 番号   | 要件                                                                                                                                                   |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-1 | **PDF 解析**: 目次 (outline) や「第 *n* 章」パターンで章を検出しテキスト抽出。                                                                                                 |
| FR-2 | **脚本生成 (Gemini Text)**: 各章を 10 分で聴ける長さ（≒ 1400~1500 字 ×2 人）で、<br>`Host:` / `Guest:` 行ラベル付き対話スクリプトを生成。                                                  |
| FR-3 | **マルチスピーカー TTS**: <br> `model:"gemini-2.5-pro-preview-tts"` などを使用し、<br> `responseModalities:["AUDIO"]`, `multiSpeakerVoiceConfig` を含むリクエストで MP3 を取得。 |
| FR-4 | **ファイル出力**: 章ごとに `01_Intro.txt` / `01_Intro.mp3`、全章連結 `episode.mp3`、`manifest.json` を保存。                                                             |
| FR-5 | **チャプタータグ**: `episode.mp3` に ID3v2 `CHAP` / `CTOC` を埋め込み、再生アプリでスキップ可能に。                                                                              |
| FR-6 | **RSS 生成**: `--rss` 指定時に `feed.xml` を出力し、ホスティング先 URL を反映。                                                                                            |
| FR-7 | **並列処理**: 章単位で Gemini Text → TTS を非同期実行 (`--max-concurrency`)。                                                                                       |
| FR-8 | **再実行制御**: `--skip-existing` で既存 MP3/TXT をスキップ。                                                                                                      |
| FR-9 | **ログ**: `rich` + `tqdm` でプログレスバー、詳細は `logs/tool.log`。                                                                                                |

---

## 3. 非機能要件

| 区分    | 要件                                                                     |
| ----- | ---------------------------------------------------------------------- |
| NFR-1 | **性能**: 100 ページ（約 2 万字）の PDF を 10 分以内に完全処理（API 待ち時間含まず）。               |
| NFR-2 | **リトライ**: Gemini API の 429/5xx を指数バックオフで最大 5 回。失敗章は `status:"failed"`。 |
| NFR-3 | **セキュリティ**: API キーは `.env` または OS キーチェーンで管理、標準出力に露出させない。               |
| NFR-4 | **環境互換**: Python 3.10+、Windows/macOS/Linux。公式 Dockerfile も提供。          |

---

## 4. CLI 仕様

```bash
$ pdf_podcast \
    --input            book.pdf \
    --output-dir       ./podcast \
    --model            gemini-2.5-pro-preview-tts \
    --voice-host       Kore           # speaker "Host"
    --voice-guest      Puck           # speaker "Guest"
    --bitrate          320k \
    --bgm              ./assets/jingle.mp3 \
    --max-concurrency  4 \
    --skip-existing \
    --rss --site-url "https://example.com"
```

| オプション                            | 説明                                   | 必須 |
| -------------------------------- | ------------------------------------ | -- |
| `--input` / `--output-dir`       | 対象 PDF / 出力先                         | ✔︎ |
| `--model`                        | Gemini TTS モデル ID（Pro か Flash TTS 系） |    |
| `--voice-host` / `--voice-guest` | 話者ごとの `voiceName`                    |    |
| `--bgm`                          | ジングル or BGM MP3 を挿入                  |    |
| `--rss`                          | RSS を生成（`--site-url` と併用）            |    |
| `--max-concurrency`              | 章単位の並列実行数                            |    |
| `--skip-existing`                | 既存ファイル上書き防止                          |    |

---

## 5. 内部モジュール構成

```
pdf_podcast/
├─ __main__.py          # CLI
├─ pdf_parser.py        # PDF → {chapter: text}
├─ script_builder.py    # Gemini プロンプト生成・呼び出し
├─ tts_client.py        # Gemini TTS ラッパ（multi-speaker）
├─ audio_mixer.py       # BGM・正規化・連結
├─ id3_tags.py          # CHAP / CTOC 付与
├─ rss_builder.py       # RSS feed.xml
├─ manifest.py          # 進行状況メタ
└─ tests/               # pytest
```

---

## 6. 主要ライブラリ

| ライブラリ                                     | 用途                |
| ----------------------------------------- | ----------------- |
| `google-generativeai>=0.5.0`              | Gemini Text & TTS |
| `pdfminer.six` / `pypdf`                  | PDF 解析            |
| `pydub`, `ffmpeg-python`                  | 音声後処理             |
| `mutagen`                                 | ID3v2 タグ操作        |
| `rich`, `tqdm`, `python-dotenv`, `pytest` | 補助                |

---

## 7. 処理フロー

```mermaid
graph TD
    A[CLI 起動] --> B[PDF 解析]
    B --> C[対話スクリプト Prompt 生成]
    C --> D[Gemini Text → スクリプト]
    D --> E[Gemini TTS (multi-speaker)]
    E --> F[音声後処理<br>(BGM・正規化)]
    F --> G[ID3 CHAP 付与 & 連結]
    G --> H[ファイル保存 / RSS 更新]
```

---

## 8. エラーハンドリング

1. **Gemini quota / rate-limit**

   * 429/5xx → バックオフ再試行、5 回失敗で `failed_rate_limit`。
2. **PDF parse failure** → 終了コード 2、ログ保存。
3. **SIGINT (Ctrl-C)** → `manifest.json` フラッシュ後に安全終了。

---

## 9. テスト計画

| ID    | シナリオ        | 期待結果                              |
| ----- | ----------- | --------------------------------- |
| UT-01 | 見出し付き PDF   | 章数 = MP3 数、すべて正常生成                |
| UT-02 | 2 章 Podcast | `episode.mp3` 長さ ≈ 各章合計 + BGM     |
| UT-03 | API キー欠如    | エラーメッセージ & 終了コード 1                |
| IT-01 | 429 注入      | 再試行ログ記録 & 該当章 `failed_rate_limit` |
| IT-02 | RSS 検証      | `feed.xml` が Feed Validator 合格    |
