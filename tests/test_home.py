"""Tests for Home.py - net worth calculation and account grouping logic."""
import pandas as pd
import pytest

from tests._helpers import calculate_net_worth
from tests.conftest import BALANCE_HISTORY_SCRUBBED_COLUMNS, _ts


class TestNetWorthCalculation:
    """Test the net worth calculation logic from Home.configure_page."""

    def test_net_worth_assets_minus_liabilities(self, make_balance_spreadsheet):
        """Net worth = sum(assets) - sum(liabilities)."""
        bs = make_balance_spreadsheet()
        net_worth, _balances, _classes = calculate_net_worth(bs)

        # Latest Checking (Asset) = 5500, latest Credit Card (Liability) = 1600
        assert net_worth == pytest.approx(5500.0 - 1600.0)

    def test_liability_group_classified_correctly(self, make_balance_spreadsheet):
        bs = make_balance_spreadsheet()
        _, _, classes = calculate_net_worth(bs)

        assert classes["Credit Card"] == "Liability"
        assert classes["Checking"] == "Asset"

    def test_group_balances_are_positive(self, make_balance_spreadsheet):
        """Group balances stored as positive regardless of asset/liability class."""
        bs = make_balance_spreadsheet()
        _, balances, _ = calculate_net_worth(bs)

        for group, balance in balances.items():
            assert balance >= 0

    def test_single_asset_group(self, make_balance_spreadsheet, scrubbed_balance_df):
        """Only asset accounts — net worth equals total balance."""
        df = scrubbed_balance_df[scrubbed_balance_df["Class"] == "Asset"].copy()
        bs = make_balance_spreadsheet(df)
        net_worth, _, _ = calculate_net_worth(bs)

        # Latest Checking balance = 5500
        assert net_worth == pytest.approx(5500.0)

    def test_single_liability_group(self, make_balance_spreadsheet, scrubbed_balance_df):
        """Only liability accounts — net worth is negative."""
        df = scrubbed_balance_df[scrubbed_balance_df["Class"] == "Liability"].copy()
        bs = make_balance_spreadsheet(df)
        net_worth, _, _ = calculate_net_worth(bs)

        # Latest Credit Card balance = 1600, net worth = -1600
        assert net_worth == pytest.approx(-1600.0)

    def test_empty_balance_history(self, make_balance_spreadsheet):
        """Empty balance data produces zero net worth."""
        empty_df = pd.DataFrame(columns=BALANCE_HISTORY_SCRUBBED_COLUMNS)
        bs = make_balance_spreadsheet(empty_df)
        net_worth, balances, _ = calculate_net_worth(bs)

        assert net_worth == pytest.approx(0.0)
        assert len(balances) == 0

    def test_multiple_asset_groups(self, make_balance_spreadsheet, scrubbed_balance_df):
        """Multiple asset groups sum correctly."""
        # Add a Savings account as a second asset group
        new_rows = [
            (_ts("2024-04-01"), _ts("2024-04-01 10:00:00"), "Savings", "9999", "acct-003", "bal-009",
             "Bank of America", 10000.00, "2024-04", "14", "Depository", "Asset", "Active",
             _ts("2023-01-01"), "Savings", None),
        ]
        extra_df = pd.DataFrame(new_rows, columns=BALANCE_HISTORY_SCRUBBED_COLUMNS)
        df = pd.concat([scrubbed_balance_df, extra_df], ignore_index=True)

        bs = make_balance_spreadsheet(df)
        net_worth, _, _ = calculate_net_worth(bs)

        # Checking 5500 + Savings 10000 - Credit Card 1600 = 13900
        assert net_worth == pytest.approx(13900.0)
