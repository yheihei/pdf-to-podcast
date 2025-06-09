import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import google.generativeai as genai
from pdfminer.high_level import extract_pages, extract_text
from pdfminer.layout import LTTextContainer
from pypdf import PdfReader

from .rate_limiter import GeminiRateLimiter, RateLimitConfig

logger = logging.getLogger(__name__)


@dataclass
class Section:
    """中項目の情報を保持するデータクラス"""
    title: str
    section_number: str  # "1.1", "2.3" など
    start_page: int
    end_page: int
    text: str = ""
    parent_chapter: str = ""  # 所属する章のタイトル


@dataclass
class Chapter:
    """章の情報を保持するデータクラス"""
    title: str
    start_page: int
    end_page: int
    text: str = ""
    sections: List['Section'] = None
    
    def __post_init__(self):
        if self.sections is None:
            self.sections = []


class PDFParser:
    """PDFファイルから章を検出し、テキストを抽出するクラス"""
    
    def __init__(self, pdf_path: str, gemini_model: str = "gemini-2.5-flash-preview-05-20", api_key: Optional[str] = None, manual_offset: Optional[int] = None):
        """
        PDFパーサーを初期化
        
        Args:
            pdf_path: 解析するPDFファイルのパス
            gemini_model: 使用するGeminiモデル
            api_key: Google API キー（省略時は環境変数から取得）
            manual_offset: 手動ページオフセット（論理ページ番号 + オフセット = 物理ページ番号）
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.gemini_model = gemini_model
        self.pdf_reader = PdfReader(str(self.pdf_path))
        self.total_pages = len(self.pdf_reader.pages)
        
        # API キーの設定
        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        else:
            logger.warning("Google API key not found. Please set GOOGLE_API_KEY environment variable.")
        
        # レートリミッターの初期化
        rate_limit_config = RateLimitConfig(rpm_limit=15)  # Free tier
        self.rate_limiter = GeminiRateLimiter(rate_limit_config)
        
        # ページオフセットの設定
        if manual_offset is not None:
            self._page_offset = manual_offset
            self._offset_detected = True
            logger.info(f"Manual page offset set: {manual_offset}")
        else:
            # 自動検出（非同期なので後で実行）
            self._page_offset = 0  # 初期値
            self._offset_detected = False
        
    async def extract_chapters(self) -> List[Chapter]:
        """
        LLMを使用して章を検出し、各章のテキストを抽出
        
        Returns:
            Chapter オブジェクトのリスト
        """
        logger.info(f"Extracting chapters from {self.pdf_path}")
        
        # ページオフセットを検出（自動検出の場合のみ）
        if not self._offset_detected:
            await self._detect_page_offset()
        
        # PDFから章構造を検出するためのサンプルテキストを取得
        sample_text = self._get_sample_text()
        
        # LLMで章を検出
        chapter_info = await self._detect_chapters_with_llm(sample_text)
        
        # 各章のテキストを抽出
        chapters = []
        for ch in chapter_info:
            # LLMから返された論理ページ番号を物理ページ番号に変換
            physical_start = self._convert_to_physical_page(ch["start_page"])
            physical_end = self._convert_to_physical_page(ch["end_page"])
            
            logger.debug(f"Converting chapter '{ch['title']}': logical pages {ch['start_page']}-{ch['end_page']} -> physical pages {physical_start}-{physical_end}")
            
            text = self.extract_text(physical_start, physical_end)
            chapter = Chapter(
                title=ch["title"],
                start_page=ch["start_page"],  # manifestには論理ページ番号を保存
                end_page=ch["end_page"],      # manifestには論理ページ番号を保存
                text=text
            )
            chapters.append(chapter)
            logger.info(f"Extracted chapter: {chapter.title} (logical pages {chapter.start_page}-{chapter.end_page}, physical pages {physical_start}-{physical_end})")
        
        return chapters
    
    async def extract_sections(self) -> List[Section]:
        """
        LLMを使用して中項目を検出し、各中項目のテキストを抽出
        
        Returns:
            Section オブジェクトのリスト
        """
        logger.info(f"Extracting sections from {self.pdf_path}")
        
        # ページオフセットを検出（自動検出の場合のみ）
        if not self._offset_detected:
            await self._detect_page_offset()
        
        # PDFから中項目構造を検出するためのサンプルテキストを取得
        sample_text = self._get_sample_text()
        
        # LLMで中項目を検出
        section_info = await self._detect_sections_with_llm(sample_text)
        
        # 各中項目のテキストを抽出
        sections = []
        for sec in section_info:
            # LLMから返された論理ページ番号を物理ページ番号に変換
            physical_start = self._convert_to_physical_page(sec["start_page"])
            physical_end = self._convert_to_physical_page(sec["end_page"])
            
            logger.debug(f"Converting section '{sec['title']}': logical pages {sec['start_page']}-{sec['end_page']} -> physical pages {physical_start}-{physical_end}")
            
            text = self.extract_text(physical_start, physical_end)
            section = Section(
                title=sec["title"],
                section_number=sec.get("section_number", ""),
                start_page=sec["start_page"],  # manifestには論理ページ番号を保存
                end_page=sec["end_page"],      # manifestには論理ページ番号を保存
                text=text,
                parent_chapter=sec.get("parent_chapter", "")
            )
            sections.append(section)
            logger.info(f"Extracted section: {section.section_number} {section.title} (logical pages {section.start_page}-{section.end_page}, physical pages {physical_start}-{physical_end})")
        
        return sections
    
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
    
    async def _detect_chapters_with_llm(self, sample_text: str) -> List[dict]:
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
            
            # Use rate limiter for API call
            response = await self.rate_limiter.call_with_backoff(
                model.generate_content, prompt
            )
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
    
    async def _detect_sections_with_llm(self, sample_text: str) -> List[dict]:
        """
        Gemini APIで中項目構造を解析
        
        Args:
            sample_text: 分析対象のテキスト
            
        Returns:
            中項目情報のリスト
        """
        try:
            model = genai.GenerativeModel(self.gemini_model)
            
            prompt = f"""あなたはPDF文書の構造を解析する専門家です。
