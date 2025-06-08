# FR-1: PDF解析機能の実装計画

## 概要
PDFファイルから章（チャプター）を検出し、各章のテキストを抽出する機能を実装する。

## 実装内容

### 1. モジュール構成
- `pdf_podcast/pdf_parser.py`: PDF解析のメインモジュール
- 必要なライブラリ: `pdfminer.six`, `pypdf`, `google-generativeai`

### 2. 主要機能

#### 2.1 章の検出ロジック（LLMベース）
- PDFの全文または先頭部分をGemini APIに送信
- プロンプトで章タイトルとページ範囲の抽出を指示
- 構造化出力（JSON）で章情報を取得
- 目次、セクション、エピローグなども柔軟に認識

#### 2.2 テキスト抽出
- 各章のページ範囲を特定
- pdfminer.sixを使用してテキストを抽出
- レイアウト解析による適切な読み順の維持

### 3. API設計

```python
class PDFParser:
    def __init__(self, pdf_path: str, gemini_model: str = "gemini-2.5-flash-preview-05-20"):
        """PDFファイルを読み込み、Gemini APIクライアントを初期化"""
        
    def extract_chapters(self) -> List[Chapter]:
        """LLMを使用して章を検出してリストで返す"""
        
    def extract_text(self, start_page: int, end_page: int) -> str:
        """指定ページ範囲のテキストを抽出"""
        
    def _detect_chapters_with_llm(self, sample_text: str) -> List[dict]:
        """Gemini APIで章構造を解析"""

@dataclass
class Chapter:
    title: str
    start_page: int
    end_page: int
    text: str
```

### 4. LLMプロンプト設計

```
あなたはPDF文書の構造を解析する専門家です。
以下のPDFテキストから章（チャプター）を検出してください。

要件：
1. 各章のタイトルとページ番号を抽出
2. 序章、エピローグ、付録なども含める
3. 目次がある場合は優先的に使用
4. 目次がない場合は本文から推測

出力形式（JSON）:
{
  "chapters": [
    {"title": "序章", "start_page": 1, "end_page": 10},
    {"title": "第1章 はじめに", "start_page": 11, "end_page": 25},
    ...
  ]
}
```

### 5. エラーハンドリング
- PDF読み込みエラー
- Gemini APIエラー（レート制限、タイムアウト）
- 章が検出できない場合のフォールバック（全体を1章として扱う）
- 破損したPDFの処理

### 6. テスト方針
- サンプルPDF（test/test.pdf）を使用した単体テスト
- LLMモックを使用した章検出ロジックのテスト
- テキスト抽出の正確性検証
- API エラー時のリトライ動作確認