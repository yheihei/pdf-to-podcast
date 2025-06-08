# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 応答のルール
- 常に日本語で応答してください。コード部分はそのままにしてください。

## 単体テスト方法

```
pytest
```

## 出力テスト方法

```
python -m pdf_podcast --input test/test.pdf --output-dir ./output
```

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
