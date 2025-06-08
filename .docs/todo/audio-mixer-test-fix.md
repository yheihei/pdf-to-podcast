# test_audio_mixer.py テストエラー修正Plan

## 問題分析

現在のテストエラーの原因：

1. **test_concatenate_with_bgm**: normalizeエフェクト使用時にMockオブジェクトの属性(`max`, `max_possible_amplitude`)が不足
2. **test_concatenate_missing_files**: 同じnormalizeエラー
3. **test_apply_audio_effects**: 同じnormalizeエラー

## 根本原因

- `pydub.effects.normalize`がAudioSegmentオブジェクトの`max`と`max_possible_amplitude`属性を使用
- 現在のMockセットアップがこれらの属性を提供していない

## 修正Plan

### 1. Mock AudioSegmentの改善
- `max`属性を追加（サンプル最大値を返す）
- `max_possible_amplitude`属性を追加（最大可能振幅を返す）
- normalizeエフェクトがエラーなく動作するよう適切な値を設定

### 2. normalizeパッチの統一
- 全テストで`@patch('pdf_podcast.audio_mixer.normalize')`を使用
- AudioSegmentのMockとnormalizeのMockを分離

### 3. テストケース別対応
- `test_concatenate_with_bgm`: normalizeパッチ追加
- `test_concatenate_missing_files`: normalizeパッチ追加  
- `test_apply_audio_effects`: 既存パッチ確認・修正

### 4. 実装順序
1. Mock AudioSegmentに不足属性追加
2. normalizeパッチを各テストメソッドに適用
3. テスト実行・検証
4. 必要に応じて追加調整

### 5. 検証
- `pytest tests/test_audio_mixer.py -v`で全テスト通過確認
- エラーメッセージとスタックトレースの消失確認