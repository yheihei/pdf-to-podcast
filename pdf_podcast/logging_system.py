"""Logging system module with rich console output and progress tracking."""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
)
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from tqdm import tqdm


class PodcastLogger:
    """Enhanced logging system for podcast generation with rich output and progress tracking."""
    
    def __init__(self, log_dir: Optional[Path] = None, verbose: bool = False):
        """Initialize podcast logger.
        
        Args:
            log_dir: Directory to save log files (defaults to ./logs)
            verbose: Enable verbose logging output
        """
        self.console = Console()
        self.verbose = verbose
        
        # Setup log directory
        if log_dir is None:
            log_dir = Path("./logs")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # Progress tracking
        self.progress = None
        self.task_ids: Dict[str, Any] = {}
        
    def _setup_logging(self) -> None:
        """Setup logging configuration with rich handler and file output."""
        # Configure root logger
        logging.basicConfig(
            level=logging.DEBUG if self.verbose else logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[
                RichHandler(
                    console=self.console,
                    show_path=self.verbose,
                    show_time=True,
                    rich_tracebacks=True
                )
            ]
        )
        
        # Add file handler for detailed logs
        log_file = self.log_dir / f"tool_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Add file handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        
        self.console.print(f"[dim]Logs will be saved to: {log_file}[/dim]")
    
    def print_header(self, title: str, subtitle: Optional[str] = None) -> None:
        """Print styled header with title and optional subtitle.
        
        Args:
            title: Main title text
            subtitle: Optional subtitle text
        """
        header_text = f"[bold blue]{title}[/bold blue]"
        if subtitle:
            header_text += f"\n[dim]{subtitle}[/dim]"
        
        panel = Panel(
            header_text,
            border_style="blue",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def print_summary(self, data: Dict[str, Any]) -> None:
        """Print summary table with key-value data.
        
        Args:
            data: Dictionary of summary data to display
        """
        table = Table(title="Summary", show_header=True, header_style="bold magenta")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in data.items():
            table.add_row(str(key), str(value))
        
        self.console.print(table)
    
    def print_progress_summary(self, summary: Dict[str, Any]) -> None:
        """Print progress summary with statistics.
        
        Args:
            summary: Progress summary data from manifest
        """
        table = Table(title="Progress Summary", show_header=True, header_style="bold yellow")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        # Main statistics
        table.add_row("Total Chapters", str(summary.get("total_chapters", 0)))
        table.add_row("Completed", str(summary.get("completed_chapters", 0)))
        table.add_row("Failed", str(summary.get("failed_chapters", 0)))
        table.add_row("Progress", f"{summary.get('progress_percent', 0):.1f}%")
        table.add_row("Episode Ready", "✅" if summary.get("episode_ready", False) else "❌")
        
        self.console.print(table)
        
        # Status breakdown
        if "status_counts" in summary:
            status_table = Table(title="Chapter Status Breakdown", show_header=True)
            status_table.add_column("Status", style="cyan")
            status_table.add_column("Count", style="green")
            
            for status, count in summary["status_counts"].items():
                if count > 0:
                    status_table.add_row(status.replace("_", " ").title(), str(count))
            
            self.console.print(status_table)
    
    def start_progress(self, total_tasks: Optional[int] = None) -> Progress:
        """Start progress tracking with rich progress bar.
        
        Args:
            total_tasks: Total number of tasks (optional for indeterminate progress)
            
        Returns:
            Progress object for task management
        """
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=False
        )
        
        self.progress.start()
        return self.progress
    
    def add_task(self, description: str, total: Optional[int] = None) -> Any:
        """Add a new task to progress tracking.
        
        Args:
            description: Task description
            total: Total units for this task
            
        Returns:
            Task ID for updating progress
        """
        if self.progress is None:
            self.start_progress()
        
        task_id = self.progress.add_task(description, total=total)
        self.task_ids[description] = task_id
        return task_id
    
    def update_task(self, task_id: Any, advance: int = 1, description: Optional[str] = None) -> None:
        """Update task progress.
        
        Args:
            task_id: Task ID returned from add_task
            advance: Number of units to advance
            description: Optional new description
        """
        if self.progress:
            self.progress.update(task_id, advance=advance, description=description)
    
    def complete_task(self, task_id: Any, description: Optional[str] = None) -> None:
        """Mark task as completed.
        
        Args:
            task_id: Task ID to complete
            description: Optional completion message
        """
        if self.progress:
            if description:
                self.progress.update(task_id, description=f"✅ {description}")
            else:
                self.progress.update(task_id, description="✅ Completed")
    
    def stop_progress(self) -> None:
        """Stop progress tracking."""
        if self.progress:
            self.progress.stop()
            self.progress = None
            self.task_ids.clear()
    
    def print_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Print formatted error message.
        
        Args:
            message: Error message
            exception: Optional exception object
        """
        error_text = f"[bold red]❌ Error:[/bold red] {message}"
        if exception and self.verbose:
            error_text += f"\n[dim red]{str(exception)}[/dim red]"
        
        self.console.print(error_text)
    
    def print_warning(self, message: str) -> None:
        """Print formatted warning message.
        
        Args:
            message: Warning message
        """
        self.console.print(f"[bold yellow]⚠️  Warning:[/bold yellow] {message}")
    
    def print_success(self, message: str) -> None:
        """Print formatted success message.
        
        Args:
            message: Success message
        """
        self.console.print(f"[bold green]✅ Success:[/bold green] {message}")
    
    def print_info(self, message: str) -> None:
        """Print formatted info message.
        
        Args:
            message: Info message
        """
        self.console.print(f"[blue]ℹ️  Info:[/blue] {message}")
    
    def print_chapter_status(self, chapter_title: str, status: str, details: Optional[str] = None) -> None:
        """Print chapter processing status.
        
        Args:
            chapter_title: Title of the chapter
            status: Current status
            details: Optional additional details
        """
        status_icons = {
            "pending": "⏳",
            "script_generated": "📝",
            "audio_generated": "🎵",
            "completed": "✅",
            "failed": "❌",
            "failed_rate_limit": "🚫"
        }
        
        icon = status_icons.get(status, "📋")
        status_text = status.replace("_", " ").title()
        
        message = f"{icon} [bold]{chapter_title}[/bold]: {status_text}"
        if details:
            message += f" [dim]({details})[/dim]"
        
        self.console.print(message)
    
    def create_simple_progress_bar(self, total: int, description: str = "Processing") -> tqdm:
        """Create a simple tqdm progress bar for compatibility.
        
        Args:
            total: Total number of items
            description: Description for the progress bar
            
        Returns:
            tqdm progress bar instance
        """
        return tqdm(
            total=total,
            desc=description,
            unit="item",
            ncols=80,
            file=sys.stdout
        )
    
    def print_file_info(self, file_path: Path, description: str) -> None:
        """Print file information.
        
        Args:
            file_path: Path to the file
            description: Description of the file
        """
        if file_path.exists():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            self.console.print(f"📁 {description}: [cyan]{file_path}[/cyan] ({size_mb:.1f} MB)")
        else:
            self.console.print(f"📁 {description}: [red]{file_path}[/red] (not found)")


def setup_logger(log_dir: Optional[Path] = None, verbose: bool = False) -> PodcastLogger:
    """Setup and return a configured podcast logger.
    
    Args:
        log_dir: Directory to save log files
        verbose: Enable verbose logging
        
    Returns:
        Configured PodcastLogger instance
    """
    return PodcastLogger(log_dir=log_dir, verbose=verbose)