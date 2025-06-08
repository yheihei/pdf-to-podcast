# Planフェーズ: Gemini TTS マルチスピーカー音声対応修正

## 現状分析

### 確認された問題
- 現在の`tts_client.py:69-75`で`voice_config`を使用
- `voice_host`のみが設定され、`voice_guest`は無視されている
- `types.VoiceConfig`使用により単一音声のみ対応

### 影響範囲
修正が必要な関数（すべて同じパターン）：
1. `generate_audio()` (行37-98) - メイン音声生成関数
2. `generate_audio_with_retry()` (行221-283) - リトライ付き版
3. `generate_chapter_audios()` (行175-219) - 複数章同期版
4. `generate_chapter_audios_async()` (行285-372) - 複数章非同期版

## 実装Plan

### Phase 1: Core API修正
**タスク1.1: `generate_audio()`メソッドの修正**
- 行67-77の`config`設定を修正
- `voice_config` → `multi_speaker_voice_config`に変更
- Host/Guest両方の音声設定を追加

**修正内容:**
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

### Phase 2: 他関数への適用
**タスク2.1: `generate_audio_with_retry()`の修正**
- 基本的に`generate_audio()`を呼び出すだけなので自動的に対応

**タスク2.2: `generate_chapter_audios()`の修正**
- 基本的に`generate_audio()`を呼び出すだけなので自動的に対応

**タスク2.3: `generate_chapter_audios_async()`の修正**
- 基本的に`generate_audio_with_retry()`を呼び出すだけなので自動的に対応

### Phase 3: テストと検証
**タスク3.1: 単体テスト実行**
```bash
pytest tests/test_tts_client.py
```

**タスク3.2: 統合テスト実行**
```bash
python -m pdf_podcast --input test/test.pdf --output-dir ./output
```

**タスク3.3: 音声検証**
- Host/Guest音声の違いを確認

## リスク要因と対策

### 技術的リスク
1. **API変更による互換性問題**
   - 対策: 段階的修正、十分なテスト

2. **Gemini APIの制限**
   - 長いスクリプトでの音声切り替え無視
   - 対策: エラーハンドリング強化、必要に応じて分割

### 検証方法
1. **既存機能の維持確認**
   - CLI引数（`--voice-host`, `--voice-guest`）動作確認
   - エラーハンドリング動作確認

2. **新機能の確認**
   - Host/Guest異なる音声生成確認

## 受け入れ基準チェックリスト
- [ ] Host役とGuest役で異なる音声が生成される
- [ ] 既存のCLI引数が正常に動作する  
- [ ] 既存のテストがすべて通る
- [ ] エラーハンドリングが正常に動作する
- [ ] パフォーマンスの劣化がない

## 次のフェーズへの条件
✅ Planが完成
⏸️ ユーザーからの承認待ち → 承認後にImpフェーズに移行