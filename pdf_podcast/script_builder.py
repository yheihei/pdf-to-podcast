"""Script builder module for generating podcast dialogue scripts using Gemini API."""

import logging
from typing import Dict, List, Optional
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
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
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