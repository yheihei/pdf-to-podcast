import json
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pdf_podcast.pdf_parser import Chapter, PDFParser, Section


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