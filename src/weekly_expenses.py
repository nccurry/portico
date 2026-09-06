"""Weekly expense report calculations for Discord notifications."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from src.analysis.data_health import find_uncategorized_transactions
from src.analysis.merchants import normalize_merchant_name
from src.config import TransactionSetSettings
from src.transaction_sets import transaction_set_mask

AVERAGE_WEEKS = 48
ROLLING_WEEKS = 4
TOP_VENDOR_COUNT = 3


class WeeklyExpenseError(ValueError):
    """Raised when report configuration or source data is invalid."""


@dataclass(frozen=True)
class ReportPeriod:
    """Current week and its comparison windows."""

    start: dt.date
    end: dt.date
    comparison_start: dt.date
    comparison_end: dt.date
    average_weeks: int = AVERAGE_WEEKS
    rolling_weeks: int = ROLLING_WEEKS

    @property
    def rolling_start(self) -> dt.date:
        """Return the start of the rolling window ending with this report."""
        return self.end - dt.timedelta(days=(self.rolling_weeks * 7) - 1)

    @property
    def previous_rolling_start(self) -> dt.date:
        """Return the start of the preceding rolling window."""
        return self.rolling_start - dt.timedelta(days=self.rolling_weeks * 7)

    @property
    def previous_rolling_end(self) -> dt.date:
        """Return the end of the preceding rolling window."""
        return self.rolling_start - dt.timedelta(days=1)


@dataclass(frozen=True)
class VendorTotal:
    """Current-week spending for one vendor."""

    name: str
    amount: float


@dataclass(frozen=True)
class CategoryTotal:
    """Weekly and rolling spending for one category."""

    name: str
    amount: float
    average_amount: float
    rolling_amount: float
    previous_rolling_amount: float
    top_vendors: tuple[VendorTotal, ...] = ()

    @property
    def change(self) -> float:
        """Return the dollar change from the usual weekly amount."""
        return _money(self.amount - self.average_amount)

    @property
    def rolling_change(self) -> float:
        """Return the dollar change from the preceding rolling window."""
        return _money(self.rolling_amount - self.previous_rolling_amount)


@dataclass(frozen=True)
class WeeklyExpenseReport:
    """Values shown in one weekly Discord summary."""

    period: ReportPeriod
    categories: tuple[CategoryTotal, ...]
    selected_total: float
    average_selected_total: float
    rolling_selected_total: float
    previous_rolling_selected_total: float
    all_expenses_total: float
    uncategorized_count: int
    uncategorized_total: float

    @property
    def selected_change(self) -> float:
        """Return the selected-category change from the usual weekly amount."""
        return _money(self.selected_total - self.average_selected_total)

    @property
    def rolling_selected_change(self) -> float:
        """Return the watched-total change from the preceding rolling window."""
        return _money(self.rolling_selected_total - self.previous_rolling_selected_total)


def completed_week(
    today: dt.date,
    period_end: dt.date | None = None,
    *,
    average_weeks: int = AVERAGE_WEEKS,
    rolling_weeks: int = ROLLING_WEEKS,
) -> ReportPeriod:
    """Return a completed week and its trailing average window."""
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
    if average_weeks < 1 or rolling_weeks < 1:
        raise WeeklyExpenseError("Weekly summary windows must be at least one week.")
    comparison_start = comparison_end - dt.timedelta(days=(average_weeks * 7) - 1)
    return ReportPeriod(start, end, comparison_start, comparison_end, average_weeks, rolling_weeks)


def calculate_weekly_report(
    transactions: pd.DataFrame,
    transaction_sets: Sequence[TransactionSetSettings],
    watched_transaction_sets: Sequence[str],
    period: ReportPeriod,
    *,
    top_merchant_count: int = TOP_VENDOR_COUNT,
    merchant_aliases: Mapping[str, str] | None = None,
) -> WeeklyExpenseReport:
    """Calculate weekly spending, averages, and rolling comparisons."""
    if not watched_transaction_sets:
        raise WeeklyExpenseError("Configure at least one watched transaction set.")

    expense_rows = transactions[transactions["Type"] == "Expense"].copy()
    watched_mask = pd.Series(False, index=expense_rows.index, dtype="bool")
    try:
        for transaction_set_key in watched_transaction_sets:
            watched_mask |= transaction_set_mask(
                expense_rows,
                transaction_set_key=transaction_set_key,
                transaction_sets=transaction_sets,
                aliases=merchant_aliases,
            )
    except ValueError as error:
        raise WeeklyExpenseError(str(error)) from error

    uncategorized_rows = find_uncategorized_transactions(transactions)
    uncategorized_mask = pd.Series(
        expense_rows.index.isin(uncategorized_rows.index),
        index=expense_rows.index,
        dtype="bool",
    )
    watched_rows = expense_rows[watched_mask & ~uncategorized_mask].copy()
    watched_dates = watched_rows["Date"].dt.date
    current = watched_rows[watched_dates.between(period.start, period.end)]
    comparison = watched_rows[watched_dates.between(period.comparison_start, period.comparison_end)]
    rolling = watched_rows[watched_dates.between(period.rolling_start, period.end)]
    previous_rolling = watched_rows[watched_dates.between(period.previous_rolling_start, period.previous_rolling_end)]

    category_amounts = [
        (str(category), _money(-float(amount)))
        for category, amount in current.groupby("Category")["Amount"].sum().items()
    ]
    category_amounts = [(category, amount) for category, amount in category_amounts if amount != 0]
    category_amounts.sort(key=lambda item: (-item[1], item[0]))
    category_totals = []
    for category, _ in category_amounts:
        current_rows = current[current["Category"] == category]
        comparison_rows = comparison[comparison["Category"] == category]
        rolling_rows = rolling[rolling["Category"] == category]
        previous_rolling_rows = previous_rolling[previous_rolling["Category"] == category]
        category_totals.append(
            CategoryTotal(
                name=category,
                amount=_spending(current_rows),
                average_amount=_average_weekly_spending(comparison_rows, period.average_weeks),
                rolling_amount=_spending(rolling_rows),
                previous_rolling_amount=_spending(previous_rolling_rows),
                top_vendors=_top_vendors(current_rows, top_merchant_count, aliases=merchant_aliases),
            )
        )
    category_totals_tuple = tuple(category_totals)
    expense_dates = expense_rows["Date"].dt.date
    current_expenses = expense_rows[expense_dates.between(period.start, period.end)]

    return WeeklyExpenseReport(
        period=period,
        categories=category_totals_tuple,
        selected_total=_spending(current),
        average_selected_total=_average_weekly_spending(comparison, period.average_weeks),
        rolling_selected_total=_spending(rolling),
        previous_rolling_selected_total=_spending(previous_rolling),
        all_expenses_total=_spending(current_expenses),
        uncategorized_count=len(uncategorized_rows),
        uncategorized_total=_money(float(uncategorized_rows["Amount"].abs().sum())),
    )


def _spending(rows: pd.DataFrame) -> float:
    """Convert signed expense amounts into net positive spending."""
    return _money(-float(rows["Amount"].sum()))


def _average_weekly_spending(rows: pd.DataFrame, weeks: int) -> float:
    """Return average spending across the trailing week window."""
    return _money(_spending(rows) / weeks)


def _top_vendors(
    rows: pd.DataFrame,
    count: int,
    *,
    aliases: Mapping[str, str] | None = None,
) -> tuple[VendorTotal, ...]:
    """Return the largest positive net vendor totals for the current week."""
    if rows.empty:
        return ()

    vendors = rows.assign(
        Vendor=rows["Full Description"].map(lambda description: normalize_merchant_name(description, aliases=aliases))
    )
    totals = vendors.groupby("Vendor", as_index=False)["Amount"].sum()
    totals["Amount"] = -totals["Amount"]
    totals = totals[totals["Amount"] > 0].sort_values(["Amount", "Vendor"], ascending=[False, True])
    return tuple(
        VendorTotal(name=str(row.Vendor), amount=_money(float(row.Amount)))
        for row in totals.head(count).itertuples(index=False)
    )


def _money(value: float) -> float:
    """Round a monetary value and remove negative zero."""
    rounded = round(value, 2)
    return 0.0 if rounded == 0 else rounded
