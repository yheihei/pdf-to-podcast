"""Script builder module for generating podcast dialogue scripts using Gemini API."""

import asyncio
import logging
from typing import Dict, List, Optional
from pathlib import Path
import google.generativeai as genai
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DialogueScript:
    """Represents a dialogue script with host and guest lines."""
    chapter_title: str
    lines: List[Dict[str, str]]  # List of {"speaker": "Host/Guest", "text": "..."}
    total_chars: int


class ScriptBuilder:
    """Generates podcast dialogue scripts from chapter content using Gemini API."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro-preview-06-05"):
        """Initialize ScriptBuilder with Gemini API configuration.
        
        Args:
            api_key: Google API key for Gemini
            model_name: Gemini model to use for text generation
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
    def generate_dialogue_script(self, chapter_title: str, chapter_content: str) -> DialogueScript:
        """Generate a dialogue script from chapter content.
        
        Args:
            chapter_title: Title of the chapter
            chapter_content: Full text content of the chapter
            
        Returns:
            DialogueScript object containing the dialogue
        """
        logger.info(f"Generating dialogue script for chapter: {chapter_title}")
        
        prompt = self._create_dialogue_prompt(chapter_title, chapter_content)
        
        try:
            response = self.model.generate_content(prompt)
            dialogue_lines = self._parse_dialogue_response(response.text)
            
            total_chars = sum(len(line["text"]) for line in dialogue_lines)
            
            return DialogueScript(
                chapter_title=chapter_title,
                lines=dialogue_lines,
                total_chars=total_chars
            )
            
        except Exception as e:
            logger.error(f"Failed to generate dialogue script: {e}")
            raise
    
    def _create_dialogue_prompt(self, chapter_title: str, chapter_content: str) -> str:
        """Create prompt for dialogue generation.
        
        Args:
            chapter_title: Title of the chapter
            chapter_content: Full text content
            
        Returns:
            Formatted prompt string
        """
        return f"""あなたはポッドキャストの台本作成者です。以下の章の内容を、ホストとゲストの自然な対話形式に変換してください。

章タイトル: {chapter_title}

章の内容:
{chapter_content}

要件:
1. 10分で聴ける長さ（合計2800〜3000文字程度）
2. HostとGuestの2人による自然な対話形式
3. 各発言は必ず「Host:」または「Guest:」で始める
4. 内容を正確に要約しながら、リスナーが理解しやすい対話にする
5. 専門用語は適切に説明を加える
6. 日本語で記述する

出力形式:
Host: [ホストの発言]
Guest: [ゲストの発言]
Host: [ホストの発言]
...

対話を生成してください:"""
    
    def _parse_dialogue_response(self, response_text: str) -> List[Dict[str, str]]:
        """Parse dialogue response into structured format.
        
        Args:
            response_text: Raw response from Gemini API
            
        Returns:
            List of dialogue entries
        """
        lines = []
        current_speaker = None
        current_text = []
        
        for line in response_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('Host:'):
                if current_speaker and current_text:
                    lines.append({
                        "speaker": current_speaker,
                        "text": ' '.join(current_text).strip()
                    })
                current_speaker = "Host"
                current_text = [line[5:].strip()]
                
            elif line.startswith('Guest:'):
                if current_speaker and current_text:
                    lines.append({
                        "speaker": current_speaker,
                        "text": ' '.join(current_text).strip()
                    })
                current_speaker = "Guest"
                current_text = [line[6:].strip()]
                
            else:
                # Continuation of previous speaker's text
                if current_text:
                    current_text.append(line)
        
        # Add the last speaker's text
        if current_speaker and current_text:
            lines.append({
                "speaker": current_speaker,
                "text": ' '.join(current_text).strip()
            })
        
        return lines
    
    def generate_scripts_for_chapters(self, chapters: Dict[str, str]) -> Dict[str, DialogueScript]:
        """Generate dialogue scripts for multiple chapters.
        
        Args:
            chapters: Dictionary of chapter_title -> chapter_content
            
        Returns:
            Dictionary of chapter_title -> DialogueScript
        """
        scripts = {}
        
        for title, content in chapters.items():
            try:
                script = self.generate_dialogue_script(title, content)
                scripts[title] = script
                logger.info(f"Generated script for '{title}' with {len(script.lines)} dialogue lines")
            except Exception as e:
                logger.error(f"Failed to generate script for chapter '{title}': {e}")
                # Continue with other chapters
                
        return scripts
    
    def save_script_to_file(self, script: DialogueScript, output_path: Path) -> bool:
        """Save dialogue script to text file.
        
        Args:
            script: DialogueScript to save
            output_path: Path to save the script file
            
        Returns:
            True if successful
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# {script.chapter_title}\n\n")
                
                for line in script.lines:
                    f.write(f"{line['speaker']}: {line['text']}\n\n")
                
                f.write(f"# Statistics\n")
                f.write(f"Total characters: {script.total_chars}\n")
                f.write(f"Total lines: {len(script.lines)}\n")
            
            logger.info(f"Saved script to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save script to {output_path}: {e}")
            return False
    
    async def generate_scripts_async(
        self,
        chapters: Dict[str, str],
        output_dir: Optional[Path] = None,
        max_concurrency: int = 4,
        skip_existing: bool = False
    ) -> Dict[str, DialogueScript]:
        """Generate dialogue scripts for multiple chapters asynchronously.
        
        Args:
            chapters: Dictionary of chapter_title -> chapter_content
            output_dir: Optional directory to save script files
            max_concurrency: Maximum number of concurrent requests
            skip_existing: Skip chapters with existing script files
            
        Returns:
            Dictionary of chapter_title -> DialogueScript
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        scripts = {}
        
        async def process_chapter(title: str, content: str) -> Optional[DialogueScript]:
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
                    
                    # Generate script (run in thread pool since it's not async)
                    script = await asyncio.get_event_loop().run_in_executor(
                        None, self.generate_dialogue_script, title, content
                    )
                    
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
            if isinstance(result, DialogueScript):
                scripts[title] = result
                logger.info(f"Generated script for '{title}' with {len(result.lines)} dialogue lines")
            elif isinstance(result, Exception):
                logger.error(f"Exception processing chapter '{title}': {result}")
        
        return scripts