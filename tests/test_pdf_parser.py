import json
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pdf_podcast.pdf_parser import Chapter, PDFParser, Section
from pdfminer.layout import LTTextContainer


class TestPDFParser:
    """PDFParserのテストクラス"""
    
    @pytest.fixture
    def sample_pdf_path(self):
        """テスト用PDFファイルのパス"""
        return "test/test.pdf"
    
    @pytest.fixture
    def mock_pdf_reader(self):
        """PDFReaderのモック"""
        reader = Mock()
        reader.pages = [Mock() for _ in range(10)]  # 10ページのPDF
        return reader
    
    def test_init_with_valid_pdf(self, sample_pdf_path):
        """有効なPDFファイルでの初期化テスト"""
        # test.pdfが存在する場合のみテスト
        if Path(sample_pdf_path).exists():
            parser = PDFParser(sample_pdf_path)
            assert parser.pdf_path == Path(sample_pdf_path)
            assert parser.gemini_model == "gemini-2.5-flash-preview-05-20"
    
    def test_init_with_invalid_pdf(self):
        """存在しないPDFファイルでの初期化テスト"""
        with pytest.raises(FileNotFoundError):
            PDFParser("nonexistent.pdf")
    
    @patch('pdf_podcast.pdf_parser.PdfReader')
    @patch('pdf_podcast.pdf_parser.Path')
    @pytest.mark.asyncio
    async def test_extract_chapters_with_llm_response(self, mock_path, mock_pdf_reader_class):
        """LLMレスポンスを使った章抽出のテスト"""
        # モックの設定
        mock_path.return_value.exists.return_value = True
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(50)]
        mock_pdf_reader_class.return_value = mock_reader
        
        parser = PDFParser("dummy.pdf")
        parser.total_pages = 50
        
        # LLMレスポンスのモック
        mock_llm_response = [
            {"title": "序章", "start_page": 1, "end_page": 5},
            {"title": "第1章 はじめに", "start_page": 6, "end_page": 20},
            {"title": "第2章 実装", "start_page": 21, "end_page": 40},
            {"title": "終章", "start_page": 41, "end_page": 50}
        ]
        
        with patch.object(parser, '_get_sample_text', return_value="sample text"):
            with patch.object(parser, '_detect_chapters_with_llm', return_value=mock_llm_response):
                with patch.object(parser, 'extract_text', side_effect=lambda s, e: f"Text from page {s} to {e}"):
                    chapters = await parser.extract_chapters()
        
        assert len(chapters) == 4
        assert chapters[0].title == "序章"
        assert chapters[0].start_page == 1
        assert chapters[0].end_page == 5
        assert chapters[0].text == "Text from page 1 to 5"
        
        assert chapters[1].title == "第1章 はじめに"
        assert chapters[1].start_page == 6
        assert chapters[1].end_page == 20
    
    @patch('pdf_podcast.pdf_parser.genai.GenerativeModel')
    @pytest.mark.asyncio
    async def test_detect_chapters_with_llm(self, mock_genai_model):
        """LLMによる章検出のテスト"""
        # Gemini APIレスポンスのモック
        mock_response = Mock()
        mock_response.text = '''```json
{
  "chapters": [
    {"title": "Introduction", "start_page": 1, "end_page": 10},
    {"title": "Chapter 1", "start_page": 11, "end_page": 30}
  ]
}
```'''
        
        mock_model_instance = Mock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_genai_model.return_value = mock_model_instance
        
        # PDFParserの部分的なインスタンス化
        parser = PDFParser.__new__(PDFParser)
        parser.gemini_model = "gemini-2.5-flash-preview-05-20"
        parser.total_pages = 50
        
        # rate_limiterのモック
        from unittest.mock import AsyncMock
        parser.rate_limiter = Mock()
        parser.rate_limiter.call_with_backoff = AsyncMock(return_value=mock_response)
        
        result = await parser._detect_chapters_with_llm("sample text")
        
        assert len(result) == 2
        assert result[0]["title"] == "Introduction"
        assert result[0]["start_page"] == 1
        assert result[0]["end_page"] == 10
    
    @patch('pdf_podcast.pdf_parser.genai.GenerativeModel')
    @pytest.mark.asyncio
    async def test_detect_chapters_with_llm_error(self, mock_genai_model):
        """LLMエラー時のフォールバックテスト"""
        # エラーを発生させる
        mock_genai_model.side_effect = Exception("API Error")
        
        parser = PDFParser.__new__(PDFParser)
        parser.gemini_model = "gemini-2.5-flash-preview-05-20"
        parser.total_pages = 100
        
        # rate_limiterのモック
        from unittest.mock import AsyncMock
        parser.rate_limiter = Mock()
        parser.rate_limiter.call_with_backoff = AsyncMock(side_effect=Exception("API Error"))
        
        result = await parser._detect_chapters_with_llm("sample text")
        
        # フォールバック: 全体を1章として扱う
        assert len(result) == 1
        assert result[0]["title"] == "全体"
        assert result[0]["start_page"] == 1
        assert result[0]["end_page"] == 100
    
    @patch('pdf_podcast.pdf_parser.extract_text')
    def test_extract_text(self, mock_extract_text):
        """テキスト抽出のテスト"""
        mock_extract_text.return_value = "Page content"
        
        parser = PDFParser.__new__(PDFParser)
        parser.pdf_path = Path("dummy.pdf")
        parser.total_pages = 20
        
        # 3ページ分のテキストを抽出
        text = parser.extract_text(5, 7)
        
        # extract_textが3回呼ばれることを確認
        assert mock_extract_text.call_count == 3
        assert text == "Page content\nPage content\nPage content"
    
    @patch('pdf_podcast.pdf_parser.PdfReader')
    @patch('pdf_podcast.pdf_parser.Path')
    @pytest.mark.asyncio
    async def test_extract_sections_with_llm_response(self, mock_path, mock_pdf_reader_class):
        """LLMレスポンスを使った中項目抽出のテスト"""
        # モックの設定
        mock_path.return_value.exists.return_value = True
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(50)]
        mock_pdf_reader_class.return_value = mock_reader
        
        parser = PDFParser("dummy.pdf")
        parser.total_pages = 50
        
        # LLMレスポンスのモック
        mock_llm_response = [
            {
                "title": "データ構造の基礎", 
                "section_number": "1.1", 
                "start_page": 1, 
                "end_page": 10,
                "parent_chapter": "第1章 プログラミング基礎"
            },
            {
                "title": "アルゴリズムの基本", 
                "section_number": "1.2", 
                "start_page": 11, 
                "end_page": 20,
                "parent_chapter": "第1章 プログラミング基礎"
            },
            {
                "title": "オブジェクト指向設計", 
                "section_number": "2.1", 
                "start_page": 21, 
                "end_page": 30,
                "parent_chapter": "第2章 設計パターン"
            }
        ]
        
        with patch.object(parser, '_get_sample_text', return_value="sample text"):
            with patch.object(parser, '_detect_sections_with_llm', return_value=mock_llm_response):
                with patch.object(parser, 'extract_text', side_effect=lambda s, e: f"Text from page {s} to {e}"):
                    sections = await parser.extract_sections()
        
        assert len(sections) == 3
        assert sections[0].title == "データ構造の基礎"
        assert sections[0].section_number == "1.1"
        assert sections[0].start_page == 1
        assert sections[0].end_page == 10
        assert sections[0].parent_chapter == "第1章 プログラミング基礎"
        assert sections[0].text == "Text from page 1 to 10"
        
        assert sections[1].title == "アルゴリズムの基本"
        assert sections[1].section_number == "1.2"
        assert sections[1].start_page == 11
        assert sections[1].end_page == 20
    
    @patch('pdf_podcast.pdf_parser.genai.GenerativeModel')
    @pytest.mark.asyncio
    async def test_detect_sections_with_llm(self, mock_genai_model):
        """LLMによる中項目検出のテスト"""
        # Gemini APIレスポンスのモック
        mock_response = Mock()
        mock_response.text = '''```json
{
  "sections": [
    {"title": "Introduction to Programming", "section_number": "1.1", "start_page": 1, "end_page": 10, "parent_chapter": "Chapter 1"},
    {"title": "Basic Concepts", "section_number": "1.2", "start_page": 11, "end_page": 20, "parent_chapter": "Chapter 1"}
  ]
}
```'''
        
        mock_model_instance = Mock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_genai_model.return_value = mock_model_instance
        
        # PDFParserの部分的なインスタンス化
        parser = PDFParser.__new__(PDFParser)
        parser.gemini_model = "gemini-2.5-flash-preview-05-20"
        parser.total_pages = 50
        
        # rate_limiterのモック
        from unittest.mock import AsyncMock
        parser.rate_limiter = Mock()
        parser.rate_limiter.call_with_backoff = AsyncMock(return_value=mock_response)
        
        result = await parser._detect_sections_with_llm("sample text")
        
        assert len(result) == 2
        assert result[0]["title"] == "Introduction to Programming"
        assert result[0]["section_number"] == "1.1"
        assert result[0]["start_page"] == 1
        assert result[0]["end_page"] == 10
        assert result[0]["parent_chapter"] == "Chapter 1"
    
    @patch('pdf_podcast.pdf_parser.PdfReader')
    @patch('pdf_podcast.pdf_parser.Path')
    def test_init_with_manual_offset(self, mock_path, mock_pdf_reader_class):
        """手動オフセット指定での初期化テスト"""
        # モックの設定
        mock_path.return_value.exists.return_value = True
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(50)]
        mock_pdf_reader_class.return_value = mock_reader
        
        # 手動オフセット指定
        parser = PDFParser("dummy.pdf", manual_offset=5)
        
        assert parser.page_offset == 5
        assert parser._offset_detected == True
    
    @patch('pdf_podcast.pdf_parser.PdfReader')
    @patch('pdf_podcast.pdf_parser.Path')
    def test_convert_to_physical_page(self, mock_path, mock_pdf_reader_class):
        """ページ番号変換機能のテスト"""
        # モックの設定
        mock_path.return_value.exists.return_value = True
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(50)]
        mock_pdf_reader_class.return_value = mock_reader
        
        # オフセット5で初期化
        parser = PDFParser("dummy.pdf", manual_offset=5)
        
        # 論理ページ1 → 物理ページ6
        assert parser._convert_to_physical_page(1) == 6
        # 論理ページ10 → 物理ページ15
        assert parser._convert_to_physical_page(10) == 15
        # 論理ページ50 → 物理ページ55
        assert parser._convert_to_physical_page(50) == 55
    
    def test_extract_number_from_text(self):
        """テキストからページ番号抽出のテスト"""
        parser = PDFParser.__new__(PDFParser)
        
        # 単独の数字
        assert parser._extract_number_from_text("123") == 123
        assert parser._extract_number_from_text("  42  ") == 42
        
        # ハイフンで囲まれた数字
        assert parser._extract_number_from_text("- 15 -") == 15
        
        # ページ/総ページ形式
        assert parser._extract_number_from_text("25 / 100") == 25
        
        # 無効なパターン
        assert parser._extract_number_from_text("Chapter 1") is None
        assert parser._extract_number_from_text("123abc") is None
        assert parser._extract_number_from_text("abc123def") is None
        assert parser._extract_number_from_text("") is None
        
        # 範囲外の数字
        assert parser._extract_number_from_text("0") is None
        assert parser._extract_number_from_text("10001") is None
    
    @patch('pdf_podcast.pdf_parser.extract_pages')
    @patch('pdf_podcast.pdf_parser.PdfReader')
    @patch('pdf_podcast.pdf_parser.Path')
    @pytest.mark.asyncio
    async def test_detect_page_offset_success(self, mock_path, mock_pdf_reader_class, mock_extract_pages):
        """ページオフセット検出成功のテスト"""
        # モックの設定
        mock_path.return_value.exists.return_value = True
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(50)]
        mock_pdf_reader_class.return_value = mock_reader
        
        # PDFページレイアウトのモック
        mock_text_element = Mock(spec=LTTextContainer)
        mock_text_element.get_text.return_value = "1"  # 1ページ目に"1"が記載
        mock_text_element.y0 = 50  # フッター領域（下部）
        
        mock_page_layout = Mock()
        mock_page_layout.height = 800
        mock_page_layout.__iter__ = lambda self: iter([mock_text_element])
        
        mock_extract_pages.return_value = [mock_page_layout]
        
        parser = PDFParser("dummy.pdf")
        
        # ページ1（物理）に"1"（論理）が記載されている場合、オフセットは0
        offset = await parser._detect_page_offset()
        assert offset == 0
        assert parser._offset_detected == True
    
    @patch('pdf_podcast.pdf_parser.extract_pages')
    @patch('pdf_podcast.pdf_parser.PdfReader')
    @patch('pdf_podcast.pdf_parser.Path')
    @pytest.mark.asyncio
    async def test_detect_page_offset_with_offset(self, mock_path, mock_pdf_reader_class, mock_extract_pages):
        """前付けありPDFでのオフセット検出テスト"""
        # モックの設定
        mock_path.return_value.exists.return_value = True
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(50)]
        mock_pdf_reader_class.return_value = mock_reader
        
        # 物理ページ6に論理ページ"1"が記載されている場合
        mock_text_elements = []
        for i in range(20):  # 最初の20ページをチェック
            mock_text_element = Mock(spec=LTTextContainer)
            if i == 5:  # 物理ページ6（0ベースで5）
                mock_text_element.get_text.return_value = "1"  # 論理ページ1
            elif i == 6:  # 物理ページ7（0ベースで6）
                mock_text_element.get_text.return_value = "2"  # 論理ページ2
            else:
                mock_text_element.get_text.return_value = "header text"  # その他
            mock_text_element.y0 = 50  # フッター領域
            mock_text_elements.append(mock_text_element)
        
        def mock_extract_pages_func(*args, **kwargs):
            page_numbers = kwargs.get('page_numbers', [0])
            page_idx = page_numbers[0]
            if page_idx < len(mock_text_elements):
                mock_page_layout = Mock()
                mock_page_layout.height = 800
                mock_page_layout.__iter__ = lambda self: iter([mock_text_elements[page_idx]])
                return [mock_page_layout]
            return []
        
        mock_extract_pages.side_effect = mock_extract_pages_func
        
        parser = PDFParser("dummy.pdf")
        
        # 物理ページ6に論理ページ1が記載 → オフセット = 6 - 1 = 5
        offset = await parser._detect_page_offset()
        assert offset == 5
        assert parser._offset_detected == True
    
    @patch('pdf_podcast.pdf_parser.extract_pages')
    @patch('pdf_podcast.pdf_parser.PdfReader')
    @patch('pdf_podcast.pdf_parser.Path')
    @pytest.mark.asyncio
    async def test_detect_page_offset_failure(self, mock_path, mock_pdf_reader_class, mock_extract_pages):
        """ページオフセット検出失敗のテスト"""
        # モックの設定
        mock_path.return_value.exists.return_value = True
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(50)]
        mock_pdf_reader_class.return_value = mock_reader
        
        # ページ番号が見つからない場合
        mock_extract_pages.side_effect = Exception("PDF processing error")
        
        parser = PDFParser("dummy.pdf")
        
        # エラー時はオフセット0でフォールバック
        offset = await parser._detect_page_offset()
        assert offset == 0
        assert parser._offset_detected == True
    
    @patch('pdf_podcast.pdf_parser.PdfReader')
    @patch('pdf_podcast.pdf_parser.Path')
    @pytest.mark.asyncio
    async def test_extract_chapters_with_offset(self, mock_path, mock_pdf_reader_class):
        """オフセットありでの章抽出テスト"""
        # モックの設定
        mock_path.return_value.exists.return_value = True
        mock_reader = Mock()
        mock_reader.pages = [Mock() for _ in range(50)]
        mock_pdf_reader_class.return_value = mock_reader
        
        # オフセット5で初期化
        parser = PDFParser("dummy.pdf", manual_offset=5)
        parser.total_pages = 50
        
        # LLMレスポンスのモック（論理ページ番号）
        mock_llm_response = [
            {"title": "第1章", "start_page": 1, "end_page": 10},  # 論理ページ
            {"title": "第2章", "start_page": 11, "end_page": 20},  # 論理ページ
        ]
        
        extracted_pages = []
        def mock_extract_text(start, end):
            extracted_pages.append((start, end))
            return f"Text from page {start} to {end}"
        
        with patch.object(parser, '_get_sample_text', return_value="sample text"):
            with patch.object(parser, '_detect_chapters_with_llm', return_value=mock_llm_response):
                with patch.object(parser, 'extract_text', side_effect=mock_extract_text):
                    chapters = await parser.extract_chapters()
        
        # 章データの確認
        assert len(chapters) == 2
        assert chapters[0].title == "第1章"
        assert chapters[0].start_page == 1  # manifestには論理ページを保存
        assert chapters[0].end_page == 10
        
        # 実際にextract_textに渡されたページは物理ページ番号
        assert extracted_pages[0] == (6, 15)  # 論理1-10 → 物理6-15
        assert extracted_pages[1] == (16, 25)  # 論理11-20 → 物理16-25