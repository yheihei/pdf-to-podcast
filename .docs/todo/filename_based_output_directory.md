# Plan: ファイル名ベースの出力ディレクトリ構造変更

## 概要
タイムスタンプベースのディレクトリ構造から、入力PDFファイル名ベースのディレクトリ構造に変更する実装プランです。

## 実装ステップ

### Step 1: ファイル名安全化ユーティリティの作成
- **対象**: `pdf_podcast/__main__.py`
- **内容**: 
  - PDFファイル名から安全なディレクトリ名を生成する関数`_sanitize_filename()`を追加
  - 不正文字の置換、連続アンダースコアの統合、前後の空白・ドット削除を実装

### Step 2: 重複ディレクトリ名の処理
- **対象**: `pdf_podcast/__main__.py`
- **内容**:
  - 既存ディレクトリ名と重複する場合の連番付与機能`_get_unique_dirname()`を追加
  - 例：`test` → `test_2` → `test_3`

### Step 3: メインロジックの変更
- **対象**: `pdf_podcast/__main__.py`
- **内容**:
  - 84行目: `self.timestamp`の代わりに`self.pdf_dirname`を生成
  - `PodcastGenerator.__init__()`でPDFファイル名からディレクトリ名を決定
  - 232行目: scriptsディレクトリパスを`self.pdf_dirname`ベースに変更  
  - 287行目: audioディレクトリパスを`self.pdf_dirname`ベースに変更

### Step 4: 既存テストの確認と更新
- **対象**: 関連するテストファイル
- **内容**:
  - 出力ディレクトリ構造に依存するテストがあるかチェック
  - 必要に応じてテストケースを更新

### Step 5: 動作確認テスト
- **内容**:
  - 新しいPDFファイルでの正常動作確認
  - 同じPDFファイル名での重複処理確認
  - 特殊文字を含むファイル名での安全化確認

## 技術的考慮事項

### 実装詳細
1. **ファイル名安全化関数**
   ```python
   def _sanitize_filename(self, filename: str) -> str:
       # 拡張子を除去
       # 不正文字を_に置換
       # 連続_を単一_に
       # 前後の空白・ドットを削除
   ```

2. **一意性保証関数**
   ```python
   def _get_unique_dirname(self, base_name: str, base_dir: Path) -> str:
       # 既存ディレクトリをチェック
       # 重複時は連番を付与
   ```

3. **変更箇所の特定**
   - `self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")` → `self.pdf_dirname = self._get_pdf_dirname()`
   - `scripts_dir = self.output_dir / "scripts" / self.timestamp` → `scripts_dir = self.output_dir / "scripts" / self.pdf_dirname`
   - `audio_dir = self.output_dir / "audio" / self.timestamp` → `audio_dir = self.output_dir / "audio" / self.pdf_dirname`

### 後方互換性
- 既存のタイムスタンプベースディレクトリは影響を受けない
- マニフェストファイルの構造は変更なし

## リスク分析
- **低リスク**: 新規作成ファイルのパスのみ変更、既存ファイル削除なし
- **テスト必要**: ディレクトリ作成ロジックの変更による影響確認

## 完了基準
1. 新しいPDFファイルでファイル名ベースのディレクトリが作成される
2. 同名ファイルでの連番処理が正常動作する
3. 特殊文字ファイル名が適切に安全化される
4. 既存の単体テストが全て通る
5. 出力テストが正常に完了する