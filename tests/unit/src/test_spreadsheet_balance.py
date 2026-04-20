"""Tests for ``BalanceHistorySpreadsheet`` data methods and sparkline helpers.

Covers:
    - ``get_latest_balance_by_group`` and its end-date / single-account / empty
      / overlapping-entries / latest-time variations.
    - ``get_balance_history_by_account_id`` and ``get_balance_history_by_group``.
    - The module-level ``calculate_group_sparkline`` and
      ``calculate_net_worth_sparkline`` helpers.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from src.spreadsheet import (
    calculate_group_sparkline,
    calculate_net_worth_sparkline,
)
from tests._helpers import _balance_df, _utc

if TYPE_CHECKING:
    from src.spreadsheet import BalanceHistorySpreadsheet


class TestBalanceHistory:

    def test_latest_balance_tuple_and_total(self, sample_balance_df: pd.DataFrame, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        bs = make_balance_spreadsheet(sample_balance_df)
        df_result, total = bs.get_latest_balance_by_group("Assets")
        assert total == pytest.approx(15000)
        assert isinstance(df_result, pd.DataFrame)
        assert set(df_result.columns) == {"Account", "Balance"}

    def test_latest_balance_with_end_date(self, sample_balance_df: pd.DataFrame, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        bs = make_balance_spreadsheet(sample_balance_df)
        _df_result, total = bs.get_latest_balance_by_group("Assets", end_date=_utc(2024, 1, 1))
        assert total == pytest.approx(15000)

    def test_get_groups(self, sample_balance_df: pd.DataFrame, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        bs = make_balance_spreadsheet(sample_balance_df)
        groups = list(bs.get_groups())
        assert "Assets" in groups
        assert "Liabilities" in groups

    def test_balance_history_by_account_reindexes(
        self,
        sample_balance_df: pd.DataFrame,
        make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet],
    ) -> None:
        bs = make_balance_spreadsheet(sample_balance_df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 15)
        result = bs.get_balance_history_by_account_id("a1", start, end)
        assert len(result) == 15

    def test_balance_history_by_account_missing_dates_filled(
        self,
        sample_balance_df: pd.DataFrame,
        make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet],
    ) -> None:
        bs = make_balance_spreadsheet(sample_balance_df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 15)
        result = bs.get_balance_history_by_account_id("a1", start, end)
        assert result["Balance"].isna().sum() == 0

    def test_balance_history_by_group_sums_across_accounts(
        self,
        sample_balance_df: pd.DataFrame,
        make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet],
    ) -> None:
        bs = make_balance_spreadsheet(sample_balance_df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 15)
        result = bs.get_balance_history_by_group("Assets", start, end)
        last_val = result.iloc[-1]
        assert last_val == pytest.approx(15000)

    def test_balance_history_single_account_group(self, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """A group with a single account should still work correctly."""
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "Mortgage", "Account ID": "a3",
             "Institution": "Lender", "Group": "Liabilities", "Class": "Liability",
             "Balance": 200000, "Hide": ""},
            {"Date": "2024-01-15", "Account": "Mortgage", "Account ID": "a3",
             "Institution": "Lender", "Group": "Liabilities", "Class": "Liability",
             "Balance": 199500, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 15)
        result = bs.get_balance_history_by_group("Liabilities", start, end)
        assert result.iloc[-1] == pytest.approx(199500)

    def test_balance_history_different_date_range(
        self,
        sample_balance_df: pd.DataFrame,
        make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet],
    ) -> None:
        """Requesting a range that includes actual data points fills gaps via bfill/ffill."""
        bs = make_balance_spreadsheet(sample_balance_df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 10)
        result = bs.get_balance_history_by_account_id("a1", start, end)
        assert len(result) == 10
        assert result["Balance"].iloc[0] == pytest.approx(5000)
        assert result["Balance"].isna().sum() == 0

    def test_balance_history_by_group_empty_group(
        self,
        sample_balance_df: pd.DataFrame,
        make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet],
    ) -> None:
        """A group with no matching data returns an empty series."""
        bs = make_balance_spreadsheet(sample_balance_df)
        result = bs.get_balance_history_by_group("NonExistent")
        assert result.empty

    def test_balance_history_by_group_overlapping_entries(self, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """Multiple entries per account per date keeps the last one."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1000, "Hide": ""},
            {"Date": "2024-01-01", "Time": "2024-01-01 12:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1500, "Hide": ""},
            {"Date": "2024-01-02", "Time": "2024-01-02 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 2000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 2)
        result = bs.get_balance_history_by_group("Assets", start, end)
        assert result.iloc[0] == pytest.approx(1500)
        assert result.iloc[1] == pytest.approx(2000)

    def test_latest_balance_uses_latest_time(self, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """When multiple entries share the same date, the latest time wins."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1000, "Hide": ""},
            {"Date": "2024-01-01", "Time": "2024-01-01 15:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1500, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        _, total = bs.get_latest_balance_by_group("Assets")
        assert total == pytest.approx(1500)

    def test_latest_balance_empty_group(self, sample_balance_df: pd.DataFrame, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """A group with no accounts returns empty df and total 0."""
        bs = make_balance_spreadsheet(sample_balance_df)
        df_result, total = bs.get_latest_balance_by_group("NonExistent")
        assert df_result.empty
        assert total == pytest.approx(0.0)


class TestSparklines:

    def test_group_sparkline_weekly_resample(self, sample_balance_df: pd.DataFrame) -> None:
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 31)
        result = calculate_group_sparkline.__wrapped__(sample_balance_df, "Assets", start, end)  # type: ignore[attr-defined]
        assert "Balance" in result.columns
        assert "Date" in result.columns
        assert len(result) >= 1

    def test_group_sparkline_empty_group(self, sample_balance_df: pd.DataFrame) -> None:
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 31)
        result = calculate_group_sparkline.__wrapped__(sample_balance_df, "NonExistent", start, end)  # type: ignore[attr-defined]
        assert result.empty

    def test_net_worth_subtracts_liabilities(self, sample_balance_df: pd.DataFrame) -> None:
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 31)
        result = calculate_net_worth_sparkline.__wrapped__(sample_balance_df, start, end)  # type: ignore[attr-defined]
        assert "NetWorth" in result.columns
        nonzero = result[result["NetWorth"] != 0]
        assert all(nonzero["NetWorth"] < 0)

    def test_group_sparkline_ffills_missing_weeks(self) -> None:
        """Accounts with data on different weeks should forward-fill so the sum
        doesn't drop when one account has no entry for a given week."""
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-15", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5500, "Hide": ""},
            {"Date": "2024-01-01", "Account": "Savings", "Account ID": "a2",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 10000, "Hide": ""},
        ])
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 21)
        result = calculate_group_sparkline.__wrapped__(df, "Assets", start, end)  # type: ignore[attr-defined]
        assert (result["Balance"] >= 10000).all()

    def test_net_worth_sparkline_ffills_missing_weeks(self) -> None:
        """Net worth sparkline should forward-fill so accounts missing
        data in some weeks don't cause the net worth to spike."""
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-15", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5500, "Hide": ""},
            {"Date": "2024-01-01", "Account": "Credit Card", "Account ID": "a2",
             "Institution": "Chase", "Group": "Credit Card", "Class": "Liability",
             "Balance": 2000, "Hide": ""},
        ])
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 21)
        result = calculate_net_worth_sparkline.__wrapped__(df, start, end)  # type: ignore[attr-defined]
        assert (result["NetWorth"] <= 3500).all()


class TestLatestBalanceEdgeCases:

    def test_multiple_accounts_same_group_different_dates(self, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """Each account's latest entry is used, even if they're on different dates."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 4500, "Hide": ""},
            {"Date": "2024-01-10", "Time": "2024-01-10 08:00:00", "Account": "Savings", "Account ID": "a2",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 10000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        _, total = bs.get_latest_balance_by_group("Assets")
        assert total == pytest.approx(14500)

    def test_end_date_excludes_future_entries(self, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """Entries after end_date are excluded from latest balance."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 5000, "Hide": ""},
            {"Date": "2024-02-01", "Time": "2024-02-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 6000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        _, total = bs.get_latest_balance_by_group("Assets", end_date=_utc(2024, 1, 15))
        assert total == pytest.approx(5000)

    def test_single_entry_per_account(self, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """Works correctly when each account has exactly one balance entry."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-01", "Time": "2024-01-01 09:00:00", "Account": "Savings", "Account ID": "a2",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 10000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        df_result, total = bs.get_latest_balance_by_group("Assets")
        assert total == pytest.approx(15000)
        assert len(df_result) == 2
