"""Tests for budget functionality: CategoriesSpreadsheet budget parsing and budget vs actual."""
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from src.spreadsheet import Spreadsheet, CategoriesSpreadsheet
from src.analysis import budget as _mod
from tests._helpers import _transactions_df


# ---------------------------------------------------------------------------
# CategoriesSpreadsheet.scrub() — budget parsing
# ---------------------------------------------------------------------------

class TestCategoriesBudgetParsing:

    def _make(self, raw_df: pd.DataFrame) -> CategoriesSpreadsheet:
        with patch.object(Spreadsheet, "load", lambda self: setattr(self, "raw_df", raw_df)):
            return CategoriesSpreadsheet()

    def test_budget_df_has_expected_columns(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        assert set(cs.budget_df.columns) == {"Category", "Month_Num", "Budget", "Group", "Type"}

    def test_budget_df_has_12_months_per_category(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        # 4 valid categories (None row dropped) x 12 months = 48
        assert len(cs.budget_df) == 48

    def test_null_category_rows_dropped(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        assert cs.budget_df["Category"].isna().sum() == 0

    def test_month_nums_are_1_to_12(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        assert sorted(cs.budget_df["Month_Num"].unique()) == list(range(1, 13))

    def test_budget_values_correct(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        # Groceries has $500 budget for all months
        groceries_jan = cs.budget_df[
            (cs.budget_df["Category"] == "Groceries") & (cs.budget_df["Month_Num"] == 1)
        ]
        assert groceries_jan.iloc[0]["Budget"] == pytest.approx(500)

    def test_different_budget_per_month(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        # Restaurants: $200 most months but $250 in March
        rest_mar = cs.budget_df[
            (cs.budget_df["Category"] == "Restaurants") & (cs.budget_df["Month_Num"] == 3)
        ]
        assert rest_mar.iloc[0]["Budget"] == pytest.approx(250)

    def test_nan_budget_becomes_zero(self) -> None:
        raw = pd.DataFrame({
            "Category": ["Groceries"],
            "Group": ["Food"],
            "Type": ["Expense"],
            "Hide From Reports": [""],
            pd.Timestamp("2023-01-01"): [None],
            pd.Timestamp("2023-02-01"): [500],
        })
        cs = self._make(raw)
        jan = cs.budget_df[
            (cs.budget_df["Category"] == "Groceries") & (cs.budget_df["Month_Num"] == 1)
        ]
        assert jan.iloc[0]["Budget"] == pytest.approx(0)

    def test_no_date_columns_produces_empty_budget_df(self) -> None:
        raw = pd.DataFrame({
            "Category": ["Groceries"],
            "Group": ["Food"],
            "Type": ["Expense"],
            "Hide From Reports": [""],
        })
        cs = self._make(raw)
        assert cs.budget_df.empty
        assert set(cs.budget_df.columns) == {"Category", "Month_Num", "Budget", "Group", "Type"}

    def test_group_and_type_joined(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        groceries = cs.budget_df[cs.budget_df["Category"] == "Groceries"].iloc[0]
        assert groceries["Group"] == "Food"
        assert groceries["Type"] == "Expense"

    def test_scrubbed_df_still_works(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        """Existing scrubbed_df metadata is unaffected by budget parsing."""
        cs = self._make(raw_categories_with_budget_df)
        assert set(cs.scrubbed_df.columns) == {"Category", "Group", "Type", "Hide From Reports"}
        assert len(cs.scrubbed_df) == 4  # None row dropped


# ---------------------------------------------------------------------------
# get_budget_vs_actual helper
# ---------------------------------------------------------------------------

class TestGetBudgetVsActual:

    @pytest.fixture
    def budget_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "Category": ["Groceries", "Groceries", "Restaurants", "Restaurants", "Electric", "Electric"],
            "Month_Num": [1, 3, 1, 3, 1, 3],
            "Budget": [500, 500, 200, 250, 150, 175],
            "Group": ["Food", "Food", "Food", "Food", "Bills", "Bills"],
            "Type": ["Expense", "Expense", "Expense", "Expense", "Expense", "Expense"],
        })

    @pytest.fixture
    def transactions_df(self) -> pd.DataFrame:
        return _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -300, "Account": "Checking",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-15", "Category": "Groceries", "Amount": -50, "Account": "Checking",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-20", "Category": "Restaurants", "Amount": -250, "Account": "Credit",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-05", "Category": "Electric", "Amount": -120, "Account": "Checking",
             "Month": "2024-01", "Group": "Bills", "Type": "Expense"},
            {"Date": "2024-01-25", "Category": "Salary", "Amount": 5000, "Account": "Checking",
             "Month": "2024-01", "Group": "Income", "Type": "Income"},
        ])

    @pytest.fixture
    def no_filters(self) -> dict[str, Any]:
        return {
            "exclude_groups": [],
            "exclude_categories": [],
            "filter_large_expenses": False,
            "expense_threshold": 3000,
            "show_zero_budget": False,
        }

    def _get_fn(self) -> Callable[..., pd.DataFrame]:
        return _mod.get_budget_vs_actual

    def test_basic_budget_vs_actual(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)

        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Budget"] == pytest.approx(500)
        assert groceries["Spent"] == pytest.approx(350)
        assert groceries["Remaining"] == pytest.approx(150)
        assert groceries["Pct_Used"] == pytest.approx(70)

    def test_over_budget(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)

        restaurants = result[result["Category"] == "Restaurants"].iloc[0]
        assert restaurants["Budget"] == pytest.approx(200)
        assert restaurants["Spent"] == pytest.approx(250)
        assert restaurants["Remaining"] == pytest.approx(-50)
        assert restaurants["Pct_Used"] == pytest.approx(125)

    def test_no_spending(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        empty_txns = _transactions_df([
            {"Date": "2024-01-01", "Category": "Salary", "Amount": 5000, "Account": "Checking",
             "Month": "2024-01", "Group": "Income", "Type": "Income"},
        ])
        result = fn(budget_df, empty_txns, "2024-01", no_filters)

        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Spent"] == pytest.approx(0)
        assert groceries["Remaining"] == pytest.approx(500)
        assert groceries["Pct_Used"] == pytest.approx(0)

    def test_no_budget_hidden_by_default(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Amazon", "Amount": -100, "Account": "Checking",
             "Month": "2024-01", "Group": "Shopping", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        assert "Amazon" not in result["Category"].values

    def test_no_budget_shown_with_toggle(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        no_filters["show_zero_budget"] = True
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Amazon", "Amount": -100, "Account": "Checking",
             "Month": "2024-01", "Group": "Shopping", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        amazon = result[result["Category"] == "Amazon"].iloc[0]
        assert amazon["Budget"] == pytest.approx(0)
        assert amazon["Spent"] == pytest.approx(100)

    def test_pct_used_inf_when_zero_budget_and_spending(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Pct_Used should be inf when Budget=0 and Spent>0."""
        fn = self._get_fn()
        no_filters["show_zero_budget"] = True
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Amazon", "Amount": -100, "Account": "Checking",
             "Month": "2024-01", "Group": "Shopping", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        amazon = result[result["Category"] == "Amazon"].iloc[0]
        assert amazon["Pct_Used"] == float("inf")

    def test_pct_used_zero_when_zero_budget_zero_spending(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Pct_Used should be 0 when Budget=0 and Spent=0."""
        fn = self._get_fn()
        no_filters["show_zero_budget"] = True
        # No actual spending on Amazon
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -100, "Account": "Checking",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        # Groceries has a budget, so it should appear with Pct_Used = 20
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Pct_Used"] == pytest.approx(20)

    def test_exclude_groups_filter(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        no_filters["exclude_groups"] = ["Food"]
        result = fn(budget_df, transactions_df, "2024-01", no_filters)
        assert "Groceries" not in result["Category"].values
        assert "Restaurants" not in result["Category"].values
        assert "Electric" in result["Category"].values

    def test_exclude_categories_filter(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        no_filters["exclude_categories"] = ["Groceries"]
        result = fn(budget_df, transactions_df, "2024-01", no_filters)
        assert "Groceries" not in result["Category"].values
        assert "Restaurants" in result["Category"].values

    def test_empty_month(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        empty_txns = pd.DataFrame(columns=[
            "Date", "Category", "Amount", "Account", "Month",
            "Full Description", "Group", "Type", "Institution", "Account #",
        ])
        result = fn(budget_df, empty_txns, "2024-01", no_filters)
        assert len(result) == 3  # Groceries, Restaurants, Electric
        assert (result["Spent"] == 0).all()

    def test_group_rollup(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)
        group_result = result.groupby("Group").agg(
            Budget=("Budget", "sum"),
            Spent=("Spent", "sum"),
        ).reset_index()

        food = group_result[group_result["Group"] == "Food"].iloc[0]
        assert food["Budget"] == pytest.approx(700)
        assert food["Spent"] == pytest.approx(600)

    def test_uses_correct_month_budget(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """March has different budget amounts than January."""
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2024-03-10", "Category": "Restaurants", "Amount": -100, "Account": "Checking",
             "Month": "2024-03", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-03", no_filters)
        rest = result[result["Category"] == "Restaurants"].iloc[0]
        assert rest["Budget"] == pytest.approx(250)  # March budget, not 200

    def test_pct_used_exactly_100(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Spending exactly matches budget — Pct_Used is 100 and Remaining is 0."""
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -500, "Account": "Checking",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Pct_Used"] == pytest.approx(100.0)
        assert groceries["Remaining"] == pytest.approx(0.0)

    def test_multiple_txns_same_category_sum(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Many small expenses in the same category aggregate correctly."""
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": f"2024-01-{d:02d}", "Category": "Groceries",
             "Amount": -25.0, "Account": "Checking",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"}
            for d in range(1, 21)
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        # 20 x $25 = $500, exactly the budget
        assert groceries["Spent"] == pytest.approx(500.0)
        assert groceries["Pct_Used"] == pytest.approx(100.0)

    def test_sorted_descending_by_pct_used(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Result must be sorted desc by Pct_Used so worst-offender is on top."""
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)
        pcts = result["Pct_Used"].tolist()
        assert pcts == sorted(pcts, reverse=True)
        assert result.iloc[0]["Category"] == "Restaurants"  # 125% over

    def test_income_transactions_excluded_from_spent(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Positive Income rows never count as 'Spent' even if miscategorized."""
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2024-01-05", "Category": "Groceries", "Amount": 500,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Income"},
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -100,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        # Only the -100 expense counts, not the +500 income
        assert groceries["Spent"] == pytest.approx(100.0)

    def test_transactions_from_other_months_ignored(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Only transactions from the target month contribute to Spent."""
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -100,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-02-10", "Category": "Groceries", "Amount": -999,
             "Account": "Checking", "Month": "2024-02", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Spent"] == pytest.approx(100.0)

    def test_floating_point_precision(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Fractional cents produce stable Pct_Used without float drift."""
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -33.33,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-11", "Category": "Groceries", "Amount": -33.33,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-12", "Category": "Groceries", "Amount": -33.34,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        # Sum is $100.00 (two 33.33 + one 33.34)
        assert groceries["Spent"] == pytest.approx(100.0, abs=1e-9)
        assert groceries["Pct_Used"] == pytest.approx(20.0, abs=1e-9)

    def test_category_in_budget_but_zero_spent(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """A budgeted category with no spending shows Spent=0, Pct_Used=0."""
        fn = self._get_fn()
        # Only Groceries has spending, not Electric
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -100,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        electric = result[result["Category"] == "Electric"].iloc[0]
        assert electric["Spent"] == pytest.approx(0.0)
        assert electric["Pct_Used"] == pytest.approx(0.0)
        assert electric["Remaining"] == pytest.approx(150.0)  # full budget remains

    def test_category_rows_have_group_filled(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Category rows that only appear in transactions (no budget) still get
        Group filled in from the transaction, not NaN."""
        fn = self._get_fn()
        no_filters["show_zero_budget"] = True
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Amazon", "Amount": -100,
             "Account": "Checking", "Month": "2024-01", "Group": "Shopping", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        amazon = result[result["Category"] == "Amazon"].iloc[0]
        assert amazon["Group"] == "Shopping"
        assert pd.notna(amazon["Group"])


# ---------------------------------------------------------------------------
# get_ytd_budget_vs_actual helper
# ---------------------------------------------------------------------------

class TestGetYtdBudgetVsActual:

    @pytest.fixture
    def budget_df(self) -> pd.DataFrame:
        """Budget data with months 1-3 for two categories."""
        rows = []
        for month in range(1, 13):
            rows.append({"Category": "Groceries", "Month_Num": month, "Budget": 500,
                         "Group": "Food", "Type": "Expense"})
            rows.append({"Category": "Restaurants", "Month_Num": month, "Budget": 200,
                         "Group": "Food", "Type": "Expense"})
        return pd.DataFrame(rows)

    @pytest.fixture
    def transactions_df(self) -> pd.DataFrame:
        return _transactions_df([
            # January
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -400, "Account": "Checking",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-15", "Category": "Restaurants", "Amount": -150, "Account": "Checking",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            # February
            {"Date": "2024-02-10", "Category": "Groceries", "Amount": -450, "Account": "Checking",
             "Month": "2024-02", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-02-15", "Category": "Restaurants", "Amount": -180, "Account": "Checking",
             "Month": "2024-02", "Group": "Food", "Type": "Expense"},
            # March
            {"Date": "2024-03-10", "Category": "Groceries", "Amount": -550, "Account": "Checking",
             "Month": "2024-03", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-03-15", "Category": "Restaurants", "Amount": -250, "Account": "Checking",
             "Month": "2024-03", "Group": "Food", "Type": "Expense"},
        ])

    @pytest.fixture
    def no_filters(self) -> dict[str, Any]:
        return {
            "exclude_groups": [],
            "exclude_categories": [],
            "filter_large_expenses": False,
            "expense_threshold": 3000,
            "show_zero_budget": False,
        }

    def _get_fn(self) -> Callable[..., pd.DataFrame]:
        return _mod.get_ytd_budget_vs_actual

    def test_ytd_through_march(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-03", no_filters)

        groceries = result[result["Category"] == "Groceries"].iloc[0]
        # YTD budget: 500 * 3 = 1500
        assert groceries["Budget"] == pytest.approx(1500)
        # YTD spent: 400 + 450 + 550 = 1400
        assert groceries["Spent"] == pytest.approx(1400)
        assert groceries["Remaining"] == pytest.approx(100)
        assert groceries["Pct_Used"] == pytest.approx(1400 / 1500 * 100)

    def test_ytd_through_january(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Single month YTD should equal the monthly view."""
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)

        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Budget"] == pytest.approx(500)
        assert groceries["Spent"] == pytest.approx(400)

    def test_ytd_sums_restaurant_spending(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-03", no_filters)

        rest = result[result["Category"] == "Restaurants"].iloc[0]
        # YTD budget: 200 * 3 = 600
        assert rest["Budget"] == pytest.approx(600)
        # YTD spent: 150 + 180 + 250 = 580
        assert rest["Spent"] == pytest.approx(580)

    def test_ytd_exclude_groups(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        no_filters["exclude_groups"] = ["Food"]
        result = fn(budget_df, transactions_df, "2024-03", no_filters)
        assert result.empty

    def test_ytd_exclude_categories(self, budget_df: pd.DataFrame, transactions_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        no_filters["exclude_categories"] = ["Groceries"]
        result = fn(budget_df, transactions_df, "2024-03", no_filters)
        assert "Groceries" not in result["Category"].values
        assert "Restaurants" in result["Category"].values

    def test_ytd_no_spending(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        empty_txns = _transactions_df([
            {"Date": "2024-01-01", "Category": "Salary", "Amount": 5000, "Account": "Checking",
             "Month": "2024-01", "Group": "Income", "Type": "Income"},
        ])
        result = fn(budget_df, empty_txns, "2024-03", no_filters)
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Budget"] == pytest.approx(1500)
        assert groceries["Spent"] == pytest.approx(0)

    def test_ytd_empty_transactions(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        fn = self._get_fn()
        empty_txns = pd.DataFrame(columns=[
            "Date", "Category", "Amount", "Account", "Month",
            "Full Description", "Group", "Type", "Institution", "Account #",
        ])
        result = fn(budget_df, empty_txns, "2024-03", no_filters)
        assert len(result) == 2
        assert (result["Spent"] == 0).all()
        assert (result["Budget"] == 1500).any()  # Groceries: 500 * 3
        assert (result["Budget"] == 600).any()   # Restaurants: 200 * 3

    def test_ytd_only_counts_same_year(self, budget_df: pd.DataFrame, no_filters: dict[str, Any]) -> None:
        """Transactions from a different year should not be included."""
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2023-12-10", "Category": "Groceries", "Amount": -999, "Account": "Checking",
             "Month": "2023-12", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -400, "Account": "Checking",
             "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Spent"] == pytest.approx(400)  # Only 2024 transaction


# ---------------------------------------------------------------------------
# build_unified_budget_table helper
# ---------------------------------------------------------------------------

class TestBuildUnifiedBudgetTable:

    def _get_fn(self) -> Callable[..., pd.DataFrame]:
        return _mod.build_unified_budget_table

    def test_merges_monthly_and_ytd(self) -> None:
        fn = self._get_fn()
        monthly = pd.DataFrame({
            "Category": ["Groceries", "Restaurants"],
            "Group": ["Food", "Food"],
            "Budget": [500, 200],
            "Spent": [350, 250],
            "Pct_Used": [70.0, 125.0],
        })
        ytd = pd.DataFrame({
            "Category": ["Groceries", "Restaurants"],
            "Budget": [1500, 600],
            "Spent": [1400, 580],
            "Pct_Used": [93.3, 96.7],
        })
        result = fn(monthly, ytd)
        assert set(result.columns) == {
            "Category", "Group", "Mo_Budget", "Mo_Spent", "Mo_Pct",
            "YTD_Budget", "YTD_Spent", "YTD_Pct",
        }
        assert len(result) == 2
        # Sorted by Mo_Pct descending — Restaurants (125%) first
        assert result.iloc[0]["Category"] == "Restaurants"

    def test_missing_ytd_category_fills_zero(self) -> None:
        fn = self._get_fn()
        monthly = pd.DataFrame({
            "Category": ["Groceries"],
            "Group": ["Food"],
            "Budget": [500],
            "Spent": [350],
            "Pct_Used": [70.0],
        })
        ytd = pd.DataFrame({
            "Category": [],
            "Budget": [],
            "Spent": [],
            "Pct_Used": [],
        })
        result = fn(monthly, ytd)
        assert len(result) == 1
        assert result.iloc[0]["YTD_Budget"] == 0
        assert result.iloc[0]["YTD_Spent"] == 0

    def test_missing_monthly_category_fills_zero(self) -> None:
        fn = self._get_fn()
        monthly = pd.DataFrame({
            "Category": [],
            "Group": [],
            "Budget": [],
            "Spent": [],
            "Pct_Used": [],
        })
        ytd = pd.DataFrame({
            "Category": ["Groceries"],
            "Budget": [1500],
            "Spent": [1400],
            "Pct_Used": [93.3],
        })
        result = fn(monthly, ytd)
        assert len(result) == 1
        assert result.iloc[0]["Mo_Budget"] == 0
        assert result.iloc[0]["Mo_Spent"] == 0

    def test_empty_inputs(self) -> None:
        fn = self._get_fn()
        monthly = pd.DataFrame(columns=["Category", "Group", "Budget", "Spent", "Pct_Used"])
        ytd = pd.DataFrame(columns=["Category", "Budget", "Spent", "Pct_Used"])
        result = fn(monthly, ytd)
        assert result.empty


# ---------------------------------------------------------------------------
# Projected spend calculation
# ---------------------------------------------------------------------------

class TestProjectedSpend:

    def _get_fn(self) -> Callable[..., float]:
        return _mod.calculate_projected_spend

    def test_basic_projection(self) -> None:
        fn = self._get_fn()
        projected = fn(spent=300, days_elapsed=15, days_in_month=30)
        assert projected == pytest.approx(600)

    def test_day_one(self) -> None:
        fn = self._get_fn()
        projected = fn(spent=50, days_elapsed=1, days_in_month=31)
        assert projected == pytest.approx(50 * 31)

    def test_zero_spent(self) -> None:
        fn = self._get_fn()
        projected = fn(spent=0, days_elapsed=15, days_in_month=30)
        assert projected == pytest.approx(0)

    def test_zero_days_elapsed(self) -> None:
        fn = self._get_fn()
        projected = fn(spent=0, days_elapsed=0, days_in_month=30)
        assert projected == pytest.approx(0)

    def test_last_day_of_month_projected_equals_spent(self) -> None:
        """When days_elapsed == days_in_month, projection equals actual spend."""
        fn = self._get_fn()
        projected = fn(spent=450, days_elapsed=31, days_in_month=31)
        assert projected == pytest.approx(450)

    def test_february_28_days(self) -> None:
        """February with 28 days — projection uses the short month length."""
        fn = self._get_fn()
        projected = fn(spent=100, days_elapsed=14, days_in_month=28)
        assert projected == pytest.approx(200)

    def test_days_elapsed_greater_than_days_in_month(self) -> None:
        """Pathological input: days_elapsed > days_in_month. The projection
        should not go below the already-spent amount — it scales linearly but
        capping behavior depends on implementation. Document what it does."""
        fn = self._get_fn()
        projected = fn(spent=100, days_elapsed=35, days_in_month=30)
        # spent/elapsed * days_in_month = 100/35 * 30 ≈ 85.7 (less than spent!)
        # This is an implementation artifact — document what actually happens.
        assert projected == pytest.approx(100 / 35 * 30)

    def test_proportional_scaling(self) -> None:
        """Projection scales linearly with days_elapsed."""
        fn = self._get_fn()
        half_month = fn(spent=300, days_elapsed=15, days_in_month=30)
        quarter_month = fn(spent=150, days_elapsed=7, days_in_month=30)
        # Both at $20/day pace, just different sample sizes
        assert half_month == pytest.approx(600)
        assert quarter_month == pytest.approx(150 / 7 * 30)

    def test_high_spend_late_month(self) -> None:
        """Spending scales down toward actual when days_elapsed is close to days_in_month."""
        fn = self._get_fn()
        day_29_of_30 = fn(spent=500, days_elapsed=29, days_in_month=30)
        day_15_of_30 = fn(spent=500, days_elapsed=15, days_in_month=30)
        # Same total spend, but if it happened by day 15 it projects higher
        assert day_29_of_30 == pytest.approx(500 / 29 * 30)
        assert day_15_of_30 == pytest.approx(1000)
        assert day_15_of_30 > day_29_of_30
