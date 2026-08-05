#!/usr/bin/env python3
"""Command-line entry point for weekly Discord expense summaries."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run() -> int:
    """Import and run the notifier after adding the repository root."""
    from src.discord_notifier import main

    return main()


if __name__ == "__main__":
    raise SystemExit(run())
