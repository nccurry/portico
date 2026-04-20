"""Tests for Pages/1_Income_and_Savings.py - process_income_expense_data and savings summary."""
from collections.abc import Callable
from typing import Any

import pytest
import pandas as pd

from src.spreadsheet import TransactionsSpreadsheet
from tests._pages import income_and_savings as _mod

process_income_expense_data = _mod.process_income_expense_data
calculate_savings_summary = _mod.calculate_savings_summary


class TestProcessIncomeExpenseData:

    def test_separates_income_expense(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        # Should have Income and Expense columns
        assert 'Income' in result.columns
        assert 'Expense' in result.columns
        # Income values should be positive, Expense values negative
        assert (result['Income'] >= 0).all()
        assert (result['Expense'] <= 0).all()

    def test_savings_equals_income_plus_expense(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        for _, row in result.iterrows():
            assert row['Savings'] == pytest.approx(row['Income'] + row['Expense'])

    def test_savings_rate_calculation(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        for _, row in result.iterrows():
            if row['Income_Display'] > 0.01:
                expected_rate = row['Savings'] / row['Income_Display'] * 100
                assert row['Savings_Rate'] == pytest.approx(expected_rate)

    def test_savings_rate_zero_income(self, basic_filters: dict[str, Any], make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet]) -> None:
        """When income is 0, savings rate should be 0 (no division by zero)."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [-500],
            'Type': ['Expense'],
            'Category': ['Groceries'],
            'Group': ['Food'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['STORE PURCHASE'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)

        # Should not crash and savings rate should be 0
        assert (result['Savings_Rate'] == 0).all()

    def test_output_sorted_by_month(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        months = result['Month'].tolist()
        assert months == sorted(months)

    def test_only_income_month_gives_100_percent_rate(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Month with income but no expenses should have 100% savings rate."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [5000],
            'Type': ['Income'],
            'Category': ['Salary'],
            'Group': ['Income'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['PAYROLL'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)

        assert len(result) == 1
        assert result.iloc[0]['Savings_Rate'] == pytest.approx(100.0)
        assert result.iloc[0]['Savings'] == pytest.approx(5000.0)

    def test_only_expense_month_gives_zero_rate(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Month with only expenses should have 0% savings rate (no income to divide by)."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [-500],
            'Type': ['Expense'],
            'Category': ['Groceries'],
            'Group': ['Food'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['STORE'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)

        assert result.iloc[0]['Savings_Rate'] == 0
        assert result.iloc[0]['Expense'] == pytest.approx(-500.0)

    def test_multiple_months_varying_ratios(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Each month gets its own savings rate, varying by income/expense mix."""
        df = pd.DataFrame({
            'Date': pd.to_datetime([
                '2024-01-15', '2024-01-20',  # Jan: 1000 income, 200 expense
                '2024-02-15', '2024-02-20',  # Feb: 1000 income, 800 expense
            ], utc=True),
            'Amount': [1000, -200, 1000, -800],
            'Type': ['Income', 'Expense', 'Income', 'Expense'],
            'Category': ['Salary', 'Groceries', 'Salary', 'Groceries'],
            'Group': ['Income', 'Food', 'Income', 'Food'],
            'Account': ['Checking'] * 4,
            'Month': ['2024-01', '2024-01', '2024-02', '2024-02'],
            'Full Description': ['PAY', 'STORE', 'PAY', 'STORE'],
            'Institution': ['Bank'] * 4,
            'Account #': ['1234'] * 4,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)

        jan = result[result['Month'] == '2024-01'].iloc[0]
        feb = result[result['Month'] == '2024-02'].iloc[0]

        # Jan: (1000 - 200) / 1000 * 100 = 80%
        assert jan['Savings_Rate'] == pytest.approx(80.0)
        # Feb: (1000 - 800) / 1000 * 100 = 20%
        assert feb['Savings_Rate'] == pytest.approx(20.0)

    def test_empty_dataframe(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
        empty_transactions_df: pd.DataFrame,
    ) -> None:
        """Empty transactions produce empty result without errors."""
        ts = make_transactions_spreadsheet(empty_transactions_df)
        result = process_income_expense_data(ts, basic_filters)

        assert len(result) == 0

    def test_income_display_is_absolute(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Income_Display and Expense_Display are absolute values."""
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        assert (result['Income_Display'] >= 0).all()
        assert (result['Expense_Display'] >= 0).all()

    def test_net_equals_savings(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Net column should equal Savings column."""
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        for _, row in result.iterrows():
            assert row['Net'] == pytest.approx(row['Savings'])

    def test_exclude_groups_filter(self, make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet]) -> None:
        """Excluding a group removes its transactions from the calculation."""
        # Use the conftest scrubbed_transactions_df which has Bills, Food, Shopping, Income
        filters = {
            'exclude_groups': ['Food'],
            'exclude_categories': [],
            'filter_large_income': False,
            'income_threshold': 50000,
            'filter_large_expenses': False,
            'expense_threshold': 50000,
            'target_rate': 20,
        }
        # Default fixture has: Salary(Income), Groceries(Food), Electric(Bills),
        # Salary(Income), Restaurants(Food), Amazon(Shopping), Salary(Income), Internet(Bills)
        ts = make_transactions_spreadsheet()
        result = process_income_expense_data(ts, filters)

        # With Food excluded, expenses are: Electric(-95), Amazon(-200), Internet(-79.99)
        total_expense = result['Expense'].sum()
        assert abs(total_expense) == pytest.approx(95.0 + 200.0 + 79.99)


class TestCalculateSavingsSummary:
    """Test ``calculate_savings_summary`` — pure metrics derived from pivot data."""

    def _pivot(self, rows: list[dict]) -> pd.DataFrame:
        """Build a minimal df_pivot from row dicts."""
        return pd.DataFrame(rows)

    def test_empty_pivot(self) -> None:
        """Empty input returns zeroed summary."""
        result = calculate_savings_summary(pd.DataFrame())
        assert result["avg_monthly_rate"] == 0.0
        assert result["overall_rate"] == 0.0
        assert result["avg_monthly_amount"] == 0.0
        assert result["total_saved"] == 0.0
        assert result["num_months"] == 0

    def test_single_month(self) -> None:
        df = self._pivot([{
            "Savings_Rate": 50.0,
            "Income_Display": 4000.0,
            "Savings": 2000.0,
        }])
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(50.0)
        assert result["overall_rate"] == pytest.approx(50.0)
        assert result["avg_monthly_amount"] == pytest.approx(2000.0)
        assert result["total_saved"] == pytest.approx(2000.0)
        assert result["num_months"] == 1

    def test_weighted_vs_simple_avg_diverge(self) -> None:
        """Months with unequal income cause weighted and simple averages to differ."""
        df = self._pivot([
            {"Savings_Rate": 80.0, "Income_Display": 1000.0, "Savings": 800.0},
            {"Savings_Rate": 20.0, "Income_Display": 9000.0, "Savings": 1800.0},
        ])
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(50.0)
        assert result["overall_rate"] == pytest.approx(26.0)

    def test_zero_income_overall_rate(self) -> None:
        """When total income is zero, overall_rate should be 0 (no division error)."""
        df = self._pivot([
            {"Savings_Rate": 0.0, "Income_Display": 0.0, "Savings": -500.0},
        ])
        result = calculate_savings_summary(df)
        assert result["overall_rate"] == 0.0
        assert result["total_saved"] == pytest.approx(-500.0)

    def test_negative_savings(self) -> None:
        """Spending more than earning produces negative savings metrics."""
        df = self._pivot([
            {"Savings_Rate": -25.0, "Income_Display": 4000.0, "Savings": -1000.0},
        ])
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(-25.0)
        assert result["overall_rate"] == pytest.approx(-25.0)
        assert result["total_saved"] == pytest.approx(-1000.0)

    def test_num_months(self) -> None:
        df = self._pivot([
            {"Savings_Rate": 10.0, "Income_Display": 5000.0, "Savings": 500.0},
            {"Savings_Rate": 20.0, "Income_Display": 5000.0, "Savings": 1000.0},
            {"Savings_Rate": 30.0, "Income_Display": 5000.0, "Savings": 1500.0},
        ])
        result = calculate_savings_summary(df)
        assert result["num_months"] == 3
        assert result["total_saved"] == pytest.approx(3000.0)
        assert result["avg_monthly_amount"] == pytest.approx(1000.0)
