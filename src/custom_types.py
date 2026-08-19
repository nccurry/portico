"""Shared type definitions for the application.

All custom type definitions (TypedDict, PEP 695 type aliases, Protocol, NewType)
for production code live here. Inline Final, ClassVar, and one-shot parameter
annotations stay at their usage site.
"""

from collections.abc import Sequence
from typing import ReadOnly, TypedDict

from streamlit.elements.lib.column_config_utils import ColumnConfigMappingInput


type ColumnConfig = ColumnConfigMappingInput


class TransactionFilterOptions(TypedDict, total=False):
    """Optional filters understood by the shared transaction pipeline."""

    include_groups: ReadOnly[Sequence[str]]
    include_categories: ReadOnly[Sequence[str]]
    exclude_groups: ReadOnly[Sequence[str]]
    exclude_categories: ReadOnly[Sequence[str]]
    exclude_income_categories: ReadOnly[Sequence[str]]
    exclude_expense_categories: ReadOnly[Sequence[str]]
    filter_large_income: ReadOnly[bool]
    income_threshold: ReadOnly[int]
    filter_large_expenses: ReadOnly[bool]
    expense_threshold: ReadOnly[int]


class IncomeExpenseFilters(TransactionFilterOptions):
    """Sidebar filter state for the Income & Savings page."""

    exclude_groups: list[str]
    exclude_income_categories: list[str]
    exclude_expense_categories: list[str]
    filter_large_income: bool
    income_threshold: int
    filter_large_expenses: bool
    expense_threshold: int
    target_rate: int


class SpendingFilters(TransactionFilterOptions):
    """Sidebar filter state for the Spending by Category page."""

    include_groups: list[str]
    include_categories: list[str]
    exclude_groups: list[str]
    exclude_categories: list[str]
    filter_large_expenses: bool
    expense_threshold: int


class BudgetFilters(TransactionFilterOptions):
    """Sidebar filter state for the Budget page."""

    exclude_groups: list[str]
    exclude_categories: list[str]
    filter_large_expenses: bool
    expense_threshold: int
    show_zero_budget: bool


class FIFilters(TransactionFilterOptions):
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


class TransactionExplorerSummary(TypedDict):
    """Headline values for a filtered set of transactions."""

    transaction_count: int
    inflow: float
    outflow: float
    net_amount: float
    median_magnitude: float


class SavingsSummary(TypedDict):
    """Period cash-flow metrics for the Income & Savings page."""

    total_income: float
    total_net_expenses: float
    total_cash_flow_surplus: float
    weighted_savings_rate: float | None
    average_monthly_surplus: float
    positive_surplus_months: int
    num_months: int


class DuplicateSummary(TypedDict):
    """Headline values for potential duplicate pairs."""

    pair_count: int
    total_amount: float
    affected_months: int


class SubscriptionSummary(TypedDict):
    """Headline subscription inventory metrics."""

    active_count: int
    monthly_run_rate: float
    trailing_12_month_spend: float
    prior_12_month_spend: float
    annual_change_pct: float | None
    pending_estimate_count: int


class MerchantPeriodSummary(TypedDict):
    """Matched-period metrics for merchant spending exploration."""

    total_spending: float
    average_monthly_spending: float
    merchant_count: int
    repeat_spending_share: float


class BudgetSummary(TypedDict):
    """Aggregate budget-versus-actual values for a period."""

    budget: float
    spent: float
    remaining: float
    pct_used: float


class SpendingSummary(TypedDict):
    """Matched-period metrics for spending exploration."""

    total_spending: float
    average_monthly_spending: float
    comparison_spending: float
    change: float
    change_pct: float | None
    transaction_count: int
    num_months: int


class YearOverYearSummary(TypedDict):
    """Matched calendar-year spending metrics for one group or category."""

    current_year: int
    current_total: float
    previous_year: int | None
    previous_total: float | None
    change: float | None
    change_pct: float | None
    through_month: int


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
    total_spending: float
    total_inflow: float
    cashflow_gap: float
    coverage_ratio: float
    runway_years: float | None
