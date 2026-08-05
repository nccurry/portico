"""Tests for src/filters.py — calculate_date_range and apply_transaction_filters."""
import pandas as pd
from datetime import timedelta
from unittest.mock import MagicMock, patch

from src.custom_types import TransactionFilterOptions
from src.filters import (
    apply_transaction_filters,
    calculate_date_range,
    default_fi_accounts,
    render_fi_filters,
    render_income_expense_filters,
    render_spending_filters,
)
from tests._helpers import _df_from_rows, _make_row


# ---------------------------------------------------------------------------
# calculate_date_range tests
# ---------------------------------------------------------------------------

class TestCalculateDateRange:

    def test_this_month(self) -> None:
        start, end = calculate_date_range("This Month")
        now = pd.Timestamp.now(tz="UTC")
        assert start.day == 1
        assert start.month == now.month
        assert start.year == now.year
        # end should be approximately now
        assert abs((end - now).total_seconds()) < 2

    def test_last_month(self) -> None:
        start, end = calculate_date_range("Last Month")
        now = pd.Timestamp.now(tz="UTC")
        first_of_this_month = now.replace(day=1)
        expected_end = first_of_this_month - timedelta(days=1)
        expected_start = expected_end.replace(day=1)
        assert start.day == 1
        assert start.month == expected_start.month
        assert end.day == expected_end.day

    def test_last_3_months(self) -> None:
        start, end = calculate_date_range("Last 3 Months")
        assert start == end - pd.DateOffset(months=3)

    def test_last_6_months(self) -> None:
        start, end = calculate_date_range("Last 6 Months")
        assert start == end - pd.DateOffset(months=6)

    def test_last_12_months(self) -> None:
        start, end = calculate_date_range("Last 12 Months")
        assert start == end - pd.DateOffset(months=12)

    def test_year_to_date(self) -> None:
        start, end = calculate_date_range("Year to Date")
        now = pd.Timestamp.now(tz="UTC")
        assert start.month == 1
        assert start.day == 1
        assert start.year == now.year
        assert abs((end - now).total_seconds()) < 2

    def test_all_time_with_df(self) -> None:
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

    def test_all_time_without_df(self) -> None:
        start, end = calculate_date_range("All Time")
        assert start == end - pd.DateOffset(years=5)

    def test_unknown_period(self) -> None:
        start, end = calculate_date_range("Made Up Period")
        assert start == end - pd.DateOffset(months=3)


# ---------------------------------------------------------------------------
# apply_transaction_filters tests
# ---------------------------------------------------------------------------

