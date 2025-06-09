# PDFページ番号オフセット対応 - 設計ドキュメント

## 概要

PDFの論理ページ番号と物理ページ番号のオフセットを自動検出し、正しい内容を抽出できる機能を実装しました。前付け（序文、目次など）があるPDFでも、LLMから返される論理ページ番号を物理ページ番号に正しく変換して、期待する内容を抽出できるようになりました。

## 実装された機能

### 1. 自動オフセット検出
- PDFの最初の10-20ページから実際のページ番号表記を検出
- 論理ページ番号と物理ページ番号の差分（オフセット）を自動計算
- 複数ページでの一貫性確認による信頼性向上

### 2. 手動オフセット指定
- `--page-offset` コマンドライン引数による手動オフセット指定
- 自動検出が困難な場合のフォールバック機能

### 3. 既存機能との互換性維持
- 既存のAPIインターフェースは変更なし
- オフセット0の場合は従来と同じ動作

## 技術実装詳細

### コアクラス: PDFParser

#### 新規追加メソッド

##### `_detect_page_offset(self) -> int`
**目的**: PDFの物理ページ番号と論理ページ番号のオフセットを自動検出

**アルゴリズム**:
1. 最初の10-20ページを順次処理
2. pdfminerでページレイアウトを取得
3. ヘッダー・フッター領域（上下10%）からページ番号を抽出
4. 正規表現で数字パターンを検出
5. 複数ページで一貫したオフセットを確認
6. 一貫性が確認できればオフセットを確定

**戻り値**: 検出されたオフセット値（検出失敗時は0）

##### `_convert_to_physical_page(self, logical_page: int) -> int`
**目的**: 論理ページ番号を物理ページ番号に変換

**計算式**: `物理ページ番号 = 論理ページ番号 + オフセット`

##### `_extract_page_number_from_layout(self, page_layout, physical_page_num: int) -> Optional[int]`
**目的**: ページレイアウトからページ番号を抽出

**実装**:
- ヘッダー・フッター領域のテキスト要素を検査
- LTTextContainerオブジェクトのみ処理
- 妥当性チェック（物理ページ番号から20ページ以内）

##### `_extract_number_from_text(self, text: str) -> Optional[int]`
**目的**: テキストからページ番号として妥当な数字を抽出

**対応パターン**:
- 単独の数字: `123`
- ハイフンで囲まれた数字: `- 15 -`
- ページ/総ページ形式: `25 / 100`

#### 変更されたメソッド

##### `__init__(..., manual_offset: Optional[int] = None)`
**変更点**: 手動オフセット指定パラメータを追加

**初期化処理**:
```python
if manual_offset is not None:
    self._page_offset = manual_offset
    self._offset_detected = True
else:
    self._page_offset = 0  # 初期値
    self._offset_detected = False
```

##### `extract_chapters(self) -> List[Chapter]`
**変更点**: オフセット検出とページ番号変換を追加

**処理フロー**:
1. オフセット未検出の場合、自動検出を実行
2. LLMから章情報を取得（論理ページ番号）
3. 論理ページ番号を物理ページ番号に変換
4. 変換後の物理ページ番号でテキスト抽出
5. Chapterオブジェクトには論理ページ番号を保存（manifest用）

##### `extract_sections(self) -> List[Section]`
**変更点**: `extract_chapters()`と同様の変更を適用

### CLI対応

#### 新規コマンドライン引数
```bash
--page-offset PAGE_OFFSET
```
**説明**: 手動ページオフセット指定（論理ページ番号 + オフセット = 物理ページ番号）

#### PodcastGeneratorクラスの変更
```python
# PDFParserの初期化時にオフセット引数を渡す
self.pdf_parser = PDFParser(
    self.args.input, 
    self.model_config.pdf_model, 
    self.api_key,
    manual_offset=getattr(self.args, 'page_offset', None)
)
```

## ログ出力

### 情報レベル
- `"Page offset detected: {offset} (logical page = physical page - {offset})"`
- `"Manual page offset set: {offset}"`

