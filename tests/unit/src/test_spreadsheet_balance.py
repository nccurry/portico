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
    get_all_accounts,
    get_portfolio_value,
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

    def test_negative_asset_balance_handled(self, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """Negative asset balance (e.g. overdraft) is summed as-is."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Overdraft", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": -50, "Hide": ""},
            {"Date": "2024-01-01", "Time": "2024-01-01 09:00:00", "Account": "Savings", "Account ID": "a2",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 1000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        _, total = bs.get_latest_balance_by_group("Assets")
        assert total == pytest.approx(950)

    def test_exact_same_timestamp_stable_order(self, make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet]) -> None:
        """Two rows with the exact same Date+Time: keep='last' picks the row
        that appears later in the input. Document the stable tie-break behavior."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 12:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 100, "Hide": ""},
            {"Date": "2024-01-01", "Time": "2024-01-01 12:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 200, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        _, total = bs.get_latest_balance_by_group("Assets")
        assert total == pytest.approx(200)


class TestSparklineMath:
    """Verify the core math of the sparkline helpers — forward-fill, resampling,
    and sign handling."""

    def test_net_worth_equals_assets_minus_liabilities_at_each_point(self) -> None:
        """NetWorth at each week = sum(asset balances) - sum(liability balances)
        using the forward-filled latest balance per account per week."""
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-01", "Account": "Credit", "Account ID": "a2",
             "Institution": "Chase", "Group": "Credit", "Class": "Liability",
             "Balance": 1000, "Hide": ""},
            {"Date": "2024-01-15", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 6000, "Hide": ""},
            {"Date": "2024-01-15", "Account": "Credit", "Account ID": "a2",
             "Institution": "Chase", "Group": "Credit", "Class": "Liability",
             "Balance": 1500, "Hide": ""},
        ])
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 21)
        result = calculate_net_worth_sparkline.__wrapped__(df, start, end)  # type: ignore[attr-defined]
        # By the last week both accounts have reported: 6000 - 1500 = 4500
        assert result["NetWorth"].iloc[-1] == pytest.approx(4500.0)

    def test_sparkline_balance_column_is_sum_not_average(self) -> None:
        """Weekly resample + ffill + sum means the group total is the sum of
        each account's latest balance, not the average."""
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "A", "Account ID": "aa",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 100, "Hide": ""},
            {"Date": "2024-01-01", "Account": "B", "Account ID": "bb",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 200, "Hide": ""},
            {"Date": "2024-01-01", "Account": "C", "Account ID": "cc",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 300, "Hide": ""},
        ])
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 14)
        result = calculate_group_sparkline.__wrapped__(df, "Assets", start, end)  # type: ignore[attr-defined]
        # Sum is 600, not avg 200. Later weeks are forward-filled.
        non_nan_balances = result["Balance"].dropna()
        assert len(non_nan_balances) >= 1
        assert non_nan_balances.iloc[-1] == pytest.approx(600.0)

    def test_nan_class_defaults_to_multiplier_1(self) -> None:
        """Accounts with missing Class are treated as Assets (multiplier 1)."""
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "Unknown", "Account ID": "u1",
             "Institution": "Bank", "Group": "???", "Class": None,
             "Balance": 500, "Hide": ""},
            {"Date": "2024-01-01", "Account": "Known", "Account ID": "k1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1000, "Hide": ""},
        ])
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 7)
        result = calculate_net_worth_sparkline.__wrapped__(df, start, end)  # type: ignore[attr-defined]
        # Both treated as positive contribution: 500 + 1000 = 1500
        assert result["NetWorth"].iloc[-1] == pytest.approx(1500.0)

    def test_date_range_filter_excludes_out_of_range_weeks(self) -> None:
        """Weeks outside [start_date, end_date] are filtered out of the result."""
        df = _balance_df([
            {"Date": f"2024-{m:02d}-01", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1000 * m, "Hide": ""}
            for m in range(1, 7)
        ])
        start = _utc(2024, 3, 1)
        end = _utc(2024, 4, 30)
        result = calculate_group_sparkline.__wrapped__(df, "Assets", start, end)  # type: ignore[attr-defined]
        # All result dates should be within [start, end]
        assert (result["Date"] >= start).all()
        assert (result["Date"] <= end).all()


class TestGetAllAccounts:
    """Verify get_all_accounts filters Hide rows and returns sorted uniques."""

    def test_excludes_hidden_accounts(self, fi_balance_df: pd.DataFrame) -> None:
        result = get_all_accounts(fi_balance_df)
        assert "Hidden Acct" not in result

    def test_returns_sorted_unique_accounts(self, fi_balance_df: pd.DataFrame) -> None:
        result = get_all_accounts(fi_balance_df)
        assert result == sorted(set(result))
        assert set(result) == {"Brokerage", "401k", "HSA", "Savings", "Margin Loan"}

    def test_empty_frame(self) -> None:
        df = pd.DataFrame(columns=["Date", "Account", "Hide"])
        assert get_all_accounts(df) == []


