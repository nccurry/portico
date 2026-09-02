from __future__ import annotations

import datetime as dt
import json
import os
import sys
from dataclasses import replace
from email.message import Message
from io import BytesIO, TextIOWrapper
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd
import pytest

from src.discord_notifier import (
    NotifierConfig,
    NotifierError,
    build_report,
    google_export_url,
    load_config,
    load_state,
    main,
    post_webhook,
    read_google_sheet,
    report_payload,
    save_delivery,
    was_sent,
)
from src.discord_notifier import (
    test_payload as build_test_payload,
)
from src.weekly_expenses import (
    CategoryTotal,
    ReportPeriod,
    VendorTotal,
    WeeklyExpenseReport,
)


def sample_report() -> WeeklyExpenseReport:
    return WeeklyExpenseReport(
        period=ReportPeriod(
            start=dt.date(2026, 7, 26),
            end=dt.date(2026, 8, 1),
            comparison_start=dt.date(2026, 5, 31),
            comparison_end=dt.date(2026, 7, 25),
        ),
        categories=(
            CategoryTotal(
                name="Everyday Food",
                amount=120.0,
                average_amount=100.0,
                rolling_amount=440.0,
                previous_rolling_amount=500.0,
                top_vendors=(VendorTotal("KROGER", 80.0), VendorTotal("ALDI", 40.0)),
            ),
            CategoryTotal(
                name="Local Dining",
                amount=40.0,
                average_amount=60.0,
                rolling_amount=240.0,
                previous_rolling_amount=200.0,
                top_vendors=(VendorTotal("CAFE", 40.0),),
            ),
        ),
        selected_total=160.0,
        average_selected_total=160.0,
        rolling_selected_total=680.0,
        previous_rolling_selected_total=700.0,
        all_expenses_total=900.0,
        uncategorized_count=4,
    )


def sample_config() -> NotifierConfig:
    return NotifierConfig(
        transactions_url="https://docs.google.com/spreadsheets/d/example/edit?gid=1",
        categories_url="https://docs.google.com/spreadsheets/d/example/edit?gid=2",
        webhook_url="https://discord.com/api/webhooks/123/test-token",
        categories=("Everyday Food", "Local Dining"),
    )


