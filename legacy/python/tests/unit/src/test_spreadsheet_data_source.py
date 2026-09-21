import sys
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


def test_local_source_reads_csv_without_opening_connection(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    pd.DataFrame({"value": [1]}).to_csv(tmp_path / "example.csv", index=False)
    settings = SimpleNamespace(data=SimpleNamespace(source="local", directory=tmp_path))
    monkeypatch.setattr("src.spreadsheet.get_settings", lambda: settings)
    monkeypatch.setitem(sys.modules, "streamlit_gsheets", None)

    def reject_connection(*args: object, **kwargs: object) -> Never:
        raise AssertionError("local CSV mode must not open a Google Sheets connection")

    monkeypatch.setattr("src.spreadsheet.st.connection", reject_connection)
    spreadsheet = ExampleSpreadsheet()

    assert spreadsheet.raw_df.to_dict(orient="records") == [{"value": 1}]


def test_remote_source_reads_the_configured_connection(monkeypatch: MonkeyPatch) -> None:
    expected = pd.DataFrame({"value": [2]})
    settings = SimpleNamespace(data=SimpleNamespace(source="remote"))
    connection = SimpleNamespace(read=lambda: expected)
    monkeypatch.setattr("src.spreadsheet.get_settings", lambda: settings)
    monkeypatch.setattr("src.spreadsheet.st.connection", lambda **kwargs: connection)

    spreadsheet = ExampleSpreadsheet()

    assert spreadsheet.raw_df.equals(expected)
