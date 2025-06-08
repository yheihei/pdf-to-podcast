# Planフェーズ: 出力ディレクトリのタイムスタンプ構造対応

## 現状分析

### 確認された出力パス生成箇所
- **スクリプト保存**: `__main__.py:233` → `scripts_dir = self.output_dir / "scripts"`
- **音声保存**: `__main__.py:290` → `audio_dir = self.output_dir / "audio"`

### 修正が必要な箇所
1. **行233**: スクリプトディレクトリパス生成
2. **行290**: 音声ディレクトリパス生成  
3. **新規**: タイムスタンプ生成ロジック（`run()`メソッド開始時）

## 実装Plan

### Phase 1: コア機能実装

**タスク1.1: datetimeインポート追加**
- 行3付近にて`import datetime`を追加

**タスク1.2: タイムスタンプ生成ロジック追加**
- `run()`メソッド（行77）の開始部分にタイムスタンプ生成を追加
- 形式: `YYYYMMDD_HHMMSS`
- 全体で一貫して使用

**タスク1.3: スクリプトディレクトリパス修正**
- 行233: `scripts_dir = self.output_dir / "scripts" / timestamp`

**タスク1.4: 音声ディレクトリパス修正**  
- 行290: `audio_dir = self.output_dir / "audio" / timestamp`

### 修正内容詳細

#### 修正1: インポート追加（行3付近）
```python
import datetime
```

#### 修正2: タイムスタンプ生成（run()メソッド開始時）
```python
async def run(self) -> int:
    """Run the podcast generation process."""
    try:
        # Generate timestamp for this execution
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Print header
        self.podcast_logger.print_header(...)
```

#### 修正3: スクリプトディレクトリパス修正（行233）
```python
# Before
scripts_dir = self.output_dir / "scripts"

# After  
scripts_dir = self.output_dir / "scripts" / timestamp
```

#### 修正4: 音声ディレクトリパス修正（行290）
```python
# Before
audio_dir = self.output_dir / "audio"

# After
audio_dir = self.output_dir / "audio" / timestamp
```

### タイムスタンプの渡し方
- `run()`メソッドでタイムスタンプを生成
- 各サブメソッド（`_generate_scripts`, `_generate_audio`）にパラメータとして渡す
- または、インスタンス変数として保存 → `self.timestamp = timestamp`

**推奨**: インスタンス変数として保存する方法（シンプル）

### Phase 2: テストと検証

**タスク2.1: 基本動作テスト**
- 単一実行での正常動作確認
- ディレクトリ構造の確認

**タスク2.2: 複数実行テスト**
- 異なるタイムスタンプでの複数実行確認  
- ディレクトリ重複がないことの確認

**タスク2.3: エラーハンドリング確認**
- ディレクトリ作成失敗時の動作確認

## 受け入れ基準チェックリスト
- [ ] `import datetime`が追加される
- [ ] タイムスタンプ生成ロジックが`run()`メソッドに追加される
- [ ] スクリプトが `<output>/scripts/<timestamp>/` に保存される
- [ ] 音声が `<output>/audio/<timestamp>/` に保存される
- [ ] エピソードは従来通り `<output>/episode.mp3` に保存される
- [ ] 複数回実行時に異なるタイムスタンプディレクトリが作成される

## リスク要因と対策

### 技術的リスク
1. **タイムスタンプの渡し方**
   - メソッド引数 vs インスタンス変数
   - 対策: インスタンス変数を使用してシンプルに

2. **ディレクトリ作成エラー**
   - 権限不足等
   - 対策: 既存のディレクトリ作成ロジックを活用（`mkdir(parents=True, exist_ok=True)`）

## 次のフェーズへの条件
✅ Planが完成
⏸️ ユーザーからの承認待ち → 承認後にImpフェーズに移行