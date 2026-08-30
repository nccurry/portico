"""Headless Google Sheets and Discord workflow for weekly expense summaries."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import datetime as dt
from io import TextIOWrapper
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import tomllib
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

import pandas as pd

from src.scrubbing import SpreadsheetSchemaError, scrub_categories, scrub_transactions
from src.sheet_config import SheetConfigError, parse_sheet_location
from src.weekly_expenses import (
    AVERAGE_WEEKS,
    ROLLING_WEEKS,
    ReportPeriod,
    WeeklyExpenseError,
    WeeklyExpenseReport,
    calculate_weekly_report,
    completed_week,
    validate_selected_categories,
)


DEFAULT_SECRETS_PATH = Path(".streamlit/secrets.toml")
DEFAULT_STATE_PATH = Path(".local/discord-weekly-state.json")
HTTP_TIMEOUT_SECONDS = 30
USER_AGENT = "portico-weekly-summary/1.0"


class NotifierError(RuntimeError):
    """Raised when configuration or an external notifier operation fails."""


@dataclass(frozen=True)
class NotifierConfig:
    """Private settings required by the headless notifier."""

    transactions_url: str
    categories_url: str
    webhook_url: str
    categories: tuple[str, ...]


def load_config(path: Path = DEFAULT_SECRETS_PATH) -> NotifierConfig:
    """Load and validate notifier settings from Streamlit secrets."""
    try:
        with path.open("rb") as secrets_file:
            data = tomllib.load(secrets_file)
    except FileNotFoundError as error:
        raise NotifierError("Missing .streamlit/secrets.toml. Copy and edit the example file.") from error
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise NotifierError("The Streamlit secrets file is not valid TOML.") from error

    connections = _table(data, "connections")
    transactions = _table(connections, "transactions")
    categories_connection = _table(connections, "categories")
    notifications = _table(data, "notifications")
    discord = _table(notifications, "discord")

    category_values = discord.get("categories")
    if not isinstance(category_values, list) or not all(isinstance(item, str) for item in category_values):
        raise NotifierError("notifications.discord.categories must be a TOML array of strings.")
    if not category_values:
        raise NotifierError("notifications.discord.categories must contain at least one Category value.")
    if len(set(category_values)) != len(category_values):
        raise NotifierError("notifications.discord.categories must not contain duplicates.")
    if any(not item or item != item.strip() for item in category_values):
        raise NotifierError("Each notifications.discord.categories item must be a non-empty exact Category value.")

    config = NotifierConfig(
        transactions_url=_string(transactions, "spreadsheet", "connections.transactions"),
        categories_url=_string(categories_connection, "spreadsheet", "connections.categories"),
        webhook_url=_string(discord, "webhook_url", "notifications.discord"),
        categories=tuple(category_values),
    )
    google_export_url(config.transactions_url)
    google_export_url(config.categories_url)
    _validate_webhook_url(config.webhook_url)
    return config


def google_export_url(sheet_url: str) -> str:
    """Convert a configured Google Sheets tab URL to a CSV export URL."""
    try:
        return parse_sheet_location(sheet_url).export_url
    except SheetConfigError as error:
        raise NotifierError("A Google Sheets connection URL is invalid.") from error


def read_google_sheet(sheet_url: str, label: str) -> pd.DataFrame:
    """Read one link-accessible Google Sheets tab without Streamlit."""
    request = Request(google_export_url(sheet_url), headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return pd.read_csv(response)
    except (HTTPError, URLError, OSError, ValueError) as error:
        raise NotifierError(f"Failed to read the {label} sheet. Check link access and the configured gid.") from error


def load_report_data(config: NotifierConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and scrub the category metadata and transactions."""
    try:
        raw_categories = read_google_sheet(config.categories_url, "Categories")
        metadata, _ = scrub_categories(raw_categories)
        raw_transactions = read_google_sheet(config.transactions_url, "Transactions")
        transactions = scrub_transactions(raw_transactions, metadata)
    except SpreadsheetSchemaError as error:
        raise NotifierError(str(error)) from error
    except (TypeError, ValueError) as error:
        raise NotifierError("A configured sheet contains invalid spreadsheet data.") from error
    return transactions, metadata


def check_webhook(webhook_url: str) -> None:
    """Check webhook access without creating a Discord message."""
    _discord_request(webhook_url, method="GET")


