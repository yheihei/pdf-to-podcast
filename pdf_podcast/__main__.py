"""Main CLI entry point for PDF podcast generation tool."""

import argparse
import asyncio
import os
import sys
import signal
import re
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from dotenv import load_dotenv

from .pdf_parser import PDFParser, Chapter, Section
from .script_builder import ScriptBuilder
from .tts_client import TTSClient
from .audio_mixer import AudioMixer
from .manifest import ManifestManager, ChapterInfo, ChapterStatus, SectionInfo, SectionStatus
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
        # Handle output_dir for scripts-to-audio mode
        if hasattr(args, 'scripts_to_audio') and args.scripts_to_audio:
            # In scripts-to-audio mode, output_dir might be None
            self.output_dir = Path(args.output_dir) if args.output_dir else None
            self.manifest_path = self.output_dir / "manifest.json" if self.output_dir else None
        else:
            self.output_dir = Path(args.output_dir)
            self.manifest_path = self.output_dir / "manifest.json"
        
        # Setup logging
        if hasattr(args, 'scripts_to_audio') and args.scripts_to_audio:
            # In scripts-to-audio mode, place logs in a temp directory or scripts directory parent
            scripts_dir = Path(args.scripts_to_audio)
            if scripts_dir.parent.name == "scripts":
                # Standard structure: use output base for logs
                self.log_dir = scripts_dir.parent.parent / "logs"
            else:
                # Non-standard structure: use scripts directory parent
                self.log_dir = scripts_dir.parent / "logs"
        else:
            self.log_dir = self.output_dir / "logs"
        self.podcast_logger = setup_logger(log_dir=self.log_dir, verbose=args.verbose)
        
        # Initialize components
        self.api_key = self._get_api_key()
        self.model_config = ModelConfig.from_args(args)
        self.pdf_parser = None
        self.script_builder = None
        self.tts_client = None
        self.audio_mixer = None
        # Initialize manifest manager only if manifest_path is available
        self.manifest_manager = ManifestManager(self.manifest_path) if self.manifest_path else None
        
        # Apply quality settings
        self._apply_quality_settings()
        
        # Initialize audio mixer with quality settings
        self.audio_mixer = AudioMixer(
            bitrate=self.args.bitrate,
            channels=self.quality_settings["channels"]
        )
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _apply_quality_settings(self) -> None:
        """Apply quality preset settings to override individual parameters."""
        quality_presets = {
            "high": {
                "bitrate": "320k",
                "sample_rate": 24000,
                "channels": 2
            },
            "standard": {
                "bitrate": "128k", 
                "sample_rate": 22050,
                "channels": 1
            },
            "compact": {
                "bitrate": "96k",
                "sample_rate": 16000,
                "channels": 1
            }
        }
        
        preset = quality_presets.get(self.args.quality, quality_presets["standard"])
        
        # Override bitrate only if not explicitly set by user
        if self.args.bitrate == "128k":  # default value
            self.args.bitrate = preset["bitrate"]
        
        # Store quality settings for later use
        self.quality_settings = preset
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to create safe directory name.
        
        Args:
            filename: Original filename (with or without extension)
            
        Returns:
            Sanitized filename safe for directory usage
        """
        # Remove extension if present
        name = Path(filename).stem
        
        # Replace unsafe characters with underscore
        unsafe_chars = r'[/\\:*?"<>|]'
        sanitized = re.sub(unsafe_chars, '_', name)
        
        # Replace consecutive underscores with single underscore
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Strip leading/trailing whitespace and dots
        sanitized = sanitized.strip(' .')
        
        # Ensure we have a valid name
        if not sanitized:
            sanitized = "unknown"
            
        return sanitized
    
    def _get_unique_dirname(self, base_name: str, base_dir: Path) -> str:
        """Get unique directory name by adding suffix if needed.
        
        Args:
            base_name: Base directory name
            base_dir: Parent directory to check for existing subdirectories
            
        Returns:
            Unique directory name (may have numeric suffix)
        """
        # Try the base name first
        candidate = base_name
        counter = 2
        
        while (base_dir / candidate).exists():
            candidate = f"{base_name}_{counter}"
            counter += 1
            
        return candidate
        
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
    
    def _signal_handler(self, _signum, _frame):
        """Handle interrupt signal for graceful shutdown."""
        self.podcast_logger.print_warning("Interrupt received. Saving progress...")
        if hasattr(self, 'manifest_manager') and self.manifest_manager:
            self.manifest_manager.save()
        sys.exit(0)
    
    def validate_scripts_directory(self, scripts_dir_path: str) -> Path:
        """指定されたスクリプトディレクトリの存在を確認
        
        Args:
            scripts_dir_path: スクリプトディレクトリのパス
            
        Returns:
            検証済みのPathオブジェクト
            
        Raises:
            ValueError: ディレクトリが存在しない、またはディレクトリでない場合
        """
        scripts_dir = Path(scripts_dir_path)
        if not scripts_dir.exists():
            raise ValueError(f"スクリプトディレクトリが見つかりません: {scripts_dir_path}")
        if not scripts_dir.is_dir():
            raise ValueError(f"指定されたパスはディレクトリではありません: {scripts_dir_path}")
        return scripts_dir
    
    def get_missing_audio_files(self, scripts_dir: Path, audio_dir: Path) -> list[Path]:
        """音声が未生成のスクリプトファイルを取得
        
        Args:
            scripts_dir: スクリプトディレクトリのパス
            audio_dir: 音声ディレクトリのパス
            
        Returns:
            音声未生成のスクリプトファイルのリスト
        """
        script_files = {f.stem: f for f in scripts_dir.glob("*.txt")}
        audio_files = {f.stem for f in audio_dir.glob("*.mp3")}
        
        missing = []
        for stem, script_path in script_files.items():
            if stem not in audio_files:
                missing.append(script_path)
        
        return missing
    
    def handle_rate_limit_error(self, scripts_dir: str, processed: int, total: int):
        """429エラー時の処理停止とガイダンス表示
        
        Args:
            scripts_dir: スクリプトディレクトリのパス
            processed: 処理済みファイル数
            total: 総ファイル数
        """
        print(f"❌ レート制限エラー (429) が発生しました\n")
        print(f"API制限: Free Tierは1分間に3リクエストまで")
        print(f"処理状況:")
        print(f"- 処理済み: {processed}/{total} ファイル ({processed/total*100:.1f}%)")
        print(f"- 残り: {total-processed} ファイル\n")
        print(f"時間をおいて以下のコマンドで処理を再開してください:")
        print(f"python -m pdf_podcast --scripts-to-audio {scripts_dir}\n")
        print(f"推奨待機時間: 2-5分")
        print(f"※ 既存の音声ファイルは自動でスキップされます")
        sys.exit(1)
    
    async def run_scripts_to_audio(self) -> int:
        """Run scripts-to-audio mode.
        
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            scripts_dir = self.validate_scripts_directory(self.args.scripts_to_audio)
            
            # Determine audio directory
            if hasattr(self.args, 'output_dir') and self.args.output_dir:
                # If output-dir is specified, use it as base
                output_base = Path(self.args.output_dir)
                audio_dir = output_base / "audio" / scripts_dir.name
            else:
                # Try to infer from scripts directory structure
                # Assume structure: .../output/scripts/dirname -> .../output/audio/dirname
                scripts_parent = scripts_dir.parent
                if scripts_parent.name == "scripts":
                    output_base = scripts_parent.parent
                    audio_dir = output_base / "audio" / scripts_dir.name
                else:
                    # Default: place audio directory as sibling to scripts directory
                    audio_dir = scripts_parent / "audio" / scripts_dir.name
            
            # Ensure audio directory exists
            audio_dir.mkdir(parents=True, exist_ok=True)
            
            # Print header
            self.podcast_logger.print_header(
                "Scripts-to-Audio モード",
                f"スクリプトから音声のみを生成"
            )
            
            # Print progress information
            script_files = list(scripts_dir.glob("*.txt"))
            audio_files = list(audio_dir.glob("*.mp3"))
            missing_audio_files = self.get_missing_audio_files(scripts_dir, audio_dir)
            
            self.podcast_logger.print_info(f"スクリプトディレクトリ: {scripts_dir}")
            self.podcast_logger.print_info(f"音声ディレクトリ: {audio_dir}")
            self.podcast_logger.print_info(f"- スクリプト総数: {len(script_files)}")
            self.podcast_logger.print_info(f"- 生成済み音声: {len(audio_files)}")
            self.podcast_logger.print_info(f"- 未生成音声: {len(missing_audio_files)}")
            self.podcast_logger.print_info(f"- 処理対象: {len(missing_audio_files)}ファイル")
            
            if not missing_audio_files:
                self.podcast_logger.print_success("すべてのスクリプトに対応する音声ファイルが既に存在します。")
                return 0
            
            # Initialize TTS client
            self.tts_client = TTSClient(
                api_key=self.api_key,
                model_name=self.model_config.tts_model,
                sample_rate=self.quality_settings["sample_rate"],
                channels=self.quality_settings["channels"],
                bitrate=self.args.bitrate
            )
            
            # Generate audio for missing files only
            self.podcast_logger.start_progress()
            task_id = self.podcast_logger.add_task(f"音声生成中...", total=len(missing_audio_files))
            
            processed = 0
            for script_file in missing_audio_files:
                try:
                    # Read script content
                    with open(script_file, 'r', encoding='utf-8') as f:
                        script_content = f.read()
                    
                    # Generate audio
                    audio_filename = script_file.stem + ".mp3"
                    audio_path = audio_dir / audio_filename
                    
                    self.tts_client.generate_audio(
                        lecture_content=script_content,
                        voice=self.args.voice,
                        output_path=audio_path
                    )
                    
                    processed += 1
                    self.podcast_logger.update_task(task_id, advance=1)
                    
                except Exception as e:
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        # Handle rate limit error
                        self.handle_rate_limit_error(self.args.scripts_to_audio, processed, len(missing_audio_files))
                    else:
                        self.podcast_logger.print_error(f"Failed to generate audio for {script_file.name}: {str(e)}")
                        continue
            
            self.podcast_logger.complete_task(task_id, f"Generated {processed} audio files")
            self.podcast_logger.stop_progress()
            
            # Print completion summary
            self.podcast_logger.print_success(f"Scripts-to-Audio 処理が完了しました！")
            self.podcast_logger.print_info(f"生成された音声ファイル: {processed}個")
            self.podcast_logger.print_info(f"音声ファイル保存先: {audio_dir}")
            
            return 0
            
        except ValueError as e:
            self.podcast_logger.print_error(str(e))
            return 1
        except KeyboardInterrupt:
            self.podcast_logger.print_warning("Process interrupted by user")
            return 1
        except Exception as e:
            self.podcast_logger.print_error(f"Unexpected error: {str(e)}", e)
            return 1
    
    async def run(self) -> int:
        """Run the podcast generation process.
        
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        # Check if scripts-to-audio mode
        if hasattr(self.args, 'scripts_to_audio') and self.args.scripts_to_audio:
            return await self.run_scripts_to_audio()
        
        try:
            # Generate directory name based on PDF filename
            pdf_filename = Path(self.args.input).name
            sanitized_name = self._sanitize_filename(pdf_filename)
            
            # Ensure unique directory names for scripts and audio
            scripts_base_dir = self.output_dir / "scripts"
            audio_base_dir = self.output_dir / "audio"
            scripts_base_dir.mkdir(parents=True, exist_ok=True)
            audio_base_dir.mkdir(parents=True, exist_ok=True)
            
            self.pdf_dirname = self._get_unique_dirname(sanitized_name, scripts_base_dir)
            
            # Print header
            self.podcast_logger.print_header(
                "PDF Podcast Generator",
                f"Converting {self.args.input} to podcast format"
            )
            
            # Print configuration summary
            self._print_configuration()
            
            # Step 1: Parse PDF and extract sections (中項目対応)
            self.podcast_logger.print_info("Step 1: Parsing PDF and extracting sections...")
            sections = await self._parse_pdf_sections()
            if not sections:
                return 2
            
            # Step 2: Create or load manifest
            manifest = await self._setup_section_manifest(sections)
            
            # Step 3: Generate scripts
            self.podcast_logger.print_info("Step 2: Generating section scripts...")
            scripts = await self._generate_section_scripts(sections)
            
            # Step 4: Generate audio
            self.podcast_logger.print_info("Step 3: Generating section audio files...")
            audio_paths = await self._generate_section_audio(scripts)
            
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
            "Quality": f"{self.args.quality} ({self.args.bitrate}, {self.quality_settings['sample_rate']}Hz, {'Mono' if self.quality_settings['channels'] == 1 else 'Stereo'})",
            "Max Concurrency": self.args.max_concurrency,
            "Skip Existing": self.args.skip_existing,
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
    
    async def _parse_pdf_sections(self) -> list[Section]:
        """Parse PDF and extract sections.
        
        Returns:
            List of extracted sections
        """
        try:
            # Initialize PDF parser
            self.pdf_parser = PDFParser(self.args.input, self.model_config.pdf_model, self.api_key)
            
            # Extract sections
            progress = self.podcast_logger.start_progress()
            task_id = self.podcast_logger.add_task("Extracting sections from PDF...")
            
            sections = await self.pdf_parser.extract_sections()
            
            self.podcast_logger.complete_task(task_id, f"Extracted {len(sections)} sections")
            self.podcast_logger.stop_progress()
            
            # Print section summary
            for i, section in enumerate(sections, 1):
                self.podcast_logger.print_info(f"Section {i}: {section.section_number} {section.title} (pages {section.start_page}-{section.end_page})")
            
            return sections
            
        except Exception as e:
            self.podcast_logger.print_error(f"Failed to parse PDF sections: {str(e)}", e)
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
            self.manifest_manager.load_manifest()
            self.manifest_manager.create_manifest(
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
    
    async def _setup_section_manifest(self, sections: list[Section]) -> Optional[Any]:
        """Setup section manifest for tracking progress.
        
        Args:
            sections: List of sections from PDF
            
        Returns:
            Manifest object or None if failed
        """
        try:
            # Convert sections to SectionInfo
            section_infos = []
            for section in sections:
                section_info = SectionInfo(
                    title=section.title,
                    section_number=section.section_number,
                    start_page=section.start_page,
                    end_page=section.end_page,
                    parent_chapter=section.parent_chapter,
                    text_chars=len(section.text)
                )
                section_infos.append(section_info)
            
            # Create section manifest (always create new for section processing)
            self.manifest_manager.create_section_manifest(
                pdf_path=str(self.args.input),
                output_dir=str(self.output_dir),
                sections=section_infos,
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
            self.podcast_logger.print_error(f"Failed to setup section manifest: {str(e)}", e)
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
            scripts_dir = self.output_dir / "scripts" / self.pdf_dirname
            
            # Generate scripts asynchronously
            self.podcast_logger.start_progress()
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
            # Initialize TTS client with configured model and quality settings
            self.tts_client = TTSClient(
                api_key=self.api_key, 
                model_name=self.model_config.tts_model,
                sample_rate=self.quality_settings["sample_rate"],
                channels=self.quality_settings["channels"],
                bitrate=self.args.bitrate
            )
            
            # Convert scripts to lecture content format
            lecture_scripts = {}
            for title, script in scripts.items():
                lecture_scripts[title] = script.content
            
            # Setup output directory for audio
            audio_dir = self.output_dir / "audio" / self.pdf_dirname
            
            # Generate audio asynchronously
            self.podcast_logger.start_progress()
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
            
            self.podcast_logger.start_progress()
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
    
    async def _generate_section_scripts(self, sections: list[Section]) -> Dict[str, Any]:
        """Generate scripts for sections.
        
        Args:
            sections: List of sections
            
        Returns:
            Dictionary of section scripts
        """
        try:
            # Initialize script builder
            self.script_builder = ScriptBuilder(self.api_key, self.model_config.script_model)
            
            # Setup output directory for scripts
            scripts_dir = self.output_dir / "scripts" / self.pdf_dirname
            
            # Generate scripts for each section
            self.podcast_logger.start_progress()
            task_id = self.podcast_logger.add_task(f"Generating section scripts for {len(sections)} sections...", total=len(sections))
            
            section_scripts = {}
            for section in sections:
                try:
                    # Generate context for the section
                    context = {
                        "parent_chapter": section.parent_chapter,
                        "section_number": section.section_number,
                        "total_sections": len(sections)
                    }
                    
                    # Generate script for this section
                    section_script = await self.script_builder.generate_section_script(section, context)
                    
                    # Create section key for storage
                    section_key = f"{section.section_number}_{section.title}"
                    section_scripts[section_key] = section_script
                    
                    # Save script file
                    safe_title = "".join(c for c in section.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    safe_title = safe_title.replace(' ', '_')[:50]
                    script_filename = f"{section.section_number.replace('.', '_')}_{safe_title}.txt"
                    script_path = scripts_dir / script_filename
                    
                    # Ensure directory exists
                    script_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write script content
                    with open(script_path, 'w', encoding='utf-8') as f:
                        f.write(section_script.content)
                    
                    # Update manifest
                    self.manifest_manager.update_section(
                        section_number=section.section_number,
                        status=SectionStatus.SCRIPT_GENERATED,
                        script_path=str(script_path),
                        text_chars=section_script.total_chars
                    )
                    
                    self.podcast_logger.update_task(task_id)
                    
                except Exception as e:
                    self.podcast_logger.print_error(f"Failed to generate script for section {section.section_number}: {str(e)}", e)
                    # Update manifest with failure
                    self.manifest_manager.update_section(
                        section_number=section.section_number,
                        status=SectionStatus.FAILED,
                        error_message=str(e)
                    )
            
            self.podcast_logger.complete_task(task_id, f"Generated {len(section_scripts)} section scripts")
            self.podcast_logger.stop_progress()
            
            return section_scripts
            
        except Exception as e:
            self.podcast_logger.print_error(f"Failed to generate section scripts: {str(e)}", e)
            return {}
    
    async def _generate_section_audio(self, section_scripts: Dict[str, Any]) -> Dict[str, Path]:
        """Generate audio files from section scripts.
        
        Args:
            section_scripts: Dictionary of section scripts
            
        Returns:
            Dictionary of audio file paths
        """
        try:
            # Initialize TTS client with configured model and quality settings
            self.tts_client = TTSClient(
                api_key=self.api_key, 
                model_name=self.model_config.tts_model,
                sample_rate=self.quality_settings["sample_rate"],
                channels=self.quality_settings["channels"],
                bitrate=self.args.bitrate
            )
            
            # Setup output directory for audio
            audio_dir = self.output_dir / "audio" / self.pdf_dirname
            
            # Generate audio asynchronously
            self.podcast_logger.start_progress()
            task_id = self.podcast_logger.add_task(f"Generating audio for {len(section_scripts)} sections...", total=len(section_scripts))
            
            audio_paths = await self.tts_client.generate_section_audios_async(
                section_scripts=section_scripts,
                output_dir=audio_dir,
                voice=self.args.voice,
                max_concurrency=self.args.max_concurrency,
                skip_existing=self.args.skip_existing
            )
            
            # Update manifest with audio information
            for section_key, audio_path in audio_paths.items():
                # Extract section number from section key
                section_number = section_key.split('_')[0].replace('_', '.')
                self.manifest_manager.update_section(
                    section_number=section_number,
                    status=SectionStatus.AUDIO_GENERATED,
                    audio_path=str(audio_path)
                )
                self.podcast_logger.update_task(task_id)
            
            self.podcast_logger.complete_task(task_id, f"Generated {len(audio_paths)} audio files")
            self.podcast_logger.stop_progress()
            
            return audio_paths
            
        except Exception as e:
            self.podcast_logger.print_error(f"Failed to generate section audio: {str(e)}", e)
            return {}
    
    def _print_completion_summary(self, _: Optional[Path]) -> None:
        """Print completion summary.
        
        Args:
            _: Unused argument (kept for compatibility)
        """
        self.podcast_logger.print_header("Podcast Generation Complete!")
        
        self.podcast_logger.print_success(f"Section audio files generated successfully!")
        
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
    
    # Required arguments (conditionally)
    parser.add_argument(
        "--input",
        type=str,
        help="Path to input PDF file (required in normal mode)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for generated files (required in normal mode, optional in scripts-to-audio mode)"
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
        default="128k",
        help="Audio bitrate (default: 128k)"
    )
    
    parser.add_argument(
        "--quality",
        type=str,
        choices=["high", "standard", "compact"],
        default="standard",
        help="Audio quality preset: high (320kbps/24kHz/stereo), standard (128kbps/22kHz/mono), compact (96kbps/16kHz/mono)"
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
    
    parser.add_argument(
        "--scripts-to-audio",
        type=str,
        metavar="SCRIPTS_DIR",
        help="指定されたスクリプトディレクトリから音声のみを生成（PDF解析とスクリプト生成をスキップ）"
    )
    
    return parser


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # Check if scripts-to-audio mode
    if hasattr(args, 'scripts_to_audio') and args.scripts_to_audio:
        # Validate scripts directory
        if not Path(args.scripts_to_audio).exists():
            print(f"Error: Scripts directory not found: {args.scripts_to_audio}")
            return 1
        if not Path(args.scripts_to_audio).is_dir():
            print(f"Error: Specified path is not a directory: {args.scripts_to_audio}")
            return 1
        
        # In scripts-to-audio mode, input PDF is not required
        # Set a dummy value for compatibility with PodcastGenerator
        args.input = args.input or "dummy.pdf"
        
        # Create output directory if specified
        if hasattr(args, 'output_dir') and args.output_dir:
            Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    else:
        # Normal mode - validate required arguments
        if not args.input:
            print("Error: --input is required in normal mode")
            return 1
        if not args.output_dir:
            print("Error: --output-dir is required in normal mode")
            return 1
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