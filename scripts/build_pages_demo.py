#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14.6,<3.15"
# dependencies = []
# ///
"""Build the static GitHub Pages artifact for the Portico demo."""

from __future__ import annotations

import argparse
import re
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
REVISION_PATTERN = re.compile(r"[A-Za-z0-9._-]+")


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


def clean_output(output: Path) -> None:
    """Replace a prior build only inside its explicit output directory."""
    resolved = output.resolve()
    build_root = (PROJECT_ROOT / "build").resolve()
    if resolved == build_root or not resolved.is_relative_to(build_root):
        raise ValueError("The Pages output must be inside the build directory")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def build_gallery(output: Path, revision: str) -> None:
    """Build the screenshot gallery."""
    if REVISION_PATTERN.fullmatch(revision) is None:
        raise ValueError("Revision must contain only letters, numbers, dots, underscores, or hyphens")
    template = (PROJECT_ROOT / "web-demo" / "static-gallery.html").read_text(encoding="utf-8")
    (output / "index.html").write_text(template.replace("__REVISION__", revision), encoding="utf-8")
    shutil.copy2(PROJECT_ROOT / "assets" / "brand" / "logo.svg", output / "logo.svg")
    images = output / "images"
    images.mkdir()
    for name in SCREENSHOTS:
        shutil.copy2(PROJECT_ROOT / "assets" / "screenshots" / name, images / name)
    (output / ".nojekyll").touch()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--revision", default=None)
    return parser.parse_args()


def main() -> None:
    """Build the selected Pages artifact."""
    args = parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    clean_output(output)
    build_gallery(output, args.revision or current_revision())


if __name__ == "__main__":
    main()