class TestGetPortfolioValue:
    """Math coverage for get_portfolio_value against fi_balance_df.

    Hand-computed totals are inlined next to each assertion so the test is
    the spec.
    """

    def test_sums_selected_assets_at_latest_date(self, fi_balance_df: pd.DataFrame) -> None:
        # Brokerage latest = 120000 (2024-02-01 20:00), 401k latest = 220000
        # Expected: 120000 + 220000 = 340000
        _, total = get_portfolio_value(fi_balance_df, ["Brokerage", "401k"])
        assert total == pytest.approx(340000)

    def test_signs_liabilities_negatively(self, fi_balance_df: pd.DataFrame) -> None:
        # Brokerage latest 120000 (Asset), Margin Loan 5000 (Liability)
        # Expected: 120000 - 5000 = 115000
        _, total = get_portfolio_value(fi_balance_df, ["Brokerage", "Margin Loan"])
        assert total == pytest.approx(115000)

    def test_single_account_liability_only(self, fi_balance_df: pd.DataFrame) -> None:
        _, total = get_portfolio_value(fi_balance_df, ["Margin Loan"])
        assert total == pytest.approx(-5000)

    def test_all_five_accounts(self, fi_balance_df: pd.DataFrame) -> None:
        # Brokerage 120000 + 401k 220000 + HSA 15000 + Savings 11000 - Margin 5000 = 361000
        _, total = get_portfolio_value(
            fi_balance_df, ["Brokerage", "401k", "HSA", "Savings", "Margin Loan"]
        )
        assert total == pytest.approx(361000)

    def test_ignores_unselected_accounts(self, fi_balance_df: pd.DataFrame) -> None:
        # Same selection as test_sums_selected_assets, adding HSA bumps total by 15000
        _, base = get_portfolio_value(fi_balance_df, ["Brokerage", "401k"])
        _, with_hsa = get_portfolio_value(fi_balance_df, ["Brokerage", "401k", "HSA"])
        assert with_hsa - base == pytest.approx(15000)

    def test_uses_latest_time_on_same_date(self, fi_balance_df: pd.DataFrame) -> None:
        # Brokerage has two entries on 2024-02-01: 115000 at 08:00, 120000 at 20:00
        # Latest Time (20:00) wins: 120000
        _, total = get_portfolio_value(fi_balance_df, ["Brokerage"])
        assert total == pytest.approx(120000)

    def test_respects_as_of_earlier_date(self, fi_balance_df: pd.DataFrame) -> None:
        # as_of=2024-01-01 → Brokerage 100000, 401k 200000 (Feb observations excluded)
        _, total = get_portfolio_value(
            fi_balance_df, ["Brokerage", "401k"], as_of=_utc(2024, 1, 1)
        )
        assert total == pytest.approx(300000)

    def test_empty_selection_returns_zero(self, fi_balance_df: pd.DataFrame) -> None:
        df_result, total = get_portfolio_value(fi_balance_df, [])
        assert total == 0.0
        assert df_result.empty
        assert list(df_result.columns) == ["Account", "Balance"]

    def test_unknown_account_returns_zero(self, fi_balance_df: pd.DataFrame) -> None:
        df_result, total = get_portfolio_value(fi_balance_df, ["Does Not Exist"])
        assert total == 0.0
        assert df_result.empty

    def test_excludes_hidden_accounts_even_if_selected(self, fi_balance_df: pd.DataFrame) -> None:
        # "Hidden Acct" has Hide="Hide" and Balance=99000; selecting it should be ignored.
        _, total = get_portfolio_value(fi_balance_df, ["Brokerage", "Hidden Acct"])
        assert total == pytest.approx(120000)

    def test_per_account_frame_shape(self, fi_balance_df: pd.DataFrame) -> None:
        df_result, _ = get_portfolio_value(
            fi_balance_df, ["Brokerage", "401k", "Margin Loan"]
        )
        assert list(df_result.columns) == ["Account", "Balance"]
        assert len(df_result) == 3
        # Verify each account's balance row (signed) matches the latest observation.
        bal_by_account = dict(zip(df_result["Account"], df_result["Balance"], strict=True))
        assert bal_by_account["Brokerage"] == pytest.approx(120000)
        assert bal_by_account["401k"] == pytest.approx(220000)
        assert bal_by_account["Margin Loan"] == pytest.approx(-5000)

    def test_method_wrapper_delegates(
        self,
        fi_balance_df: pd.DataFrame,
        make_balance_spreadsheet: Callable[[pd.DataFrame | None], BalanceHistorySpreadsheet],
    ) -> None:
        bs = make_balance_spreadsheet(fi_balance_df)
        _, total = bs.get_portfolio_value(["Brokerage", "401k"])
        assert total == pytest.approx(340000)
