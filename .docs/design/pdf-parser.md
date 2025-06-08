# FR-1: PDF解析機能の設計書

## 実装概要

FR-1（PDF解析：目次や章パターンでの章検出とテキスト抽出）を、LLM（Gemini）を使用したアプローチで実装しました。

## アーキテクチャ

### モジュール構成

```
pdf_podcast/
├── __init__.py
├── pdf_parser.py       # PDF解析のメインモジュール
tests/
├── __init__.py
├── test_pdf_parser.py  # ユニットテスト
```

### 主要クラス

#### 1. Chapter データクラス
```python
@dataclass
class Chapter:
    title: str        # 章のタイトル
    start_page: int   # 開始ページ（1から始まる）
    end_page: int     # 終了ページ（含む）
    text: str = ""    # 抽出されたテキスト
```

#### 2. PDFParser クラス
PDFファイルから章を検出し、テキストを抽出するメインクラス。

主要メソッド：
- `__init__(pdf_path, gemini_model)`: 初期化
- `extract_chapters()`: 章の検出とテキスト抽出
- `extract_text(start_page, end_page)`: 指定ページ範囲のテキスト抽出
- `_detect_chapters_with_llm(sample_text)`: LLMによる章構造解析

## 実装詳細

### 1. LLMベースの章検出

従来のルールベース手法の代わりに、Gemini APIを使用して柔軟な章検出を実現：

```python
def _detect_chapters_with_llm(self, sample_text: str) -> List[dict]:
    # PDFの先頭部分（最大20ページ）をGeminiに送信
    # 章タイトルとページ範囲を構造化出力（JSON）で取得
```

#### プロンプト設計
- 目次の優先的な使用
- 序章、エピローグ、付録の認識
- 目次がない場合の本文からの推測
- ページ番号の正確な抽出

### 2. テキスト抽出

`pdfminer.six`を使用した高精度なテキスト抽出：
- ページ単位での処理
- レイアウト情報の保持
- エラーハンドリング（破損ページのスキップ）

### 3. エラーハンドリング

3つのレベルでのエラー処理：
1. **ファイルレベル**: PDFファイルの存在確認
2. **APIレベル**: Gemini APIエラーのキャッチとフォールバック
3. **ページレベル**: 個別ページの抽出エラーの処理

フォールバック戦略：
- LLMエラー時は全体を1章として扱う
- ページ抽出エラー時は該当ページをスキップ

## 技術選定の理由

### LLMアプローチの採用理由
1. **柔軟性**: 様々な書籍フォーマットに対応可能
2. **文脈理解**: 「序章」「間奏」などの特殊な章も認識
3. **メンテナンス性**: ルールの追加・更新が不要
4. **将来性**: モデルの改善により精度が向上

### 使用ライブラリ
- **google-generativeai**: Gemini APIクライアント
- **pdfminer.six**: 高精度なPDFテキスト抽出
- **pypdf**: PDFメタデータの読み取り

## テスト戦略

### ユニットテスト
1. **初期化テスト**: 有効/無効なPDFパスでの動作確認
2. **章検出テスト**: LLMレスポンスのモック使用
3. **エラーハンドリングテスト**: APIエラー時のフォールバック
4. **テキスト抽出テスト**: ページ範囲指定の動作確認

### テストカバレッジ
- 全メソッドのテストを実装
- エラーケースとフォールバックのテスト
- モックを使用したAPIレスポンスのテスト

## 今後の拡張性

1. **キャッシュ機能**: 同じPDFの再解析を高速化
2. **並列処理**: 大きなPDFの処理時間短縮
3. **カスタムプロンプト**: ユーザー定義の章検出ルール
4. **複数モデル対応**: Gemini以外のLLM対応

## 使用方法

```python
from pdf_podcast.pdf_parser import PDFParser
import google.generativeai as genai

# API設定
genai.configure(api_key="YOUR_API_KEY")

# PDF解析
parser = PDFParser("book.pdf")
chapters = parser.extract_chapters()

# 結果の利用
for chapter in chapters:
    print(f"{chapter.title}: {chapter.start_page}-{chapter.end_page}")
```