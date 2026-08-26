"""Parse link-readable Google Sheet URLs without exposing their values."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


class SheetConfigError(ValueError):
    """A user-facing Google Sheet configuration error."""


@dataclass(frozen=True)
class SheetLocation:
    """A parsed Google Sheet document and tab."""

    document_id: str
    gid: int

    @property
    def export_url(self) -> str:
        """Return the read-only CSV export URL."""
        return f"https://docs.google.com/spreadsheets/d/{self.document_id}/export?format=csv&gid={self.gid}"


def parse_sheet_location(value: object) -> SheetLocation:
    """Parse one link-readable Google Sheet URL."""
    if not isinstance(value, str) or not value.strip():
        raise SheetConfigError("spreadsheet must be a non-empty URL")
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.hostname != "docs.google.com":
        raise SheetConfigError("spreadsheet must use an https://docs.google.com URL")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3 or parts[0:2] != ["spreadsheets", "d"] or not parts[2]:
        raise SheetConfigError("spreadsheet URL must contain /spreadsheets/d/<document-id>")
    document_id = parts[2]
    if not all(character.isalnum() or character in {"-", "_"} for character in document_id):
        raise SheetConfigError("spreadsheet URL has an invalid document ID")

    gids = parse_qs(parsed.query).get("gid", []) + parse_qs(parsed.fragment).get("gid", [])
    if not gids or any(not gid.isdigit() for gid in gids) or len(set(gids)) != 1:
        raise SheetConfigError("spreadsheet URL must contain one numeric gid")
    return SheetLocation(document_id=document_id, gid=int(gids[0]))
