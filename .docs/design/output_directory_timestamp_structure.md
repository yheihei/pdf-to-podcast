# 設計書: 出力ディレクトリのタイムスタンプ構造対応

## 実装概要

### 目的
PDFポッドキャスト生成時の出力ファイルをタイムスタンプ付きディレクトリに整理し、複数回実行時の重複を防ぐ。

### 変更前後の構造

#### 変更前
```
output/
├── scripts/
│   ├── Chapter1.txt
│   └── Chapter2.txt
├── audio/
│   ├── 01_Chapter1.mp3
│   └── 02_Chapter2.mp3
└── episode.mp3
```

#### 変更後
```
output/
├── scripts/
│   └── 20250608_170014/
│       ├── Chapter1.txt
│       └── Chapter2.txt
├── audio/
│   └── 20250608_170014/
│       ├── 01_Chapter1.mp3
│       └── 02_Chapter2.mp3
└── episode.mp3
```

## 実装詳細

### 修正ファイル
- `pdf_podcast/__main__.py`

### 変更内容

#### 1. datetimeモジュールのインポート追加
```python
# Before (行3-10)
import argparse
import asyncio
import os
...

# After  
import argparse
import asyncio
import datetime  # 追加
import os
...
```

#### 2. タイムスタンプ生成ロジック追加
```python
# run()メソッド開始時（行83付近）
async def run(self) -> int:
    try:
        # Generate timestamp for this execution
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Print header
        ...
```

#### 3. スクリプトディレクトリパス修正
```python
# Before (行233)
scripts_dir = self.output_dir / "scripts"

# After
scripts_dir = self.output_dir / "scripts" / self.timestamp
```

#### 4. 音声ディレクトリパス修正
```python
# Before (行290)
audio_dir = self.output_dir / "audio"

# After
audio_dir = self.output_dir / "audio" / self.timestamp
```

## 技術仕様

### タイムスタンプ形式
- **フォーマット**: `YYYYMMDD_HHMMSS`
- **例**: `20250608_170014`
- **生成タイミング**: `run()`メソッド開始時に1回のみ

### インスタンス変数として保存
- `self.timestamp`として保存し、複数のメソッドで共有
- メソッド引数として渡す必要がなく、実装がシンプル

### ディレクトリ作成
- 既存の`mkdir(parents=True, exist_ok=True)`ロジックを活用
- タイムスタンプディレクトリも自動的に作成される

## 動作確認

### 基本テスト結果
✅ タイムスタンプ生成: `20250608_170014`形式で正常生成  
✅ ディレクトリ構造: 期待通りの階層構造を作成  
✅ ディレクトリ作成: `mkdir(parents=True, exist_ok=True)`で正常作成

### 影響のないファイル
- `script_builder.py`: パスが渡されるだけなので変更不要
- `tts_client.py`: パスが渡されるだけなので変更不要  
- `audio_mixer.py`: パスが渡されるだけなので変更不要

## 受け入れ基準

### 必須条件 ✅
- [x] スクリプトが `<output>/scripts/<timestamp>/` に保存される
- [x] 音声が `<output>/audio/<timestamp>/` に保存される  
- [x] エピソードは従来通り `<output>/episode.mp3` に保存される
- [x] 複数回実行時に異なるタイムスタンプディレクトリが作成される
- [x] 既存のCLI引数が正常に動作する

### 望ましい条件 ✅
- [x] 実装がシンプルで理解しやすい
- [x] 既存コードへの影響が最小限
- [x] エラーハンドリングが適切（既存ロジック活用）

## 今後の考慮事項

### 運用面
1. **古いディレクトリのクリーンアップ**
   - 長期運用時の自動削除機能（将来の拡張として）

2. **タイムスタンプ重複対策**
   - 秒単位での生成のため、通常の使用では重複の可能性は極めて低い
   - 必要に応じてミリ秒やランダム文字列を追加可能

### 拡張性
- 将来的にタイムスタンプ以外の情報（ユーザーID、プロジェクト名等）を追加可能な構造

## 実装完了
- **実装日**: 2025/06/08
- **変更ファイル**: `pdf_podcast/__main__.py` (4箇所の修正)
- **テスト**: 基本動作確認完了
- **ドキュメント**: 設計書・Plan完備