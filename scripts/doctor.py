"""Validate configured local CSV data or remote spreadsheet data."""

from __future__ import annotations

import argparse
import math
import sys
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

from src.config import ConfigError, Settings, load_settings
from src.scrubbing import (
    BALANCE_HISTORY_REQUIRED_COLUMNS,
    CATEGORIES_REQUIRED_COLUMNS,
    TRANSACTIONS_REQUIRED_COLUMNS,
    SpreadsheetSchemaError,
    validate_required_columns,
)
from src.sheet_config import SheetConfigError, SheetLocation, parse_sheet_location

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SECRETS_PATH = PROJECT_ROOT / ".streamlit" / "secrets.toml"
SHEET_NAMES = ("transactions", "balance_history", "categories", "accounts")
EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_USAGE = 2


@dataclass(frozen=True)
class DoctorResult:
    """One safe diagnostic result."""

    name: str
    passed: bool
    detail: str


SheetReader = Callable[[SheetLocation, float], pd.DataFrame]


def _read_google_sheet(location: SheetLocation, timeout: float) -> pd.DataFrame:
    request = Request(location.export_url, headers={"User-Agent": "portico-doctor/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return pd.read_csv(BytesIO(response.read()))


def _read_secrets(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError as error:
        raise ConfigError(f"Secrets file does not exist: {path.name}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Invalid TOML in {path.name}: {error}") from error
    except OSError as error:
        raise ConfigError(f"Could not read secrets file: {path.name}") from error


def _sheet_locations(path: Path) -> dict[str, SheetLocation]:
    secrets = _read_secrets(path)
    connections = secrets.get("connections")
    if not isinstance(connections, dict):
        raise ConfigError("Secrets must contain a [connections] table")

    locations: dict[str, SheetLocation] = {}
    for name in SHEET_NAMES:
        connection = connections.get(name)
        if not isinstance(connection, dict):
            raise ConfigError(f"Secrets must contain [connections.{name}]")
        try:
            locations[name] = parse_sheet_location(connection.get("spreadsheet"))
        except SheetConfigError as error:
            raise ConfigError(f"connections.{name}.spreadsheet: {error}") from error

    mappings = [(location.document_id, location.gid) for location in locations.values()]
    if len(mappings) != len(set(mappings)):
        raise ConfigError("Two connections point to the same Google Sheet tab")
    return locations


def _validate_sheet(name: str, dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        raise SpreadsheetSchemaError(f"{name} sheet is empty")
    if name == "transactions":
        validate_required_columns(dataframe, TRANSACTIONS_REQUIRED_COLUMNS, "Transactions")
        pd.to_datetime(dataframe["Date"], format="mixed", errors="raise")
        pd.to_numeric(dataframe["Amount"].astype(str).str.replace(r"[$,]", "", regex=True), errors="raise")
    elif name == "balance_history":
        validate_required_columns(dataframe, BALANCE_HISTORY_REQUIRED_COLUMNS, "Balance History")
        pd.to_datetime(dataframe["Date"], format="mixed", errors="raise")
        pd.to_numeric(dataframe["Balance"].astype(str).str.replace(r"[$,]", "", regex=True), errors="raise")
    elif name == "categories":
        validate_required_columns(dataframe, CATEGORIES_REQUIRED_COLUMNS, "Categories")
    elif len(dataframe.columns) < 4:
        raise SpreadsheetSchemaError(f"Accounts sheet must have at least 4 columns; found {len(dataframe.columns)}")


def _safe_error(error: Exception) -> str:
    """Return a diagnostic message that cannot contain sheet values or URLs."""
    if isinstance(error, (ConfigError, SpreadsheetSchemaError)):
        return str(error)
    if isinstance(error, FileNotFoundError):
        return "required data file is missing"
    return f"{type(error).__name__}: data could not be read or parsed"


def run_doctor(
    settings: Settings,
    *,
    secrets_path: Path = DEFAULT_SECRETS_PATH,
    timeout: float = 10.0,
    sheet_reader: SheetReader = _read_google_sheet,
) -> list[DoctorResult]:
    """Run safe checks for the selected data source."""
    results = [DoctorResult("configuration", True, f"data source is {settings.data.source}")]
    if settings.data.source == "local":
        directory = settings.data.directory
        assert directory is not None
        sources = {name: directory / f"{name}.csv" for name in SHEET_NAMES}
        for name, path in sources.items():
            try:
                dataframe = pd.read_csv(path)
                _validate_sheet(name, dataframe)
            except Exception as error:
                results.append(DoctorResult(name, False, _safe_error(error)))
            else:
                results.append(DoctorResult(name, True, "local CSV data is readable and has the expected schema"))
        return results

    try:
        locations = _sheet_locations(secrets_path)
    except ConfigError as error:
        results.append(DoctorResult("remote spreadsheet", False, str(error)))
        return results

    for name, location in locations.items():
        try:
            dataframe = sheet_reader(location, timeout)
            _validate_sheet(name, dataframe)
        except Exception as error:
            results.append(DoctorResult(name, False, _safe_error(error)))
        else:
            results.append(DoctorResult(name, True, "sheet is readable and has the expected schema"))
    return results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Portico data settings without printing financial rows or URLs.",
        epilog="Exit codes: 0 = all checks passed, 1 = a check failed, 2 = invalid command usage.",
    )
    parser.add_argument(
        "--secrets",
        type=Path,
        default=DEFAULT_SECRETS_PATH,
        help="Path to Streamlit secrets.toml for remote spreadsheet mode.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Maximum seconds for each remote spreadsheet request.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the configuration doctor and print safe results."""
    arguments = _parser().parse_args(argv)
    if not math.isfinite(arguments.timeout) or arguments.timeout <= 0:
        print("[FAIL] timeout: --timeout must be a finite number greater than zero", file=sys.stderr)
        return EXIT_USAGE
    try:
        settings = load_settings()
    except ConfigError as error:
        print(f"[FAIL] configuration: {error}", file=sys.stderr)
        return EXIT_CHECK_FAILED

    results = run_doctor(settings, secrets_path=arguments.secrets, timeout=arguments.timeout)
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        output = sys.stdout if result.passed else sys.stderr
        print(f"[{marker}] {result.name}: {result.detail}", file=output)
    return EXIT_OK if all(result.passed for result in results) else EXIT_CHECK_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
