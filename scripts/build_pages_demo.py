#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14.6,<3.15"
# dependencies = []
# ///
"""Build the static GitHub Pages artifact for the Portico demo."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "pages"
SCREENSHOTS = (
    "demo-overview.png",
    "demo-spending.png",
    "demo-budget.png",
    "demo-financial-independence.png",
    "demo-data-health.png",
)


def current_revision() -> str:
    """Return the source revision for local builds."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_gallery(revision: str) -> None:
    """Build the screenshot gallery."""
    if DEFAULT_OUTPUT.exists():
        shutil.rmtree(DEFAULT_OUTPUT)
    DEFAULT_OUTPUT.mkdir(parents=True)

    template = (PROJECT_ROOT / "web-demo" / "static-gallery.html").read_text(encoding="utf-8")
    (DEFAULT_OUTPUT / "index.html").write_text(template.replace("__REVISION__", revision), encoding="utf-8")
    shutil.copy2(PROJECT_ROOT / "assets" / "brand" / "logo.svg", DEFAULT_OUTPUT / "logo.svg")
    images = DEFAULT_OUTPUT / "images"
    images.mkdir()
    for name in SCREENSHOTS:
        shutil.copy2(PROJECT_ROOT / "assets" / "screenshots" / name, images / name)
    (DEFAULT_OUTPUT / ".nojekyll").touch()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default=None)
    return parser.parse_args()


def main() -> None:
    """Build the selected Pages artifact."""
    args = parse_args()
    build_gallery(args.revision or current_revision())


if __name__ == "__main__":
    main()
