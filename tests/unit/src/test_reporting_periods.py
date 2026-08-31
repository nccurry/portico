"""Tests for shared reporting-period helpers."""

import pytest

from src.reporting_periods import month_lookback_options, rolling_month_window


def test_month_lookback_options_use_compact_labels() -> None:
    assert month_lookback_options((1, 3, 12, 24)) == {"1M": 1, "3M": 3, "1Y": 12, "2Y": 24}


@pytest.mark.uses_real_dates
def test_rolling_month_window_includes_current_month() -> None:
    assert rolling_month_window(3) == (
        "2026-02",
        "2026-04",
    )
