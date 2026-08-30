"""Tests for ``TransactionsSpreadsheet`` data methods.

Covers:
    - Metadata helpers (``get_total_months``, ``get_groups``, ``get_group_categories``).
    - ``filter_transactions`` and its include/ignore axes.
    - ``get_amount_by_group`` and ``get_amount_by_group_category`` aggregators.
    - ``get_monthly_amounts_by_*`` helpers.
    - NaN/None tolerance across the transactions surface.
"""

import pandas as pd
import pytest

from tests._helpers import _transactions_df, _utc
from tests.custom_types import TransactionsSpreadsheetFactory


class TestTransactionsMetadata:
    def test_get_total_months(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """get_total_months divides timedelta by np.timedelta64(1,'M')."""
        rows = [
            {
                "Date": "2024-01-10",
                "Category": "A",
                "Amount": -10,
                "Account": "C",
                "Month": "2024-01",
                "Group": "G",
                "Type": "Expense",
            },
            {
                "Date": "2024-03-10",
                "Category": "B",
                "Amount": -20,
                "Account": "C",
                "Month": "2024-03",
                "Group": "G",
                "Type": "Expense",
            },
        ]
        defaults = {"Full Description": "", "Institution": "", "Account #": ""}
        records = [{**defaults, **r} for r in rows]
        df = pd.DataFrame(records)
        df["Date"] = pd.to_datetime(df["Date"])
        df["Amount"] = df["Amount"].astype(float)
        ts = make_transactions_spreadsheet(df)
        assert ts.get_total_months() == 2

    def test_get_groups(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        groups = list(ts.get_groups())
        assert "Food" in groups
        assert "Housing" in groups
        assert "Income" in groups

    def test_get_group_categories(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        cats = list(ts.get_group_categories("Food"))
        assert "Groceries" in cats
        assert "Dining" in cats
        assert "Rent" not in cats


class TestFilterTransactions:
    def test_no_filters(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions()
        assert len(result) == len(sample_transactions_df)

    def test_include_categories(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(include_categories=["Groceries"])
        assert all(result["Category"] == "Groceries")
        assert len(result) == 2

    def test_ignore_categories(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(ignore_categories=["Groceries"])
        assert "Groceries" not in result["Category"].values

    def test_include_groups(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(include_groups=["Food"])
        assert all(result["Group"] == "Food")

    def test_ignore_groups(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(ignore_groups=["Food"])
        assert "Food" not in result["Group"].values

    def test_include_types(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(include_types=["Income"])
        assert all(result["Type"] == "Income")

    def test_ignore_types_filters_type_column(
        self,
        sample_transactions_df: pd.DataFrame,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """ignore_types should exclude rows by Type, not Group."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(ignore_types=["Transfer"])
        assert "Transfer" not in result["Type"].values

    def test_include_and_ignore_same_axis(
        self,
        sample_transactions_df: pd.DataFrame,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """ignore_categories is applied after include_categories, so ignore wins."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(
            include_categories=["Groceries", "Rent"],
            ignore_categories=["Rent"],
        )
        assert "Groceries" in result["Category"].values
        assert "Rent" not in result["Category"].values

    def test_date_range(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        start = _utc(2024, 2, 1)
        end = _utc(2024, 2, 28)
        result = ts.filter_transactions(start_date=start, end_date=end)
        assert all((result["Date"] >= start) & (result["Date"] <= end))

    def test_filtered_columns(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(filtered_columns=["Date", "Amount"])
        assert list(result.columns) == ["Date", "Amount"]

    def test_group_by_column(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(group_by_column="Group")
        assert "Amount" in result.columns
        assert "Food" in result.index

    def test_empty_df(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        empty = pd.DataFrame(
            {
                "Date": pd.Series([], dtype="datetime64[ns, UTC]"),
                "Category": pd.Series([], dtype=str),
                "Amount": pd.Series([], dtype=float),
                "Account": pd.Series([], dtype=str),
                "Month": pd.Series([], dtype=str),
                "Full Description": pd.Series([], dtype=str),
                "Group": pd.Series([], dtype=str),
                "Type": pd.Series([], dtype=str),
                "Institution": pd.Series([], dtype=str),
                "Account #": pd.Series([], dtype=str),
            }
        )
        ts = make_transactions_spreadsheet(empty)
        result = ts.filter_transactions()
        assert len(result) == 0


class TestGetAmountByGroup:
    def test_basic(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group()
        assert "Amount" in result.columns
        assert result.loc["Food", "Amount"] == pytest.approx(-140)

    def test_invert_amount(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group(invert_amount=True)
        assert result.loc["Food", "Amount"] == pytest.approx(140)

    def test_ignore_types_filters_type_column(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """ignore_types=['Transfer'] removes Transfer-typed rows regardless of group name."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-01",
                    "Category": "A",
                    "Amount": 100,
                    "Account": "C",
                    "Month": "2024-01",
                    "Group": "Savings",
                    "Type": "Transfer",
                },
                {
                    "Date": "2024-01-02",
                    "Category": "B",
                    "Amount": 200,
                    "Account": "C",
                    "Month": "2024-01",
                    "Group": "Savings",
                    "Type": "Income",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        result = ts.get_amount_by_group(ignore_types=["Transfer"])
        assert result.loc["Savings", "Amount"] == pytest.approx(200)


class TestGetAmountByGroupCategory:
    def test_basic(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("Food")
        assert "Groceries" in result.index
        assert "Dining" in result.index
        assert result.loc["Groceries", "Amount"] == pytest.approx(-110)

    def test_invert(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("Food", invert_amount=True)
        assert result.loc["Groceries", "Amount"] == pytest.approx(110)

    def test_empty_group(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """A group that doesn't exist returns an empty DataFrame."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("NonExistent")
        assert result.empty

    def test_include_categories_narrows_within_group(
        self,
        sample_transactions_df: pd.DataFrame,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """include_categories combined with group filter returns only matching categories."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("Food", include_categories=["Groceries"])
        assert "Groceries" in result.index
        assert "Dining" not in result.index

    def test_include_categories_outside_group_returns_empty(
        self,
        sample_transactions_df: pd.DataFrame,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """A category not in the requested group returns nothing."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("Food", include_categories=["Rent"])
        assert result.empty


class TestMonthlyAmounts:
    def test_monthly_by_category(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_monthly_amounts_by_category("Groceries")
        assert "2024-01" in result.index
        assert "2024-02" in result.index
        assert result.loc["2024-01", "Amount"] == pytest.approx(-50)

    def test_monthly_by_category_invert(
        self,
        sample_transactions_df: pd.DataFrame,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_monthly_amounts_by_category("Groceries", invert_amount=True)
        assert result.loc["2024-01", "Amount"] == pytest.approx(50)

    def test_monthly_by_group(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_monthly_amounts_by_group("Food")
        assert "2024-01" in result.index
        assert result.loc["2024-01", "Amount"] == pytest.approx(-50)
        assert result.loc["2024-03", "Amount"] == pytest.approx(-30)

    def test_monthly_by_group_invert(
        self, sample_transactions_df: pd.DataFrame, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_monthly_amounts_by_group("Food", invert_amount=True)
        assert result.loc["2024-01", "Amount"] == pytest.approx(50)


class TestNaNHandling:
    def test_filter_transactions_nan_amount(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """NaN in Amount column should not crash filter_transactions."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-10",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
                {
                    "Date": "2024-01-15",
                    "Category": "Dining",
                    "Amount": float("nan"),
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        result = ts.filter_transactions()
        assert len(result) == 2

    def test_get_amount_by_group_nan_amount(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """NaN amounts propagate through sum - group total includes NaN contribution."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-10",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
                {
                    "Date": "2024-01-15",
                    "Category": "Dining",
                    "Amount": float("nan"),
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        result = ts.get_amount_by_group()
        assert result.loc["Food", "Amount"] == pytest.approx(-50)

    def test_filter_transactions_nan_category(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """NaN Category: isin() excludes NaN, so include_categories filter drops NaN rows."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-10",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
                {
                    "Date": "2024-01-15",
                    "Category": None,
                    "Amount": -30,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        result = ts.filter_transactions(include_categories=["Groceries"])
        assert len(result) == 1
        assert result.iloc[0]["Category"] == "Groceries"

    def test_filter_transactions_nan_group(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """NaN Group: isin() excludes NaN, so include_groups filter drops NaN rows."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-10",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
                {
                    "Date": "2024-01-15",
                    "Category": "Dining",
                    "Amount": -30,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": None,
                    "Type": "Expense",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        result = ts.filter_transactions(include_groups=["Food"])
        assert len(result) == 1

    def test_filter_transactions_nan_date(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """NaT Date: between() returns False for NaT, so those rows are dropped."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-10",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
            ]
        )
        nan_row = pd.DataFrame(
            [
                {
                    "Date": pd.NaT,
                    "Category": "Dining",
                    "Amount": -30,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                    "Full Description": "",
                    "Institution": "",
                    "Account #": "",
                }
            ]
        )
        df = pd.concat([df, nan_row], ignore_index=True)
        ts = make_transactions_spreadsheet(df)
        result = ts.filter_transactions(start_date=_utc(2024, 1, 1), end_date=_utc(2024, 12, 31))
        assert len(result) == 1

    def test_get_monthly_amounts_by_category_nan_amount(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """NaN in Amount is skipped by groupby sum."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-10",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
                {
                    "Date": "2024-01-20",
                    "Category": "Groceries",
                    "Amount": float("nan"),
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        result = ts.get_monthly_amounts_by_category("Groceries")
        assert result.loc["2024-01", "Amount"] == pytest.approx(-50)

    def test_get_total_months_single_row(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """A single transaction should return 0 total months (min == max)."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-03-15",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-03",
                    "Group": "Food",
                    "Type": "Expense",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        assert ts.get_total_months() == 0

    def test_get_monthly_amounts_nonexistent_category(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """Querying a category that doesn't exist returns an empty DataFrame."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-10",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        result = ts.get_monthly_amounts_by_category("NonExistent")
        assert result.empty

    def test_groupby_nan_group_key(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Rows with NaN Group are excluded from groupby results by default."""
        df = _transactions_df(
            [
                {
                    "Date": "2024-01-10",
                    "Category": "Groceries",
                    "Amount": -50,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": "Food",
                    "Type": "Expense",
                },
                {
                    "Date": "2024-01-15",
                    "Category": "Dining",
                    "Amount": -30,
                    "Account": "Checking",
                    "Month": "2024-01",
                    "Group": None,
                    "Type": "Expense",
                },
            ]
        )
        ts = make_transactions_spreadsheet(df)
        result = ts.get_amount_by_group()
        assert "Food" in result.index
        assert len(result) == 1


class TestAggregationMath:
    """Hand-verified aggregation math across multiple months/categories."""

    def test_sum_across_months_is_stable(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Summing the same category across months returns a deterministic total."""
        rows = [
            {
                "Date": "2024-01-10",
                "Category": "Groceries",
                "Amount": -100.00,
                "Account": "Checking",
                "Month": "2024-01",
                "Group": "Food",
                "Type": "Expense",
            },
            {
                "Date": "2024-02-10",
                "Category": "Groceries",
                "Amount": -150.50,
                "Account": "Checking",
                "Month": "2024-02",
                "Group": "Food",
                "Type": "Expense",
            },
            {
                "Date": "2024-03-10",
                "Category": "Groceries",
                "Amount": -75.25,
                "Account": "Checking",
                "Month": "2024-03",
                "Group": "Food",
                "Type": "Expense",
            },
        ]
        ts = make_transactions_spreadsheet(_transactions_df(rows))
        result = ts.get_amount_by_group()
        # Sum = -100 + -150.50 + -75.25 = -325.75
        assert result.loc["Food", "Amount"] == pytest.approx(-325.75)

    def test_monthly_breakdown_row_per_month(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """get_monthly_amounts_by_category produces one row per month."""
        rows = [
            {
                "Date": "2024-01-10",
                "Category": "Groceries",
                "Amount": -100,
                "Account": "Checking",
                "Month": "2024-01",
                "Group": "Food",
                "Type": "Expense",
            },
            {
                "Date": "2024-01-20",
                "Category": "Groceries",
                "Amount": -50,
                "Account": "Checking",
                "Month": "2024-01",
                "Group": "Food",
                "Type": "Expense",
            },
            {
                "Date": "2024-02-10",
                "Category": "Groceries",
                "Amount": -200,
                "Account": "Checking",
                "Month": "2024-02",
                "Group": "Food",
                "Type": "Expense",
            },
        ]
        ts = make_transactions_spreadsheet(_transactions_df(rows))
        result = ts.get_monthly_amounts_by_category("Groceries")
        # January sum = -150, February sum = -200
        assert result.loc["2024-01", "Amount"] == pytest.approx(-150)
        assert result.loc["2024-02", "Amount"] == pytest.approx(-200)

    def test_get_total_months_single_month_is_zero(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """Single-month data yields 0 because (latest.month - earliest.month) = 0.

        Documents the current implementation: get_total_months counts *whole*
        month boundaries crossed, not elapsed time. Two dates in the same
        calendar month return 0 even if 30 days apart.
        """
        rows = [
            {
                "Date": "2024-01-10",
                "Category": "A",
                "Amount": -10,
                "Account": "C",
                "Month": "2024-01",
                "Group": "G",
                "Type": "Expense",
            },
            {
                "Date": "2024-01-20",
                "Category": "A",
                "Amount": -20,
                "Account": "C",
                "Month": "2024-01",
                "Group": "G",
                "Type": "Expense",
            },
        ]
        ts = make_transactions_spreadsheet(_transactions_df(rows))
        assert ts.get_total_months() == 0

    def test_get_total_months_year_span(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Jan 1 to Dec 31 spans 11 whole month boundaries: (12 - 1) + 12*0 = 11."""
        rows = [
            {
                "Date": "2024-01-01",
                "Category": "A",
                "Amount": -10,
                "Account": "C",
                "Month": "2024-01",
                "Group": "G",
                "Type": "Expense",
            },
            {
                "Date": "2024-12-31",
                "Category": "A",
                "Amount": -20,
                "Account": "C",
                "Month": "2024-12",
                "Group": "G",
                "Type": "Expense",
            },
        ]
        ts = make_transactions_spreadsheet(_transactions_df(rows))
        assert ts.get_total_months() == 11

    def test_get_total_months_cross_year(self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory) -> None:
        """Dec 2023 to Feb 2024 crosses the year boundary: (2024-2023)*12 + (2-12) = 2."""
        rows = [
            {
                "Date": "2023-12-15",
                "Category": "A",
                "Amount": -10,
                "Account": "C",
                "Month": "2023-12",
                "Group": "G",
                "Type": "Expense",
            },
            {
                "Date": "2024-02-15",
                "Category": "A",
                "Amount": -20,
                "Account": "C",
                "Month": "2024-02",
                "Group": "G",
                "Type": "Expense",
            },
        ]
        ts = make_transactions_spreadsheet(_transactions_df(rows))
        assert ts.get_total_months() == 2

    def test_zero_amount_does_not_break_aggregation(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """A $0 transaction contributes zero, doesn't skew totals."""
        rows = [
            {
                "Date": "2024-01-10",
                "Category": "Groceries",
                "Amount": -100,
                "Account": "Checking",
                "Month": "2024-01",
                "Group": "Food",
                "Type": "Expense",
            },
            {
                "Date": "2024-01-11",
                "Category": "Groceries",
                "Amount": 0,
                "Account": "Checking",
                "Month": "2024-01",
                "Group": "Food",
                "Type": "Expense",
            },
        ]
        ts = make_transactions_spreadsheet(_transactions_df(rows))
        result = ts.get_amount_by_group()
        assert result.loc["Food", "Amount"] == pytest.approx(-100)

    def test_extremely_large_amounts_no_overflow(
        self, make_transactions_spreadsheet: TransactionsSpreadsheetFactory
    ) -> None:
        """Large values (e.g., big wire transfer) don't cause float overflow."""
        rows = [
            {
                "Date": "2024-01-10",
                "Category": "Home",
                "Amount": -500000.00,
                "Account": "Checking",
                "Month": "2024-01",
                "Group": "Housing",
                "Type": "Expense",
            },
            {
                "Date": "2024-01-11",
                "Category": "Home",
                "Amount": -250000.50,
                "Account": "Checking",
                "Month": "2024-01",
                "Group": "Housing",
                "Type": "Expense",
            },
        ]
        ts = make_transactions_spreadsheet(_transactions_df(rows))
        result = ts.get_amount_by_group()
        assert result.loc["Housing", "Amount"] == pytest.approx(-750000.50)
