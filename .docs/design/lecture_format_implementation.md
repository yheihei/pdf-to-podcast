# 講義形式への変更実装設計書

## 実装概要

PDFポッドキャスト生成システムを対話形式から講義形式へ完全に移行しました。

## 実装した変更

### 1. ScriptBuilderクラスの変更

#### データ構造の変更
- `DialogueScript` → `LectureScript`に変更
- `lines: List[Dict[str, str]]` → `content: str`に変更
- speaker情報を完全に削除

#### メソッドの変更
- `generate_dialogue_script` → `generate_lecture_script`
- `_create_dialogue_prompt` → `_create_lecture_prompt`
- `_parse_dialogue_response` → `_parse_lecture_response`

#### プロンプトの変更
講義形式のプロンプトに変更：
- 講師が視聴者に語りかける形式
- 導入、本論、まとめの構造
- 「みなさん」「〜ですね」などの講義らしい表現を使用

### 2. TTSClientクラスの変更

#### メソッドシグネチャの変更
- `dialogue_lines: List[Dict[str, str]]` → `lecture_content: str`
- `voice_host`, `voice_guest` パラメータを削除
- 単一の `voice` パラメータに統一

#### 音声生成の簡略化
- multi-speaker機能を削除
- 単一話者用のシンプルな実装に変更
- `_create_multi_speaker_content`関連メソッドを削除

### 3. CLIインターフェースの変更

#### パラメータの変更
- `--voice-host`, `--voice-guest` を削除
- `--voice` パラメータを追加（デフォルト: Kore）

#### 内部処理の変更
- `dialogue_scripts` → `lecture_scripts`
- `script.lines` → `script.content`

### 4. manifest.pyの変更

#### フィールドの変更
- `voice_host`, `voice_guest` を削除
- 単一の `voice` フィールドに統一

### 5. script_validator.pyの変更

#### 検証ロジックの変更
- 対話行数チェックを削除
- 段落数と段落長のチェックを追加
- Host/Guestバランスチェックを削除
- 講義形式に適した検証に変更

## 削除された機能

1. Host/Guest対話形式
2. マルチスピーカー音声合成
3. 対話形式のスクリプト検証
4. speaker関連の全てのロジック

## 技術的詳細

### LectureScriptデータ構造
```python
@dataclass
class LectureScript:
    chapter_title: str
    content: str  # 講義内容（改行で区切られた段落）
    total_chars: int
```

### 講義プロンプトテンプレート
- 5分で聴ける長さ（1500〜2000文字程度）
- 講師が視聴者に語りかける形式
- 導入、本論、まとめの構造
- 段落ごとに改行を入れて区切りを明確化

### 音声生成の変更
- Gemini TTS APIの単一話者モードを使用
- speech_configを単純化（multi_speaker_voice_configを削除）
- voice_configで単一の音声を指定

## 注意事項

1. 後方互換性はありません（破壊的変更）
2. 既存の対話形式のスクリプトは使用できません
3. manifestファイルの形式が変更されているため、古いmanifestは削除が必要

## テスト状況

- インポートテスト: 完了
- 基本動作確認: 実行中
- 単体テストの更新: 必要（今後の課題）