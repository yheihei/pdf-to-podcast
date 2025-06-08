import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import google.generativeai as genai
from pdfminer.high_level import extract_pages, extract_text
from pdfminer.layout import LTTextContainer
from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """章の情報を保持するデータクラス"""
    title: str
    start_page: int
    end_page: int
    text: str = ""


class PDFParser:
    """PDFファイルから章を検出し、テキストを抽出するクラス"""
    
    def __init__(self, pdf_path: str, gemini_model: str = "gemini-2.5-flash-preview-05-20"):
        """
        PDFパーサーを初期化
        
        Args:
            pdf_path: 解析するPDFファイルのパス
            gemini_model: 使用するGeminiモデル
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.gemini_model = gemini_model
        self.pdf_reader = PdfReader(str(self.pdf_path))
        self.total_pages = len(self.pdf_reader.pages)
        
    def extract_chapters(self) -> List[Chapter]:
        """
        LLMを使用して章を検出し、各章のテキストを抽出
        
        Returns:
            Chapter オブジェクトのリスト
        """
        logger.info(f"Extracting chapters from {self.pdf_path}")
        
        # PDFから章構造を検出するためのサンプルテキストを取得
        sample_text = self._get_sample_text()
        
        # LLMで章を検出
        chapter_info = self._detect_chapters_with_llm(sample_text)
        
        # 各章のテキストを抽出
        chapters = []
        for ch in chapter_info:
            text = self.extract_text(ch["start_page"], ch["end_page"])
            chapter = Chapter(
                title=ch["title"],
                start_page=ch["start_page"],
                end_page=ch["end_page"],
                text=text
            )
            chapters.append(chapter)
            logger.info(f"Extracted chapter: {chapter.title} (pages {chapter.start_page}-{chapter.end_page})")
        
        return chapters
    
    def extract_text(self, start_page: int, end_page: int) -> str:
        """
        指定ページ範囲のテキストを抽出
        
        Args:
            start_page: 開始ページ（1から始まる）
            end_page: 終了ページ（含む）
            
        Returns:
            抽出されたテキスト
        """
        text_parts = []
        
        # pdfminerはページ番号が0から始まるため調整
        for page_num in range(start_page - 1, min(end_page, self.total_pages)):
            try:
                page_text = extract_text(
                    str(self.pdf_path),
                    page_numbers=[page_num],
                    maxpages=1
                )
                text_parts.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
        
        return "\n".join(text_parts)
    
    def _get_sample_text(self, max_pages: int = 20) -> str:
        """
        章構造を検出するためのサンプルテキストを取得
        
        Args:
            max_pages: 取得する最大ページ数
            
        Returns:
            サンプルテキスト
        """
        sample_pages = min(max_pages, self.total_pages)
        sample_text = extract_text(
            str(self.pdf_path),
            maxpages=sample_pages
        )
        
        # テキストが長すぎる場合は切り詰める（トークン制限対策）
        max_chars = 50000
        if len(sample_text) > max_chars:
            sample_text = sample_text[:max_chars]
            
        return sample_text
    
    def _detect_chapters_with_llm(self, sample_text: str) -> List[dict]:
        """
        Gemini APIで章構造を解析
        
        Args:
            sample_text: 分析対象のテキスト
            
        Returns:
            章情報のリスト
        """
        try:
            model = genai.GenerativeModel(self.gemini_model)
            
            prompt = f"""あなたはPDF文書の構造を解析する専門家です。
以下のPDFテキストから章（チャプター）を検出してください。

要件：
1. 各章のタイトルとページ番号を抽出
2. 序章、エピローグ、付録なども含める
3. 目次がある場合は優先的に使用
4. 目次がない場合は本文から推測
5. ページ番号は本文中に記載されているページ番号を使用

重要：
- 総ページ数は {self.total_pages} ページです
- 各章の終了ページは次の章の開始ページ-1、最後の章は総ページ数とします

出力は以下のJSON形式で返してください：
{{
  "chapters": [
    {{"title": "序章", "start_page": 1, "end_page": 10}},
    {{"title": "第1章 はじめに", "start_page": 11, "end_page": 25}},
    ...
  ]
}}

PDFテキスト：
{sample_text}
"""
            
            response = model.generate_content(prompt)
            result_text = response.text.strip()
            
            # JSONを抽出（マークダウンコードブロックに囲まれている場合も考慮）
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            elif "```" in result_text:
                start = result_text.find("```") + 3
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            
            result = json.loads(result_text)
            chapters = result.get("chapters", [])
            
            # 章が検出されなかった場合のフォールバック
            if not chapters:
                logger.warning("No chapters detected, treating entire PDF as single chapter")
                chapters = [{
                    "title": "全体",
                    "start_page": 1,
                    "end_page": self.total_pages
                }]
            
            return chapters
            
        except Exception as e:
            logger.error(f"Failed to detect chapters with LLM: {e}")
            # エラー時のフォールバック
            return [{
                "title": "全体",
                "start_page": 1,
                "end_page": self.total_pages
            }]