"""Command-line entry point for weekly Discord expense summaries."""

from __future__ import annotations

from src.discord_notifier import main


if __name__ == "__main__":
    raise SystemExit(main())
