"""Script builder module for generating podcast dialogue scripts using Gemini API."""

import asyncio
import logging
from typing import Dict, Optional, List
from pathlib import Path
import google.generativeai as genai
from dataclasses import dataclass

from .rate_limiter import GeminiRateLimiter, RateLimitConfig
from .script_validator import ScriptValidator
from .pdf_parser import Section

logger = logging.getLogger(__name__)


@dataclass
class LectureScript:
    """Represents a lecture script for a single speaker."""
    chapter_title: str
    content: str  # Lecture content as a single formatted text
    total_chars: int


@dataclass
class SectionScript:
    """Represents a lecture script for a single section."""
    section_title: str
    section_number: str  # "1.1", "2.3" など
    content: str  # Lecture content as a single formatted text
    total_chars: int
    parent_chapter: str = ""  # 所属する章のタイトル


class ScriptBuilder:
    """Generates podcast lecture scripts from chapter content using Gemini API."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro-preview-06-05"):
        """Initialize ScriptBuilder with Gemini API configuration.
        
        Args:
            api_key: Google API key for Gemini
            model_name: Gemini model to use for text generation
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
        # レートリミッターの初期化
        rate_limit_config = RateLimitConfig(rpm_limit=15)  # Free tier
        self.rate_limiter = GeminiRateLimiter(rate_limit_config)
        
        # スクリプト検証の初期化
        self.validator = ScriptValidator()
        
    async def generate_lecture_script(self, chapter_title: str, chapter_content: str) -> LectureScript:
        """Generate a lecture script from chapter content.
        
        Args:
            chapter_title: Title of the chapter
            chapter_content: Full text content of the chapter
            
        Returns:
            LectureScript object containing the lecture
        """
        logger.info(f"Generating lecture script for chapter: {chapter_title}")
        
        prompt = self._create_lecture_prompt(chapter_title, chapter_content)
        
        try:
            # Use rate limiter for API call
            response = await self.rate_limiter.call_with_backoff(
                self.model.generate_content, prompt
            )
            
            # Debug: Log the raw response
            logger.info(f"Raw API response for '{chapter_title}': {response.text[:500]}...")
            
            lecture_content = self._parse_lecture_response(response.text)
            
            total_chars = len(lecture_content)
            
            script = LectureScript(
                chapter_title=chapter_title,
                content=lecture_content,
                total_chars=total_chars
            )
            
            # スクリプト検証の実行
            validation_result = self.validator.validate_script(script)
            self.validator.log_validation_results(validation_result, chapter_title)
            
            # 改善提案の表示
            if not validation_result.is_valid or validation_result.has_warnings:
                suggestions = self.validator.get_improvement_suggestions(validation_result)
                if suggestions:
                    logger.info(f"章 '{chapter_title}' の改善提案:")
                    for suggestion in suggestions:
                        logger.info(f"  - {suggestion}")
            
            return script
            
        except Exception as e:
            logger.error(f"Failed to generate lecture script: {e}")
            raise
    
    async def generate_section_script(self, section: Section, context: Optional[Dict] = None) -> SectionScript:
        """Generate a lecture script from section content.
        
        Args:
            section: Section object containing title, content, etc.
            context: Optional context containing related sections info
            
        Returns:
            SectionScript object containing the lecture
        """
        logger.info(f"Generating section script for: {section.section_number} {section.title}")
        
        prompt = self._create_section_prompt(section, context)
        
        try:
            # Use rate limiter for API call
            response = await self.rate_limiter.call_with_backoff(
                self.model.generate_content, prompt
            )
            
            # Debug: Log the raw response
            logger.info(f"Raw API response for '{section.section_number}': {response.text[:500]}...")
            
            lecture_content = self._parse_lecture_response(response.text)
            
            total_chars = len(lecture_content)
            
            script = SectionScript(
                section_title=section.title,
                section_number=section.section_number,
                content=lecture_content,
                total_chars=total_chars,
                parent_chapter=section.parent_chapter
            )
            
            # スクリプト検証の実行
            # Note: SectionScript用のvalidation_resultを作成するため、LectureScriptに変換
            temp_lecture_script = LectureScript(
                chapter_title=f"{section.section_number} {section.title}",
                content=lecture_content,
                total_chars=total_chars
            )
            validation_result = self.validator.validate_script(temp_lecture_script)
            self.validator.log_validation_results(validation_result, f"{section.section_number} {section.title}")
            
            # 改善提案の表示
            if not validation_result.is_valid or validation_result.has_warnings:
                suggestions = self.validator.get_improvement_suggestions(validation_result)
                if suggestions:
                    logger.info(f"中項目 '{section.section_number} {section.title}' の改善提案:")
                    for suggestion in suggestions:
                        logger.info(f"  - {suggestion}")
            
            return script
            
        except Exception as e:
            logger.error(f"Failed to generate section script: {e}")
            raise
    
    def _create_lecture_prompt(self, chapter_title: str, chapter_content: str) -> str:
        """Create prompt for lecture generation.
        
        Args:
            chapter_title: Title of the chapter
            chapter_content: Full text content
            
        Returns:
            Formatted prompt string
        """
        return f"""あなたはオンライン講義の講師です。以下の章の内容を、視聴者に向けた分かりやすい講義形式に変換してください。

章タイトル: {chapter_title}

章の内容:
{chapter_content}

要件:
1. 【重要】合計1500〜1800文字以内で必ず収める（1800文字を超えないこと）
2. 講師が視聴者に語りかける形式
3. 導入、本論、まとめの構造を持つ
4. 内容を正確に要約しながら、視聴者が理解しやすい説明にする
5. 専門用語は適切に説明を加える
6. 日本語で記述する
7. 段落ごとに改行を入れて、話の区切りを明確にする
8. 「みなさん」「〜ですね」など、講義らしい表現を使用する

【制限事項】
- 生成する講義内容は必ず1800文字以内に収めること
- 文字数が超過する場合は、詳細を省略して要点のみに絞ること

講義内容を生成してください:"""
    
    def _create_section_prompt(self, section: Section, context: Optional[Dict] = None) -> str:
        """Create prompt for section lecture generation.
        
        Args:
            section: Section object containing title, content, etc.
            context: Optional context containing related sections info
            
        Returns:
            Formatted prompt string
        """
        # コンテキスト情報の構築
        context_info = ""
        if context:
            if "previous_section" in context:
                prev = context["previous_section"]
                context_info += f"\n前の中項目: {prev.get('section_number', '')} {prev.get('title', '')}"
            if "next_section" in context:
                next_sec = context["next_section"]
                context_info += f"\n次の中項目: {next_sec.get('section_number', '')} {next_sec.get('title', '')}"
            if "chapter_overview" in context:
                context_info += f"\n章の概要: {context['chapter_overview']}"
        
        return f"""あなたはオンライン講義の講師です。以下の中項目の内容を、視聴者に向けた分かりやすい講義形式に変換してください。

中項目番号: {section.section_number}
中項目タイトル: {section.title}
所属章: {section.parent_chapter}
{context_info}

中項目の内容:
{section.text}

要件:
1. 【重要】合計1200〜1500文字以内で必ず収める（1500文字を超えないこと）
2. 講師が視聴者に語りかける形式
3. 導入、本論、まとめの構造を持つ
4. 中項目の内容を正確に要約しながら、視聴者が理解しやすい説明にする
5. 専門用語は適切に説明を加える
6. 日本語で記述する
7. 段落ごとに改行を入れて、話の区切りを明確にする
8. 「みなさん」「〜ですね」など、講義らしい表現を使用する
9. 中項目番号とタイトルを冒頭で明確に紹介する
10. 所属する章との関連性を意識した説明を行う

【制限事項】
- 生成する講義内容は必ず1500文字以内に収めること
- 文字数が超過する場合は、詳細を省略して要点のみに絞ること
- 章全体ではなく、この中項目に特化した内容にする

講義内容を生成してください:"""
    
    def _parse_lecture_response(self, response_text: str) -> str:
        """Parse lecture response into formatted text.
        
        Args:
            response_text: Raw response from Gemini API
            
        Returns:
            Formatted lecture content
        """
        logger.info(f"Parsing response text length: {len(response_text)}")
        logger.info(f"First 200 chars: {response_text[:200]}")
        
        # Clean up the response text
        cleaned_text = response_text.strip()
        
        # Ensure proper paragraph separation
        paragraphs = []
        for paragraph in cleaned_text.split('\n'):
            paragraph = paragraph.strip()
            if paragraph:
                paragraphs.append(paragraph)
        
        # Join paragraphs with double newlines for clear separation
        lecture_content = '\n\n'.join(paragraphs)
        
        logger.info(f"Parsed lecture with {len(paragraphs)} paragraphs")
        if not lecture_content:
            logger.warning("No lecture content was parsed from the response!")
        
        return lecture_content
    
    def generate_scripts_for_chapters(self, chapters: Dict[str, str]) -> Dict[str, LectureScript]:
        """Generate lecture scripts for multiple chapters.
        
        Args:
            chapters: Dictionary of chapter_title -> chapter_content
            
        Returns:
            Dictionary of chapter_title -> LectureScript
        """
        scripts = {}
        
        for title, content in chapters.items():
            try:
                script = self.generate_lecture_script(title, content)
                scripts[title] = script
                logger.info(f"Generated script for '{title}' with {script.total_chars} characters")
            except Exception as e:
                logger.error(f"Failed to generate script for chapter '{title}': {e}")
                # Continue with other chapters
                
        return scripts
    
    async def generate_scripts_for_sections(self, sections: List[Section]) -> Dict[str, SectionScript]:
        """Generate lecture scripts for multiple sections.
        
        Args:
            sections: List of Section objects
            
        Returns:
            Dictionary of section_key -> SectionScript
        """
        scripts = {}
        
        for i, section in enumerate(sections):
            try:
                # コンテキスト情報の構築
                context = {}
                if i > 0:
                    prev_section = sections[i-1]
                    context["previous_section"] = {
                        "section_number": prev_section.section_number,
                        "title": prev_section.title
                    }
                if i < len(sections) - 1:
                    next_section = sections[i+1]
                    context["next_section"] = {
                        "section_number": next_section.section_number,
                        "title": next_section.title
                    }
                
                # スクリプト生成
                script = await self.generate_section_script(section, context)
                section_key = f"{section.section_number}_{section.title}"
                scripts[section_key] = script
                logger.info(f"Generated script for '{section.section_number} {section.title}' with {script.total_chars} characters")
            except Exception as e:
                logger.error(f"Failed to generate script for section '{section.section_number} {section.title}': {e}")
                # Continue with other sections
                
        return scripts
    
    def save_script_to_file(self, script: LectureScript, output_path: Path) -> bool:
        """Save lecture script to text file.
        
        Args:
            script: LectureScript to save
            output_path: Path to save the script file
            
        Returns:
            True if successful
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# {script.chapter_title}\n\n")
                f.write(script.content)
                f.write("\n\n# Statistics\n")
                f.write(f"Total characters: {script.total_chars}\n")
            
            logger.info(f"Saved script to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save script to {output_path}: {e}")
            return False
    
    def save_section_script_to_file(self, script: SectionScript, output_path: Path) -> bool:
        """Save section script to text file.
        
        Args:
            script: SectionScript to save
            output_path: Path to save the script file
            
        Returns:
            True if successful
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# {script.section_number} {script.section_title}\n\n")
                f.write(f"**所属章:** {script.parent_chapter}\n\n")
                f.write(script.content)
                f.write("\n\n# Statistics\n")
                f.write(f"Total characters: {script.total_chars}\n")
            
            logger.info(f"Saved section script to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save section script to {output_path}: {e}")
            return False
    
    async def generate_scripts_async(
        self,
        chapters: Dict[str, str],
        output_dir: Optional[Path] = None,
        max_concurrency: int = 1,
        skip_existing: bool = False
    ) -> Dict[str, LectureScript]:
        """Generate lecture scripts for multiple chapters asynchronously.
        
        Args:
            chapters: Dictionary of chapter_title -> chapter_content
            output_dir: Optional directory to save script files
            max_concurrency: Maximum number of concurrent requests
            skip_existing: Skip chapters with existing script files
            
        Returns:
            Dictionary of chapter_title -> LectureScript
        """
        # Force max_concurrency to 1 for Free tier compliance
        actual_concurrency = 1
        semaphore = asyncio.Semaphore(actual_concurrency)
        
        if max_concurrency > 1:
            logger.warning(f"max_concurrency reduced from {max_concurrency} to 1 for Free tier rate limit compliance")
        scripts = {}
        
        async def process_chapter(title: str, content: str) -> Optional[LectureScript]:
            async with semaphore:
                try:
                    # Check if script file already exists
                    if skip_existing and output_dir:
                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_title = safe_title.replace(' ', '_')[:50]
                        script_path = output_dir / f"{safe_title}.txt"
                        
                        if script_path.exists():
                            logger.info(f"Skipping existing script: {title}")
                            return None
                    
                    # Generate script (now async)
                    script = await self.generate_lecture_script(title, content)
                    
                    # Save to file if output directory specified
                    if output_dir:
                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_title = safe_title.replace(' ', '_')[:50]
                        script_path = output_dir / f"{safe_title}.txt"
                        self.save_script_to_file(script, script_path)
                    
                    return script
                    
                except Exception as e:
                    logger.error(f"Failed to generate script for chapter '{title}': {e}")
                    return None
        
        # Process chapters concurrently
        tasks = [process_chapter(title, content) for title, content in chapters.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect successful results
        for (title, _), result in zip(chapters.items(), results):
            if isinstance(result, LectureScript):
                scripts[title] = result
                logger.info(f"Generated script for '{title}' with {result.total_chars} characters")
            elif isinstance(result, Exception):
                logger.error(f"Exception processing chapter '{title}': {result}")
        
        return scripts