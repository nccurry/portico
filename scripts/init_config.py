#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14.6,<3.15"
# dependencies = []
# ///
"""Create an ignored local settings file without overwriting user data."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = PROJECT_ROOT / "config" / "local.example.toml"
TARGET = PROJECT_ROOT / "config" / "local.toml"


def main() -> int:
    """Copy the local settings example when the target does not exist."""
    if TARGET.exists():
        print(f"Local configuration already exists: {TARGET}", file=sys.stderr)
        return 1
    shutil.copyfile(SOURCE, TARGET)
    print(f"Created {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
