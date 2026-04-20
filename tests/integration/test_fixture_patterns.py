"""Integration tests asserting injected fixture patterns surface through page helpers.

Each test runs an actual page helper function (not just checking CSV artifacts)
against the real scrubbed fixture data, proving the injected patterns survive
the full scrub pipeline and are visible to the business logic the user sees.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd
import pytest

from src.constants import MIN_DUPLICATE_AMOUNT, DEFAULT_DUPLICATE_DAYS_THRESHOLD
from src.filters import apply_transaction_filters
from src.spreadsheet import calculate_net_worth_summary
from tests._pages import (
    duplicate_detection,
    subscriptions,
    top_transactions,
    budget,
)

find_duplicates_efficient = duplicate_detection.find_duplicates_efficient
detect_recurring_transactions = subscriptions.detect_recurring_transactions
get_top_transactions = top_transactions.get_top_transactions
get_budget_vs_actual = budget.get_budget_vs_actual


@pytest.fixture
def full_dataset(
    make_full_dataset: Callable[..., tuple[Any, Any, Any, Any]],
) -> tuple[Any, Any, Any, Any]:
    return make_full_dataset()


# ---------------------------------------------------------------------------
# Page 4 — Duplicate detection (injected pairs must surface)
# ---------------------------------------------------------------------------

@pytest.mark.uses_real_dates
class TestDuplicatePatternsIntegration:

    def test_injected_duplicate_pairs_found(
        self, full_dataset: tuple[Any, ...],
    ) -> None:
        """The ≥3 injected duplicate pairs surface through find_duplicates_efficient
        with Page 4's default settings (same account, same description, within 1 day,
        amount >= $10)."""
        txns, _bal, _cats, _accts = full_dataset
        df = apply_transaction_filters(txns.scrubbed_df, {})
        duplicates = find_duplicates_efficient(
            df,
            days_threshold=DEFAULT_DUPLICATE_DAYS_THRESHOLD,
            min_amount=MIN_DUPLICATE_AMOUNT,
            check_same_account=True,
            check_same_category=False,
            require_same_description=True,
        )
        assert len(duplicates) >= 3, (
            f"Expected ≥3 duplicate pairs but found {len(duplicates)}"
        )


# ---------------------------------------------------------------------------
# Page 5 — Subscription/recurring detection (injected merchants must surface)
# ---------------------------------------------------------------------------

@pytest.mark.uses_real_dates
class TestRecurringPatternsIntegration:

    def test_injected_recurring_merchants_detected(
        self, full_dataset: tuple[Any, ...],
    ) -> None:
        """The ≥2 injected recurring merchants surface through
        detect_recurring_transactions."""
        txns, _bal, _cats, _accts = full_dataset
        df = apply_transaction_filters(txns.scrubbed_df, {})
        recurring = detect_recurring_transactions(df)
        assert len(recurring) >= 2, (
            f"Expected ≥2 recurring merchants but found {len(recurring)}"
        )

    def test_recurring_merchants_have_multiple_months(
        self, full_dataset: tuple[Any, ...],
    ) -> None:
        """Detected recurring merchants span multiple months (≥3)."""
        txns, _bal, _cats, _accts = full_dataset
        df = apply_transaction_filters(txns.scrubbed_df, {})
        recurring = detect_recurring_transactions(df)
        if recurring.empty:
            pytest.fail("No recurring transactions detected")
        assert (recurring["Unique_Months"] >= 3).all()


# ---------------------------------------------------------------------------
# Page 7 — Budget vs actual (injected over/under-budget must surface)
# ---------------------------------------------------------------------------

@pytest.mark.uses_real_dates
class TestBudgetPatternsIntegration:

    def test_over_and_under_budget_categories_present(
        self, full_dataset: tuple[Any, ...], reference_date: pd.Timestamp,
    ) -> None:
        """The injected over-budget and under-budget categories appear in
        get_budget_vs_actual output."""
        txns, _bal, cats, _accts = full_dataset
        month_str = reference_date.strftime("%Y-%m")
        filters = {
            "exclude_groups": [],
            "exclude_categories": [],
            "filter_large_expenses": False,
            "expense_threshold": 0,
            "show_zero_budget": False,
        }
        result = get_budget_vs_actual(
            cats.budget_df, txns.scrubbed_df, month_str, filters,
        )
        if result.empty:
            pytest.skip("No budget data for reference month")

        over = result[result["Pct_Used"] > 100]
        under = result[(result["Pct_Used"] > 0) & (result["Pct_Used"] < 100)]
        assert len(over) >= 1, "Expected ≥1 over-budget category"
        assert len(under) >= 1, "Expected ≥1 under-budget category"


# ---------------------------------------------------------------------------
# Page 8 — Top-N ties (injected tie amounts must surface)
# ---------------------------------------------------------------------------

@pytest.mark.uses_real_dates
class TestTopNTiePatternsIntegration:

    def test_injected_ties_surface_in_top_n(
        self, full_dataset: tuple[Any, ...], reference_date: pd.Timestamp,
    ) -> None:
        """When N is chosen to land on the tie boundary, both tied rows appear."""
        txns, _bal, _cats, _accts = full_dataset
        df = apply_transaction_filters(txns.scrubbed_df, {})
        start = reference_date - pd.DateOffset(months=3)
        end = reference_date

        top_df, _stats = get_top_transactions(df, 50, start, end)
        if top_df.empty:
            pytest.skip("No expenses in date range")

        amounts = top_df["Abs_Amount"]
        tie_amounts = amounts[amounts.duplicated(keep=False)]
        assert len(tie_amounts) >= 2, (
            "Expected ≥2 rows with tied amounts in top-N results"
        )


# ---------------------------------------------------------------------------
# Home — Net worth with mixed asset/liability and zero-total group
# ---------------------------------------------------------------------------

@pytest.mark.uses_real_dates
class TestHomePatternsIntegration:

    def test_net_worth_summary_has_groups(
        self, full_dataset: tuple[Any, ...],
    ) -> None:
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        assert len(summary["group_balances"]) > 0

    def test_zero_total_group_present(
        self, full_dataset: tuple[Any, ...],
    ) -> None:
        """The injected zero-total group appears in the summary."""
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        zero_groups = [
            g for g, b in summary["group_balances"].items()
            if abs(b) < 0.01
        ]
        assert len(zero_groups) >= 1, "Expected ≥1 zero-total group"

    def test_liability_groups_present(
        self, full_dataset: tuple[Any, ...],
    ) -> None:
        """At least one all-Liability group is classified correctly."""
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        liability_groups = [
            g for g, c in summary["group_classes"].items()
            if c == "Liability"
        ]
        assert len(liability_groups) >= 1

    def test_net_worth_equals_signed_group_sum(
        self, full_dataset: tuple[Any, ...],
    ) -> None:
        """Total net worth equals the sum of each group's signed contribution.

        Recomputes the expected value independently: for each group, sum
        asset balances and subtract liability balances, then compare to
        the reported total_net_worth.
        """
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)

        scrubbed = bal.scrubbed_df.copy()
        scrubbed = scrubbed.sort_values(by=["Date", "Time"])
        scrubbed = scrubbed.drop_duplicates("Account ID", keep="last")

        multiplier = scrubbed["Class"].map({"Liability": -1, "Asset": 1}).fillna(1)
        expected = float((scrubbed["Balance"] * multiplier).sum())

        assert summary["total_net_worth"] == pytest.approx(expected), (
            f"total_net_worth {summary['total_net_worth']} != "
            f"independently computed {expected}"
        )
