"""Tests for budget functionality: CategoriesSpreadsheet budget parsing and budget vs actual."""

from importlib import import_module
from unittest.mock import patch

import pandas as pd
import pytest

from src.custom_types import BudgetFilters
from src.spreadsheet import Spreadsheet, CategoriesSpreadsheet
from src.analysis import budget as _mod


budget_page = import_module("pages.7_Budget")


# ---------------------------------------------------------------------------
# CategoriesSpreadsheet.scrub() — budget parsing
# ---------------------------------------------------------------------------


class TestCategoriesBudgetParsing:
    def _make(self, raw_df: pd.DataFrame) -> CategoriesSpreadsheet:
        with patch.object(Spreadsheet, "load", lambda self: setattr(self, "raw_df", raw_df)):
            return CategoriesSpreadsheet()

    def test_budget_df_has_expected_columns(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        assert set(cs.budget_df.columns) == {"Category", "Month", "Budget", "Group", "Type"}

    def test_budget_df_has_12_months_per_category(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        # 4 valid categories (None row dropped) x 12 months = 48
        assert len(cs.budget_df) == 48

    def test_null_category_rows_dropped(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        assert cs.budget_df["Category"].isna().sum() == 0

    def test_months_preserve_year_and_month(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        assert sorted(cs.budget_df["Month"].unique()) == [f"2023-{month:02d}" for month in range(1, 13)]

    def test_budget_values_correct(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        # Groceries has $500 budget for all months
        groceries_jan = cs.budget_df[(cs.budget_df["Category"] == "Groceries") & (cs.budget_df["Month"] == "2023-01")]
        assert groceries_jan.iloc[0]["Budget"] == pytest.approx(500)

    def test_different_budget_per_month(self, raw_categories_with_budget_df: pd.DataFrame) -> None:
        cs = self._make(raw_categories_with_budget_df)
        # Restaurants: $200 most months but $250 in March
        rest_mar = cs.budget_df[(cs.budget_df["Category"] == "Restaurants") & (cs.budget_df["Month"] == "2023-03")]
        assert rest_mar.iloc[0]["Budget"] == pytest.approx(250)

    def test_same_month_number_in_multiple_years_is_preserved(self) -> None:
        raw = pd.DataFrame(
            {
                "Category": ["Groceries"],
                "Group": ["Food"],
                "Type": ["Expense"],
                "Hide From Reports": [""],
                pd.Timestamp("2023-01-01"): [500],
                pd.Timestamp("2024-01-01"): [600],
            }
        )
        cs = self._make(raw)
        groceries = cs.budget_df[cs.budget_df["Category"] == "Groceries"]
        assert groceries.set_index("Month")["Budget"].to_dict() == {
            "2023-01": 500,
            "2024-01": 600,
        }

    def test_nan_budget_becomes_zero(self) -> None:
        raw = pd.DataFrame(
            {
                "Category": ["Groceries"],
                "Group": ["Food"],
                "Type": ["Expense"],
                "Hide From Reports": [""],
                pd.Timestamp("2023-01-01"): [None],
                pd.Timestamp("2023-02-01"): [500],
            }
        )
        cs = self._make(raw)
        jan = cs.budget_df[(cs.budget_df["Category"] == "Groceries") & (cs.budget_df["Month"] == "2023-01")]
        assert jan.iloc[0]["Budget"] == pytest.approx(0)

    def test_no_date_columns_produces_empty_budget_df(self) -> None:
        raw = pd.DataFrame(
            {
                "Category": ["Groceries"],
                "Group": ["Food"],
                "Type": ["Expense"],
                "Hide From Reports": [""],
            }
        )
        cs = self._make(raw)
        assert cs.budget_df.empty
        assert set(cs.budget_df.columns) == {"Category", "Month", "Budget", "Group", "Type"}

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


class TestDefaultBudgetGroups:
    def test_uses_positive_expense_budgets_for_selected_month(self) -> None:
        budgets = pd.DataFrame(
            [
                {"Category": "Shopping", "Group": "Shopping", "Type": "Expense", "Month": "2026-08", "Budget": 2500},
                {"Category": "Groceries", "Group": "Food", "Type": "Expense", "Month": "2026-08", "Budget": 2000},
                {"Category": "Travel", "Group": "Travel", "Type": "Expense", "Month": "2026-08", "Budget": 0},
                {
                    "Category": "Streaming",
                    "Group": "Entertainment",
                    "Type": "Expense",
                    "Month": "2026-08",
                    "Budget": 50,
                },
                {"Category": "Paycheck", "Group": "Income", "Type": "Income", "Month": "2026-08", "Budget": 100},
                {"Category": "Travel", "Group": "Travel", "Type": "Expense", "Month": "2026-09", "Budget": 1000},
            ]
        )
        available = ["Shopping", "Food", "Travel", "Entertainment", "Income"]

        assert _mod.get_default_budget_groups(budgets, "2026-08", available) == [
            "Shopping",
            "Food",
            "Entertainment",
        ]
        assert _mod.get_default_budget_groups(budgets, "2026-09", available) == ["Travel"]

    def test_no_positive_budget_returns_no_defaults(self) -> None:
        budgets = pd.DataFrame(
            [
                {"Category": "Travel", "Group": "Travel", "Type": "Expense", "Month": "2026-08", "Budget": 0},
            ]
        )
        assert _mod.get_default_budget_groups(budgets, "2026-08", ["Travel"]) == []
        assert _mod.get_default_budget_groups(budgets, "2026-09", ["Travel"]) == []


class TestBudgetPulseAnalysis:
    def test_current_month_progress_uses_today_when_transactions_are_older(self) -> None:
        transactions = pd.DataFrame({"Date": [pd.Timestamp("2026-03-20", tz="UTC")]})

        with patch.object(
            budget_page,
            "reporting_anchor",
            return_value=pd.Timestamp("2026-04-15", tz="UTC"),
        ):
            progress, latest = budget_page._month_progress(transactions, "2026-04")

        assert progress == pytest.approx(0.5)
        assert latest == pd.Timestamp("2026-03-20", tz="UTC")

    @pytest.fixture
    def filters(self) -> BudgetFilters:
        return {
            "exclude_groups": [],
            "exclude_categories": [],
            "filter_large_expenses": False,
            "expense_threshold": 3000,
        }

    @pytest.fixture
    def budgets(self) -> pd.DataFrame:
        rows = []
        for month in ["2024-01", "2024-02", "2024-03", "2024-04"]:
            rows.extend(
                [
                    {
                        "Category": "Groceries",
                        "Group": "Food",
                        "Type": "Expense",
                        "Month": month,
                        "Budget": 100.0,
                    },
                    {
                        "Category": "Dining",
                        "Group": "Food",
                        "Type": "Expense",
                        "Month": month,
                        "Budget": 50.0,
                    },
                    {
                        "Category": "Shopping",
                        "Group": "Shopping",
                        "Type": "Expense",
                        "Month": month,
                        "Budget": 200.0,
                    },
                ]
            )
        return pd.DataFrame(rows)

    @pytest.fixture
    def transactions(self) -> pd.DataFrame:
        rows = [
            ("2024-01-05", "2024-01", "Food", "Groceries", -80.0),
            ("2024-01-08", "2024-01", "Food", "Coffee", -20.0),
            ("2024-01-10", "2024-01", "Shopping", "Shopping", -100.0),
            ("2024-02-05", "2024-02", "Food", "Groceries", -120.0),
            ("2024-02-08", "2024-02", "Food", "Coffee", -30.0),
            ("2024-02-10", "2024-02", "Shopping", "Shopping", -250.0),
            ("2024-03-10", "2024-03", "Shopping", "Shopping", -150.0),
            ("2024-04-05", "2024-04", "Food", "Groceries", -70.0),
            ("2024-04-08", "2024-04", "Food", "Coffee", -40.0),
            ("2024-04-10", "2024-04", "Shopping", "Shopping", -50.0),
            ("2024-04-11", "2024-04", "Shopping", "Shopping", 10.0),
        ]
        return pd.DataFrame(
            {
                "Date": pd.to_datetime([row[0] for row in rows], utc=True),
                "Month": [row[1] for row in rows],
                "Group": [row[2] for row in rows],
                "Category": [row[3] for row in rows],
                "Type": "Expense",
                "Amount": [row[4] for row in rows],
                "Account": "Checking",
                "Full Description": [f"Transaction {index}" for index in range(len(rows))],
            }
        )

    def test_history_separates_tracked_and_outside_plan_spending(
        self,
        budgets: pd.DataFrame,
        transactions: pd.DataFrame,
        filters: BudgetFilters,
    ) -> None:
        history = _mod.build_budget_history(
            budgets,
            transactions,
            "2024-04",
            filters,
            ["Food", "Shopping"],
            lookback_months=3,
        )

        food = history[history["Entity"].eq("Food")].set_index("Month")
        assert food.loc["2024-01", "Tracked_Spent"] == pytest.approx(80.0)
        assert food.loc["2024-01", "Outside_Plan"] == pytest.approx(20.0)
        assert food.loc["2024-03", "Spent"] == pytest.approx(0.0)
        shopping = history[history["Entity"].eq("Shopping") & history["Month"].eq("2024-04")].iloc[0]
        assert shopping["Spent"] == pytest.approx(40.0)

    def test_performance_uses_median_and_trailing_budget_hit_rate(
        self,
        budgets: pd.DataFrame,
        transactions: pd.DataFrame,
        filters: BudgetFilters,
    ) -> None:
        history = _mod.build_budget_history(
            budgets,
            transactions,
            "2024-04",
            filters,
            ["Food", "Shopping"],
            lookback_months=3,
        )
        performance = _mod.build_budget_performance(history, "2024-04").set_index("Entity")

        assert performance.loc["Food", "Typical_Spend"] == pytest.approx(100.0)
        assert performance.loc["Food", "Vs_Typical"] == pytest.approx(10.0)
        assert performance.loc["Food", "Success_Rate"] == pytest.approx(100.0)
        assert performance.loc["Shopping", "Typical_Spend"] == pytest.approx(150.0)
        assert performance.loc["Shopping", "Success_Rate"] == pytest.approx(2 / 3 * 100)

    def test_summary_reconciles_month_and_typical_totals(
        self,
        budgets: pd.DataFrame,
        transactions: pd.DataFrame,
        filters: BudgetFilters,
    ) -> None:
        history = _mod.build_budget_history(
            budgets,
            transactions,
            "2024-04",
            filters,
            ["Food", "Shopping"],
            lookback_months=3,
        )

        assert _mod.summarize_budget_history(history, "2024-04") == {
            "budget": pytest.approx(350.0),
            "tracked_spent": pytest.approx(110.0),
            "outside_plan": pytest.approx(40.0),
            "spent": pytest.approx(150.0),
            "remaining": pytest.approx(200.0),
            "pct_used": pytest.approx(150 / 350 * 100),
            "typical_spend": pytest.approx(200.0),
            "vs_typical": pytest.approx(-50.0),
        }

    def test_category_history_includes_budgeted_and_unbudgeted_drivers(
        self,
        budgets: pd.DataFrame,
        transactions: pd.DataFrame,
        filters: BudgetFilters,
    ) -> None:
        history = _mod.build_budget_history(
            budgets,
            transactions,
            "2024-04",
            filters,
            ["Food"],
            dimension="Category",
            lookback_months=3,
        )
        performance = _mod.build_budget_performance(history, "2024-04").set_index("Entity")

        assert set(performance.index) == {"Coffee", "Dining", "Groceries"}
        assert performance.loc["Coffee", "Budget"] == pytest.approx(0.0)
        assert performance.loc["Coffee", "Outside_Plan"] == pytest.approx(40.0)
        assert performance.loc["Dining", "Spent"] == pytest.approx(0.0)
        assert performance.loc["Groceries", "Typical_Spend"] == pytest.approx(80.0)

    def test_adjustments_apply_to_history_and_budget_scope(
        self,
        budgets: pd.DataFrame,
        transactions: pd.DataFrame,
        filters: BudgetFilters,
    ) -> None:
        filters["exclude_categories"] = ["Coffee", "Groceries"]
        history = _mod.build_budget_history(
            budgets,
            transactions,
            "2024-04",
            filters,
            ["Food"],
            lookback_months=3,
        )
        current = history[history["Month"].eq("2024-04")].iloc[0]

        assert current["Budget"] == pytest.approx(50.0)
        assert current["Spent"] == pytest.approx(0.0)
