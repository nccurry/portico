"""Tests for Home.py - net worth calculation and account grouping logic.

These exercise ``src.spreadsheet.calculate_net_worth_summary`` directly, which
is the function ``Home.configure_page`` delegates to. That keeps the page
file a thin orchestrator and gives the tests a stable, importable target.
"""
from collections.abc import Callable

import pandas as pd
import pytest

from src.spreadsheet import BalanceHistorySpreadsheet, calculate_net_worth_summary
from tests.conftest import BALANCE_HISTORY_SCRUBBED_COLUMNS, _ts


class TestNetWorthCalculation:
    """Test ``calculate_net_worth_summary`` against various balance shapes."""

    def test_net_worth_assets_minus_liabilities(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        """Net worth = sum(assets) - sum(liabilities)."""
        bs = make_balance_spreadsheet()
        summary = calculate_net_worth_summary(bs)
        assert summary["total_net_worth"] == pytest.approx(5500.0 - 1600.0)

    def test_liability_group_classified_correctly(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        bs = make_balance_spreadsheet()
        summary = calculate_net_worth_summary(bs)
        assert summary["group_classes"]["Credit Card"] == "Liability"
        assert summary["group_classes"]["Checking"] == "Asset"

    def test_group_balances_are_positive(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        """Group balances stored as positive regardless of asset/liability class."""
        bs = make_balance_spreadsheet()
        summary = calculate_net_worth_summary(bs)
        for balance in summary["group_balances"].values():
            assert balance >= 0

    def test_group_accounts_returned_per_group(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        """``group_accounts`` provides the per-account latest-balance frame."""
        bs = make_balance_spreadsheet()
        summary = calculate_net_worth_summary(bs)
        accounts = summary["group_accounts"]
        assert set(accounts.keys()) == {"Checking", "Credit Card"}
        for df in accounts.values():
            assert set(df.columns) == {"Account", "Balance"}

    def test_single_asset_group(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet], scrubbed_balance_df: pd.DataFrame) -> None:
        """Only asset accounts - net worth equals total balance."""
        df = scrubbed_balance_df[scrubbed_balance_df["Class"] == "Asset"].copy()
        bs = make_balance_spreadsheet(df)
        summary = calculate_net_worth_summary(bs)
        assert summary["total_net_worth"] == pytest.approx(5500.0)

    def test_single_liability_group(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet], scrubbed_balance_df: pd.DataFrame) -> None:
        """Only liability accounts - net worth is negative."""
        df = scrubbed_balance_df[scrubbed_balance_df["Class"] == "Liability"].copy()
        bs = make_balance_spreadsheet(df)
        summary = calculate_net_worth_summary(bs)
        assert summary["total_net_worth"] == pytest.approx(-1600.0)

    def test_empty_balance_history(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        """Empty balance data produces zero net worth."""
        empty_df = pd.DataFrame(columns=BALANCE_HISTORY_SCRUBBED_COLUMNS)
        bs = make_balance_spreadsheet(empty_df)
        summary = calculate_net_worth_summary(bs)
        assert summary["total_net_worth"] == pytest.approx(0.0)
        assert summary["group_balances"] == {}
        assert summary["group_accounts"] == {}

    def test_multiple_asset_groups(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet], scrubbed_balance_df: pd.DataFrame) -> None:
        """Multiple asset groups sum correctly."""
        new_rows = [
            (_ts("2024-04-01"), _ts("2024-04-01 10:00:00"), "Savings", "9999", "acct-003", "bal-009",
             "Bank of America", 10000.00, "2024-04", "14", "Depository", "Asset", "Active",
             _ts("2023-01-01"), "Savings", None),
        ]
        extra_df = pd.DataFrame(new_rows, columns=BALANCE_HISTORY_SCRUBBED_COLUMNS)
        df = pd.concat([scrubbed_balance_df, extra_df], ignore_index=True)

        bs = make_balance_spreadsheet(df)
        summary = calculate_net_worth_summary(bs)
        assert summary["total_net_worth"] == pytest.approx(13900.0)

    def test_skips_blank_and_nan_groups(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet], scrubbed_balance_df: pd.DataFrame) -> None:
        """Groups that are blank or NaN are excluded (mirrors Home.py filtering)."""
        df = scrubbed_balance_df.copy()
        blank_row = df.iloc[[0]].copy()
        blank_row["Group"] = ""
        nan_row = df.iloc[[0]].copy()
        nan_row["Group"] = pd.NA
        df = pd.concat([df, blank_row, nan_row], ignore_index=True)

        bs = make_balance_spreadsheet(df)
        summary = calculate_net_worth_summary(bs)
        assert "" not in summary["group_balances"]
        assert all(g for g in summary["group_balances"])

    def test_zero_total_group(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        """A group whose balances sum to zero still appears in the summary."""
        df = pd.DataFrame(
            [
                (_ts("2024-03-01"), _ts("2024-03-01 09:00:00"), "Acct-A", "1111", "id-a", "bal-a",
                 "Bank", 500.0, "2024-03", "09", "Depository", "Asset", "Active",
                 _ts("2023-01-01"), "ZeroGroup", None),
                (_ts("2024-03-01"), _ts("2024-03-01 10:00:00"), "Acct-B", "2222", "id-b", "bal-b",
                 "Bank", -500.0, "2024-03", "09", "Depository", "Asset", "Active",
                 _ts("2023-01-01"), "ZeroGroup", None),
            ],
            columns=BALANCE_HISTORY_SCRUBBED_COLUMNS,
        )
        bs = make_balance_spreadsheet(df)
        summary = calculate_net_worth_summary(bs)
        assert "ZeroGroup" in summary["group_balances"]
        assert summary["group_balances"]["ZeroGroup"] == pytest.approx(0.0)
        assert summary["total_net_worth"] == pytest.approx(0.0)

    def test_multi_account_group_accounts_shape(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        """group_accounts has one row per account within a group."""
        df = pd.DataFrame(
            [
                (_ts("2024-03-01"), _ts("2024-03-01 09:00:00"), "Checking-1", "1111", "id-1", "bal-1",
                 "Bank", 1000.0, "2024-03", "09", "Depository", "Asset", "Active",
                 _ts("2023-01-01"), "Banking", None),
                (_ts("2024-03-01"), _ts("2024-03-01 10:00:00"), "Checking-2", "2222", "id-2", "bal-2",
                 "Bank", 2000.0, "2024-03", "09", "Depository", "Asset", "Active",
                 _ts("2023-01-01"), "Banking", None),
            ],
            columns=BALANCE_HISTORY_SCRUBBED_COLUMNS,
        )
        bs = make_balance_spreadsheet(df)
        summary = calculate_net_worth_summary(bs)
        accts = summary["group_accounts"]["Banking"]
        assert len(accts) == 2
        assert set(accts["Account"]) == {"Checking-1", "Checking-2"}
        assert summary["group_balances"]["Banking"] == pytest.approx(3000.0)

    def test_mixed_asset_liability_group(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        """A group with both asset and liability accounts signs each individually."""
        df = pd.DataFrame(
            [
                (_ts("2024-03-01"), _ts("2024-03-01 09:00:00"), "Brokerage", "1111", "id-1", "bal-1",
                 "Bank", 10000.0, "2024-03", "09", "Investment", "Asset", "Active",
                 _ts("2023-01-01"), "Investing", None),
                (_ts("2024-03-01"), _ts("2024-03-01 10:00:00"), "Margin Loan", "2222", "id-2", "bal-2",
                 "Bank", 3000.0, "2024-03", "09", "Loan", "Liability", "Active",
                 _ts("2023-01-01"), "Investing", None),
            ],
            columns=BALANCE_HISTORY_SCRUBBED_COLUMNS,
        )
        bs = make_balance_spreadsheet(df)
        summary = calculate_net_worth_summary(bs)
        # Asset 10000 - Liability 3000 = 7000 net
        assert summary["total_net_worth"] == pytest.approx(7000.0)
        # Dominant class is Asset (1 asset vs 1 liability, tie goes to Asset)
        assert summary["group_classes"]["Investing"] == "Asset"

    def test_total_equals_independent_signed_sum(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet], scrubbed_balance_df: pd.DataFrame) -> None:
        """total_net_worth matches an independently computed signed sum across
        all accounts, guarding against sign or aggregation regressions."""
        bs = make_balance_spreadsheet()
        summary = calculate_net_worth_summary(bs)

        df = scrubbed_balance_df.copy()
        df = df.sort_values(by=["Date", "Time"])
        df = df.drop_duplicates("Account ID", keep="last")
        multiplier = df["Class"].map({"Liability": -1, "Asset": 1}).fillna(1)
        expected = float((df["Balance"] * multiplier).sum())

        assert summary["total_net_worth"] == pytest.approx(expected)

    def test_majority_liability_group(self, make_balance_spreadsheet: Callable[..., BalanceHistorySpreadsheet]) -> None:
        """When liabilities outnumber assets, dominant class is Liability."""
        df = pd.DataFrame(
            [
                (_ts("2024-03-01"), _ts("2024-03-01 09:00:00"), "Asset-Acct", "1111", "id-1", "bal-1",
                 "Bank", 5000.0, "2024-03", "09", "Investment", "Asset", "Active",
                 _ts("2023-01-01"), "Mixed", None),
                (_ts("2024-03-01"), _ts("2024-03-01 10:00:00"), "Loan-A", "2222", "id-2", "bal-2",
                 "Bank", 2000.0, "2024-03", "09", "Loan", "Liability", "Active",
                 _ts("2023-01-01"), "Mixed", None),
                (_ts("2024-03-01"), _ts("2024-03-01 11:00:00"), "Loan-B", "3333", "id-3", "bal-3",
                 "Bank", 1000.0, "2024-03", "09", "Loan", "Liability", "Active",
                 _ts("2023-01-01"), "Mixed", None),
            ],
            columns=BALANCE_HISTORY_SCRUBBED_COLUMNS,
        )
        bs = make_balance_spreadsheet(df)
        summary = calculate_net_worth_summary(bs)
        # Asset 5000 - Liability (2000 + 1000) = 2000 net
        assert summary["total_net_worth"] == pytest.approx(2000.0)
        assert summary["group_classes"]["Mixed"] == "Liability"
