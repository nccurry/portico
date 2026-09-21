"""Tests for report periods anchored to the loaded spreadsheet data."""

import pandas as pd

from src.reporting_periods import current_timestamp, month_lookback_options, reporting_anchor, rolling_month_window


def test_current_timestamp_is_current_utc_time() -> None:
    now = pd.Timestamp.now(tz="UTC")
    assert abs((current_timestamp() - now).total_seconds()) < 2


def test_reporting_anchor_uses_the_latest_source_date() -> None:
    data = pd.DataFrame({"Date": ["1995-03-15", "1995-04-20"]})

    assert reporting_anchor(data) == pd.Timestamp("1995-04-20", tz="UTC")


def test_rolling_month_window_ends_at_the_latest_source_month() -> None:
    data = pd.DataFrame({"Date": ["1995-04-20"]})

    assert rolling_month_window(3, data) == ("1995-02", "1995-04")


def test_month_lookback_options_use_compact_labels() -> None:
    assert month_lookback_options((3, 6, 12, 24)) == {"3M": 3, "6M": 6, "1Y": 12, "2Y": 24}
