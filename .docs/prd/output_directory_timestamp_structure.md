# PRD: 出力ディレクトリのタイムスタンプ構造対応

## 問題の概要

### 現在の構造
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

### 要求される新しい構造
```
output/
├── scripts/
│   └── <timestamp>/
│       ├── Chapter1.txt
│       └── Chapter2.txt
├── audio/
│   └── <timestamp>/
│       ├── 01_Chapter1.mp3
│       └── 02_Chapter2.mp3
└── episode.mp3
```

## 要件

### 機能要件
1. **タイムスタンプ付きディレクトリ作成**
   - 各実行時に`YYYYMMDD_HHMMSS`形式のタイムスタンプを生成
   - スクリプトと音声それぞれにタイムスタンプディレクトリを作成

2. **出力パス変更**
   - スクリプト: `<output_dir>/scripts/<timestamp>/*.txt`
   - 音声: `<output_dir>/audio/<timestamp>/*.mp3`
   - エピソード: `<output_dir>/episode.mp3` (変更なし)

3. **既存機能の維持**
   - CLIオプション、エラーハンドリング、非同期処理等はすべて維持
   - マニフェストファイルの動作は維持

### 非機能要件
1. **互換性**
   - 既存のCLIオプションは変更しない
   - 既存のAPI・関数シグネチャは維持

2. **利便性**
   - タイムスタンプは実行開始時に1回生成し、全体で統一

## 技術仕様

### 修正対象ファイル
1. **`__main__.py`**
   - タイムスタンプ生成ロジック追加
   - ディレクトリパス生成の修正

2. **影響しないファイル**
   - `script_builder.py`: パスが渡されるだけなので変更不要
   - `tts_client.py`: パスが渡されるだけなので変更不要
   - `audio_mixer.py`: パスが渡されるだけなので変更不要

### 実装詳細

#### タイムスタンプ生成
```python
import datetime

# 実行開始時に1回生成
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
```

#### ディレクトリパス変更
```python
# Before
scripts_dir = self.output_dir / "scripts"
audio_dir = self.output_dir / "audio"

# After  
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
scripts_dir = self.output_dir / "scripts" / timestamp
audio_dir = self.output_dir / "audio" / timestamp
```

### 修正箇所

#### __main__.py
1. **import追加** (行2-10付近)
   ```python
   import datetime
   ```

2. **タイムスタンプ生成** (run()メソッド開始時)
   ```python
   timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
   ```

3. **スクリプトディレクトリパス修正** (行233付近)
   ```python
   scripts_dir = self.output_dir / "scripts" / timestamp
   ```

4. **音声ディレクトリパス修正** (行290付近)
   ```python
   audio_dir = self.output_dir / "audio" / timestamp
   ```

## 実装計画

### Phase 1: コア機能実装
1. タイムスタンプ生成ロジック追加
2. ディレクトリパス生成の修正
3. 動作テスト

### Phase 2: テストと検証
1. 既存テストの実行
2. 新しいディレクトリ構造での統合テスト
3. 複数回実行での重複確認

## 受け入れ基準

### 必須条件
- [ ] スクリプトが `<output>/scripts/<timestamp>/` に保存される
- [ ] 音声が `<output>/audio/<timestamp>/` に保存される
- [ ] エピソードは従来通り `<output>/episode.mp3` に保存される
- [ ] 既存のCLIオプションが正常に動作する
- [ ] 複数回実行時に異なるタイムスタンプディレクトリが作成される

### 望ましい条件  
- [ ] 既存のテストがすべて通る
- [ ] パフォーマンスの劣化がない
- [ ] ログ出力が適切である

## リスク要因

### 技術的リスク
1. **ディレクトリ作成失敗**
   - 権限不足によるディレクトリ作成エラー
   - 対策: 適切なエラーハンドリング

2. **タイムスタンプ重複**
   - 高速実行時の同一タイムスタンプ
   - 対策: 秒まで含む形式で十分回避可能

### 互換性リスク
1. **既存ワークフローへの影響**
   - 出力パスが変わることによる後続処理への影響
   - 対策: ドキュメント更新、段階的導入検討