#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14.6,<3.15"
# dependencies = []
# ///
"""Reject private data in files that can be committed to the repository."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def repository_files() -> list[Path]:
    """Return tracked and untracked files, excluding ignored local files."""
    output = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    return [Path(item.decode()) for item in output.split(b"\0") if item]


def sensitive_path_reason(path: Path) -> str | None:
    """Return why a path must not be committed, if applicable."""
    normalized = path.as_posix().lower()
    name = path.name.lower()

    if normalized.startswith(".idea/"):
        return "IDE metadata can contain local paths"
    if normalized == ".streamlit/secrets.toml":
        return "Streamlit secrets file"
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return "environment secrets file"
    if path.suffix.lower() in {".key", ".p12", ".pem", ".pfx", ".xlsx"}:
        return "credential or private-data file type"
    if re.fullmatch(r"(?:credentials|service-account).*\.json", name):
        return "credentials file"
    return None


def populated_notebook(path: Path, text: str) -> bool:
    """Return whether a notebook contains saved execution outputs."""
    if path.suffix.lower() != ".ipynb":
        return False
    try:
        notebook = json.loads(text)
    except json.JSONDecodeError:
        return True
    return any(cell.get("outputs") for cell in notebook.get("cells", []))


def sensitive_text_patterns() -> dict[str, re.Pattern[str]]:
    """Return patterns for private text that must not be committed."""
    unix_home = "/" + "home" + "/"
    mac_home = "/" + "Users" + "/"
    placeholder_user = r"(?!(?:example|portico|tester|tiller|user|vscode)(?:[/\s\"']|$))"
    return {
        "absolute user path": re.compile(
            r"(?:(?i:[A-Z]:[\\/]Users[\\/])[^\\/\s]+|"
            + re.escape(unix_home)
            + placeholder_user
            + r"[^/\s]+|"
            + re.escape(mac_home)
            + placeholder_user
            + r"[^/\s]+)"
        ),
        "email address": re.compile(
            r"(?i)\b(?![^@\s]+@(?:example\.com|users\.noreply\.github\.com)\b)"
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
        ),
        "private key": re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        "service credential": re.compile(
            r"\b(?:gh[pousr]_" + r"[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
            r"|sk-" + r"[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}"
            r"|AKIA[0-9A-Z]{16})\b"
        ),
        "Discord webhook token": re.compile(r"(?i)discord(?:app)?\.com/api/webhooks/[0-9]{5,}/[A-Za-z0-9._-]{20,}"),
        "Google Sheet document ID": re.compile(
            "docs.google.com/"
            + r"spreadsheets/d/[A-Za-z0-9_-]{20,}"
            + r"|SPREADSHEET_ID\s*=\s*[\"']?[A-Za-z0-9_-]{20,}"
        ),
        "internal corporate domain": re.compile(r"(?i)\b(?:nvi" + r"dia\.com|pinlight-" + r"software)\b"),
    }


def main() -> int:
    """Scan repository candidates and report actionable violations."""
    violations: list[str] = []
    for path in repository_files():
        if reason := sensitive_path_reason(path):
            violations.append(f"{path}: {reason}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            continue
        if populated_notebook(path, text):
            violations.append(f"{path}: notebook contains saved outputs")
        for label, pattern in sensitive_text_patterns().items():
            if pattern.search(text):
                violations.append(f"{path}: {label}")

    if violations:
        print("Repository privacy check failed:", file=sys.stderr)
        for violation in sorted(set(violations)):
            print(f"  - {violation}", file=sys.stderr)
        return 1

    print("Repository privacy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