以下のPDFテキストから中項目（サブセクション）を検出してください。

要件：
1. 各中項目のタイトル、番号（1.1、1.2、2.1など）、ページ番号を抽出
2. 章レベル（第1章、第2章など）ではなく、その下の中項目レベルを対象とする
3. 目次がある場合は優先的に使用
4. 目次がない場合は本文から推測
5. ページ番号は本文中に記載されているページ番号を使用
6. 所属する章の情報も含める

重要：
- 総ページ数は {self.total_pages} ページです
- 各中項目の終了ページは次の中項目の開始ページ-1、最後の中項目は該当章の終了ページとします
- 中項目が検出されない場合は、章レベルでの抽出にフォールバックします

出力は以下のJSON形式で返してください：
{{
  "sections": [
    {{"title": "データ構造の基礎", "section_number": "1.1", "start_page": 1, "end_page": 5, "parent_chapter": "第1章 プログラミング基礎"}},
    {{"title": "アルゴリズムの基本", "section_number": "1.2", "start_page": 6, "end_page": 15, "parent_chapter": "第1章 プログラミング基礎"}},
    {{"title": "オブジェクト指向設計", "section_number": "2.1", "start_page": 16, "end_page": 25, "parent_chapter": "第2章 設計パターン"}},
    ...
  ]
}}

