"""Tests for src/filters.py — calculate_date_range and apply_transaction_filters."""
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
        """When both include_groups and include_categories are set, rows matching
        either filter are included (union/OR)."""
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

    def test_include_categories_only(self, scrubbed_transactions_df):
        """When only include_categories is set (no include_groups), matching rows are kept."""
        filters = {"include_categories": ["Electric", "Internet"]}
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert set(result["Category"].unique()) == {"Electric", "Internet"}
        assert len(result) == 2

    def test_empty_include_lists_fall_through_to_excludes(self, scrubbed_transactions_df):
        """Empty include lists are falsy and should fall through to exclude logic."""
        filters = {
            "include_groups": [],
            "include_categories": [],
            "exclude_groups": ["Food"],
        }
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert "Food" not in result["Group"].values

    def test_empty_dataframe(self, empty_transactions_df):
        """An empty DataFrame passes through without error."""
        result = apply_transaction_filters(empty_transactions_df, {})
        assert len(result) == 0

    def test_nan_group_kept_after_transfer_exclusion(self):
        """NaN in Group: 'Group != Transfer' is True for NaN, so NaN-group rows survive."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Groceries", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", "Mystery", -25.0, None, "Expense"),
        )
        # Set the Group to actual NaN (not the string "None")
        df.loc[1, "Group"] = float('nan')
        result = apply_transaction_filters(df, {})
        # NaN != "Transfer" evaluates to True, so the row is kept
        assert len(result) == 2

    def test_nan_type_bypasses_large_expense_filter(self):
        """NaN in Type: 'Type != Expense' is True for NaN, so the large-expense filter
        doesn't apply and the row is kept regardless of amount."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Normal", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", "BigMystery", -99999.0, "Food", None),
        )
        df.loc[1, "Type"] = float('nan')
        filters = {"filter_large_expenses": True, "expense_threshold": 1000}
        result = apply_transaction_filters(df, filters)
        # NaN Type != "Expense" is True, so the OR short-circuits and the row is kept
        assert "BigMystery" in result["Category"].values

    def test_nan_amount_with_large_expense_filter(self):
        """NaN in Amount: abs(NaN) is NaN, and NaN <= threshold is False,
        but Type != 'Expense' is False, so the whole condition is False and the row is dropped."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Normal", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", "NanAmount", float('nan'), "Food", "Expense"),
        )
        filters = {"filter_large_expenses": True, "expense_threshold": 1000}
        result = apply_transaction_filters(df, filters)
        # NaN amount: (Type != "Expense") is False, abs(NaN) <= 1000 is False => row dropped
        assert "NanAmount" not in result["Category"].values
        assert len(result) == 1

    def test_nan_category_excluded_by_include_filter(self):
        """NaN category is not in any include list, so it's excluded by include_categories."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Groceries", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", None, -25.0, "Food", "Expense"),
        )
        df.loc[1, "Category"] = float('nan')
        filters = {"include_categories": ["Groceries"]}
        result = apply_transaction_filters(df, filters)
        assert len(result) == 1

    def test_both_large_income_and_expense_filters(self):
        """Both income and expense threshold filters applied simultaneously."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Salary", 3000.0, "Income", "Income"),
            _make_row("2024-01-02", "Bonus", 25000.0, "Income", "Income"),
            _make_row("2024-01-03", "Groceries", -100.0, "Food", "Expense"),
            _make_row("2024-01-04", "Car", -8000.0, "Transport", "Expense"),
        )
        filters = {
            "filter_large_income": True,
            "income_threshold": 10000,
            "filter_large_expenses": True,
            "expense_threshold": 5000,
        }
        result = apply_transaction_filters(df, filters)
        assert "Bonus" not in result["Category"].values
        assert "Car" not in result["Category"].values
        assert "Salary" in result["Category"].values
        assert "Groceries" in result["Category"].values
        assert len(result) == 2

    def test_transfer_excluded_even_in_include_groups(self):
        """Transfer group is always excluded, even if explicitly included."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Groceries", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", "Bank Xfer", -500.0, "Transfer", "Transfer"),
        )
        filters = {"include_groups": ["Food", "Transfer"]}
        result = apply_transaction_filters(df, filters)
        assert "Transfer" not in result["Group"].values
        assert len(result) == 1

    def test_include_groups_with_exclude_categories(self, scrubbed_transactions_df):
        """Include groups takes precedence — exclude_categories is ignored when includes are set."""
        filters = {
            "include_groups": ["Food"],
            "exclude_categories": ["Groceries"],
        }
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        # Include takes precedence, so Groceries is still included (it's in Food group)
        assert "Groceries" in result["Category"].values
