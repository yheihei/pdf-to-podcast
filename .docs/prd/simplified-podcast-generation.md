# PRD: シンプル化されたポッドキャスト生成システム

## 1. 概要
現在のPDFポッドキャスト生成システムから以下の機能を削除し、シンプルで軽量なシステムにする：
- 大規模コンテンツの分割処理フォールバック機能
- TTS処理のタイムアウト検出機能
- episode.mp3の生成機能

## 2. 変更対象と詳細

### 2.1 フォールバック処理の削除
**対象ファイル**: `pdf_podcast/tts_client.py:258行目`
- `generate_audio_with_retry`メソッドのフォールバック処理を削除
- 2000文字制限チェックと3チャンク分割処理を削除
- シンプルな1回実行のみに変更

### 2.2 TTS処理タイムアウトの削除
**対象ファイル**: `pdf_podcast/tts_client.py:111-160行目`
- `generate_audio_with_timeout`メソッドの削除
- `asyncio.wait_for`によるタイムアウト処理を削除
- 直接的なTTS API呼び出しに変更

### 2.3 episode.mp3生成の削除
**対象ファイル**: `pdf_podcast/__main__.py:330-392行目`
- `_create_episode`メソッドの削除または無効化
- `AudioMixer.concatenate_chapters`の呼び出し削除
- episode.mp3生成のメインフロー無効化

### 2.4 章ごとのmp3生成のみ保持
**対象ファイル**: `pdf_podcast/tts_client.py:328-417行目`
- `generate_chapter_audios_async`メソッドは保持
- 章ごとの音声ファイル生成機能は維持
- 出力先：`{output_dir}/audio/{timestamp}/`

## 3. 期待される効果

### 3.1 処理速度の向上
- フォールバック処理がないため、エラー時の処理時間短縮
- タイムアウト待機時間の削除

### 3.2 システムの単純化
- エラーハンドリングロジックの簡素化
- メンテナンス性の向上
- デバッグの容易化

### 3.3 リソース使用量の削減
- episode.mp3生成のための音声結合処理が不要
- メモリ使用量の削減
- ストレージ使用量の削減

## 4. 影響範囲

### 4.1 ユーザー体験への影響
- **正の影響**：処理がよりシンプルで予測可能
- **負の影響**：大規模コンテンツでのエラー時の自動復旧機能なし

### 4.2 出力への影響
- episode.mp3が生成されなくなる
- 章ごとのmp3ファイルのみ利用可能
- ユーザーが必要に応じて手動で結合する必要

## 5. 実装優先度
1. **高**: TTS処理タイムアウトの削除（安全性に関わる）
2. **高**: フォールバック処理の削除（処理フローの簡素化）
3. **中**: episode.mp3生成の削除（ユーザビリティ影響）

この変更により、システムがよりシンプルで予測可能になり、章ごとの音声ファイル生成に特化したツールとなります。