"""Sentinel test: freezegun's tz_offset=0 must align with tz-aware fixtures.

If freezegun ever returns a naive datetime against UTC fixtures, the page
integration tests collapse with 'Cannot compare tz-naive and tz-aware'. This
file is the canary.
"""
from __future__ import annotations

import pandas as pd
import pytest


@pytest.mark.uses_real_dates
def test_frozen_time_aligns_with_tz_aware_fixture(reference_date: pd.Timestamp) -> None:
    """``pd.Timestamp.now(tz='UTC')`` must equal the frozen reference date."""
    now = pd.Timestamp.now(tz="UTC")
    # Down to seconds: freezegun is exact.
    assert abs((now - reference_date).total_seconds()) < 1.0


@pytest.mark.uses_real_dates
def test_frozen_time_does_not_break_naive_arithmetic(reference_date: pd.Timestamp) -> None:
    """Naive ``pd.Timestamp.now()`` is fine for code that explicitly opts out of tz."""
    now_naive = pd.Timestamp.now()
    expected_naive = reference_date.tz_localize(None)
    assert abs((now_naive - expected_naive).total_seconds()) < 1.0
