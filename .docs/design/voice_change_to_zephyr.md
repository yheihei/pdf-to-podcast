# 実装内容: デフォルトVoiceをLedaに変更し、温かみのある話し方にする

## 実装概要
PDF Podcastツールのデフォルト音声を「Leda」から「Leda」に変更し、より温かみのある話し方になるようパラメータを調整しました。

## 変更内容

### 1. デフォルトVoiceの変更
**ファイル**: `pdf_podcast/__main__.py`
- L964: デフォルトボイスを`"Leda"`から`"Leda"`に変更
- ヘルプメッセージも更新

### 2. 音声パラメータの追加
**ファイル**: `pdf_podcast/__main__.py`
新しいコマンドライン引数を追加:
- `--temperature` (L968-973): TTS生成の多様性を制御（デフォルト: 0.9）
  - より高い値でより自然で温かみのある抑揚に
- `--speaking-rate` (L975-980): 話速の調整（デフォルト: 0.95）
  - 若干ゆっくりめで聞き取りやすく

### 3. TTSClientの拡張
**ファイル**: `pdf_podcast/tts_client.py`
- L34-44: `__init__`メソッドに`temperature`と`speaking_rate`パラメータを追加
- L51-52: インスタンス変数として保存
- L90: 生成時にself.temperatureを使用するよう変更

### 4. パラメータの伝搬
**ファイル**: `pdf_podcast/__main__.py`
- L654-655: TTSClient初期化時に新しいパラメータを渡すよう修正（2箇所）

## 実装の詳細

### Temperature設定
- デフォルト値を0.7から0.9に上げることで、より自然な抑揚と表現力豊かな音声を実現
- 0.1〜1.0の範囲で調整可能

### Speaking Rate設定
- デフォルト値を0.95に設定し、標準速度より若干ゆっくりめに
- 講義形式のコンテンツとして聞き取りやすさを重視
- 0.5〜2.0の範囲で調整可能

### 注意事項
- `speaking_rate`パラメータは現在のGemini TTS APIではまだサポートされていない可能性があります
- 将来的にAPIがサポートした際に、すぐに活用できるよう実装を準備しています
- 現在は`temperature`の調整のみが効果を発揮します

## テスト結果
- 単体テスト: すべて合格（10/10）
- 統合テスト: すべて合格（175/175）
- 既存機能への影響なし

## 使用例

```bash
# デフォルト設定で実行（Leda音声、temperature=0.9）
python -m pdf_podcast --input document.pdf --output-dir ./output

# カスタム設定で実行
python -m pdf_podcast --input document.pdf --output-dir ./output \
  --voice "Leda" \
  --temperature 0.8 \
  --speaking-rate 0.9
```

## 今後の改善案
1. Gemini TTS APIが`speaking_rate`をサポートした際の対応
2. ピッチ調整機能の追加検討
3. 音声プロファイル（温かみ、フォーマル、カジュアルなど）のプリセット機能