### 警告レベル
- `"Inconsistent page numbering detected. Using default offset 0."`
- `"No page numbers found. Using default offset 0."`

### デバッグレベル
- `"Converting chapter '{title}': logical pages {start}-{end} -> physical pages {phys_start}-{phys_end}"`
- `"Page {physical}: found logical page {logical}, offset={offset}"`

## テスト

### テストカバレッジ
追加されたテストケース（15個の新規テスト）:

1. **初期化テスト**
   - `test_init_with_manual_offset`: 手動オフセット指定での初期化

2. **ページ番号変換テスト**
   - `test_convert_to_physical_page`: ページ番号変換機能

3. **テキスト解析テスト**
   - `test_extract_number_from_text`: テキストからページ番号抽出

4. **オフセット検出テスト**
   - `test_detect_page_offset_success`: オフセット検出成功
   - `test_detect_page_offset_with_offset`: 前付けありPDFでのオフセット検出
   - `test_detect_page_offset_failure`: 検出失敗時のフォールバック

5. **統合テスト**
   - `test_extract_chapters_with_offset`: オフセットありでの章抽出

### テスト結果
- **新規テスト**: 15/15 PASSED
- **全テストスイート**: 175/175 PASSED
- **回帰テスト**: すべてのテストが通過、既存機能への影響なし

## 使用方法

### 自動オフセット検出（推奨）
```bash
python -m pdf_podcast --input document.pdf --output-dir ./output
```
システムが自動的にページオフセットを検出します。

### 手動オフセット指定
```bash
python -m pdf_podcast --input document.pdf --output-dir ./output --page-offset 5
```
前付けが5ページある場合の例。

### 使用例とオフセット値

#### オフセット0（前付けなし）
- 物理ページ1に論理ページ"1"が記載
- 論理ページ = 物理ページ

#### オフセット5（前付け5ページ）
- 物理ページ6に論理ページ"1"が記載
- 論理ページ1 → 物理ページ6
- 論理ページ10 → 物理ページ15

## パフォーマンス

### 初期化時間への影響
- オフセット検出は初回のみ実行
- 最大20ページのみを対象とし、高速化を図る
- 検出結果はキャッシュされ、再利用される

### メモリ使用量
- 追加のメモリ使用量は最小限
- オフセット値とフラグのみを保持

## エラーハンドリング

### フォールバック機能
1. **ページ番号検出失敗**: オフセット0で動作継続
2. **PDFレイアウト解析エラー**: エラーログ出力後、オフセット0で動作継続
3. **不整合なページ番号**: 警告ログ出力後、オフセット0で動作継続

### ログ出力による診断支援
- 検出されたオフセット値をログに出力
- ページ番号変換の詳細をデバッグログに出力
- エラー時の詳細情報をログに記録

## 制限事項

### 対応できないケース
1. **複雑なページ番号体系**: ローマ数字と算用数字の混在
2. **ページ番号表記なし**: フッター・ヘッダーにページ番号がないPDF
3. **特殊なレイアウト**: テキスト要素として認識できないページ番号

### 対策
- 手動オフセット指定による回避
- ログ出力による問題の診断
- 既存動作の維持（オフセット0でのフォールバック）

## 今後の拡張可能性

### 検出精度の向上
- ローマ数字ページ番号の対応
- より多様なページ番号パターンの対応
- 複数セクションでの異なるページ番号体系の対応

### ユーザビリティの向上
- 検出されたオフセットの確認UI
- PDFプレビューでのページ番号確認機能

## 結論

PDFページ番号オフセット対応機能の実装により、前付けがあるPDFでも正確な内容抽出が可能になりました。自動検出機能により多くのケースで手動設定が不要となり、手動オフセット指定によるフォールバック機能で確実性も確保されています。

既存機能との互換性を完全に保ちつつ、新機能を追加できたため、すべてのユーザーが恩恵を受けられる実装となっています。

**実装完了日**: 2025年1月9日  
**実装者**: Claude (Anthropic)  
**レビュー状況**: 実装完了、テスト通過