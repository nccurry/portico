import pytest

from src.sheet_config import SheetConfigError, parse_sheet_location


@pytest.mark.parametrize(
    "url",
    [
        "https://docs.google.com/spreadsheets/d/example_123/edit?usp=sharing&gid=42",
        "https://docs.google.com/spreadsheets/d/example_123/edit#gid=42",
        "https://docs.google.com/spreadsheets/d/example_123/edit?gid=42#gid=42",
    ],
)
def test_parse_google_sheet_tab_url(url: str) -> None:
    location = parse_sheet_location(url)

    assert location.document_id == "example_123"
    assert location.gid == 42
    assert location.export_url == ("https://docs.google.com/spreadsheets/d/example_123/export?format=csv&gid=42")


@pytest.mark.parametrize(
    "url",
    [
        "http://docs.google.com/spreadsheets/d/example/edit?gid=1",
        "https://example.com/spreadsheets/d/example/edit?gid=1",
        "https://docs.google.com/spreadsheets/d/example/edit",
        "https://docs.google.com/spreadsheets/d/example/edit?gid=abc",
        "https://docs.google.com/spreadsheets/d/example/edit?gid=1#gid=2",
    ],
)
def test_reject_invalid_sheet_urls(url: str) -> None:
    with pytest.raises(SheetConfigError):
        parse_sheet_location(url)
