# FR-2, FR-3 実装設計書

## 概要
PDFポッドキャスト変換ツールの要件定義書に基づき、FR-2（脚本生成）とFR-3（マルチスピーカーTTS）を実装しました。

## 実装内容

### 1. script_builder.py (FR-2)
**機能**: 各章を10分で聴ける長さの対話スクリプトに変換

#### 主要クラス
- `ScriptBuilder`: Gemini APIを使用して対話脚本を生成
- `DialogueScript`: 生成された対話データを格納するデータクラス

#### 主要メソッド
- `generate_dialogue_script()`: 単一章の対話スクリプト生成
- `generate_scripts_for_chapters()`: 複数章のバッチ処理
- `_create_dialogue_prompt()`: プロンプト生成
- `_parse_dialogue_response()`: レスポンス解析

#### 特徴
- Host/Guestの2人による自然な対話形式
- 合計2800〜3000文字程度（10分相当）
- エラーハンドリングとロギング機能

### 2. tts_client.py (FR-3)
**機能**: マルチスピーカーTTSでMP3音声を生成

#### 主要クラス
- `TTSClient`: Gemini TTS APIを使用した音声生成
- `VoiceConfig`: 話者の音声設定を格納するデータクラス

#### 主要メソッド
- `generate_audio()`: 対話スクリプトから音声生成
- `generate_chapter_audios()`: 複数章のバッチ処理
- `_create_multi_speaker_content()`: スピーカータグ付きコンテンツ生成
- `_extract_audio_data()`: レスポンスから音声データ抽出

#### 特徴
- `<speaker id="...">` タグによる話者分離
- multiSpeakerVoiceConfigによる声の個別設定
- MP3形式での出力
- ファイル保存機能

## APIの使用

### Gemini Text API (script_builder.py)
```python
model = genai.GenerativeModel("gemini-2.0-flash-exp")
response = model.generate_content(prompt)
```

### Gemini TTS API (tts_client.py)
```python
model = genai.GenerativeModel("gemini-2.5-pro-preview-tts")
response = model.generate_content(
    [content],
    generation_config={
        "multiSpeakerVoiceConfig": {
            "speakers": [
                {"speakerId": "Host", "voiceName": "Kore"},
                {"speakerId": "Guest", "voiceName": "Puck"}
            ]
        },
        "response_modalities": ["AUDIO"],
        "response_mime_type": "audio/mp3"
    }
)
```

## テスト

両モジュールに対して包括的なユニットテストを実装：
- `test_script_builder.py`: 9個のテストケース
- `test_tts_client.py`: 10個のテストケース

すべてのテストがパスすることを確認済み。

## 今後の統合

これらのモジュールは、以下のフローで統合されます：
1. PDFParser で章を抽出
2. ScriptBuilder で対話スクリプト生成
3. TTSClient で音声生成
4. 後続モジュールで音声編集・ID3タグ付与・RSS生成