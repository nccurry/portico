"""Full-pipeline integration tests against real CSV fixture data.

Exercises the complete data flow: CSV → Spreadsheet.scrub() → pure helpers →
computed results, verifying cross-sheet joins, column schemas, and data integrity.
"""

import pandas as pd
import pytest

from src.analysis.spending import build_spending_ledger
from src.analysis.subscriptions import build_subscription_inventory, build_subscription_lifecycles
from src.config import get_settings
from src.custom_types import SpendingFilters
from src.filters import calculate_date_range
from src.spreadsheet import calculate_net_worth_summary
from src.transaction_filters import apply_transaction_filters
from tests.custom_types import FullDatasetFactory, SpreadsheetBundle

# ---------------------------------------------------------------------------
# Fixture: unpack the four spreadsheets once per class
# ---------------------------------------------------------------------------


@pytest.fixture
def full_dataset(
    make_full_dataset: FullDatasetFactory,
) -> SpreadsheetBundle:
    return make_full_dataset()


# ---------------------------------------------------------------------------
# Transactions pipeline
# ---------------------------------------------------------------------------


class TestTransactionsPipeline:
    def test_scrubbed_df_not_empty(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        assert not txns.scrubbed_df.empty

    def test_required_columns_present(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        expected = {
            "Date",
            "Amount",
            "Category",
            "Group",
            "Type",
            "Account",
            "Month",
            "Full Description",
            "Institution",
            "Account #",
        }
        assert expected.issubset(set(txns.scrubbed_df.columns))

    def test_dates_are_utc_aware(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        assert txns.scrubbed_df["Date"].dt.tz is not None

    def test_types_are_income_or_expense(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        valid_types = {"Income", "Expense", "Transfer", ""}
        actual_types = set(txns.scrubbed_df["Type"].dropna().unique())
        assert actual_types.issubset(valid_types)

    def test_month_format_yyyy_mm(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        months = txns.scrubbed_df["Month"].dropna().unique()
        for m in months:
            assert len(m) == 7 and m[4] == "-", f"Bad month format: {m}"

    def test_get_all_categories_nonempty(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        cats = txns.get_all_categories()
        assert len(cats) > 0
        assert all(isinstance(c, str) and c.strip() for c in cats)

    def test_get_all_groups_excludes_transfer(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        groups = txns.get_all_groups()
        assert "Transfer" not in groups
        assert len(groups) > 0

    def test_filter_pipeline_preserves_rows(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        df = txns.scrubbed_df.copy()
        original_len = len(df)
        filtered = apply_transaction_filters(df, {})
        # Only Transfers should be removed
        transfer_count = len(txns.scrubbed_df[txns.scrubbed_df["Group"] == "Transfer"])
        assert len(filtered) == original_len - transfer_count


# ---------------------------------------------------------------------------
# Balance history pipeline
# ---------------------------------------------------------------------------


class TestBalancePipeline:
    def test_scrubbed_df_not_empty(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, bal, _cats, _accts = full_dataset
        assert not bal.scrubbed_df.empty

    def test_required_columns_present(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, bal, _cats, _accts = full_dataset
        expected = {"Date", "Balance", "Account", "Account #", "Institution", "Group", "Class"}
        assert expected.issubset(set(bal.scrubbed_df.columns))

    def test_net_worth_computes(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        assert isinstance(summary["total_net_worth"], float)
        assert len(summary["group_balances"]) > 0

    def test_group_classes_are_asset_or_liability(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        for cls in summary["group_classes"].values():
            assert cls in {"Asset", "Liability"}

    def test_latest_balance_matches_demo_data_date(
        self,
        full_dataset: SpreadsheetBundle,
        demo_latest_date: pd.Timestamp,
    ) -> None:
        """Keep demo reports inside the committed balance history."""
        _txns, bal, _cats, _accts = full_dataset
        assert bal.scrubbed_df["Date"].max() == demo_latest_date


# ---------------------------------------------------------------------------
# Categories / budget pipeline
# ---------------------------------------------------------------------------


class TestCategoriesPipeline:
    def test_scrubbed_df_not_empty(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, _bal, cats, _accts = full_dataset
        assert not cats.scrubbed_df.empty

    def test_budget_df_covers_synthetic_years(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, _bal, cats, _accts = full_dataset
        if not cats.budget_df.empty:
            months = sorted(cats.budget_df["Month"].unique())
            assert months == [f"{year}-{month:02d}" for year in range(1992, 1996) for month in range(1, 13)]

    def test_budget_categories_appear_in_transactions(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, cats, _accts = full_dataset
        if cats.budget_df.empty:
            pytest.skip("No budget data in fixture")
        budget_cats = set(cats.budget_df["Category"].unique())
        txn_cats = set(txns.scrubbed_df["Category"].dropna().unique())
        overlap = budget_cats & txn_cats
        assert len(overlap) > 0, "Budget categories should overlap with transaction categories"


# ---------------------------------------------------------------------------
# Cross-sheet join integrity
# ---------------------------------------------------------------------------


class TestCrossSheetJoins:
    def test_transaction_groups_overlap_with_categories(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, cats, _accts = full_dataset
        cat_groups = set(cats.scrubbed_df["Group"].dropna().unique())
        txn_groups = set(txns.scrubbed_df["Group"].dropna().unique())
        overlap = txn_groups & cat_groups
        assert len(overlap) > 0, "Transaction groups should overlap with category groups"

    def test_balance_groups_from_accounts(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, bal, _cats, accts = full_dataset
        acct_groups = set(accts.scrubbed_df["Group"].dropna().unique())
        bal_groups = set(bal.scrubbed_df["Group"].dropna().unique())
        assert bal_groups.issubset(acct_groups)

    def test_date_range_covers_fixture_data(self, full_dataset: SpreadsheetBundle) -> None:
        txns, _bal, _cats, _accts = full_dataset
        start, end = calculate_date_range("All Time", txns.scrubbed_df)
        assert start <= txns.scrubbed_df["Date"].min()
        assert end >= txns.scrubbed_df["Date"].max() - pd.Timedelta(days=1)


# ---------------------------------------------------------------------------
# Demo showcase scenarios
# ---------------------------------------------------------------------------


@pytest.mark.uses_real_dates
class TestDemoShowcase:
    def test_account_groups_have_multiple_realistic_accounts(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, _bal, _cats, accounts = full_dataset
        group_counts = accounts.scrubbed_df.groupby("Group")["Account"].nunique().to_dict()

        assert group_counts == {
            "Credit Cards": 2,
            "Investments": 3,
            "Liabilities": 2,
            "Retirement": 2,
            "Savings": 3,
        }
        assert not accounts.scrubbed_df["Account"].str.contains("synthetic|zero", case=False).any()

    def test_balance_history_has_rising_and_falling_account_trends(
        self,
        full_dataset: SpreadsheetBundle,
    ) -> None:
        _txns, balances, _cats, _accounts = full_dataset
        for account in ("Main Checking", "Everyday Card", "Brokerage Account"):
            changes = (
                balances.scrubbed_df.loc[balances.scrubbed_df["Account"].eq(account)]
                .sort_values("Date")["Balance"]
                .diff()
                .dropna()
            )
            assert (changes > 0).any(), account
            assert (changes < 0).any(), account

    def test_spending_has_utility_categories_and_varied_monthly_totals(
        self,
        full_dataset: SpreadsheetBundle,
    ) -> None:
        transactions, _bal, _cats, _accounts = full_dataset
        expenses = transactions.scrubbed_df.query("Type == 'Expense'")
        assert {
            "Rent",
            "Electric",
            "Natural Gas",
            "Internet",
            "Mobile Phone",
            "Water & Sewer",
            "Trash",
        }.issubset(set(expenses["Category"]))

        for category in ("Electric", "Groceries", "Restaurants"):
            monthly_totals = expenses.loc[expenses["Category"].eq(category)].groupby("Month")["Amount"].sum()
            assert len(monthly_totals) == 36
            assert monthly_totals.nunique() > 18

    def test_discretionary_defaults_leave_housing_and_bills_out(
        self,
        full_dataset: SpreadsheetBundle,
    ) -> None:
        transactions, _bal, _cats, _accounts = full_dataset
        settings = get_settings()
        filters: SpendingFilters = {
            "include_groups": [],
            "include_categories": [],
            "exclude_groups": [],
            "exclude_categories": [],
            "filter_large_expenses": False,
            "expense_threshold": 999_999,
        }
        discretionary = build_spending_ledger(
            transactions.scrubbed_df,
            filters,
            start_month="1994-05",
            end_month="1995-05",
            transaction_set_key="discretionary",
            transaction_sets=settings.transaction_sets,
        )
        included = discretionary.loc[discretionary["Included"], "Category"]
        assert "Rent" not in set(included)
        assert "Electric" not in set(included)
        assert "Restaurants" in set(included)

    def test_subscriptions_show_current_and_past_lifecycles(
        self,
        full_dataset: SpreadsheetBundle,
    ) -> None:
        transactions, _bal, _cats, _accounts = full_dataset
        subscription_categories = [
            category
            for category in transactions.scrubbed_df["Category"].dropna().unique()
            if "Subscription" in category
        ]
        inventory = build_subscription_inventory(transactions.scrubbed_df, subscription_categories)
        lifecycles = build_subscription_lifecycles(
            transactions.scrubbed_df,
            inventory,
            subscription_categories,
        )
        statuses = inventory.set_index("Merchant")["Status"].to_dict()

        assert statuses["FLICKER STREAM MEMBERSHIP"] == "Active"
        assert statuses["CLOUDBOX STORAGE PLAN"] == "Active"
        assert statuses["SOUNDWAVE MUSIC PLAN"] == "Active"
        assert statuses["FIT CLUB MEMBERSHIP"] == "Active"
        assert statuses["MORNING GAZETTE DIGITAL"] == "Inactive"
        assert statuses["PANTRY BOX DELIVERY"] == "Inactive"

        fit_club = lifecycles.loc[lifecycles["Merchant"].eq("FIT CLUB MEMBERSHIP")]
        assert len(fit_club) == 2
        assert set(fit_club["Status"]) == {"Active", "Inactive"}

    def test_budgets_cover_everyday_expenses(self, full_dataset: SpreadsheetBundle) -> None:
        _txns, _bal, categories, _accounts = full_dataset
        april_budgets = categories.budget_df.loc[categories.budget_df["Month"].eq("1995-04")].set_index("Category")

        assert april_budgets.loc["Rent", "Budget"] == 1_470
        assert april_budgets.loc["Groceries", "Budget"] == 600
        assert april_budgets.loc["Restaurants", "Budget"] == 335
        assert april_budgets.loc["Electric", "Budget"] == 135
