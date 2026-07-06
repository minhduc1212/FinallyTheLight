#!/usr/bin/env python3
"""
novel_translator - Main entry point

Usage examples:
  # Single file
  python main.py novel.txt -p my_project -g scifi

  # Directory (parallel)
  python main.py chapters/ -p my_project -g fantasy --workers 3

  # Resume after crash
  python main.py novel.txt -p my_project -g scifi --resume

  # Custom model & chunk size
  python main.py novel.txt -p my_project -m gemma4:27b --chunk-size 3000

  # Translate to Chinese
  python main.py novel.txt -p my_project -g default -l zh

  # Check checkpoint status
  python main.py --status -p my_project
"""

import argparse
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

from src.pipeline import TranslationPipeline
from src.checkpoint_manager import CheckpointManager
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn

console = Console()


GENRES = [
    'scifi', 'fantasy', 'romance', 'thriller',
    'historical', 'horror', 'default', 'xianxia', 'wuxia', 'isekai',
    'xuanhuan', 'urban', 'system', 'romcom', 'apocalypse', 'mystery'
]

LANGUAGES = ['vi', 'zh', 'en', 'ja', 'ko', 'id']


def parse_args():
    parser = argparse.ArgumentParser(
        description='📚 Novel Translation Pipeline - Multilingual & Multi-genre',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        'input', nargs='?',
        help='Input .txt/.md file or directory of files',
    )
    parser.add_argument(
        '-p', '--project', required=True,
        help='Project name (used for checkpoints, glossary files)',
    )
    parser.add_argument(
        '-g', '--genre', default='default', choices=GENRES,
        help='Novel genre (affects terminology and style)',
    )
    parser.add_argument(
        '-l', '--lang', default='vi', choices=LANGUAGES,
        help='Target language code (default: vi)',
    )
    parser.add_argument(
        '-m', '--model', default=None,
        help='Google GenAI model name (overrides config)',
    )
    parser.add_argument(
        '-o', '--output', default=None,
        help='Output directory (default: output/)',
    )
    parser.add_argument(
        '--chunk-size', type=int, default=None,
        help='Tokens per chunk (default: 2500)',
    )
    parser.add_argument(
        '--workers', type=int, default=None,
        help='Parallel file workers (default: 2)',
    )
    parser.add_argument(
        '-s', '--source-lang', default=None,
        choices=['en', 'zh', 'ja', 'ko'],
        help='Source language (default: auto-detect from content)',
    )
    parser.add_argument(
        '--resume', action='store_true',
        help='Resume from last checkpoint',
    )
    parser.add_argument(
        '--status', action='store_true',
        help='Show checkpoint status for project',
    )
    parser.add_argument(
        '--no-glossary', action='store_true',
        help='Disable auto glossary extraction (faster)',
    )
    parser.add_argument(
        '--no-summary', action='store_true',
        help='Disable auto chunk summary (faster, less context)',
    )

    return parser.parse_args()


def show_status(project: str):
    """Show checkpoint progress for a project."""
    mgr = CheckpointManager(project)
    checkpoints = mgr.list_checkpoints()

    if not checkpoints:
        console.print(f"[green]✅ No active checkpoints for project '{project}'[/green]")
        return

    console.print(f"\n[bold cyan]📋 Checkpoint status for project: {project}[/bold cyan]")
    
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        console=console,
        expand=True
    ) as progress:
        for stem in checkpoints:
            prog = mgr.get_progress(stem)
            if prog:
                count, total = prog
                progress.add_task(stem, total=total, completed=count)


def patch_settings_from_args(args):
    """Override settings.yaml values with CLI args."""
    import yaml

    with open('config/settings.yaml', 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)

    if args.no_glossary:
        settings['features']['auto_glossary'] = False
    if args.no_summary:
        settings['features']['auto_summary'] = False

    # Write back temporarily (pipeline reads from file)
    with open('config/settings.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(settings, f, allow_unicode=True, default_flow_style=False)


async def main():
    args = parse_args()

    # Status check mode
    if args.status:
        show_status(args.project)
        return

    if not args.input:
        print("❌ Please provide an input file or directory.")
        print("   Run with --help for usage.")
        sys.exit(1)

    if not Path(args.input).exists():
        print(f"❌ Input path not found: {args.input}")
        sys.exit(1)

    # Apply feature flags
    patch_settings_from_args(args)

    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan", justify="right")
    table.add_column("Value", style="bold white")
    
    table.add_row("Project", args.project)
    table.add_row("Genre", args.genre)
    table.add_row("Lang", args.lang)
    table.add_row("Model", args.model or "(from config)")
    table.add_row("Input", args.input)
    src_display = args.source_lang or 'auto'
    table.add_row("Source", src_display)
    if args.resume:
        table.add_row("Mode", "[yellow]RESUME[/yellow]")

    panel = Panel(
        table,
        title="[bold blue]📚 Novel Translator[/bold blue]",
        expand=False,
        border_style="cyan"
    )
    console.print()
    console.print(panel)
    console.print()

    pipeline = TranslationPipeline(
        project=args.project,
        model=args.model,
        genre=args.genre,
        target_lang=args.lang,
        source_lang=args.source_lang,
        output_dir=args.output,
        chunk_size=args.chunk_size,
        max_workers=args.workers,
    )

    await pipeline.run(args.input, resume=args.resume)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted. Progress saved. Run with --resume to continue.")
        sys.exit(0)