# PRD: Gemini TTS マルチスピーカー音声対応修正

## 問題の概要

### 現在の問題
- HostとGuestが同じ音声（Kore）で生成される
- Gemini APIの`voice_config`でHost音声のみが設定されている
- Guest音声（Puck）の設定が反映されていない

### 根本原因
- 現在の実装では`types.VoiceConfig`を使用しており、単一音声のみ設定可能
- マルチスピーカー対応には`types.MultiSpeakerVoiceConfig`が必要

## 要件

### 機能要件
1. **マルチスピーカー音声設定**
   - Host役とGuest役で異なる音声を使用
   - Hostのデフォルト音声: Kore
   - Guestのデフォルト音声: Puck

2. **API設定の修正**
   - `voice_config`から`multi_speaker_voice_config`への変更
   - 各スピーカーに個別の音声設定を適用

3. **既存機能の維持**
   - CLI引数（`--voice-host`, `--voice-guest`）での音声指定機能
   - エラーハンドリングとリトライ機能
   - 非同期処理機能

### 非機能要件
1. **互換性**
   - 既存のCLI引数は変更しない
   - 既存の関数シグネチャは維持
   - 既存のテストが正常に動作する

2. **制限事項への対応**
   - Gemini APIの最大2スピーカー制限を考慮
   - 長いスクリプトでの音声切り替え問題への対策

## 技術仕様

### 修正対象ファイル
- `/pdf_podcast/tts_client.py`

### 修正箇所
1. **TTSClient.generate_audio()メソッド (行62-78)**
   - `speech_config`の設定を`multi_speaker_voice_config`に変更

### 新しいAPI設定
```python
config=types.GenerateContentConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                types.SpeakerVoiceConfig(
                    speaker='Host',
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_host,
                        )
                    )
                ),
                types.SpeakerVoiceConfig(
                    speaker='Guest',
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_guest,
                        )
                    )
                ),
            ]
        )
    ),
    temperature=0.7,
)
```

### 修正が必要な関数
1. `generate_audio()` - メイン音声生成関数
2. `generate_audio_with_retry()` - リトライ付き音声生成関数  
3. `generate_chapter_audios()` - 章ごと音声生成関数
4. `generate_chapter_audios_async()` - 非同期章ごと音声生成関数

## 実装計画

### Phase 1: API設定修正
1. `generate_audio()`メソッドの`speech_config`を修正
2. 単体テストで動作確認

### Phase 2: 他の関数への適用
1. リトライ機能付き関数への適用
2. 非同期処理関数への適用
3. 全体的な動作テスト

### Phase 3: テストと検証
1. 既存テストの実行
2. 実際の音声生成でHost/Guest音声の違いを確認
3. 長いスクリプトでの動作確認

## テスト要件

### 単体テスト
1. Host/Guest異なる音声設定のテスト
2. CLI引数での音声指定のテスト
3. エラーハンドリングのテスト

### 統合テスト
1. 実際のPDF→ポッドキャスト生成での音声確認
2. 長いスクリプトでの音声切り替え確認

## リスク要因

### 技術的リスク
1. **Gemini APIの制限**
   - 長いスクリプトで音声切り替えが無視される既知のバグ
   - 2スピーカーまでの制限

2. **回避策**
   - 必要に応じてスクリプトを短いセグメントに分割
   - エラーハンドリングの強化

### 互換性リスク
1. **API変更によるBreaking Change**
   - 既存のコードが動作しなくなる可能性
   - 十分なテストで確認が必要

## 受け入れ基準

### 必須条件
- [ ] Host役とGuest役で異なる音声が生成される
- [ ] 既存のCLI引数が正常に動作する
- [ ] 既存のテストがすべて通る
- [ ] エラーハンドリングが正常に動作する

### 望ましい条件
- [ ] 長いスクリプトでも音声切り替えが正常に動作する
- [ ] パフォーマンスの劣化がない
- [ ] ログ出力が適切である

## 参考資料

### API ドキュメント
- [Gemini API Speech Generation](https://ai.google.dev/gemini-api/docs/speech-generation)
- [Multi-Speaker Voice Configuration](https://cloud.google.com/text-to-speech/docs/create-dialogue-with-multispeakers)

### 既知の問題
- [Gemini TTS ignores per-speaker voice settings](https://discuss.ai.google.dev/t/gemini-tts-ignores-per-speaker-voice-settings-in-multi-character-prompts/84125)