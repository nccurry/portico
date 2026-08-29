from pathlib import Path

import pandas as pd
import pytest
from pytest import MonkeyPatch

from scripts.doctor import EXIT_CHECK_FAILED, EXIT_OK, _sheet_locations, main, run_doctor
from src.config import ConfigError, load_settings
from src.sheet_config import SheetLocation


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULTS = PROJECT_ROOT / "config" / "defaults.toml"


def test_demo_doctor_validates_committed_data(tmp_path: Path) -> None:
    settings = load_settings(
        defaults_path=DEFAULTS,
        local_path=tmp_path / "missing.toml",
        environ={"PORTICO_DATA_SOURCE": "demo"},
        project_root=PROJECT_ROOT,
    )

    results = run_doctor(settings)

    assert all(result.passed for result in results)
    assert {result.name for result in results} == {
        "configuration",
        "transactions",
        "balance_history",
        "categories",
        "accounts",
    }


def test_live_doctor_reports_schema_failure_without_values(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(
        """
[connections.transactions]
spreadsheet = "https://docs.google.com/spreadsheets/d/book/edit?gid=1"
[connections.balance_history]
spreadsheet = "https://docs.google.com/spreadsheets/d/book/edit?gid=2"
[connections.categories]
spreadsheet = "https://docs.google.com/spreadsheets/d/book/edit?gid=3"
[connections.accounts]
spreadsheet = "https://docs.google.com/spreadsheets/d/book/edit?gid=4"
""".strip(),
        encoding="utf-8",
    )
    settings = load_settings(
        defaults_path=DEFAULTS,
        local_path=tmp_path / "missing.toml",
        environ={},
        project_root=PROJECT_ROOT,
    )

    results = run_doctor(
        settings,
        secrets_path=secrets,
        sheet_reader=lambda location, timeout: pd.DataFrame({"private value": ["do not print"]}),
    )

    assert not all(result.passed for result in results)
    output = " ".join(result.detail for result in results)
    assert "do not print" not in output
    assert "docs.google.com" not in output


def test_duplicate_sheet_tab_is_rejected(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.toml"
    connection = 'spreadsheet = "https://docs.google.com/spreadsheets/d/book/edit?gid=1"'
    secrets.write_text(
        "\n".join(
            f"[connections.{name}]\n{connection}"
            for name in ("transactions", "balance_history", "categories", "accounts")
        ),
        encoding="utf-8",
    )

    try:
        _sheet_locations(secrets)
    except ConfigError as error:
        assert "same Google Sheet tab" in str(error)
    else:
        raise AssertionError("duplicate tabs should fail validation")


def test_unreadable_secrets_path_is_reported(tmp_path: Path) -> None:
    settings = load_settings(
        defaults_path=DEFAULTS,
        local_path=tmp_path / "missing.toml",
        environ={},
        project_root=PROJECT_ROOT,
    )

    results = run_doctor(settings, secrets_path=tmp_path)

    assert results[-1].name == "Google Sheets"
    assert not results[-1].passed
    assert results[-1].detail == f"Could not read secrets file: {tmp_path.name}"


def test_network_failure_does_not_print_exception_details(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(
        "\n".join(
            f'[connections.{name}]\nspreadsheet = "https://docs.google.com/spreadsheets/d/book/edit?gid={gid}"'
            for gid, name in enumerate(("transactions", "balance_history", "categories", "accounts"), start=1)
        ),
        encoding="utf-8",
    )
    settings = load_settings(
        defaults_path=DEFAULTS,
        local_path=tmp_path / "missing.toml",
        environ={},
        project_root=PROJECT_ROOT,
    )

    def fail_read(location: SheetLocation, timeout: float) -> pd.DataFrame:
        raise RuntimeError("private URL and response details")

    results = run_doctor(settings, secrets_path=secrets, sheet_reader=fail_read)
    details = " ".join(result.detail for result in results)

    assert "private URL" not in details
    assert details.count("RuntimeError: data could not be read or parsed") == 4


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf", "-inf"])
def test_main_rejects_invalid_timeouts(monkeypatch: MonkeyPatch, timeout: str) -> None:
    monkeypatch.setenv("PORTICO_DATA_SOURCE", "demo")

    assert main([f"--timeout={timeout}"]) == 2


def test_main_returns_stable_status_codes(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("PORTICO_DATA_SOURCE", "demo")

    assert main([]) == EXIT_OK
    assert EXIT_CHECK_FAILED == 1
