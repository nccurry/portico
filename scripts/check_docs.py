#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14.6,<3.15"
# dependencies = []
# ///
"""Validate local documentation links and standalone uv script headers."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)")
HTML_LINK = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)
STANDALONE_SCRIPTS = (
    Path("scripts/build_pages_demo.py"),
    Path("scripts/check_docs.py"),
    Path("scripts/init_config.py"),
    Path("scripts/smoke_container.py"),
)
UV_HEADER = (
    "#!/usr/bin/env -S uv run --script",
    "# /// script",
    '# requires-python = ">=3.14.6,<3.15"',
    "# dependencies = []",
    "# ///",
)


def tracked_markdown_files(root: Path) -> tuple[Path, ...]:
    """Return tracked Markdown files below the repository root."""
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(root / line for line in result.stdout.splitlines() if line and (root / line).is_file())


def local_targets(document: Path) -> tuple[str, ...]:
    """Return local link targets found in one Markdown document."""
    text = document.read_text(encoding="utf-8")
    markdown = (match.group(1) or match.group(2) for match in MARKDOWN_LINK.finditer(text))
    html = (match.group(1) for match in HTML_LINK.finditer(text))
    return tuple(target for target in (*markdown, *html) if not urlsplit(target).scheme and not target.startswith("#"))


def missing_targets(document: Path, root: Path) -> tuple[str, ...]:
    """Return links that do not resolve to repository files."""
    missing: list[str] = []
    for target in local_targets(document):
        path_text = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if not path_text:
            continue
        candidate = (document.parent / path_text).resolve()
        if not candidate.is_relative_to(root.resolve()) or not candidate.exists():
            missing.append(target)
    return tuple(missing)


def has_uv_header(script: Path) -> bool:
    """Return whether a script starts with the supported uv metadata."""
    lines = script.read_text(encoding="utf-8").splitlines()
    return tuple(lines[: len(UV_HEADER)]) == UV_HEADER


def main() -> int:
    """Print documentation problems and return a process status."""
    problems: list[str] = []
    for document in tracked_markdown_files(PROJECT_ROOT):
        for target in missing_targets(document, PROJECT_ROOT):
            problems.append(f"{document.relative_to(PROJECT_ROOT)}: missing target {target}")

    for relative_script in STANDALONE_SCRIPTS:
        if not has_uv_header(PROJECT_ROOT / relative_script):
            problems.append(f"{relative_script}: missing the standard uv script header")

    if problems:
        print("Documentation checks failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1

    print("Documentation links, assets, and uv script headers are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
