"""Tests for pages/3_Year_over_Year.py - category/group extraction logic."""
import numpy as np
import pandas as pd

from tests.custom_types import TransactionsSpreadsheetFactory
from tests._helpers import _transactions_df


class TestGetAllCategories:
    """Test TransactionsSpreadsheet.get_all_categories()."""

    def test_nan_categories_excluded(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """NaN values in Category column are filtered out."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Groceries", "Amount": -10, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-02", "Category": None,        "Amount": -5,  "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-03", "Category": "Dining",    "Amount": -20, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        df.loc[1, "Category"] = np.nan
        ts = make_transactions_spreadsheet(df)
        categories = ts.get_all_categories()
        assert "Groceries" in categories
        assert "Dining" in categories
        assert len(categories) == 2

    def test_empty_string_categories_excluded(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Whitespace-only category strings are excluded."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Groceries", "Amount": -10, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "",          "Amount": -5,  "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-03", "Category": "   ",       "Amount": -20, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        categories = ts.get_all_categories()
        assert categories == ["Groceries"]

    def test_sorted_output(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Categories are returned in sorted order."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Dining",    "Amount": -10, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "Auto",      "Amount": -5,  "Account": "C", "Month": "2024-01", "Group": "Transport", "Type": "Expense"},
            {"Date": "2024-01-03", "Category": "Groceries", "Amount": -20, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        assert ts.get_all_categories() == ["Auto", "Dining", "Groceries"]

    def test_all_nan_returns_empty(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """If all categories are NaN, an empty list is returned."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": None, "Amount": -10, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        df["Category"] = np.nan
        ts = make_transactions_spreadsheet(df)
        assert ts.get_all_categories() == []


class TestGetAllGroups:
    """Test TransactionsSpreadsheet.get_all_groups()."""

    def test_nan_groups_excluded(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """NaN values in Group column are filtered out."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Groceries", "Amount": -10, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "Dining",    "Amount": -5,  "Account": "C", "Month": "2024-01", "Group": None,   "Type": "Expense"},
        ])
        df.loc[1, "Group"] = np.nan
        ts = make_transactions_spreadsheet(df)
        groups = ts.get_all_groups()
        assert groups == ["Food"]

    def test_transfer_group_excluded(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Transfer group is excluded from the group list."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Groceries",     "Amount": -10, "Account": "C", "Month": "2024-01", "Group": "Food",     "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "Bank Transfer", "Amount": 100, "Account": "C", "Month": "2024-01", "Group": "Transfer", "Type": "Transfer"},
        ])
        ts = make_transactions_spreadsheet(df)
        groups = ts.get_all_groups()
        assert "Transfer" not in groups
        assert "Food" in groups

    def test_blank_groups_excluded(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Whitespace-only group strings are excluded."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Groceries", "Amount": -10, "Account": "C", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "Other",     "Amount": -5,  "Account": "C", "Month": "2024-01", "Group": "",     "Type": "Expense"},
            {"Date": "2024-01-03", "Category": "Other2",    "Amount": -5,  "Account": "C", "Month": "2024-01", "Group": "  ",   "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        assert ts.get_all_groups() == ["Food"]

    def test_sorted_output(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Groups are returned in sorted order."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Groceries", "Amount": -10, "Account": "C", "Month": "2024-01", "Group": "Food",      "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "Gas",       "Amount": -40, "Account": "C", "Month": "2024-01", "Group": "Auto",      "Type": "Expense"},
            {"Date": "2024-01-03", "Category": "Netflix",   "Amount": -15, "Account": "C", "Month": "2024-01", "Group": "Entertainment", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        assert ts.get_all_groups() == ["Auto", "Entertainment", "Food"]

    def test_all_nan_returns_empty(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """If all groups are NaN, an empty list is returned."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "X", "Amount": -10, "Account": "C", "Month": "2024-01", "Group": None, "Type": "Expense"},
        ])
        df["Group"] = np.nan
        ts = make_transactions_spreadsheet(df)
        assert ts.get_all_groups() == []


class TestPrepareYearComparisonData:
    """Test the year-over-year data pivot from page_helpers."""

    def test_multi_year_pivot(self) -> None:
        from src.page_helpers import prepare_year_comparison_data

        # Monthly amounts indexed by YYYY-MM
        df = pd.DataFrame({
            'Amount': [100, 200, 150, 250],
        }, index=['2023-03', '2023-06', '2024-03', '2024-06'])
        df.index.name = 'Month'

        result = prepare_year_comparison_data(df)

        assert 2023 in result.columns
        assert 2024 in result.columns
        # Month 3 should have both years
        assert result.loc[3, 2023] == 100
        assert result.loc[3, 2024] == 150

    def test_missing_months_filled_with_zero(self) -> None:
        """Months without data in a year with data get filled with 0."""
        from src.page_helpers import prepare_year_comparison_data

        df = pd.DataFrame({
            'Amount': [100, 200],
        }, index=['2024-03', '2024-06'])
        df.index.name = 'Month'

        result = prepare_year_comparison_data(df)

        assert result.loc[3, 2024] == 100
        assert result.loc[6, 2024] == 200
        # Only months present in data appear (pivot doesn't pad)
        assert set(result.index) == {3, 6}

    def test_single_month_single_year(self) -> None:
        from src.page_helpers import prepare_year_comparison_data

        df = pd.DataFrame({
            'Amount': [500],
        }, index=['2024-01'])
        df.index.name = 'Month'

        result = prepare_year_comparison_data(df)

        assert len(result) == 1
        assert result.loc[1, 2024] == 500
        assert result.columns.equals(pd.Index([2024]))

    def test_empty_input(self) -> None:
        from src.page_helpers import prepare_year_comparison_data

        df = pd.DataFrame({'Amount': []})
        df.index.name = 'Month'

        result = prepare_year_comparison_data(df)
        assert result.empty