class TestApplyTransactionFilters:

    def test_always_excludes_transfer(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """Transfer group rows are always removed, even with empty filters."""
        # Add a Transfer row to the fixture data
        transfer_row = _make_row("2024-03-01", "Bank Transfer", -500.0, "Transfer", "Expense")
        df = pd.concat([scrubbed_transactions_df, pd.DataFrame([transfer_row])], ignore_index=True)
        result = apply_transaction_filters(df, {})
        assert "Transfer" not in result["Group"].values
        # All original non-Transfer rows should survive
        assert len(result) == len(scrubbed_transactions_df)

    def test_include_groups_applied(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """Only rows matching include_groups remain."""
        filters: TransactionFilterOptions = {"include_groups": ["Food"]}
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert set(result["Group"].unique()) == {"Food"}
        # Groceries + Restaurants
        assert len(result) == 2

    def test_include_groups_and_categories_union(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """When both include_groups and include_categories are set, rows matching
        either filter are included (union/OR)."""
        filters: TransactionFilterOptions = {
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

    def test_exclude_groups_applied(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """Rows with excluded groups are removed."""
        filters: TransactionFilterOptions = {"exclude_groups": ["Food", "Income"]}
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert "Food" not in result["Group"].values
        assert "Income" not in result["Group"].values
        # Bills (Electric, Internet) + Shopping (Amazon) = 3 rows
        assert len(result) == 3

    def test_exclude_categories_applied(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """Rows with excluded categories are removed."""
        filters: TransactionFilterOptions = {"exclude_categories": ["Electric", "Internet"]}
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert "Electric" not in result["Category"].values
        assert "Internet" not in result["Category"].values
        # 8 - 2 = 6 rows
        assert len(result) == 6

    def test_filter_large_expenses(self) -> None:
        """Expenses above the threshold are removed; income is unaffected."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Small",  -100.0, "Food",     "Expense"),
            _make_row("2024-01-02", "Big",   -5000.0, "Shopping", "Expense"),
            _make_row("2024-01-03", "Pay",    4000.0, "Income",   "Income"),
        )
        filters: TransactionFilterOptions = {"filter_large_expenses": True, "expense_threshold": 1000}
        result = apply_transaction_filters(df, filters)
        expenses = result[result["Type"] == "Expense"]
        assert (expenses["Amount"].abs() <= 1000).all()
        # Income row untouched
        assert "Pay" in result["Category"].values

    def test_filter_large_income(self) -> None:
        """Income above the threshold is removed; expenses are unaffected."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Salary", 3000.0,  "Income", "Income"),
            _make_row("2024-01-02", "Bonus",  25000.0, "Income", "Income"),
            _make_row("2024-01-03", "Lunch",  -15.0,   "Food",   "Expense"),
        )
        filters: TransactionFilterOptions = {"filter_large_income": True, "income_threshold": 10000}
        result = apply_transaction_filters(df, filters)
        income = result[result["Type"] == "Income"]
        assert (income["Amount"].abs() <= 10000).all()
        assert "Salary" in result["Category"].values
        assert "Bonus" not in result["Category"].values

    def test_empty_filters_dict(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """An empty filter dict removes nothing (except Transfer, which isn't present)."""
        result = apply_transaction_filters(scrubbed_transactions_df, {})
        assert len(result) == len(scrubbed_transactions_df)

    def test_include_categories_only(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """When only include_categories is set (no include_groups), matching rows are kept."""
        filters: TransactionFilterOptions = {"include_categories": ["Electric", "Internet"]}
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert set(result["Category"].unique()) == {"Electric", "Internet"}
        assert len(result) == 2

    def test_empty_include_lists_fall_through_to_excludes(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """Empty include lists are falsy and should fall through to exclude logic."""
        filters: TransactionFilterOptions = {
            "include_groups": [],
            "include_categories": [],
            "exclude_groups": ["Food"],
        }
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        assert "Food" not in result["Group"].values

    def test_empty_dataframe(self, empty_transactions_df: pd.DataFrame) -> None:
        """An empty DataFrame passes through without error."""
        result = apply_transaction_filters(empty_transactions_df, {})
        assert len(result) == 0

    def test_nan_group_kept_after_transfer_exclusion(self) -> None:
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

    def test_nan_type_bypasses_large_expense_filter(self) -> None:
        """NaN in Type: 'Type != Expense' is True for NaN, so the large-expense filter
        doesn't apply and the row is kept regardless of amount."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Normal", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", "BigMystery", -99999.0, "Food", None),
        )
        df.loc[1, "Type"] = float('nan')
        filters: TransactionFilterOptions = {"filter_large_expenses": True, "expense_threshold": 1000}
        result = apply_transaction_filters(df, filters)
        # NaN Type != "Expense" is True, so the OR short-circuits and the row is kept
        assert "BigMystery" in result["Category"].values

    def test_nan_amount_with_large_expense_filter(self) -> None:
        """NaN in Amount: abs(NaN) is NaN, and NaN <= threshold is False,
        but Type != 'Expense' is False, so the whole condition is False and the row is dropped."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Normal", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", "NanAmount", float('nan'), "Food", "Expense"),
        )
        filters: TransactionFilterOptions = {"filter_large_expenses": True, "expense_threshold": 1000}
        result = apply_transaction_filters(df, filters)
        # NaN amount: (Type != "Expense") is False, abs(NaN) <= 1000 is False => row dropped
        assert "NanAmount" not in result["Category"].values
        assert len(result) == 1

    def test_nan_category_excluded_by_include_filter(self) -> None:
        """NaN category is not in any include list, so it's excluded by include_categories."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Groceries", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", None, -25.0, "Food", "Expense"),
        )
        df.loc[1, "Category"] = float('nan')
        filters: TransactionFilterOptions = {"include_categories": ["Groceries"]}
        result = apply_transaction_filters(df, filters)
        assert len(result) == 1

    def test_both_large_income_and_expense_filters(self) -> None:
        """Both income and expense threshold filters applied simultaneously."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Salary", 3000.0, "Income", "Income"),
            _make_row("2024-01-02", "Bonus", 25000.0, "Income", "Income"),
            _make_row("2024-01-03", "Groceries", -100.0, "Food", "Expense"),
            _make_row("2024-01-04", "Car", -8000.0, "Transport", "Expense"),
        )
        filters: TransactionFilterOptions = {
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

    def test_transfer_excluded_even_in_include_groups(self) -> None:
        """Transfer group is always excluded, even if explicitly included."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Groceries", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", "Bank Xfer", -500.0, "Transfer", "Transfer"),
        )
        filters: TransactionFilterOptions = {"include_groups": ["Food", "Transfer"]}
        result = apply_transaction_filters(df, filters)
        assert "Transfer" not in result["Group"].values
        assert len(result) == 1

    def test_include_groups_with_exclude_categories(self, scrubbed_transactions_df: pd.DataFrame) -> None:
        """Include groups takes precedence — exclude_categories is ignored when includes are set."""
        filters: TransactionFilterOptions = {
            "include_groups": ["Food"],
            "exclude_categories": ["Groceries"],
        }
        result = apply_transaction_filters(scrubbed_transactions_df, filters)
        # Include takes precedence, so Groceries is still included (it's in Food group)
        assert "Groceries" in result["Category"].values

    def test_expense_threshold_exactly_equal_kept(self) -> None:
        """An expense exactly equal to the threshold is kept (uses <=, not <)."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Rent", -1000.0, "Bills", "Expense"),
        )
        filters: TransactionFilterOptions = {"filter_large_expenses": True, "expense_threshold": 1000}
        result = apply_transaction_filters(df, filters)
        assert "Rent" in result["Category"].values

    def test_expense_threshold_just_above_dropped(self) -> None:
        """An expense $0.01 above threshold is dropped."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Rent", -1000.01, "Bills", "Expense"),
        )
        filters: TransactionFilterOptions = {"filter_large_expenses": True, "expense_threshold": 1000}
        result = apply_transaction_filters(df, filters)
        assert result.empty

    def test_missing_threshold_uses_default(self) -> None:
        """filter_large_expenses=True without an explicit threshold uses the default."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Normal", -50.0, "Food", "Expense"),
        )
        filters: TransactionFilterOptions = {"filter_large_expenses": True}
        # Should not raise, should use DEFAULT_EXPENSE_THRESHOLD
        result = apply_transaction_filters(df, filters)
        assert "Normal" in result["Category"].values

    def test_filter_large_expenses_false_ignores_threshold(self) -> None:
        """When the flag is False, threshold is irrelevant and all expenses pass."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Big", -99999.0, "Food", "Expense"),
        )
        filters: TransactionFilterOptions = {"filter_large_expenses": False, "expense_threshold": 100}
        result = apply_transaction_filters(df, filters)
        assert "Big" in result["Category"].values

    def test_include_with_empty_lists_acts_like_no_include(self) -> None:
        """Empty include_groups AND empty include_categories falls through to excludes."""
        df = _df_from_rows(
            _make_row("2024-01-01", "A", -50.0, "Food", "Expense"),
            _make_row("2024-01-02", "B", -100.0, "Bills", "Expense"),
        )
        filters: TransactionFilterOptions = {
            "include_groups": [],
            "include_categories": [],
            "exclude_groups": ["Food"],
        }
        result = apply_transaction_filters(df, filters)
        # Food excluded, Bills kept
        assert len(result) == 1
        assert result.iloc[0]["Group"] == "Bills"

    def test_nan_amount_with_large_income_filter(self) -> None:
        """NaN Amount with income filter: Type != 'Income' is False (Type is Income),
        abs(NaN) <= threshold is False → row dropped."""
        df = _df_from_rows(
            _make_row("2024-01-01", "Pay", 3000.0, "Income", "Income"),
            _make_row("2024-01-02", "NanPay", float('nan'), "Income", "Income"),
        )
        filters: TransactionFilterOptions = {"filter_large_income": True, "income_threshold": 10000}
        result = apply_transaction_filters(df, filters)
        assert "NanPay" not in result["Category"].values


class TestDefaultFiAccounts:
    """default_fi_accounts drives the FI page's include_accounts default."""

    def test_matches_substring_case_insensitive(self) -> None:
        all_accounts = ["401k Fidelity", "Roth IRA Vanguard", "Joe Checking", "Brokerage Individual"]
        # "Individual" pattern should match "Brokerage Individual"
        result = default_fi_accounts(all_accounts, all_savings_accounts=[])
        assert "Brokerage Individual" in result
        assert "Joe Checking" not in result

    def test_unions_savings_accounts(self) -> None:
        all_accounts = ["Joe Checking", "Ally Savings", "HSA Fidelity"]
        result = default_fi_accounts(all_accounts, all_savings_accounts=["Ally Savings"])
        assert "Ally Savings" in result
        assert "HSA Fidelity" in result
        assert "Joe Checking" not in result

    def test_preserves_input_order(self) -> None:
        all_accounts = ["ZZZ Savings", "AAA HSA"]
        result = default_fi_accounts(all_accounts, all_savings_accounts=["ZZZ Savings"])
        assert result == ["ZZZ Savings", "AAA HSA"]

    def test_no_matches_returns_empty(self) -> None:
        assert default_fi_accounts(["Joe Checking"], all_savings_accounts=[]) == []


def _mock_filter_widgets(mock_st: MagicMock) -> None:
    """Make Streamlit widgets return their configured defaults."""
    mock_st.columns.return_value = [MagicMock(), MagicMock()]
    mock_st.multiselect.side_effect = lambda *args, **kwargs: list(kwargs["default"])
    mock_st.checkbox.side_effect = lambda *args, **kwargs: kwargs["value"]
    mock_st.number_input.side_effect = lambda *args, **kwargs: kwargs["value"]
    mock_st.selectbox.side_effect = (
        lambda *args, **kwargs: kwargs["options"][kwargs["index"]]
    )


class TestPageFilterDefaults:
    def test_income_defaults_to_dependable_income_and_routine_expenses(self) -> None:
        categories = [
            "Paycheck",
            "401k",
            "HSA",
            "Tax Return Refund",
            "Investment",
            "Credit Card Rewards",
            "RSU",
            "ESPP",
            "Bonus",
            "Received Gift",
            "Tax Return Payment",
            "Christmas",
            "Home Repairs",
            "Automobile Repairs",
            "Home Improvements",
            "Misc Maintainence",
            "Groceries",
        ]
        with patch("src.filters.st") as mock_st:
            _mock_filter_widgets(mock_st)
            result = render_income_expense_filters(
                categories,
                ["Bills", "Food", "Travel", "Donations"],
            )

        assert result["exclude_groups"] == ["Travel", "Donations"]
        assert set(result["exclude_categories"]) == set(categories) - {
            "Paycheck",
            "401k",
            "HSA",
            "Groceries",
        }
        assert result["filter_large_income"] is False
        assert result["filter_large_expenses"] is False

    def test_spending_defaults_to_discretionary_groups(self) -> None:
        with patch("src.filters.st") as mock_st:
            _mock_filter_widgets(mock_st)
            result = render_spending_filters(
                ["Christmas", "Misc Shopping", "Groceries"],
                ["Bills", "Income", "Donations", "Maintenance", "Travel", "Food", "Shopping"],
            )

        assert result["exclude_groups"] == [
            "Bills",
            "Income",
            "Donations",
            "Maintenance",
            "Travel",
        ]
        assert result["exclude_categories"] == ["Christmas"]
        assert result["filter_large_expenses"] is False

    def test_fi_defaults_to_unfiltered_actual_spending(self) -> None:
        with patch("src.filters.st") as mock_st:
            _mock_filter_widgets(mock_st)
            result = render_fi_filters(
                ["Checking", "Savings", "Individual"],
                ["Misc Travel", "Given Gift", "Tax Return Payment", "Home Improvements"],
                ["Bills", "Donations", "Income", "Maintenance", "Travel"],
                ["Savings"],
            )

        assert result["include_accounts"] == ["Savings", "Individual"]
        assert result["exclude_groups"] == []
        assert result["exclude_categories"] == []
        assert result["filter_large_expenses"] is False
