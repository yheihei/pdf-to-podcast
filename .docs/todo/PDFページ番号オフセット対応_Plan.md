# PDFページ番号オフセット対応 - 実装計画

## PRDの確認結果

PRDの内容を確認し、以下の点で実装可能であることを確認しました：

### 現在のコードベースの状況
- **PDFParser**: pdfminerとpypdfが既に使用済み
- **extract_text**: 物理ページ番号（1ベース）を受け取って処理
- **extract_chapters/sections**: LLMから論理ページ番号を受け取ってextract_textに渡している
- **CLI引数**: __main__.pyで管理されており、新しい引数の追加が可能

### 不明点・確認事項
特に大きな不明点はありませんが、以下の点について実装時に注意が必要：

1. **ページ番号検出の精度**: 様々なPDFフォーマットに対応する必要性
2. **性能影響**: 初期化時のオフセット検出による処理時間の増加
3. **テストデータ**: 前付けがあるPDFサンプルの準備

## 実装計画

### Phase 1: コア機能の実装

#### 1.1 ページオフセット検出機能 (`pdf_parser.py`)

```python
async def _detect_page_offset(self) -> int:
    """
    PDFの物理ページ番号と論理ページ番号のオフセットを検出
    
    実装方針:
    - 最初の10-20ページを対象
    - pdfminerのextract_pagesでページごとのテキスト要素を取得
    - 正規表現でページ番号パターンを検出（単独の数字、ページフッター/ヘッダー内の数字）
    - 複数ページで一貫性を確認してオフセットを算出
    - 検出失敗時は0を返す（フォールバック）
    """
```

**検出ロジック**:
1. 各ページのLTTextContainerからテキスト要素を取得
2. ページの上部/下部領域（ヘッダー/フッター想定）から数字を検出
3. 物理ページ番号との差分を計算
4. 複数ページで同じオフセットが検出されたら確定

#### 1.2 ページ番号変換機能

```python
def _convert_to_physical_page(self, logical_page: int) -> int:
    """論理ページ番号を物理ページ番号に変換"""
    return logical_page + self.page_offset

@property
def page_offset(self) -> int:
    """検出されたページオフセット値を返す"""
    return getattr(self, '_page_offset', 0)
```

#### 1.3 PDFParserの初期化処理更新

```python
def __init__(self, pdf_path: str, gemini_model: str = "gemini-2.5-flash-preview-05-20", 
             api_key: Optional[str] = None, manual_offset: Optional[int] = None):
    # 既存の初期化処理...
    
    # ページオフセットの設定
    if manual_offset is not None:
        self._page_offset = manual_offset
        logger.info(f"Manual page offset set: {manual_offset}")
    else:
        # 自動検出（非同期なので後で実行）
        self._page_offset = 0  # 初期値
        self._offset_detected = False
```

#### 1.4 既存メソッドの修正

`extract_chapters()` と `extract_sections()` 内で：

```python
# LLMからの結果を物理ページ番号に変換
for ch in chapter_info:
    physical_start = self._convert_to_physical_page(ch["start_page"])
    physical_end = self._convert_to_physical_page(ch["end_page"])
    text = self.extract_text(physical_start, physical_end)
    # ... 以下既存処理
```

### Phase 2: コマンドライン対応

#### 2.1 引数追加 (`__main__.py`)

```python
parser.add_argument(
    "--page-offset",
    type=int,
    help="Manual page offset (logical page = physical page - offset)"
)
```

#### 2.2 PodcastGeneratorクラスの更新

```python
# PDFParserの初期化時にoffset引数を渡す
self.pdf_parser = PDFParser(
    self.args.input, 
    self.model_config.pdf_model, 
    self.api_key,
    manual_offset=getattr(self.args, 'page_offset', None)
)
```

### Phase 3: ログ・デバッグ機能

#### 3.1 ログ出力の追加

```python
# オフセット検出時
logger.info(f"Page offset detected: {offset} (logical = physical - {offset})")

# ページ番号変換時（デバッグレベル）
logger.debug(f"Converting logical page {logical} to physical page {physical}")
```

### Phase 4: テスト実装

#### 4.1 単体テスト (`tests/test_pdf_parser.py`)

```python
def test_detect_page_offset():
    """オフセット検出機能のテスト"""
    
def test_convert_to_physical_page():
    """ページ番号変換機能のテスト"""
    
def test_manual_offset():
    """手動オフセット指定のテスト"""
```

#### 4.2 統合テスト

- 前付けがあるPDFでのend-to-endテスト
- 前付けがないPDFでの回帰テスト

## 実装順序

### Step 1: コア機能実装 (1-2時間)
1. `_detect_page_offset()` メソッドの実装
2. `_convert_to_physical_page()` メソッドの実装
3. PDFParserの初期化処理更新

### Step 2: 既存メソッドの修正 (30分)
1. `extract_chapters()` の修正
2. `extract_sections()` の修正

### Step 3: CLI対応 (30分)
1. コマンドライン引数の追加
2. PodcastGeneratorクラスの更新

### Step 4: ログ・テスト (1時間)
1. ログ出力の追加
2. 単体テストの作成
3. 統合テストの実行

## リスク軽減策

### 1. ページ番号検出の失敗
- フォールバック機能で現在の動作を維持
- 検出失敗をWARNINGレベルでログ出力
- 手動オフセット指定で回避可能

### 2. 性能への影響
- オフセット検出は最初の10-20ページのみ対象
- 検出結果をキャッシュして再利用
- 非同期処理で初期化時間を最小化

### 3. 既存機能への影響
- 既存のAPIインターフェースは変更しない
- 既存テストが通ることを確認
- オフセット0の場合は現在の動作と同一

## 成功基準

1. **機能性**: 前付けがあるPDFで正しい内容が抽出される
2. **互換性**: 既存のPDFでの動作に影響がない
3. **堅牢性**: オフセット検出に失敗してもエラーにならない
4. **使いやすさ**: 手動オフセット指定で問題を回避できる

## 次のステップ

このPlanの確認後、実装フェーズ（Imp）に移行し、以下の順序で実装を進めます：

1. Core機能の実装
2. 既存メソッドの修正  
3. CLI対応
4. テスト・デバッグ
5. ドキュメント更新

実装完了後はDebugフェーズで十分なテストを実施し、最後にDocフェーズで実装内容を文書化します。