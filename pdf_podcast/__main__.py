"""Main CLI entry point for PDF podcast generation tool."""

import argparse
import asyncio
import datetime
import os
import sys
import signal
from pathlib import Path
from typing import Optional, Dict, Any
import logging

import google.generativeai as genai
from dotenv import load_dotenv

from .pdf_parser import PDFParser, Chapter
from .script_builder import ScriptBuilder
from .tts_client import TTSClient
from .manifest import ManifestManager, ChapterInfo, ChapterStatus
from .logging_system import setup_logger
from .model_config import ModelConfig

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class PodcastGenerator:
    """Main podcast generation orchestrator."""
    
    def __init__(self, args: argparse.Namespace):
        """Initialize podcast generator with CLI arguments.
        
        Args:
            args: Parsed command line arguments
        """
        self.args = args
        self.output_dir = Path(args.output_dir)
        self.manifest_path = self.output_dir / "manifest.json"
        
        # Setup logging
        self.log_dir = self.output_dir / "logs"
        self.podcast_logger = setup_logger(log_dir=self.log_dir, verbose=args.verbose)
        
        # Initialize components
        self.api_key = self._get_api_key()
        self.model_config = ModelConfig.from_args(args)
        self.pdf_parser = None
        self.script_builder = None
        self.tts_client = None
        self.manifest_manager = ManifestManager(self.manifest_path)
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _get_api_key(self) -> str:
        """Get Google API key from environment or exit.
        
        Returns:
            API key string
        """
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.podcast_logger.print_error("Google API key not found. Please set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
            sys.exit(1)
        return api_key
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signal for graceful shutdown."""
        self.podcast_logger.print_warning("Interrupt received. Saving progress...")
        if hasattr(self, 'manifest_manager'):
            self.manifest_manager.save()
        sys.exit(0)
    
    async def run(self) -> int:
        """Run the podcast generation process.
        
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Generate timestamp for this execution
            self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Print header
            self.podcast_logger.print_header(
                "PDF Podcast Generator",
                f"Converting {self.args.input} to podcast format"
            )
            
            # Print configuration summary
            self._print_configuration()
            
            # Step 1: Parse PDF and extract chapters
            self.podcast_logger.print_info("Step 1: Parsing PDF and extracting chapters...")
            chapters = await self._parse_pdf()
            if not chapters:
                return 2
            
            # Step 2: Create or load manifest
            manifest = await self._setup_manifest(chapters)
            
            # Step 3: Generate scripts
            self.podcast_logger.print_info("Step 2: Generating dialogue scripts...")
            scripts = await self._generate_scripts(chapters)
            
            # Step 4: Generate audio
            self.podcast_logger.print_info("Step 3: Generating audio files...")
            audio_paths = await self._generate_audio(scripts)
            
            # Print final summary
            self._print_completion_summary(None)
            
            return 0
            
        except KeyboardInterrupt:
            self.podcast_logger.print_warning("Process interrupted by user")
            return 1
        except Exception as e:
            self.podcast_logger.print_error(f"Unexpected error: {str(e)}", e)
            return 1
    
    def _print_configuration(self) -> None:
        """Print configuration summary."""
        config_data = {
            "Input PDF": self.args.input,
            "Output Directory": self.args.output_dir,
            "Voice": self.args.voice,
            "Max Concurrency": self.args.max_concurrency,
            "Skip Existing": self.args.skip_existing,
            "Bitrate": self.args.bitrate,
            "BGM": self.args.bgm if self.args.bgm else "None"
        }
        
        # Add model configuration
        config_data.update(self.model_config.get_config_summary())
        
        self.podcast_logger.print_summary(config_data)
    
    async def _parse_pdf(self) -> list[Chapter]:
        """Parse PDF and extract chapters.
        
        Returns:
            List of extracted chapters
        """
        try:
            # Initialize PDF parser
            self.pdf_parser = PDFParser(self.args.input, self.model_config.pdf_model, self.api_key)
            
            # Extract chapters
            progress = self.podcast_logger.start_progress()
            task_id = self.podcast_logger.add_task("Extracting chapters from PDF...")
            
            chapters = await self.pdf_parser.extract_chapters()
            
            self.podcast_logger.complete_task(task_id, f"Extracted {len(chapters)} chapters")
            self.podcast_logger.stop_progress()
            
            # Print chapter summary
            for i, chapter in enumerate(chapters, 1):
                self.podcast_logger.print_info(f"Chapter {i}: {chapter.title} (pages {chapter.start_page}-{chapter.end_page})")
            
            return chapters
            
        except Exception as e:
            self.podcast_logger.print_error(f"Failed to parse PDF: {str(e)}", e)
            return []
    
    async def _setup_manifest(self, chapters: list[Chapter]) -> Optional[Any]:
        """Setup manifest for tracking progress.
        
        Args:
            chapters: List of chapters from PDF
            
        Returns:
            Manifest object or None if failed
        """
        try:
            # Convert chapters to ChapterInfo
            chapter_infos = []
            for chapter in chapters:
                chapter_info = ChapterInfo(
                    title=chapter.title,
                    start_page=chapter.start_page,
                    end_page=chapter.end_page,
                    text_chars=len(chapter.text)
                )
                chapter_infos.append(chapter_info)
            
            # Create or load manifest
            manifest = self.manifest_manager.load_manifest()
            if manifest is None:
                manifest = self.manifest_manager.create_manifest(
                    pdf_path=str(self.args.input),
                    output_dir=str(self.output_dir),
                    chapters=chapter_infos,
                    model=f"PDF:{self.model_config.pdf_model}, Script:{self.model_config.script_model}, TTS:{self.model_config.tts_model}",
                    voice=self.args.voice,
                    max_concurrency=self.args.max_concurrency,
                    skip_existing=self.args.skip_existing,
                    bgm_path=self.args.bgm
                )
            
            # Print progress summary
            summary = self.manifest_manager.get_progress_summary()
            self.podcast_logger.print_progress_summary(summary)
            
            return manifest
            
        except Exception as e:
            self.podcast_logger.print_error(f"Failed to setup manifest: {str(e)}", e)
            return None
    
    async def _generate_scripts(self, chapters: list[Chapter]) -> Dict[str, Any]:
        """Generate dialogue scripts for chapters.
        
        Args:
            chapters: List of chapters
            
        Returns:
            Dictionary of scripts
        """
        try:
            # Initialize script builder
            self.script_builder = ScriptBuilder(self.api_key, self.model_config.script_model)
            
            # Prepare chapter content
            chapter_content = {ch.title: ch.text for ch in chapters}
            
            # Setup output directory for scripts
            scripts_dir = self.output_dir / "scripts" / self.timestamp
            
            # Generate scripts asynchronously
            progress = self.podcast_logger.start_progress()
            task_id = self.podcast_logger.add_task(f"Generating scripts for {len(chapters)} chapters...", total=len(chapters))
            
            scripts = await self.script_builder.generate_scripts_async(
                chapters=chapter_content,
                output_dir=scripts_dir,
                max_concurrency=self.args.max_concurrency,
                skip_existing=self.args.skip_existing
            )
            
            # Update manifest
            for title, script in scripts.items():
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title.replace(' ', '_')[:50]
                script_path = str(scripts_dir / f"{safe_title}.txt")
                
                self.manifest_manager.update_chapter(
                    chapter_title=title,
                    status=ChapterStatus.SCRIPT_GENERATED,
                    script_path=script_path,
                    text_chars=script.total_chars
                )
                self.podcast_logger.update_task(task_id)
            
            self.podcast_logger.complete_task(task_id, f"Generated {len(scripts)} scripts")
            self.podcast_logger.stop_progress()
            
            return scripts
            
        except Exception as e:
            self.podcast_logger.print_error(f"Failed to generate scripts: {str(e)}", e)
            return {}
    
    async def _generate_audio(self, scripts: Dict[str, Any]) -> Dict[str, Path]:
        """Generate audio files from scripts.
        
        Args:
            scripts: Dictionary of dialogue scripts
            
        Returns:
            Dictionary of audio file paths
        """
        try:
            # Initialize TTS client with configured model
            self.tts_client = TTSClient(self.api_key, self.model_config.tts_model)
            
            # Convert scripts to lecture content format
            lecture_scripts = {}
            for title, script in scripts.items():
                lecture_scripts[title] = script.content
            
            # Setup output directory for audio
            audio_dir = self.output_dir / "audio" / self.timestamp
            
            # Generate audio asynchronously
            progress = self.podcast_logger.start_progress()
            task_id = self.podcast_logger.add_task(f"Generating audio for {len(scripts)} chapters...", total=len(scripts))
            
            audio_paths = await self.tts_client.generate_chapter_audios_async(
                scripts=lecture_scripts,
                output_dir=audio_dir,
                voice=self.args.voice,
                max_concurrency=self.args.max_concurrency,
                skip_existing=self.args.skip_existing
            )
            
            # Update manifest with audio information
            for title, audio_path in audio_paths.items():
                self.manifest_manager.update_chapter(
                    chapter_title=title,
                    status=ChapterStatus.AUDIO_GENERATED,
                    audio_path=str(audio_path)
                )
                self.podcast_logger.update_task(task_id)
            
            self.podcast_logger.complete_task(task_id, f"Generated {len(audio_paths)} audio files")
            self.podcast_logger.stop_progress()
            
            return audio_paths
            
        except Exception as e:
            self.podcast_logger.print_error(f"Failed to generate audio: {str(e)}", e)
            return {}
    
    async def _create_episode(self, audio_paths: Dict[str, Path]) -> Optional[Path]:
        """Create final podcast episode.
        
        Args:
            audio_paths: Dictionary of chapter audio paths
            
        Returns:
            Path to episode file or None if failed
        """
        try:
            if not audio_paths:
                self.podcast_logger.print_error("No audio files to concatenate")
                return None
            
            # Prepare chapter audio list in order
            chapter_files = list(audio_paths.values())
            
            # Setup BGM path
            bgm_path = Path(self.args.bgm) if self.args.bgm else None
            
            # Create episode
            episode_path = self.output_dir / "episode.mp3"
            
            progress = self.podcast_logger.start_progress()
            task_id = self.podcast_logger.add_task("Creating episode...")
            
            total_duration, chapter_timestamps = self.audio_mixer.concatenate_chapters(
                chapter_audio_paths=chapter_files,
                output_path=episode_path,
                bgm_path=bgm_path,
                normalize_audio=True
            )
            
            self.podcast_logger.update_task(task_id, description="Adding chapter tags...")
            
            # Add chapter tags
            chapters_info = [(title, start, end) for title, start, end in chapter_timestamps]
            
            self.chapter_tagger.add_chapters_to_mp3(
                mp3_path=episode_path,
                chapters=chapters_info,
                album_title="PDF Podcast",
                artist="PDF Podcast Generator"
            )
            
            # Update manifest
            self.manifest_manager.set_episode_path(str(episode_path), total_duration)
            
            # Mark all chapters as completed
            for title in audio_paths.keys():
                self.manifest_manager.update_chapter(
                    chapter_title=title,
                    status=ChapterStatus.COMPLETED
                )
            
            self.podcast_logger.complete_task(task_id, f"Episode created ({total_duration:.1f}s)")
            self.podcast_logger.stop_progress()
            
            return episode_path
            
        except Exception as e:
            self.podcast_logger.print_error(f"Failed to create episode: {str(e)}", e)
            return None
    
    def _print_completion_summary(self, _: Optional[Path]) -> None:
        """Print completion summary.
        
        Args:
            _: Unused argument (kept for compatibility)
        """
        self.podcast_logger.print_header("Podcast Generation Complete!")
        
        self.podcast_logger.print_success(f"Chapter audio files generated successfully!")
        
        # Print output files
        self.podcast_logger.print_info("Output files:")
        self.podcast_logger.print_file_info(self.output_dir / "scripts", "Scripts directory")
        self.podcast_logger.print_file_info(self.output_dir / "audio", "Audio directory")
        self.podcast_logger.print_file_info(self.manifest_path, "Manifest file")
        self.podcast_logger.print_file_info(self.log_dir, "Logs directory")
        
        # Final progress summary
        summary = self.manifest_manager.get_progress_summary()
        self.podcast_logger.print_progress_summary(summary)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser.
    
    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Convert PDF to podcast with multi-speaker dialogue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdf_podcast --input book.pdf --output-dir ./podcast
  pdf_podcast --input book.pdf --output-dir ./podcast --max-concurrency 2 --skip-existing
  pdf_podcast --input book.pdf --output-dir ./podcast --bgm jingle.mp3 --voice Kore
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input PDF file"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Output directory for generated files"
    )
    
    # Model configuration arguments
    parser.add_argument(
        "--model-pdf",
        type=str,
        help="Gemini model for PDF parsing (default: from env or gemini-2.5-flash-preview-05-20)"
    )
    
    parser.add_argument(
        "--model-script",
        type=str,
        help="Gemini model for script building (default: from env or gemini-2.5-pro-preview-06-05)"
    )
    
    parser.add_argument(
        "--model-tts",
        type=str,
        help="Gemini model for TTS generation (default: from env or gemini-2.5-pro-preview-tts)"
    )
    
    parser.add_argument(
        "--voice",
        type=str,
        default="Kore",
        help="Voice name for the lecturer (default: Kore)"
    )
    
    parser.add_argument(
        "--bitrate",
        type=str,
        default="320k",
        help="Audio bitrate (default: 320k)"
    )
    
    parser.add_argument(
        "--bgm",
        type=str,
        help="Path to background music MP3 file"
    )
    
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="Maximum concurrent API requests (default: 1 for rate limit compliance)"
    )
    
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip existing files (useful for resuming)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # Validate input file
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        return 1
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Create and run podcast generator
    generator = PodcastGenerator(args)
    return asyncio.run(generator.run())


if __name__ == "__main__":
    sys.exit(main())