# 講義形式への変更実装計画

## 実装タスク一覧

### 1. ScriptBuilderクラスの変更
- [ ] DialogueScriptクラスをLectureScriptクラスに変更
- [ ] generate_dialogue_scriptメソッドをgenerate_lecture_scriptに変更
- [ ] _create_dialogue_promptメソッドを_create_lecture_promptに変更
- [ ] _parse_dialogue_responseメソッドを_parse_lecture_responseに変更
- [ ] speaker関連のロジックを削除
- [ ] 講義形式のプロンプトテンプレートを作成

### 2. TTSClientクラスの変更
- [ ] multi-speaker関連のコードを削除
- [ ] generate_audioメソッドを単一話者用に簡略化
- [ ] voice_host/voice_guest パラメータを削除
- [ ] 単一のvoiceパラメータに変更
- [ ] _create_multi_speaker_content関連メソッドを削除

### 3. CLIインターフェースの変更
- [ ] --voice-host, --voice-guestパラメータを削除
- [ ] --voiceパラメータを追加（デフォルト: Kore）
- [ ] PodcastGeneratorクラスの関連箇所を修正
- [ ] 設定表示部分の修正

### 4. テストファイルの更新
- [ ] test_script_builder.pyを講義形式に対応
- [ ] test_tts_client.pyを単一話者に対応
- [ ] 対話形式のテストケースを削除

### 5. その他の修正
- [ ] script_validator.pyの対話形式検証を削除
- [ ] manifest.pyの関連フィールドを更新
- [ ] example_usage.pyの更新
- [ ] README.mdの更新

## 実装順序
1. ScriptBuilderクラスの変更（最優先）
2. TTSClientクラスの変更
3. CLIインターフェースの変更
4. テストファイルの更新
5. その他のファイルの修正

## 注意事項
- 既存の対話形式のコードは完全に削除する
- 後方互換性は考慮しない
- エラーハンドリングを適切に実装する