PDFテキスト：
{sample_text}
"""
            
            # Use rate limiter for API call
            response = await self.rate_limiter.call_with_backoff(
                model.generate_content, prompt
            )
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
            sections = result.get("sections", [])
            
            # 中項目が検出されなかった場合のフォールバック（章レベルで抽出）
            if not sections:
                logger.warning("No sections detected, falling back to chapter-level extraction")
                chapter_info = await self._detect_chapters_with_llm(sample_text)
                sections = []
                for i, ch in enumerate(chapter_info):
                    sections.append({
                        "title": ch["title"],
                        "section_number": f"{i+1}.0",
                        "start_page": ch["start_page"],
                        "end_page": ch["end_page"],
                        "parent_chapter": ch["title"]
                    })
            
            return sections
            
        except Exception as e:
            logger.error(f"Failed to detect sections with LLM: {e}")
            # エラー時のフォールバック（章レベルで抽出）
            logger.warning("Falling back to chapter-level extraction due to error")
            try:
                chapter_info = await self._detect_chapters_with_llm(sample_text)
                sections = []
                for i, ch in enumerate(chapter_info):
                    sections.append({
                        "title": ch["title"],
                        "section_number": f"{i+1}.0",
                        "start_page": ch["start_page"],
                        "end_page": ch["end_page"],
                        "parent_chapter": ch["title"]
                    })
                return sections
            except Exception as fallback_error:
                logger.error(f"Fallback to chapters also failed: {fallback_error}")
                return [{
                    "title": "全体",
                    "section_number": "1.0",
                    "start_page": 1,
                    "end_page": self.total_pages,
                    "parent_chapter": "全体"
                }]
    
    @property
    def page_offset(self) -> int:
        """検出されたページオフセット値を返す"""
        return getattr(self, '_page_offset', 0)
    
    def _convert_to_physical_page(self, logical_page: int) -> int:
        """
        論理ページ番号を物理ページ番号に変換
        
        Args:
            logical_page: 論理ページ番号（本の中でのページ番号）
            
        Returns:
            物理ページ番号（PDFファイル内の実際のページ番号）
        """
        return logical_page + self.page_offset
    
    async def _detect_page_offset(self) -> int:
        """
        PDFの物理ページ番号と論理ページ番号のオフセットを検出
        
        実装方針:
        - 最初の10-20ページを対象
        - pdfminerのextract_pagesでページごとのテキスト要素を取得
        - 正規表現でページ番号パターンを検出（単独の数字、ページフッター/ヘッダー内の数字）
        - 複数ページで一貫性を確認してオフセットを算出
        - 検出失敗時は0を返す（フォールバック）
        
        Returns:
            オフセット値（物理ページ番号 = 論理ページ番号 + オフセット）
        """
        if self._offset_detected:
            return self._page_offset
        
        try:
            logger.info("Detecting page number offset...")
            
            # 検査対象のページ数（最大20ページ、総ページ数が少ない場合はそれに合わせる）
            max_check_pages = min(20, self.total_pages)
            offsets = []
            
            for page_idx in range(max_check_pages):
                try:
                    # ページからテキスト要素を抽出
                    page_layout = list(extract_pages(str(self.pdf_path), page_numbers=[page_idx], maxpages=1))
                    if not page_layout:
                        continue
                    
                    # ページ上部・下部のテキスト要素からページ番号を探す
                    page_number = self._extract_page_number_from_layout(page_layout[0], page_idx + 1)
                    
                    if page_number is not None:
                        # オフセット計算: 物理ページ番号 = 論理ページ番号 + オフセット
                        # オフセット = 物理ページ番号 - 論理ページ番号
                        calculated_offset = (page_idx + 1) - page_number
                        offsets.append(calculated_offset)
                        logger.debug(f"Page {page_idx + 1}: found logical page {page_number}, offset={calculated_offset}")
                
                except Exception as e:
                    logger.debug(f"Failed to process page {page_idx + 1}: {e}")
                    continue
            
            # 一貫したオフセットを検出
            if offsets:
                # 最も頻繁に現れるオフセット値を選択
                from collections import Counter
                offset_counts = Counter(offsets)
                detected_offset = offset_counts.most_common(1)[0][0]
                
                # 一貫性を確認（同じオフセットが少なくとも2回以上出現）
                if offset_counts[detected_offset] >= 2:
                    self._page_offset = detected_offset
                    self._offset_detected = True
                    logger.info(f"Page offset detected: {detected_offset} (logical page = physical page - {detected_offset})")
                    return detected_offset
                else:
                    logger.warning(f"Inconsistent page numbering detected. Using default offset 0.")
            else:
                logger.warning("No page numbers found. Using default offset 0.")
            
            # フォールバック
            self._page_offset = 0
            self._offset_detected = True
            return 0
            
        except Exception as e:
            logger.error(f"Failed to detect page offset: {e}")
            self._page_offset = 0
            self._offset_detected = True
            return 0
    
    def _extract_page_number_from_layout(self, page_layout, physical_page_num: int) -> Optional[int]:
        """
        ページレイアウトからページ番号を抽出
        
        Args:
            page_layout: PDFページのレイアウト情報
            physical_page_num: 物理ページ番号（デバッグ用）
            
        Returns:
            検出されたページ番号（論理ページ番号）、見つからない場合はNone
        """
        try:
            # ページの高さを取得
            page_height = page_layout.height if hasattr(page_layout, 'height') else 800
            
            # ヘッダー・フッター領域の定義（上下10%の領域）
            header_threshold = page_height * 0.9
            footer_threshold = page_height * 0.1
            
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    text = element.get_text().strip()
                    y_position = element.y0
                    
                    # ヘッダーまたはフッター領域のテキストをチェック
                    if y_position >= header_threshold or y_position <= footer_threshold:
                        page_number = self._extract_number_from_text(text)
                        if page_number is not None:
                            # 妥当性チェック（物理ページ番号から大きく離れていない）
                            if abs(page_number - physical_page_num) <= 20:
                                return page_number
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting page number from layout: {e}")
            return None
    
    def _extract_number_from_text(self, text: str) -> Optional[int]:
        """
        テキストからページ番号として妥当な数字を抽出
        
        Args:
            text: 対象テキスト
            
        Returns:
            抽出されたページ番号、見つからない場合はNone
        """
        try:
            # 単独の数字パターンを検索（周囲に文字がないもの）
            patterns = [
                r'^\s*(\d+)\s*$',  # 単独の数字
                r'^\s*-\s*(\d+)\s*-\s*$',  # -123- 形式
                r'^\s*(\d+)\s*/\s*\d+\s*$',  # 123/456 形式（ページ/総ページ）
                r'^\s*(\d+)\s*$',  # 前後に空白がある数字
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    number = int(match.group(1))
                    # 妥当な範囲の数字かチェック（1以上10000以下）
                    if 1 <= number <= 10000:
                        return number
            
            return None
            
        except (ValueError, AttributeError):
            return None