def test_load_config_preserves_category_order(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(
        """
[connections.transactions]
spreadsheet = "https://docs.google.com/spreadsheets/d/example/edit?gid=1"
[connections.categories]
spreadsheet = "https://docs.google.com/spreadsheets/d/example/edit?gid=2"
[notifications.discord]
webhook_url = "https://discord.com/api/webhooks/123/test-token"
categories = ["Everyday Food", "Local Dining"]
""".strip(),
        encoding="utf-8",
    )

    config = load_config(secrets)

    assert config.categories == ("Everyday Food", "Local Dining")


@pytest.mark.parametrize(
    "url",
    [
        "http://discord.com/api/webhooks/123/test-token",
        "https://example.com/api/webhooks/123/test-token",
        "https://discord.com/channels/123/test-token",
    ],
)
def test_load_config_rejects_malformed_webhooks(tmp_path: Path, url: str) -> None:
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(
        f"""
[connections.transactions]
spreadsheet = "https://docs.google.com/spreadsheets/d/example/edit?gid=1"
[connections.categories]
spreadsheet = "https://docs.google.com/spreadsheets/d/example/edit?gid=2"
[notifications.discord]
webhook_url = "{url}"
categories = ["Everyday Food"]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(NotifierError, match="Discord webhook URL"):
        load_config(secrets)


def test_load_config_rejects_duplicate_categories(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(
        """
[connections.transactions]
spreadsheet = "https://docs.google.com/spreadsheets/d/example/edit?gid=1"
[connections.categories]
spreadsheet = "https://docs.google.com/spreadsheets/d/example/edit?gid=2"
[notifications.discord]
webhook_url = "https://discord.com/api/webhooks/123/test-token"
categories = ["Everyday Food", "Everyday Food"]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(NotifierError, match="duplicates"):
        load_config(secrets)


def test_google_export_url_supports_query_and_fragment_gid() -> None:
    query = google_export_url("https://docs.google.com/spreadsheets/d/example/edit?gid=42")
    fragment = google_export_url("https://docs.google.com/spreadsheets/d/example/edit#gid=43")

    assert query == "https://docs.google.com/spreadsheets/d/example/export?format=csv&gid=42"
    assert fragment == "https://docs.google.com/spreadsheets/d/example/export?format=csv&gid=43"


def test_google_export_url_rejects_conflicting_gid_values() -> None:
    with pytest.raises(NotifierError, match="Google Sheets connection URL"):
        google_export_url("https://docs.google.com/spreadsheets/d/example/edit?gid=42#gid=43")


def test_read_google_sheet_returns_csv_without_streamlit() -> None:
    response = BytesIO(b"Column A,Column B\n1,2\n")

    with patch("src.discord_notifier.urlopen", return_value=response):
        frame = read_google_sheet(
            "https://docs.google.com/spreadsheets/d/example/edit?gid=42",
            "Example",
        )

    assert frame.to_dict(orient="records") == [{"Column A": 1, "Column B": 2}]


def test_build_report_passes_configured_merchant_aliases() -> None:
    aliases = {"AMAZON MKTPL": "AMAZON", "AMAZON COM": "AMAZON"}
    settings = SimpleNamespace(weekly_summary=SimpleNamespace(top_merchant_count=3))
    transactions = pd.DataFrame()
    metadata = pd.DataFrame()

    with (
        patch("src.discord_notifier.load_report_data", return_value=(transactions, metadata)),
        patch("src.discord_notifier.configured_merchant_aliases", return_value=aliases),
        patch("src.discord_notifier.get_settings", return_value=settings),
        patch("src.discord_notifier.calculate_weekly_report", return_value=sample_report()) as calculate,
    ):
        report = build_report(sample_config(), sample_report().period)

    assert report == sample_report()
    assert calculate.call_args.kwargs["merchant_aliases"] == aliases


def test_build_report_reports_invalid_merchant_aliases() -> None:
    with (
        patch("src.discord_notifier.load_report_data", return_value=(pd.DataFrame(), pd.DataFrame())),
        patch("src.discord_notifier.configured_merchant_aliases", side_effect=ValueError("conflicting alias")),
        pytest.raises(NotifierError, match="Merchant alias configuration is invalid"),
    ):
        build_report(sample_config(), sample_report().period)


def test_report_payload_has_expected_totals_and_disables_mentions() -> None:
    payload = report_payload(sample_report())
    embed = payload["embeds"][0]

    assert payload["allowed_mentions"] == {"parse": []}
    assert embed["title"] == "Weekly spending"
    assert "Everyday Food" in embed["fields"][0]["value"]
    assert "$120.00" in embed["fields"][0]["value"]
    assert "above usual" in embed["fields"][0]["value"]
    assert "below usual" in embed["fields"][0]["value"]
    assert "Top vendors: KROGER $80.00 · ALDI $40.00" in embed["fields"][0]["value"]
    assert embed["fields"][1]["name"] == "Watched total"
    assert "$160.00" in embed["fields"][1]["value"]
    assert embed["fields"][2]["name"] == "4-week watched spending"
    assert "Everyday Food** — **$440.00" in embed["fields"][2]["value"]
    assert "$60.00 less than prior 4 weeks" in embed["fields"][2]["value"]
    assert "$40.00 more than prior 4 weeks" in embed["fields"][2]["value"]
    assert "Watched total** — **$680.00" in embed["fields"][2]["value"]
    assert "$900.00" in embed["fields"][3]["value"]
    assert embed["fields"][4]["name"] == "Needs categorization"
    assert "4 transactions" in embed["fields"][4]["value"]
    assert "still need a category" in embed["fields"][4]["value"]
    assert "8-week average" in embed["footer"]["text"]
    assert "4-week view" in embed["footer"]["text"]
    rendered = json.dumps(embed)
    assert "net inflow" not in rendered
    assert "last week" not in rendered
    assert "outstanding" not in rendered
    assert embed["color"] == 0x95A5A6


def test_report_payload_reports_when_everything_is_categorized() -> None:
    report = replace(sample_report(), uncategorized_count=0)

    embed = report_payload(report)["embeds"][0]

    assert embed["fields"][4]["value"] == "All transactions are categorized."


def test_report_payload_uses_singular_categorization_wording() -> None:
    report = replace(sample_report(), uncategorized_count=1)

    embed = report_payload(report)["embeds"][0]

    assert embed["fields"][4]["value"] == "**1 transaction** still needs a category."


def test_test_payload_contains_no_financial_values() -> None:
    serialized = json.dumps(build_test_payload())

    assert "financial data" in serialized
    assert "$" not in serialized


def test_post_webhook_uses_wait_and_returns_message_id() -> None:
    response = BytesIO(b'{"id":"message-1"}')

    with patch("src.discord_notifier.urlopen", return_value=response) as mock_urlopen:
        message_id = post_webhook(sample_config().webhook_url, build_test_payload())

    request = mock_urlopen.call_args.args[0]
    assert request.full_url.endswith("?wait=true")
    assert message_id == "message-1"


def test_discord_http_error_does_not_expose_webhook() -> None:
    error = HTTPError("private-url", 401, "Unauthorized", Message(), None)
    with (
        patch("src.discord_notifier.urlopen", side_effect=error),
        pytest.raises(NotifierError, match="HTTP 401") as raised,
    ):
        post_webhook(sample_config().webhook_url, build_test_payload())

    assert "private-url" not in str(raised.value)
    assert "test-token" not in str(raised.value)


def test_delivery_state_is_atomic_and_suppresses_duplicates(tmp_path: Path) -> None:
    state_path = tmp_path / ".local" / "state.json"
    period_end = dt.date(2026, 8, 1)

    assert not was_sent(period_end, state_path)
    save_delivery(period_end, "message-1", state_path)

    assert was_sent(period_end, state_path)
    assert load_state(state_path)["sent_periods"]["2026-08-01"]["message_id"] == "message-1"
    if os.name != "nt":
        assert state_path.stat().st_mode & 0o777 == 0o600


def test_preview_json_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("src.discord_notifier.load_config", return_value=sample_config()),
        patch("src.discord_notifier.build_report", return_value=sample_report()),
    ):
        exit_code = main(["preview", "--period-end", "2026-08-01", "--output", "json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "ok"
    assert output["categories"][0]["name"] == "Everyday Food"
    assert output["categories"][0]["average_amount"] == 100.0
    assert output["categories"][0]["top_vendors"][0] == {
        "amount": 80.0,
        "name": "KROGER",
    }
    assert output["average_period"]["weeks"] == 8
    assert output["rolling_period"] == {
        "comparison_end": "2026-07-04",
        "comparison_start": "2026-06-07",
        "end": "2026-08-01",
        "start": "2026-07-05",
        "weeks": 4,
    }
    assert output["categories"][0]["rolling_amount"] == 440.0
    assert output["rolling_selected_change"] == -20.0
    assert output["uncategorized_count"] == 4


def test_text_preview_matches_discord_title(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("src.discord_notifier.load_config", return_value=sample_config()),
        patch("src.discord_notifier.build_report", return_value=sample_report()),
    ):
        exit_code = main(["preview", "--period-end", "2026-08-01"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output.startswith("Weekly spending\n")
    assert "4-week watched spending\n" in output
    assert "Everyday Food: $440.00 (▼ $60.00 less than prior 4 weeks)" in output
    assert "4-week watched total: $680.00 (▼ $20.00 less than prior 4 weeks)" in output


def test_text_preview_uses_utf8_on_a_legacy_windows_console() -> None:
    output = BytesIO()
    stdout = TextIOWrapper(output, encoding="cp1252")
    with (
        patch.object(sys, "stdout", stdout),
        patch("src.discord_notifier.load_config", return_value=sample_config()),
        patch("src.discord_notifier.build_report", return_value=sample_report()),
    ):
        exit_code = main(["preview", "--period-end", "2026-08-01"])

    stdout.flush()
    rendered = output.getvalue().decode("utf-8")
    assert exit_code == 0
    assert "▼" in rendered


def test_send_skips_period_already_in_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / "state.json"
    save_delivery(dt.date(2026, 8, 1), "message-1", state_path)

    with (
        patch("src.discord_notifier.load_config", return_value=sample_config()),
        patch("src.discord_notifier.build_report", return_value=sample_report()) as build,
        patch("src.discord_notifier.post_webhook") as post,
    ):
        exit_code = main(
            [
                "send",
                "--period-end",
                "2026-08-01",
                "--state",
                str(state_path),
                "--output",
                "json",
            ]
        )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "skipped"
    build.assert_not_called()
    post.assert_not_called()


def test_force_sends_an_existing_period(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    save_delivery(dt.date(2026, 8, 1), "message-1", state_path)

    with (
        patch("src.discord_notifier.load_config", return_value=sample_config()),
        patch("src.discord_notifier.build_report", return_value=sample_report()),
        patch("src.discord_notifier.post_webhook", return_value="message-2") as post,
    ):
        exit_code = main(
            [
                "send",
                "--period-end",
                "2026-08-01",
                "--state",
                str(state_path),
                "--force",
            ]
        )

    assert exit_code == 0
    post.assert_called_once()
    assert load_state(state_path)["sent_periods"]["2026-08-01"]["message_id"] == "message-2"


def test_send_failure_does_not_record_delivery(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = tmp_path / "state.json"

    with (
        patch("src.discord_notifier.load_config", return_value=sample_config()),
        patch("src.discord_notifier.build_report", return_value=sample_report()),
        patch("src.discord_notifier.post_webhook", side_effect=NotifierError("Discord failed.")),
    ):
        exit_code = main(
            [
                "send",
                "--period-end",
                "2026-08-01",
                "--state",
                str(state_path),
                "--output",
                "json",
            ]
        )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["status"] == "error"
    assert not state_path.exists()