def post_webhook(webhook_url: str, payload: Mapping[str, Any]) -> str:
    """Create one Discord webhook message and return its message ID."""
    parsed = urlparse(webhook_url)
    query = parse_qs(parsed.query)
    query["wait"] = ["true"]
    target = urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    response = _discord_request(target, method="POST", payload=payload)
    message_id = response.get("id")
    if not isinstance(message_id, str) or not message_id:
        raise NotifierError("Discord accepted the request but did not return a message ID.")
    return message_id


def test_payload() -> dict[str, Any]:
    """Return a connection message that contains no financial data."""
    return {
        "embeds": [
            {
                "title": "Portico weekly summary is connected",
                "description": "No financial data was included in this test message.",
                "color": 0x95A5A6,
            }
        ],
        "allowed_mentions": {"parse": []},
    }


def report_payload(report: WeeklyExpenseReport) -> dict[str, Any]:
    """Return the Discord embed for a weekly expense report."""
    category_lines = []
    for item in report.categories:
        summary = (
            f"**{_escape_markdown(item.name)}** — **{_currency(item.amount)}** · {_usual_change_text(item.change)}"
        )
        if item.top_vendors:
            vendors = " · ".join(
                f"{_escape_markdown(vendor.name)} {_currency(vendor.amount)}" for vendor in item.top_vendors
            )
            summary = f"{summary}\nTop vendors: {vendors}"
        category_lines.append(summary)
    category_value = "\n".join(category_lines)
    if len(category_value) > 1024:
        raise NotifierError("The configured category list is too long for one Discord message.")

    rolling_lines = [
        (
            f"**{_escape_markdown(item.name)}** — **{_currency(item.rolling_amount)}** · "
            f"{_rolling_change_text(item.rolling_change)}"
        )
        for item in report.categories
    ]
    rolling_lines.append(
        f"**Watched total** — **{_currency(report.rolling_selected_total)}** · "
        f"{_rolling_change_text(report.rolling_selected_change)}"
    )
    rolling_value = "\n".join(rolling_lines)
    if len(rolling_value) > 1024:
        raise NotifierError("The configured category list is too long for one Discord message.")

    period = report.period
    color = 0xE74C3C if report.selected_change > 0 else 0x2ECC71
    if report.selected_change == 0:
        color = 0x95A5A6

    return {
        "embeds": [
            {
                "title": "Weekly spending",
                "description": f"{_date(period.start)} - {_date(period.end, include_year=True)}",
                "color": color,
                "fields": [
                    {"name": "Watched categories", "value": category_value, "inline": False},
                    {
                        "name": "Watched total",
                        "value": (
                            f"**{_currency(report.selected_total)}** · {_usual_change_text(report.selected_change)}"
                        ),
                        "inline": True,
                    },
                    {
                        "name": "4-week watched spending",
                        "value": rolling_value,
                        "inline": False,
                    },
                    {
                        "name": "All expenses",
                        "value": f"**{_currency(report.all_expenses_total)}**",
                        "inline": True,
                    },
                    {
                        "name": "Needs categorization",
                        "value": _uncategorized_text(report.uncategorized_count),
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": (
                        f"Usual = {AVERAGE_WEEKS}-week average · "
                        f"{_date(period.comparison_start, include_year=True)} - "
                        f"{_date(period.comparison_end, include_year=True)} · "
                        f"4-week view = {_date(period.rolling_start)} - {_date(period.end)} vs "
                        f"{_date(period.previous_rolling_start)} - "
                        f"{_date(period.previous_rolling_end, include_year=True)}"
                    )
                },
            }
        ],
        "allowed_mentions": {"parse": []},
    }


