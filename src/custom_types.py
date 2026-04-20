"""Shared type definitions for the application.

All custom type definitions (TypedDict, PEP 695 type aliases, Protocol, NewType)
for production code live here. Inline Final, ClassVar, and one-shot parameter
annotations stay at their usage site.
"""

from typing import TypedDict


class IncomeExpenseFilters(TypedDict):
    """Sidebar filter state for the Income & Savings page."""

    exclude_groups: list[str]
    exclude_categories: list[str]
    filter_large_income: bool
    income_threshold: int
    filter_large_expenses: bool
    expense_threshold: int
    target_rate: int


class SpendingFilters(TypedDict):
    """Sidebar filter state for the Spending by Category page."""

    include_groups: list[str]
    include_categories: list[str]
    exclude_groups: list[str]
    exclude_categories: list[str]
    filter_large_expenses: bool
    expense_threshold: int


class BudgetFilters(TypedDict):
    """Sidebar filter state for the Budget page."""

    exclude_groups: list[str]
    exclude_categories: list[str]
    filter_large_expenses: bool
    expense_threshold: int
    show_zero_budget: bool


class FIFilters(TypedDict):
    """Sidebar filter state for the Financial Independence page."""

    include_accounts: list[str]
    exclude_groups: list[str]
    exclude_categories: list[str]
    filter_large_expenses: bool
    expense_threshold: int
    expected_return_rate: float
    spending_lookback_months: int
    projection_years: int
    supplemental_annual_income: float
    supplemental_annual_spending: float
    override_annual_spending: bool
    annual_spending_override: float
    override_portfolio_value: bool
    portfolio_value_override: float


type AnyFilters = IncomeExpenseFilters | SpendingFilters | BudgetFilters | FIFilters
"""Union of all page-specific filter dicts."""


class TopTransactionsStats(TypedDict):
    """Summary statistics returned alongside the top-N transactions table."""

    total_top_n: float
    total_spending: float
    pct_of_total: float
    num_transactions: int


class DistributionStats(TypedDict):
    """Percentile and bucket breakdown of transaction amounts."""

    median: float
    mean: float
    p25: float
    p75: float
    p80: float
    p90: float
    small_count: int
    medium_count: int
    large_count: int
    small_pct: float
    medium_pct: float
    large_pct: float
    pareto_pct: float


class SavingsSummary(TypedDict):
    """Aggregated savings metrics for the Income & Savings page."""

    avg_monthly_rate: float
    overall_rate: float
    avg_monthly_amount: float
    total_saved: float
    num_months: int


class SpendingSummary(TypedDict):
    """Aggregated spending metrics for the Spending by Category page."""

    total_spending: float
    top_category: str
    top_category_amount: float
    num_categories: int


class FISummary(TypedDict):
    """Financial Independence metrics for the FI page.

    ``annual_spending`` is the data-derived baseline; ``supplemental_spending``
    is added on top to model planned/extra outflows. ``runway_years`` is
    ``None`` when expected returns + supplemental income cover total spending
    (baseline + supplemental). ``coverage_ratio`` is
    ``(annual_return + supplemental_income) / (annual_spending + supplemental_spending)``.
    """

    portfolio_value: float
    annual_return: float
    annual_spending: float
    supplemental_spending: float
    supplemental_income: float
    coverage_ratio: float
    runway_years: float | None
