"""Weekly expense report calculations for Discord notifications."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

import pandas as pd

from src.analysis.data_health import find_uncategorized_transactions


class WeeklyExpenseError(ValueError):
    """Raised when report configuration or source data is invalid."""


@dataclass(frozen=True)
class ReportPeriod:
    """Current and comparison Sunday-through-Saturday periods."""

    start: dt.date
    end: dt.date
    comparison_start: dt.date
    comparison_end: dt.date


@dataclass(frozen=True)
class CategoryTotal:
    """Current and comparison spending for one category."""

    name: str
    amount: float
    previous_amount: float

    @property
    def change(self) -> float:
        """Return the dollar change from the comparison period."""
        return _money(self.amount - self.previous_amount)


@dataclass(frozen=True)
class UncategorizedTotal:
    """Current, comparison, and outstanding uncategorized transactions."""

    amount: float
    previous_amount: float
    count: int
    previous_count: int
    outstanding_count: int

    @property
    def change(self) -> float:
        """Return the net-outflow change from the comparison period."""
        return _money(self.amount - self.previous_amount)

    @property
    def count_change(self) -> int:
        """Return the transaction-count change from the comparison period."""
        return self.count - self.previous_count


@dataclass(frozen=True)
class WeeklyExpenseReport:
    """Values shown in one weekly Discord summary."""

    period: ReportPeriod
    categories: tuple[CategoryTotal, ...]
    selected_total: float
    previous_selected_total: float
    all_expenses_total: float
    uncategorized: UncategorizedTotal

    @property
    def selected_change(self) -> float:
        """Return the selected-category change from the comparison period."""
        return _money(self.selected_total - self.previous_selected_total)


def completed_week(today: dt.date, period_end: dt.date | None = None) -> ReportPeriod:
    """Return a completed Sunday-through-Saturday period and its predecessor."""
    if period_end is None:
        days_since_saturday = (today.weekday() - 5) % 7 or 7
        end = today - dt.timedelta(days=days_since_saturday)
    else:
        if period_end.weekday() != 5:
            raise WeeklyExpenseError("PERIOD_END must be a Saturday.")
        if period_end >= today:
            raise WeeklyExpenseError("PERIOD_END must be before today.")
        end = period_end

    start = end - dt.timedelta(days=6)
    comparison_end = start - dt.timedelta(days=1)
    comparison_start = comparison_end - dt.timedelta(days=6)
    return ReportPeriod(start, end, comparison_start, comparison_end)


def validate_selected_categories(categories: tuple[str, ...], metadata: pd.DataFrame) -> None:
    """Check that configured categories are unique Tiller expense categories."""
    if not categories:
        raise WeeklyExpenseError("Configure at least one Discord expense category.")

    if len(set(categories)) != len(categories):
        raise WeeklyExpenseError("Discord expense categories must not contain duplicates.")

    metadata_names = metadata["Category"]
    if metadata_names.duplicated().any():
        raise WeeklyExpenseError("The Categories sheet contains duplicate Category values.")

    category_types = metadata.set_index("Category")["Type"]
    for position, category in enumerate(categories, start=1):
        if not category or category != category.strip():
            raise WeeklyExpenseError(
                f"Discord expense category {position} must be a non-empty exact Category value."
            )
        if category not in category_types.index:
            raise WeeklyExpenseError(
                f"Discord expense category {position} was not found in the Categories sheet."
            )
        if category_types.loc[category] != "Expense":
            raise WeeklyExpenseError(
                f"Discord expense category {position} must have Type set to Expense."
            )


def calculate_weekly_report(
    transactions: pd.DataFrame,
    metadata: pd.DataFrame,
    categories: tuple[str, ...],
    period: ReportPeriod,
) -> WeeklyExpenseReport:
    """Calculate configured and all-expense totals for two adjacent weeks."""
    validate_selected_categories(categories, metadata)

    expense_rows = transactions[transactions["Type"] == "Expense"].copy()
    transaction_dates = expense_rows["Date"].dt.date
    current = expense_rows[transaction_dates.between(period.start, period.end)]
    previous = expense_rows[
        transaction_dates.between(period.comparison_start, period.comparison_end)
    ]

    uncategorized_rows = find_uncategorized_transactions(transactions)
    uncategorized_dates = uncategorized_rows["Date"].dt.date
    current_uncategorized = uncategorized_rows[
        uncategorized_dates.between(period.start, period.end)
    ]
    previous_uncategorized = uncategorized_rows[
        uncategorized_dates.between(period.comparison_start, period.comparison_end)
    ]

    category_totals = tuple(
        CategoryTotal(
            name=category,
            amount=_spending(current[current["Category"] == category]),
            previous_amount=_spending(previous[previous["Category"] == category]),
        )
        for category in categories
    )
    selected_total = _money(sum(item.amount for item in category_totals))
    previous_selected_total = _money(sum(item.previous_amount for item in category_totals))

    return WeeklyExpenseReport(
        period=period,
        categories=category_totals,
        selected_total=selected_total,
        previous_selected_total=previous_selected_total,
        all_expenses_total=_spending(current),
        uncategorized=UncategorizedTotal(
            amount=_spending(current_uncategorized),
            previous_amount=_spending(previous_uncategorized),
            count=len(current_uncategorized),
            previous_count=len(previous_uncategorized),
            outstanding_count=len(uncategorized_rows),
        ),
    )


def _spending(rows: pd.DataFrame) -> float:
    """Convert Tiller's signed expense amounts into net positive spending."""
    return _money(-float(rows["Amount"].sum()))


def _money(value: float) -> float:
    """Round a monetary value and remove negative zero."""
    rounded = round(value, 2)
    return 0.0 if rounded == 0 else rounded
