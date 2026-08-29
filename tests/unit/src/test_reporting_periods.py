"""Tests for shared reporting-period helpers."""

import pytest

from src.reporting_periods import rolling_month_window


@pytest.mark.uses_real_dates
def test_rolling_month_window_includes_current_month() -> None:
    assert rolling_month_window(3) == (
        "2026-02",
        "2026-04",
    )
