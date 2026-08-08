"""Integration tests asserting injected fixture patterns surface through page helpers.

Each test runs an actual page helper function (not just checking CSV artifacts)
against the real scrubbed fixture data, proving the injected patterns survive
the full scrub pipeline and are visible to the business logic the user sees.
"""
import pandas as pd
import pytest

from src.custom_types import BudgetFilters
from src.constants import MIN_DUPLICATE_AMOUNT, DEFAULT_DUPLICATE_DAYS_THRESHOLD
from src.analysis.budget import get_budget_vs_actual
from src.analysis.duplicates import find_duplicates_efficient
from src.analysis.subscriptions import build_subscription_inventory, get_subscription_transactions
from src.analysis.top_transactions import get_top_transactions
from src.filters import apply_transaction_filters
from src.spreadsheet import calculate_net_worth_summary
from tests.custom_types import FullDatasetFactory, SpreadsheetBundle


@pytest.fixture
def full_dataset(
    make_full_dataset: FullDatasetFactory,
) -> SpreadsheetBundle:
    return make_full_dataset()


# ---------------------------------------------------------------------------
# Data Health — Duplicate detection (injected pairs must surface)
# ---------------------------------------------------------------------------

@pytest.mark.uses_real_dates
class TestDuplicatePatternsIntegration:

    def test_injected_duplicate_pairs_found(
        self, full_dataset: SpreadsheetBundle,
    ) -> None:
        """The ≥3 injected duplicate pairs surface through find_duplicates_efficient
        with Data Health's default settings (same account, same description, within 1 day,
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
        self, full_dataset: SpreadsheetBundle,
    ) -> None:
        """The ≥2 injected recurring merchants surface through
        the category-authoritative subscription inventory."""
        txns, _bal, _cats, _accts = full_dataset
        df = apply_transaction_filters(txns.scrubbed_df, {})
        recurring = build_subscription_inventory(
            df, ["Streaming Subscription", "Cloud Subscription"]
        )
        assert len(recurring) >= 2, (
            f"Expected ≥2 recurring merchants but found {len(recurring)}"
        )

    def test_recurring_merchants_have_multiple_months(
        self, full_dataset: SpreadsheetBundle,
    ) -> None:
        """Detected recurring merchants span multiple months (≥3)."""
        txns, _bal, _cats, _accts = full_dataset
        df = apply_transaction_filters(txns.scrubbed_df, {})
        recurring = build_subscription_inventory(
            df, ["Streaming Subscription", "Cloud Subscription"]
        )
        if recurring.empty:
            pytest.fail("No recurring transactions detected")
        for merchant in recurring["Merchant"]:
            charges = get_subscription_transactions(
                df,
                str(merchant),
                categories=["Streaming Subscription", "Cloud Subscription"],
            )
            assert charges["Date"].dt.strftime("%Y-%m").nunique() >= 3


# ---------------------------------------------------------------------------
# Page 7 — Budget vs actual (injected over/under-budget must surface)
# ---------------------------------------------------------------------------

@pytest.mark.uses_real_dates
class TestBudgetPatternsIntegration:

    def test_over_and_under_budget_categories_present(
        self, full_dataset: SpreadsheetBundle, reference_date: pd.Timestamp,
    ) -> None:
        """The injected over-budget and under-budget categories appear in
        get_budget_vs_actual output."""
        txns, _bal, cats, _accts = full_dataset
        month_str = reference_date.strftime("%Y-%m")
        filters: BudgetFilters = {
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
        self, full_dataset: SpreadsheetBundle, reference_date: pd.Timestamp,
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
        self, full_dataset: SpreadsheetBundle,
    ) -> None:
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        assert len(summary["group_balances"]) > 0

    def test_zero_total_group_present(
        self, full_dataset: SpreadsheetBundle,
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
        self, full_dataset: SpreadsheetBundle,
    ) -> None:
        """At least one all-Liability group is classified correctly."""
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        liability_groups = [
            g for g, c in summary["group_classes"].items()
            if c == "Liability"
        ]
        assert len(liability_groups) >= 1

    def test_net_worth_summary_returns_finite_dollar_amount(
        self, full_dataset: SpreadsheetBundle,
    ) -> None:
        """The headline total net worth must be a finite, real number — never
        NaN or ±Inf — given any well-formed input. This guards against silent
        corruption from bad data flowing through the aggregation."""
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)

        import math
        assert isinstance(summary["total_net_worth"], float)
        assert math.isfinite(summary["total_net_worth"])

    def test_group_balances_are_non_negative(
        self, full_dataset: SpreadsheetBundle,
    ) -> None:
        """``group_balances`` stores raw (unsigned) per-group totals — every
        value should be >= 0, regardless of whether the group is asset or
        liability. The signing happens only in ``total_net_worth``."""
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        for group, balance in summary["group_balances"].items():
            assert balance >= -0.01, f"Group {group!r} has negative balance {balance}"

    def test_each_group_classified_as_asset_or_liability(
        self, full_dataset: SpreadsheetBundle,
    ) -> None:
        """Every reported group must classify to ``Asset`` or ``Liability`` —
        never empty, never NaN. This guards against undisplayable sparkline
        colors on the Home page."""
        _txns, bal, _cats, _accts = full_dataset
        summary = calculate_net_worth_summary(bal)
        for group, cls in summary["group_classes"].items():
            assert cls in ("Asset", "Liability"), (
                f"Group {group!r} has invalid class {cls!r}"
            )
