"""Tests for Pages/2_Spending_by_Category.py - process_spending_data, calculate_distribution_stats, and spending summary."""
from collections.abc import Callable
from typing import Any

import pytest
import pandas as pd

from src.spreadsheet import TransactionsSpreadsheet
from tests._pages import spending_by_category as _mod

process_spending_data = _mod.process_spending_data
calculate_distribution_stats = _mod.calculate_distribution_stats
calculate_spending_summary = _mod.calculate_spending_summary


class TestProcessSpendingData:

    def test_filters_to_expenses_only(
        self,
        spending_transactions_df: pd.DataFrame,
        basic_spending_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        df_period, _df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        # df_period should contain only expenses
        assert (df_period['Type'] == 'Expense').all()

    def test_category_grouping_with_abs_amounts(
        self,
        spending_transactions_df: pd.DataFrame,
        basic_spending_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        _, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        # All amounts should be positive (absolute values)
        assert (df_by_category['Amount'] >= 0).all()

        # Groceries should have 200 + 100 = 300
        groceries_row = df_by_category[df_by_category['Category'] == 'Groceries']
        assert groceries_row['Amount'].values[0] == pytest.approx(300)

    def test_percentages_sum_to_100(
        self,
        spending_transactions_df: pd.DataFrame,
        basic_spending_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        _, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        total_pct = df_by_category['Percentage'].sum()
        assert total_pct == pytest.approx(100.0, abs=0.5)


class TestCalculateDistributionStats:

    def test_percentiles_correct(self, expenses_only_df: pd.DataFrame) -> None:
        stats = calculate_distribution_stats(expenses_only_df)
        amounts = expenses_only_df['Amount'].abs()

        assert stats['median'] == pytest.approx(amounts.quantile(0.50))
        assert stats['p25'] == pytest.approx(amounts.quantile(0.25))
        assert stats['p75'] == pytest.approx(amounts.quantile(0.75))
        assert stats['mean'] == pytest.approx(amounts.mean())

    def test_size_bucket_counts(self, expenses_only_df: pd.DataFrame) -> None:
        stats = calculate_distribution_stats(expenses_only_df)

        # Amounts are 10, 50, 100, 300, 500
        # small (<25): 10 -> 1
        # medium (25-250): 50, 100 -> 2
        # large (>=250): 300, 500 -> 2
        assert stats['small_count'] == 1
        assert stats['medium_count'] == 2
        assert stats['large_count'] == 2

    def test_pareto_off_by_one(self, expenses_only_df: pd.DataFrame) -> None:
        """The count should include the transaction that pushes cumulative sum past 80%."""
        stats = calculate_distribution_stats(expenses_only_df)

        # Amounts sorted desc: 500, 300, 100, 50, 10 -> total = 960
        # 80% threshold = 768
        # cumsum: 500, 800, 900, 950, 960
        # Transaction at cumsum=800 pushes past 768, so 2 transactions account for 80%
        # Expected pareto_pct = 2/5 * 100 = 40%
        assert stats['pareto_pct'] == pytest.approx(40.0)

    def test_single_transaction(self) -> None:
        """Distribution stats for a single transaction."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-05'], utc=True),
            'Amount': [-100],
            'Type': ['Expense'],
            'Category': ['Groceries'],
            'Group': ['Food'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['STORE'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        stats = calculate_distribution_stats(df)

        assert stats['median'] == pytest.approx(100.0)
        assert stats['mean'] == pytest.approx(100.0)
        assert stats['p25'] == pytest.approx(100.0)
        assert stats['p75'] == pytest.approx(100.0)
        # Single transaction accounts for 100% of spending
        assert stats['pareto_pct'] == pytest.approx(100.0)

    def test_all_same_amount(self) -> None:
        """All transactions with same amount."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03'], utc=True),
            'Amount': [-50, -50, -50],
            'Type': ['Expense'] * 3,
            'Category': ['Coffee'] * 3,
            'Group': ['Food'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01'] * 3,
            'Full Description': ['CAFE'] * 3,
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        stats = calculate_distribution_stats(df)

        assert stats['median'] == pytest.approx(50.0)
        assert stats['mean'] == pytest.approx(50.0)
        assert stats['small_count'] == 0
        assert stats['medium_count'] == 3
        assert stats['large_count'] == 0

    def test_date_range_filters_transactions(
        self,
        spending_transactions_df: pd.DataFrame,
        basic_spending_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Only transactions within the date range are included."""
        ts = make_transactions_spreadsheet(spending_transactions_df)
        # Only January
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-01-31', tz='UTC')

        df_period, _df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        # February transaction should be excluded
        assert all(d.month == 1 for d in df_period['Date'])

    def test_zero_spending_returns_zero_percentages(
        self,
        basic_spending_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """No expenses in range produces zero percentages."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [5000],
            'Type': ['Income'],
            'Category': ['Salary'],
            'Group': ['Income'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['PAY'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        df_period, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        assert len(df_period) == 0
        assert len(df_by_category) == 0


class TestCalculateSpendingSummary:
    """Test ``calculate_spending_summary`` — pure metrics from category breakdown."""

    def test_empty_df(self) -> None:
        """Empty input returns zeroed summary with empty top_category."""
        result = calculate_spending_summary(pd.DataFrame(columns=["Amount", "Category", "Percentage"]))
        assert result["total_spending"] == 0.0
        assert result["top_category"] == ""
        assert result["top_category_amount"] == 0.0
        assert result["num_categories"] == 0

    def test_single_category(self) -> None:
        df = pd.DataFrame({"Category": ["Groceries"], "Amount": [450.0], "Percentage": [100.0]})
        result = calculate_spending_summary(df)
        assert result["total_spending"] == pytest.approx(450.0)
        assert result["top_category"] == "Groceries"
        assert result["top_category_amount"] == pytest.approx(450.0)
        assert result["num_categories"] == 1

    def test_multiple_categories_top_is_first(self) -> None:
        """Top category is the first row (assumes descending sort from process_spending_data)."""
        df = pd.DataFrame({
            "Category": ["Rent", "Groceries", "Coffee"],
            "Amount": [1200.0, 300.0, 50.0],
            "Percentage": [77.4, 19.4, 3.2],
        })
        result = calculate_spending_summary(df)
        assert result["total_spending"] == pytest.approx(1550.0)
        assert result["top_category"] == "Rent"
        assert result["top_category_amount"] == pytest.approx(1200.0)
        assert result["num_categories"] == 3
