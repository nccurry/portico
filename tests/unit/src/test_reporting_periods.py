"""Tests for shared reporting-period helpers."""

from types import SimpleNamespace

import pandas as pd
import pytest

from src.reporting_periods import current_timestamp, month_lookback_options, rolling_month_window


def test_month_lookback_options_use_compact_labels() -> None:
    assert month_lookback_options((1, 3, 12, 24)) == {"1M": 1, "3M": 3, "1Y": 12, "2Y": 24}


def test_current_timestamp_uses_the_local_csv_reference_date(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(data=SimpleNamespace(reference_date="1995-04-20T00:00:00+00:00"))
    monkeypatch.setattr("src.reporting_periods.get_settings", lambda: settings)

    assert current_timestamp() == pd.Timestamp("1995-04-20T00:00:00+00:00")


@pytest.mark.uses_real_dates
def test_rolling_month_window_includes_current_month() -> None:
    assert rolling_month_window(3) == (
        "1995-02",
        "1995-04",
    )
