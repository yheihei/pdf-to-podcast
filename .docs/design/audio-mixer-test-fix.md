# test_audio_mixer.py テストエラー修正実装

## 修正内容

### 1. Mock AudioSegmentの属性追加
- `max`属性: normalizeエフェクトで使用されるサンプル最大値（32767）
- `max_possible_amplitude`属性: 最大可能振幅値（32767）
- `__getitem__`メソッド: BGMスライシング操作対応
- `__mul__`メソッド: BGM繰り返し操作対応
- `export`メソッド: オーディオ出力対応

### 2. normalizeエフェクトのパッチ追加
以下のテストメソッドに`@patch('pdf_podcast.audio_mixer.normalize')`を追加：
- `test_concatenate_with_bgm`
- `test_concatenate_missing_files` 
- `test_apply_audio_effects`

### 3. test_concatenate_missing_filesの特別対応
- `empty_mock.__add__`がchapter_mockを返すよう設定
- empty episodeにchapterが追加された際に適切にMockが連携するよう調整

## 修正されたエラー
1. **normalize AttributeError**: Mock AudioSegmentに必要属性追加で解決
2. **BGM overlay失敗**: __getitem__, __mul__メソッド追加で解決
3. **"No valid files"エラー**: empty_mockの__add__動作修正で解決

## テスト結果
- 全13テストがPASS
- エラーメッセージとスタックトレースが消失
- audio_mixerモジュールの全機能が適切にテストされている

## 技術的詳細
- pydub.effects.normalizeがAudioSegmentの内部属性に依存することを考慮
- BGM処理でのスライシング・繰り返し操作をMockで適切に模擬
- AudioSegmentの連結操作（__add__）の複雑な動作を正確に再現