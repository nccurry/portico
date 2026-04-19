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


type AnyFilters = IncomeExpenseFilters | SpendingFilters | BudgetFilters
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
