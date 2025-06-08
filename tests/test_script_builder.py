"""Tests for script_builder module."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pdf_podcast.script_builder import ScriptBuilder, LectureScript, SectionScript
from pdf_podcast.pdf_parser import Section


class TestScriptBuilder:
    """Test cases for ScriptBuilder class."""
    
    @pytest.fixture
    def mock_genai(self):
        """Mock google.generativeai module."""
        with patch('pdf_podcast.script_builder.genai') as mock:
            yield mock
    
    @pytest.fixture
    def script_builder(self, mock_genai):
        """Create ScriptBuilder instance with mocked API."""
        builder = ScriptBuilder(api_key="test-api-key", model_name="test-model")
        # Mock rate limiter
        builder.rate_limiter = Mock()
        builder.rate_limiter.call_with_backoff = AsyncMock()
        return builder
    
    def test_init(self, mock_genai):
        """Test ScriptBuilder initialization."""
        builder = ScriptBuilder(api_key="test-key", model_name="custom-model")
        
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        mock_genai.GenerativeModel.assert_called_once_with("custom-model")
    
    @pytest.mark.asyncio
    async def test_generate_lecture_script_success(self, script_builder):
        """Test successful lecture script generation."""
        # Mock response
        mock_response = Mock()
        mock_response.text = """みなさん、こんにちは。今日は第1章について学習していきましょう。

この章では、プログラミングの基本概念について説明します。特に重要なのは、変数とデータ型の理解です。

変数とは、データを格納するための箱のようなものです。Pythonでは、数値、文字列、リストなど様々なデータ型を扱うことができます。

まとめとして、変数とデータ型は프로그래밍の基礎となる重要な概念です。次回はより詳しく学習していきましょう。"""
        
        script_builder.rate_limiter.call_with_backoff.return_value = mock_response
        
        # Generate script
        result = await script_builder.generate_lecture_script(
            chapter_title="第1章: 導入",
            chapter_content="これは第1章の内容です。"
        )
        
        # Assertions
        assert isinstance(result, LectureScript)
        assert result.chapter_title == "第1章: 導入"
        assert result.total_chars > 0
        assert "みなさん、こんにちは" in result.content
    
    @pytest.mark.asyncio
    async def test_generate_section_script_success(self, script_builder):
        """Test successful section script generation."""
        # Create mock section
        section = Section(
            title="データ構造の基礎",
            section_number="1.1",
            start_page=1,
            end_page=5,
            text="データ構造についての説明...",
            parent_chapter="第1章 プログラミング基礎"
        )
        
        # Mock response
        mock_response = Mock()
        mock_response.text = """みなさん、1.1 データ構造の基礎について学習しましょう。

この中項目では、プログラミングにおけるデータ構造の基本概念を学びます。データ構造とは、データを効率的に格納・操作するための仕組みです。

主なデータ構造には、配列、リスト、スタック、キューなどがあります。それぞれに特徴があり、用途に応じて使い分けることが重要です。

以上で、データ構造の基礎について理解を深めることができました。次の中項目では、より具体的な実装について学習していきます。"""
        
        script_builder.rate_limiter.call_with_backoff.return_value = mock_response
        
        # Generate script
        result = await script_builder.generate_section_script(section)
        
        # Assertions
        assert isinstance(result, SectionScript)
        assert result.section_title == "データ構造の基礎"
        assert result.section_number == "1.1"
        assert result.parent_chapter == "第1章 プログラミング基礎"
        assert result.total_chars > 0
        assert "1.1 データ構造の基礎" in result.content
    
    @pytest.mark.asyncio
    async def test_generate_section_script_with_context(self, script_builder):
        """Test section script generation with context."""
        # Create mock section
        section = Section(
            title="アルゴリズムの基本",
            section_number="1.2",
            start_page=6,
            end_page=10,
            text="アルゴリズムについての説明...",
            parent_chapter="第1章 プログラミング基礎"
        )
        
        # Create context
        context = {
            "previous_section": {
                "section_number": "1.1",
                "title": "データ構造の基礎"
            },
            "next_section": {
                "section_number": "1.3",
                "title": "プログラム設計"
            }
        }
        
        # Mock response
        mock_response = Mock()
        mock_response.text = """みなさん、1.2 アルゴリズムの基本について学習しましょう。

前回の1.1でデータ構造について学びましたが、今回はそのデータを効率的に処理するアルゴリズムについて説明します。

アルゴリズムとは、問題を解決するための手順や方法のことです。良いアルゴリズムは、計算時間が短く、メモリ使用量が少ないという特徴があります。

次回の1.3では、これらの知識を活用したプログラム設計について学習します。"""
        
        script_builder.rate_limiter.call_with_backoff.return_value = mock_response
        
        # Generate script
        result = await script_builder.generate_section_script(section, context)
        
        # Assertions
        assert isinstance(result, SectionScript)
        assert result.section_number == "1.2"
        assert "1.1" in result.content  # Context should be reflected
    
    @pytest.mark.asyncio
    async def test_generate_scripts_for_sections(self, script_builder):
        """Test batch script generation for multiple sections."""
        # Create mock sections
        sections = [
            Section(
                title="データ構造",
                section_number="1.1",
                start_page=1,
                end_page=5,
                text="データ構造の内容",
                parent_chapter="第1章"
            ),
            Section(
                title="アルゴリズム",
                section_number="1.2",
                start_page=6,
                end_page=10,
                text="アルゴリズムの内容",
                parent_chapter="第1章"
            )
        ]
        
        # Mock responses
        mock_response1 = Mock()
        mock_response1.text = "みなさん、1.1について説明します。データ構造は重要です。"
        
        mock_response2 = Mock()
        mock_response2.text = "みなさん、1.2について説明します。アルゴリズムは重要です。"
        
        script_builder.rate_limiter.call_with_backoff.side_effect = [
            mock_response1,
            mock_response2
        ]
        
        # Generate scripts
        scripts = await script_builder.generate_scripts_for_sections(sections)
        
        # Assertions
        assert len(scripts) == 2
        assert "1.1_データ構造" in scripts
        assert "1.2_アルゴリズム" in scripts
        assert isinstance(scripts["1.1_データ構造"], SectionScript)
        assert isinstance(scripts["1.2_アルゴリズム"], SectionScript)
    
    def test_create_section_prompt(self, script_builder):
        """Test section prompt creation."""
        section = Section(
            title="テスト中項目",
            section_number="2.1",
            start_page=1,
            end_page=5,
            text="中項目の内容",
            parent_chapter="第2章 テスト章"
        )
        
        context = {
            "previous_section": {
                "section_number": "1.3",
                "title": "前の中項目"
            }
        }
        
        prompt = script_builder._create_section_prompt(section, context)
        
        assert "2.1" in prompt
        assert "テスト中項目" in prompt
        assert "第2章 テスト章" in prompt
        assert "中項目の内容" in prompt
        assert "1.3" in prompt
        assert "前の中項目" in prompt
        assert "1500文字以内" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_section_script_api_error(self, script_builder):
        """Test handling of API errors in section script generation."""
        section = Section(
            title="エラーテスト",
            section_number="1.1",
            start_page=1,
            end_page=5,
            text="テスト内容",
            parent_chapter="第1章"
        )
        
        script_builder.rate_limiter.call_with_backoff.side_effect = Exception("API Error")
        
        with pytest.raises(Exception) as exc_info:
            await script_builder.generate_section_script(section)
        
        assert "API Error" in str(exc_info.value)