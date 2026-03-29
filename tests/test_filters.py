"""Tests for src/filters.py — calculate_date_range and apply_transaction_filters."""
import pytest
import pandas as pd
from datetime import timedelta

from src.filters import calculate_date_range, apply_transaction_filters


# ---------------------------------------------------------------------------
# Helper to build a transaction row matching TRANSACTIONS_SCRUBBED_COLUMNS
# ---------------------------------------------------------------------------

def _make_row(date, category, amount, group, txn_type, account="Checking",
              month="2024-01", desc="test", institution="Test Bank", acct_num="0000"):
    return {
        "Date": pd.Timestamp(date, tz="UTC"),
        "Category": category,
        "Amount": amount,
        "Account": account,
        "Month": month,
        "Full Description": desc,
        "Group": group,
        "Type": txn_type,
        "Institution": institution,
        "Account #": acct_num,
    }


def _df_from_rows(*rows):
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# calculate_date_range tests
# ---------------------------------------------------------------------------

class TestCalculateDateRange:

    def test_this_month(self):
        start, end = calculate_date_range("This Month")
        now = pd.Timestamp.now(tz="UTC")
        assert start.day == 1
        assert start.month == now.month
        assert start.year == now.year
        # end should be approximately now
        assert abs((end - now).total_seconds()) < 2

    def test_last_month(self):
        start, end = calculate_date_range("Last Month")
        now = pd.Timestamp.now(tz="UTC")
        first_of_this_month = now.replace(day=1)
        expected_end = first_of_this_month - timedelta(days=1)
        expected_start = expected_end.replace(day=1)
        assert start.day == 1
        assert start.month == expected_start.month
        assert end.day == expected_end.day

    def test_last_3_months(self):
        start, end = calculate_date_range("Last 3 Months")
        diff = (end - start).days
        assert abs(diff - 90) < 2

    def test_last_6_months(self):
        start, end = calculate_date_range("Last 6 Months")
        diff = (end - start).days
        assert abs(diff - 180) < 2

    def test_last_12_months(self):
        start, end = calculate_date_range("Last 12 Months")
        diff = (end - start).days
        assert abs(diff - 365) < 2

    def test_year_to_date(self):
        start, end = calculate_date_range("Year to Date")
        now = pd.Timestamp.now(tz="UTC")
        assert start.month == 1
        assert start.day == 1
        assert start.year == now.year
        assert abs((end - now).total_seconds()) < 2

    def test_all_time_with_df(self):
        df = pd.DataFrame({
            "Date": [
                pd.Timestamp("2020-03-15", tz="UTC"),
                pd.Timestamp("2023-07-01", tz="UTC"),
            ]
        })
        start, end = calculate_date_range("All Time", df=df)
        assert start == pd.Timestamp("2020-03-15", tz="UTC")
        now = pd.Timestamp.now(tz="UTC")
        assert abs((end - now).total_seconds()) < 2

    def test_all_time_without_df(self):
        start, end = calculate_date_range("All Time")
        diff = (end - start).days
        # Should default to ~5 years (1825 days)
        assert abs(diff - 365 * 5) < 2

    def test_unknown_period(self):
        start, end = calculate_date_range("Made Up Period")
        diff = (end - start).days
        # Defaults to last 3 months (90 days)
        assert abs(diff - 90) < 2


# ---------------------------------------------------------------------------
# apply_transaction_filters tests
# ---------------------------------------------------------------------------

class TestApplyTransactionFilters:

    def test_always_excludes_transfer(self, scrubbed_transactions_df):
        """Transfer group rows are always removed, even with empty filters."""
        # Add a Transfer row to the fixture data
        transfer_row = _make_row("2024-03-01", "Bank Transfer", -500.0, "Transfer", "Expense")
        df = pd.concat([scrubbed_transactions_df, pd.DataFrame([transfer_row])], ignore_index=True)
        result = apply_transaction_filters(df, {})
        assert "Transfer" not in result["Group"].values
        # All original non-Transfer rows should survive
        assert len(result) == len(scrubbed_transactions_df)

    def test_include_groups_applied(self, scrubbed_transactions_df):
        """Only rows matching include_groups remain."""
        filters = {"include_groups": ["Food"]}
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert set(result["Group"].unique()) == {"Food"}
        # Groceries + Restaurants
        assert len(result) == 2

    def test_include_groups_and_categories_union(self, scrubbed_transactions_df):
        """When both include_groups and include_categories are set, expect the
        union (OR) of rows matching either filter.  Currently the elif on
        line 222 causes include_categories to be skipped entirely."""
        filters = {
            "include_groups": ["Food"],
            "include_categories": ["Electric"],
        }
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        # Food group rows: Groceries, Restaurants  (2 rows)
        # Electric category row: 1 row (Bills group)
        # Union should give 3 rows
        assert len(result) == 3
        assert "Electric" in result["Category"].values
        assert set(result[result["Group"] == "Food"]["Category"]) == {
            "Groceries",
            "Restaurants",
        }

    def test_exclude_groups_applied(self, scrubbed_transactions_df):
        """Rows with excluded groups are removed."""
        filters = {"exclude_groups": ["Food", "Income"]}
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert "Food" not in result["Group"].values
        assert "Income" not in result["Group"].values
        # Bills (Electric, Internet) + Shopping (Amazon) = 3 rows
        assert len(result) == 3

    def test_exclude_categories_applied(self, scrubbed_transactions_df):
        """Rows with excluded categories are removed."""
        filters = {"exclude_categories": ["Electric", "Internet"]}
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert "Electric" not in result["Category"].values
        assert "Internet" not in result["Category"].values
        # 8 - 2 = 6 rows
        assert len(result) == 6

    def test_filter_large_expenses(self):
        """Expenses above the threshold are removed; income is unaffected."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Small",  -100.0, "Food",     "Expense"),
            _make_row("2024-01-02", "Big",   -5000.0, "Shopping", "Expense"),
            _make_row("2024-01-03", "Pay",    4000.0, "Income",   "Income"),
        )
        filters = {"filter_large_expenses": True, "expense_threshold": 1000}
        result = apply_transaction_filters(df, filters)
        expenses = result[result["Type"] == "Expense"]
        assert (expenses["Amount"].abs() <= 1000).all()
        # Income row untouched
        assert "Pay" in result["Category"].values

    def test_filter_large_income(self):
        """Income above the threshold is removed; expenses are unaffected."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Salary", 3000.0,  "Income", "Income"),
            _make_row("2024-01-02", "Bonus",  25000.0, "Income", "Income"),
            _make_row("2024-01-03", "Lunch",  -15.0,   "Food",   "Expense"),
        )
        filters = {"filter_large_income": True, "income_threshold": 10000}
        result = apply_transaction_filters(df, filters)
        income = result[result["Type"] == "Income"]
        assert (income["Amount"].abs() <= 10000).all()
        assert "Salary" in result["Category"].values
        assert "Bonus" not in result["Category"].values

    def test_empty_filters_dict(self, scrubbed_transactions_df):
        """An empty filter dict removes nothing (except Transfer, which isn't present)."""
        result = apply_transaction_filters(scrubbed_transactions_df, {})
        assert len(result) == len(scrubbed_transactions_df)

    def test_empty_dataframe(self, empty_transactions_df):
        """An empty DataFrame passes through without error."""
        result = apply_transaction_filters(empty_transactions_df, {})
        assert len(result) == 0
