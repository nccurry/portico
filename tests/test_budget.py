"""Tests for budget functionality: CategoriesSpreadsheet budget parsing and budget vs actual."""
import pytest
import pandas as pd
from unittest.mock import patch
from importlib import import_module

from src.spreadsheet import Spreadsheet, CategoriesSpreadsheet

_mod = import_module('Pages.7_Budget')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(date_str: str) -> pd.Timestamp:
    return pd.Timestamp(date_str, tz="UTC")


def _transactions_df(rows):
    """Build a minimal scrubbed transactions DataFrame."""
    defaults = {"Full Description": "", "Institution": "", "Account #": ""}
    records = [{**defaults, **r} for r in rows]
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    df["Amount"] = df["Amount"].astype(float)
    return df


# ---------------------------------------------------------------------------
# CategoriesSpreadsheet.scrub() — budget parsing
# ---------------------------------------------------------------------------

class TestCategoriesBudgetParsing:

    def _make(self, raw_df):
        with patch.object(Spreadsheet, "load", lambda self: setattr(self, "raw_df", raw_df)):
            return CategoriesSpreadsheet()

    def test_budget_df_has_expected_columns(self, raw_categories_with_budget_df):
        cs = self._make(raw_categories_with_budget_df)
        assert set(cs.budget_df.columns) == {"Category", "Month_Num", "Budget", "Group", "Type"}

    def test_budget_df_has_12_months_per_category(self, raw_categories_with_budget_df):
        cs = self._make(raw_categories_with_budget_df)
        # 4 valid categories (None row dropped) x 12 months = 48
        assert len(cs.budget_df) == 48

    def test_null_category_rows_dropped(self, raw_categories_with_budget_df):
        cs = self._make(raw_categories_with_budget_df)
        assert cs.budget_df["Category"].isna().sum() == 0

    def test_month_nums_are_1_to_12(self, raw_categories_with_budget_df):
        cs = self._make(raw_categories_with_budget_df)
        assert sorted(cs.budget_df["Month_Num"].unique()) == list(range(1, 13))

    def test_budget_values_correct(self, raw_categories_with_budget_df):
        cs = self._make(raw_categories_with_budget_df)
        # Groceries has $500 budget for all months
        groceries_jan = cs.budget_df[
            (cs.budget_df["Category"] == "Groceries") & (cs.budget_df["Month_Num"] == 1)
        ]
        assert groceries_jan.iloc[0]["Budget"] == pytest.approx(500)

    def test_different_budget_per_month(self, raw_categories_with_budget_df):
        cs = self._make(raw_categories_with_budget_df)
        # Restaurants: $200 most months but $250 in March
        rest_mar = cs.budget_df[
            (cs.budget_df["Category"] == "Restaurants") & (cs.budget_df["Month_Num"] == 3)
        ]
        assert rest_mar.iloc[0]["Budget"] == pytest.approx(250)

    def test_nan_budget_becomes_zero(self):
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

    def test_no_date_columns_produces_empty_budget_df(self):
        raw = pd.DataFrame({
            "Category": ["Groceries"],
            "Group": ["Food"],
            "Type": ["Expense"],
            "Hide From Reports": [""],
        })
        cs = self._make(raw)
        assert cs.budget_df.empty
        assert set(cs.budget_df.columns) == {"Category", "Month_Num", "Budget", "Group", "Type"}

    def test_group_and_type_joined(self, raw_categories_with_budget_df):
        cs = self._make(raw_categories_with_budget_df)
        groceries = cs.budget_df[cs.budget_df["Category"] == "Groceries"].iloc[0]
        assert groceries["Group"] == "Food"
        assert groceries["Type"] == "Expense"

    def test_scrubbed_df_still_works(self, raw_categories_with_budget_df):
        """Existing scrubbed_df metadata is unaffected by budget parsing."""
        cs = self._make(raw_categories_with_budget_df)
        assert set(cs.scrubbed_df.columns) == {"Category", "Group", "Type", "Hide From Reports"}
        assert len(cs.scrubbed_df) == 4  # None row dropped


# ---------------------------------------------------------------------------
# get_budget_vs_actual helper
# ---------------------------------------------------------------------------

