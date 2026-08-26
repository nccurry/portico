from pathlib import Path
from types import SimpleNamespace
from typing import Never, override

import pandas as pd
from pytest import MonkeyPatch

from src.spreadsheet import Spreadsheet


class ExampleSpreadsheet(Spreadsheet):
    name = "example"

    @override
    def scrub(self) -> None:
        self.scrubbed_df = self.raw_df


def test_demo_load_reads_csv_without_opening_connection(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    pd.DataFrame({"value": [1]}).to_csv(tmp_path / "example.csv", index=False)
    settings = SimpleNamespace(data=SimpleNamespace(is_demo=True, demo_directory=tmp_path))
    monkeypatch.setattr("src.spreadsheet.get_settings", lambda: settings)

    def reject_connection(*args: object, **kwargs: object) -> Never:
        raise AssertionError("demo mode must not open a Google Sheets connection")

    monkeypatch.setattr("src.spreadsheet.st.connection", reject_connection)
    spreadsheet = ExampleSpreadsheet()

    assert spreadsheet.raw_df.to_dict(orient="records") == [{"value": 1}]


def test_live_load_reads_google_sheets_connection(monkeypatch: MonkeyPatch) -> None:
    expected = pd.DataFrame({"value": [2]})
    settings = SimpleNamespace(data=SimpleNamespace(is_demo=False))
    connection = SimpleNamespace(read=lambda: expected)
    monkeypatch.setattr("src.spreadsheet.get_settings", lambda: settings)
    monkeypatch.setattr("src.spreadsheet.st.connection", lambda **kwargs: connection)

    spreadsheet = ExampleSpreadsheet()

    assert spreadsheet.raw_df.equals(expected)
