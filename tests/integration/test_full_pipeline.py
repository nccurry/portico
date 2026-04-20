"""Full-pipeline integration tests against real CSV fixture data.

Exercises the complete data flow: CSV → Spreadsheet.scrub() → pure helpers →
computed results, verifying cross-sheet joins, column schemas, and data integrity.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

if TYPE_CHECKING:
    from src.spreadsheet import (
        AccountsSpreadsheet,
        BalanceHistorySpreadsheet,
        CategoriesSpreadsheet,
        TransactionsSpreadsheet,
    )

from src.filters import apply_transaction_filters, calculate_date_range
from src.spreadsheet import calculate_net_worth_summary


# ---------------------------------------------------------------------------
# Fixture: unpack the four spreadsheets once per class
# ---------------------------------------------------------------------------

@pytest.fixture
def full_dataset(
    make_full_dataset: Callable[..., tuple[Any, Any, Any, Any]],
) -> tuple[
    TransactionsSpreadsheet,
    BalanceHistorySpreadsheet,
    CategoriesSpreadsheet,
    AccountsSpreadsheet,
]:
    return make_full_dataset()


# ---------------------------------------------------------------------------
# Transactions pipeline
# ---------------------------------------------------------------------------

class TestTransactionsPipeline:

    def test_scrubbed_df_not_empty(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, _cats, _accts = full_dataset
        assert not txns.scrubbed_df.empty

    def test_required_columns_present(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, _cats, _accts = full_dataset
        expected = {"Date", "Amount", "Category", "Group", "Type", "Account",
                    "Month", "Full Description", "Institution", "Account #"}
        assert expected.issubset(set(txns.scrubbed_df.columns))

    def test_dates_are_utc_aware(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, _cats, _accts = full_dataset
        assert txns.scrubbed_df["Date"].dt.tz is not None

    def test_types_are_income_or_expense(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, _cats, _accts = full_dataset
        valid_types = {"Income", "Expense", "Transfer", ""}
        actual_types = set(txns.scrubbed_df["Type"].dropna().unique())
        assert actual_types.issubset(valid_types)

    def test_month_format_yyyy_mm(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, _cats, _accts = full_dataset
        months = txns.scrubbed_df["Month"].dropna().unique()
        for m in months:
            assert len(m) == 7 and m[4] == "-", f"Bad month format: {m}"

    def test_get_all_categories_nonempty(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, _cats, _accts = full_dataset
        cats = txns.get_all_categories()
        assert len(cats) > 0
        assert all(isinstance(c, str) and c.strip() for c in cats)

    def test_get_all_groups_excludes_transfer(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, _cats, _accts = full_dataset
        groups = txns.get_all_groups()
        assert "Transfer" not in groups
        assert len(groups) > 0

    def test_filter_pipeline_preserves_rows(self, full_dataset: tuple[Any, ...]) -> None:
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

    def test_scrubbed_df_not_empty(self, full_dataset: tuple[Any, ...]) -> None:
        _txns, bal, _cats, _accts = full_dataset
        assert not bal.scrubbed_df.empty

    def test_required_columns_present(self, full_dataset: tuple[Any, ...]) -> None:
        _txns, bal, _cats, _accts = full_dataset
        expected = {"Date", "Balance", "Account", "Account #", "Institution", "Group", "Class"}
        assert expected.issubset(set(bal.scrubbed_df.columns))

    def test_net_worth_computes(self, full_dataset: tuple[Any, ...]) -> None:
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        assert isinstance(summary["total_net_worth"], float)
        assert len(summary["group_balances"]) > 0

    def test_group_classes_are_asset_or_liability(self, full_dataset: tuple[Any, ...]) -> None:
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        for cls in summary["group_classes"].values():
            assert cls in {"Asset", "Liability"}


# ---------------------------------------------------------------------------
# Categories / budget pipeline
# ---------------------------------------------------------------------------

class TestCategoriesPipeline:

    def test_scrubbed_df_not_empty(self, full_dataset: tuple[Any, ...]) -> None:
        _txns, _bal, cats, _accts = full_dataset
        assert not cats.scrubbed_df.empty

    def test_budget_df_has_12_months(self, full_dataset: tuple[Any, ...]) -> None:
        _txns, _bal, cats, _accts = full_dataset
        if not cats.budget_df.empty:
            months = sorted(cats.budget_df["Month_Num"].unique())
            assert months == list(range(1, 13))

    def test_budget_categories_appear_in_transactions(self, full_dataset: tuple[Any, ...]) -> None:
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

    def test_transaction_groups_overlap_with_categories(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, cats, _accts = full_dataset
        cat_groups = set(cats.scrubbed_df["Group"].dropna().unique())
        txn_groups = set(txns.scrubbed_df["Group"].dropna().unique())
        overlap = txn_groups & cat_groups
        assert len(overlap) > 0, "Transaction groups should overlap with category groups"

    def test_balance_groups_from_accounts(self, full_dataset: tuple[Any, ...]) -> None:
        _txns, bal, _cats, accts = full_dataset
        acct_groups = set(accts.scrubbed_df["Group"].dropna().unique())
        bal_groups = set(bal.scrubbed_df["Group"].dropna().unique())
        assert bal_groups.issubset(acct_groups)

    def test_date_range_covers_fixture_data(self, full_dataset: tuple[Any, ...]) -> None:
        txns, _bal, _cats, _accts = full_dataset
        start, end = calculate_date_range("All Time", txns.scrubbed_df)
        assert start <= txns.scrubbed_df["Date"].min()
        assert end >= txns.scrubbed_df["Date"].max() - pd.Timedelta(days=1)