class TestGetBudgetVsActual:

    @pytest.fixture
    def budget_df(self):
        return pd.DataFrame({
            "Category": ["Groceries", "Groceries", "Restaurants", "Restaurants", "Electric", "Electric"],
            "Month_Num": [1, 3, 1, 3, 1, 3],
            "Budget": [500, 500, 200, 250, 150, 175],
            "Group": ["Food", "Food", "Food", "Food", "Bills", "Bills"],
            "Type": ["Expense", "Expense", "Expense", "Expense", "Expense", "Expense"],
        })

    @pytest.fixture
    def transactions_df(self):
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
    def no_filters(self):
        return {
            "exclude_groups": [],
            "exclude_categories": [],
            "filter_large_expenses": False,
            "expense_threshold": 3000,
            "show_zero_budget": False,
        }

    def _get_fn(self):
        return _mod.get_budget_vs_actual

    def test_basic_budget_vs_actual(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)

        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Budget"] == pytest.approx(500)
        assert groceries["Spent"] == pytest.approx(350)
        assert groceries["Remaining"] == pytest.approx(150)
        assert groceries["Pct_Used"] == pytest.approx(70)

    def test_over_budget(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)

        restaurants = result[result["Category"] == "Restaurants"].iloc[0]
        assert restaurants["Budget"] == pytest.approx(200)
        assert restaurants["Spent"] == pytest.approx(250)
        assert restaurants["Remaining"] == pytest.approx(-50)
        assert restaurants["Pct_Used"] == pytest.approx(125)

    def test_no_spending(self, budget_df, no_filters):
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

    def test_no_budget_hidden_by_default(self, budget_df, no_filters):
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2024-01-10", "Category": "Amazon", "Amount": -100, "Account": "Checking",
             "Month": "2024-01", "Group": "Shopping", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-01", no_filters)
        assert "Amazon" not in result["Category"].values

    def test_no_budget_shown_with_toggle(self, budget_df, no_filters):
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

    def test_exclude_groups_filter(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        no_filters["exclude_groups"] = ["Food"]
        result = fn(budget_df, transactions_df, "2024-01", no_filters)
        assert "Groceries" not in result["Category"].values
        assert "Restaurants" not in result["Category"].values
        assert "Electric" in result["Category"].values

    def test_exclude_categories_filter(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        no_filters["exclude_categories"] = ["Groceries"]
        result = fn(budget_df, transactions_df, "2024-01", no_filters)
        assert "Groceries" not in result["Category"].values
        assert "Restaurants" in result["Category"].values

    def test_empty_month(self, budget_df, no_filters):
        fn = self._get_fn()
        empty_txns = pd.DataFrame(columns=[
            "Date", "Category", "Amount", "Account", "Month",
            "Full Description", "Group", "Type", "Institution", "Account #",
        ])
        result = fn(budget_df, empty_txns, "2024-01", no_filters)
        assert len(result) == 3  # Groceries, Restaurants, Electric
        assert (result["Spent"] == 0).all()

    def test_group_rollup(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)
        group_result = result.groupby("Group").agg(
            Budget=("Budget", "sum"),
            Spent=("Spent", "sum"),
        ).reset_index()

        food = group_result[group_result["Group"] == "Food"].iloc[0]
        assert food["Budget"] == pytest.approx(700)
        assert food["Spent"] == pytest.approx(600)

    def test_uses_correct_month_budget(self, budget_df, no_filters):
        """March has different budget amounts than January."""
        fn = self._get_fn()
        txns = _transactions_df([
            {"Date": "2024-03-10", "Category": "Restaurants", "Amount": -100, "Account": "Checking",
             "Month": "2024-03", "Group": "Food", "Type": "Expense"},
        ])
        result = fn(budget_df, txns, "2024-03", no_filters)
        rest = result[result["Category"] == "Restaurants"].iloc[0]
        assert rest["Budget"] == pytest.approx(250)  # March budget, not 200


# ---------------------------------------------------------------------------
# get_ytd_budget_vs_actual helper
# ---------------------------------------------------------------------------

class TestGetYtdBudgetVsActual:

    @pytest.fixture
    def budget_df(self):
        """Budget data with months 1-3 for two categories."""
        rows = []
        for month in range(1, 13):
            rows.append({"Category": "Groceries", "Month_Num": month, "Budget": 500,
                         "Group": "Food", "Type": "Expense"})
            rows.append({"Category": "Restaurants", "Month_Num": month, "Budget": 200,
                         "Group": "Food", "Type": "Expense"})
        return pd.DataFrame(rows)

    @pytest.fixture
    def transactions_df(self):
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
    def no_filters(self):
        return {
            "exclude_groups": [],
            "exclude_categories": [],
            "filter_large_expenses": False,
            "expense_threshold": 3000,
            "show_zero_budget": False,
        }

    def _get_fn(self):
        return _mod.get_ytd_budget_vs_actual

    def test_ytd_through_march(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-03", no_filters)

        groceries = result[result["Category"] == "Groceries"].iloc[0]
        # YTD budget: 500 * 3 = 1500
        assert groceries["Budget"] == pytest.approx(1500)
        # YTD spent: 400 + 450 + 550 = 1400
        assert groceries["Spent"] == pytest.approx(1400)
        assert groceries["Remaining"] == pytest.approx(100)
        assert groceries["Pct_Used"] == pytest.approx(1400 / 1500 * 100)

    def test_ytd_through_january(self, budget_df, transactions_df, no_filters):
        """Single month YTD should equal the monthly view."""
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-01", no_filters)

        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Budget"] == pytest.approx(500)
        assert groceries["Spent"] == pytest.approx(400)

    def test_ytd_sums_restaurant_spending(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        result = fn(budget_df, transactions_df, "2024-03", no_filters)

        rest = result[result["Category"] == "Restaurants"].iloc[0]
        # YTD budget: 200 * 3 = 600
        assert rest["Budget"] == pytest.approx(600)
        # YTD spent: 150 + 180 + 250 = 580
        assert rest["Spent"] == pytest.approx(580)

    def test_ytd_exclude_groups(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        no_filters["exclude_groups"] = ["Food"]
        result = fn(budget_df, transactions_df, "2024-03", no_filters)
        assert result.empty

    def test_ytd_exclude_categories(self, budget_df, transactions_df, no_filters):
        fn = self._get_fn()
        no_filters["exclude_categories"] = ["Groceries"]
        result = fn(budget_df, transactions_df, "2024-03", no_filters)
        assert "Groceries" not in result["Category"].values
        assert "Restaurants" in result["Category"].values

    def test_ytd_no_spending(self, budget_df, no_filters):
        fn = self._get_fn()
        empty_txns = _transactions_df([
            {"Date": "2024-01-01", "Category": "Salary", "Amount": 5000, "Account": "Checking",
             "Month": "2024-01", "Group": "Income", "Type": "Income"},
        ])
        result = fn(budget_df, empty_txns, "2024-03", no_filters)
        groceries = result[result["Category"] == "Groceries"].iloc[0]
        assert groceries["Budget"] == pytest.approx(1500)
        assert groceries["Spent"] == pytest.approx(0)

    def test_ytd_empty_transactions(self, budget_df, no_filters):
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

    def test_ytd_only_counts_same_year(self, budget_df, no_filters):
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

    def _get_fn(self):
        return _mod.build_unified_budget_table

    def test_merges_monthly_and_ytd(self):
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

    def test_missing_ytd_category_fills_zero(self):
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

    def test_missing_monthly_category_fills_zero(self):
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

    def test_empty_inputs(self):
        fn = self._get_fn()
        monthly = pd.DataFrame(columns=["Category", "Group", "Budget", "Spent", "Pct_Used"])
        ytd = pd.DataFrame(columns=["Category", "Budget", "Spent", "Pct_Used"])
        result = fn(monthly, ytd)
        assert result.empty


# ---------------------------------------------------------------------------
# Projected spend calculation
# ---------------------------------------------------------------------------

class TestProjectedSpend:

    def _get_fn(self):
        return _mod.calculate_projected_spend

    def test_basic_projection(self):
        fn = self._get_fn()
        projected = fn(spent=300, days_elapsed=15, days_in_month=30)
        assert projected == pytest.approx(600)

    def test_day_one(self):
        fn = self._get_fn()
        projected = fn(spent=50, days_elapsed=1, days_in_month=31)
        assert projected == pytest.approx(50 * 31)

    def test_zero_spent(self):
        fn = self._get_fn()
        projected = fn(spent=0, days_elapsed=15, days_in_month=30)
        assert projected == pytest.approx(0)

    def test_zero_days_elapsed(self):
        fn = self._get_fn()
        projected = fn(spent=0, days_elapsed=0, days_in_month=30)
        assert projected == pytest.approx(0)
