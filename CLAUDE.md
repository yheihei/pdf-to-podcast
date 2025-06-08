# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 応答のルール
- 常に日本語で応答してください。コード部分はそのままにしてください。

## 開発コマンド

### 単体テスト方法

```bash
pytest
```

### カバレッジ付きテスト

```bash
pytest --cov=pdf_podcast
```

### 特定のテストファイル実行

```bash
pytest tests/test_specific_module.py
```

### 出力テスト方法

```bash
python -m pdf_podcast --input test/test.pdf --output-dir ./output
```

note: 時間がかかるため、ユーザーに依頼しても良い

### 依存関係管理

プロジェクトはPipfileとrequirements.txtの両方をサポート：

```bash
# Pipenvの場合
pipenv install
pipenv shell

# pipの場合  
pip install -r requirements.txt
```

## アーキテクチャ概要

このプロジェクトはPDFからポッドキャスト音声を生成するパイプライン処理システムです。

### 主要コンポーネント

1. **PDFParser** (`pdf_parser.py`): PDFから章（Chapter）や節（Section）を抽出
2. **ScriptBuilder** (`script_builder.py`): 講義形式のスクリプトを生成  
3. **TTSClient** (`tts_client.py`): Gemini TTSを使用した音声合成
4. **ManifestManager** (`manifest.py`): 処理進捗の管理・追跡
5. **PodcastGenerator** (`__main__.py`): 全体の処理を統括するメインクラス

### 処理フロー

1. PDF解析 → 章/節の抽出
2. スクリプト生成 → 講義形式のテキスト作成
3. 音声生成 → TTS APIで音声ファイル作成
4. 進捗管理 → manifest.jsonで処理状況を記録

### 設定とモデル

- **ModelConfig**: PDF解析、スクリプト生成、TTS用のGeminiモデルを個別設定可能
- **RateLimiter**: API制限に対応した非同期処理制御
- **LoggingSystem**: 詳細なログ出力とプログレス表示

## タスクの遂行方法

適用条件: 実装を依頼された時。単なる質問事項の場合適用されない。

### 基本フロー

- PRD の各項目を「Plan → Imp → Debug → Doc」サイクルで処理する  
- irreversible / high-risk 操作（削除・本番 DB 変更・外部 API 決定）は必ず停止する

#### Plan

- PRDを受け取ったら、PRDを確認し、不明点がないか確認する
- その後、PRD の各項目を Planに落とし込む
  - Planは `.docs/todo/${タスクの概要}.md` に保存
- ユーザーにPlanの確認を行い、承認されるまで次のフェーズには移行しない

#### Imp

- Planをもとに実装する

#### Debug

- 指定のテストがあればテストを行う
- 指定がなければ関連のテストを探してテストを行う
- 関連のテストがなければ停止して、なんのテストを行うべきかユーザーに確認する
- テストが通ったらフォーマッタをかける

#### Doc

- 実装を`.docs/design/${タスクの概要}.md` に保存
- ユーザーからのフィードバックを待つ。フィードバックがあれば適宜前のフェーズに戻ること