def report_as_dict(report: WeeklyExpenseReport) -> dict[str, Any]:
    """Return a stable JSON-ready representation for preview output."""
    return {
        "status": "ok",
        "period": {"start": report.period.start.isoformat(), "end": report.period.end.isoformat()},
        "average_period": {
            "start": report.period.comparison_start.isoformat(),
            "end": report.period.comparison_end.isoformat(),
            "weeks": AVERAGE_WEEKS,
        },
        "rolling_period": {
            "start": report.period.rolling_start.isoformat(),
            "end": report.period.end.isoformat(),
            "comparison_start": report.period.previous_rolling_start.isoformat(),
            "comparison_end": report.period.previous_rolling_end.isoformat(),
            "weeks": ROLLING_WEEKS,
        },
        "categories": [
            {
                "name": item.name,
                "amount": item.amount,
                "average_amount": item.average_amount,
                "change": item.change,
                "rolling_amount": item.rolling_amount,
                "previous_rolling_amount": item.previous_rolling_amount,
                "rolling_change": item.rolling_change,
                "top_vendors": [{"name": vendor.name, "amount": vendor.amount} for vendor in item.top_vendors],
            }
            for item in report.categories
        ],
        "selected_total": report.selected_total,
        "average_selected_total": report.average_selected_total,
        "selected_change": report.selected_change,
        "rolling_selected_total": report.rolling_selected_total,
        "previous_rolling_selected_total": report.previous_rolling_selected_total,
        "rolling_selected_change": report.rolling_selected_change,
        "all_expenses_total": report.all_expenses_total,
        "uncategorized_count": report.uncategorized_count,
    }


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    """Load sent-period state, failing closed when it is malformed."""
    if not path.exists():
        return {"sent_periods": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise NotifierError("The Discord delivery state is invalid. Repair it before sending.") from error
    if not isinstance(state, dict) or not isinstance(state.get("sent_periods"), dict):
        raise NotifierError("The Discord delivery state is invalid. Repair it before sending.")
    return state


def save_delivery(period_end: dt.date, message_id: str, path: Path = DEFAULT_STATE_PATH) -> None:
    """Atomically record a successful Discord delivery."""
    state = load_state(path)
    sent_periods = state["sent_periods"]
    assert isinstance(sent_periods, dict)
    sent_periods[period_end.isoformat()] = {
        "message_id": message_id,
        "sent_at": dt.datetime.now(tz=dt.UTC).isoformat(),
    }

    temp_name: str | None = None
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(path.parent, 0o700)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            json.dump(state, temp_file, indent=2, sort_keys=True)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except OSError as error:
        raise NotifierError("Failed to write the Discord delivery state.") from error
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def was_sent(period_end: dt.date, path: Path = DEFAULT_STATE_PATH) -> bool:
    """Return whether a report period already has a successful delivery."""
    sent_periods = load_state(path)["sent_periods"]
    assert isinstance(sent_periods, dict)
    return period_end.isoformat() in sent_periods


def build_report(config: NotifierConfig, period: ReportPeriod) -> WeeklyExpenseReport:
    """Load source data and calculate one report."""
    transactions, metadata = load_report_data(config)
    return calculate_weekly_report(transactions, metadata, config.categories, period)


def create_parser() -> argparse.ArgumentParser:
    """Create the non-interactive notifier CLI parser."""
    parser = argparse.ArgumentParser(
        description="Check, preview, test, or send the weekly Discord expense summary.",
        epilog=(
            "AI_CONTEXT:\n"
            "  Use --output json for machine-readable output.\n"
            "  Commands never prompt. Exit code 0 means success or an intentional duplicate skip.\n"
            "  Exit code 1 means configuration, source data, state, or network failure."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ["check", "preview", "test", "send"]:
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--output", choices=["text", "json"], default="text")
        subparser.add_argument("--secrets", type=Path, default=DEFAULT_SECRETS_PATH)
        if command in {"preview", "send"}:
            subparser.add_argument("--period-end", type=dt.date.fromisoformat)
        if command == "send":
            subparser.add_argument("--force", action="store_true")
            subparser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one notifier command and return a stable process exit code."""
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    os.umask(0o077)
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.secrets)
        if args.command == "check":
            transactions, metadata = load_report_data(config)
            validate_selected_categories(config.categories, metadata)
            check_webhook(config.webhook_url)
            local_now = dt.datetime.now().astimezone()
            result = {
                "status": "ok",
                "category_count": len(config.categories),
                "transaction_count": len(transactions),
                "local_time": local_now.isoformat(),
                "timezone": local_now.tzname() or str(local_now.tzinfo),
            }
            _emit(result, args.output, "Configuration, sheets, categories, webhook, and timezone are valid.")
            return 0

        if args.command == "test":
            message_id = post_webhook(config.webhook_url, test_payload())
            _emit(
                {"status": "sent", "message_id": message_id, "financial_data": False},
                args.output,
                "Discord test message sent. No financial data was included.",
            )
            return 0

        period = completed_week(dt.date.today(), args.period_end)
        if args.command == "preview":
            report = build_report(config, period)
            _emit(report_as_dict(report), args.output, _preview_text(report))
            return 0

        if not args.force and was_sent(period.end, args.state):
            _emit(
                {"status": "skipped", "period_end": period.end.isoformat(), "reason": "already_sent"},
                args.output,
                f"The weekly Discord summary for {period.end.isoformat()} was already sent.",
            )
            return 0

        report = build_report(config, period)
        message_id = post_webhook(config.webhook_url, report_payload(report))
        save_delivery(period.end, message_id, args.state)
        _emit(
            {"status": "sent", "period_end": period.end.isoformat(), "message_id": message_id},
            args.output,
            f"Weekly Discord summary sent for the period ending {period.end.isoformat()}.",
        )
        return 0
    except (NotifierError, WeeklyExpenseError) as error:
        if args.output == "json":
            print(json.dumps({"status": "error", "error": str(error)}, sort_keys=True))
        print(f"Error: {error}", file=sys.stderr)
        return 1


def _table(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise NotifierError(f"Missing [{key}] table in the Streamlit secrets file.")
    return value


def _string(parent: Mapping[str, Any], key: str, table_name: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value:
        raise NotifierError(f"{table_name}.{key} must be a non-empty string.")
    return value


def _validate_webhook_url(webhook_url: str) -> None:
    parsed = urlparse(webhook_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "discord.com"
        or re.fullmatch(r"/api/webhooks/[0-9]+/[A-Za-z0-9._-]+", parsed.path) is None
    ):
        raise NotifierError("notifications.discord.webhook_url must be a Discord webhook URL.")


def _discord_request(
    webhook_url: str,
    *,
    method: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_webhook_url(webhook_url)
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"User-Agent": USER_AGENT}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(webhook_url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            decoded = json.load(response)
    except HTTPError as error:
        raise NotifierError(f"Discord returned HTTP {error.code}.") from error
    except (URLError, OSError) as error:
        raise NotifierError("Discord could not be reached over HTTPS.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NotifierError("Discord returned an invalid response.") from error
    if not isinstance(decoded, dict):
        raise NotifierError("Discord returned an invalid response.")
    return decoded


def _currency(value: float) -> str:
    absolute = f"${abs(value):,.2f}"
    return f"-{absolute}" if value < 0 else absolute


def _uncategorized_text(count: int) -> str:
    if count == 0:
        return "All transactions are categorized."
    if count == 1:
        return "**1 transaction** still needs a category."
    return f"**{count} transactions** still need a category."


def _usual_change_text(change: float) -> str:
    if change > 0:
        return f"▲ {_currency(change)} above usual"
    if change < 0:
        return f"▼ {_currency(abs(change))} below usual"
    return "— right at usual"


def _rolling_change_text(change: float) -> str:
    if change > 0:
        return f"▲ {_currency(change)} more than prior 4 weeks"
    if change < 0:
        return f"▼ {_currency(abs(change))} less than prior 4 weeks"
    return "— same as prior 4 weeks"


def _date(value: dt.date, *, include_year: bool = False) -> str:
    rendered = value.strftime("%b %d, %Y" if include_year else "%b %d")
    return rendered.replace(" 0", " ")


def _escape_markdown(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()<>#+\-.!|~])", r"\\\1", value)


def _preview_text(report: WeeklyExpenseReport) -> str:
    lines = [
        "Weekly spending",
        f"{_date(report.period.start)} - {_date(report.period.end, include_year=True)}",
        "",
    ]
    for item in report.categories:
        lines.append(f"{item.name}: {_currency(item.amount)} ({_usual_change_text(item.change)})")
        if item.top_vendors:
            vendors = ", ".join(f"{vendor.name} {_currency(vendor.amount)}" for vendor in item.top_vendors)
            lines.append(f"  Top vendors: {vendors}")
    lines.extend(["", "4-week watched spending"])
    for item in report.categories:
        lines.append(f"{item.name}: {_currency(item.rolling_amount)} ({_rolling_change_text(item.rolling_change)})")
    lines.extend(
        [
            (
                f"4-week watched total: {_currency(report.rolling_selected_total)} "
                f"({_rolling_change_text(report.rolling_selected_change)})"
            ),
            "",
            (f"Watched total: {_currency(report.selected_total)} ({_usual_change_text(report.selected_change)})"),
            f"All expenses: {_currency(report.all_expenses_total)}",
            f"Needs categorization: {_uncategorized_text(report.uncategorized_count)}",
            (
                f"Usual = {AVERAGE_WEEKS}-week average, "
                f"{_date(report.period.comparison_start, include_year=True)} - "
                f"{_date(report.period.comparison_end, include_year=True)}"
            ),
        ]
    )
    return "\n".join(lines)


def _emit(data: Mapping[str, Any], output: str, text: str) -> None:
    if output == "json":
        print(json.dumps(data, sort_keys=True))
    else:
        print(text)
