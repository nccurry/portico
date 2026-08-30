"""Weekly expense report calculations for Discord notifications."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

import pandas as pd

from src.analysis.data_health import find_uncategorized_transactions
from src.analysis.merchants import normalize_merchant_name


AVERAGE_WEEKS = 8
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

    @property
    def rolling_start(self) -> dt.date:
        """Return the start of the four weeks ending with this report."""
        return self.end - dt.timedelta(days=(ROLLING_WEEKS * 7) - 1)

    @property
    def previous_rolling_start(self) -> dt.date:
        """Return the start of the preceding four-week comparison."""
        return self.rolling_start - dt.timedelta(days=ROLLING_WEEKS * 7)

    @property
    def previous_rolling_end(self) -> dt.date:
        """Return the end of the preceding four-week comparison."""
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
        """Return the dollar change from the preceding four weeks."""
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

    @property
    def selected_change(self) -> float:
        """Return the selected-category change from the usual weekly amount."""
        return _money(self.selected_total - self.average_selected_total)

    @property
    def rolling_selected_change(self) -> float:
        """Return the watched-total change from the preceding four weeks."""
        return _money(self.rolling_selected_total - self.previous_rolling_selected_total)


def completed_week(today: dt.date, period_end: dt.date | None = None) -> ReportPeriod:
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
    comparison_start = comparison_end - dt.timedelta(days=(AVERAGE_WEEKS * 7) - 1)
    return ReportPeriod(start, end, comparison_start, comparison_end)


def validate_selected_categories(categories: tuple[str, ...], metadata: pd.DataFrame) -> None:
    """Check that configured categories are unique expense categories."""
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
            raise WeeklyExpenseError(f"Discord expense category {position} must be a non-empty exact Category value.")
        if category not in category_types.index:
            raise WeeklyExpenseError(f"Discord expense category {position} was not found in the Categories sheet.")
        if category_types.loc[category] != "Expense":
            raise WeeklyExpenseError(f"Discord expense category {position} must have Type set to Expense.")


def calculate_weekly_report(
    transactions: pd.DataFrame,
    metadata: pd.DataFrame,
    categories: tuple[str, ...],
    period: ReportPeriod,
) -> WeeklyExpenseReport:
    """Calculate weekly spending, averages, and four-week comparisons."""
    validate_selected_categories(categories, metadata)

    expense_rows = transactions[transactions["Type"] == "Expense"].copy()
    transaction_dates = expense_rows["Date"].dt.date
    current = expense_rows[transaction_dates.between(period.start, period.end)]
    comparison = expense_rows[transaction_dates.between(period.comparison_start, period.comparison_end)]
    rolling = expense_rows[transaction_dates.between(period.rolling_start, period.end)]
    previous_rolling = expense_rows[
        transaction_dates.between(period.previous_rolling_start, period.previous_rolling_end)
    ]

    category_totals = []
    for category in categories:
        current_rows = current[current["Category"] == category]
        comparison_rows = comparison[comparison["Category"] == category]
        rolling_rows = rolling[rolling["Category"] == category]
        previous_rolling_rows = previous_rolling[previous_rolling["Category"] == category]
        category_totals.append(
            CategoryTotal(
                name=category,
                amount=_spending(current_rows),
                average_amount=_average_weekly_spending(comparison_rows),
                rolling_amount=_spending(rolling_rows),
                previous_rolling_amount=_spending(previous_rolling_rows),
                top_vendors=_top_vendors(current_rows),
            )
        )
    category_totals_tuple = tuple(category_totals)
    selected_total = _money(sum(item.amount for item in category_totals_tuple))
    selected_comparison = comparison[comparison["Category"].isin(categories)]
    average_selected_total = _average_weekly_spending(selected_comparison)
    rolling_selected_total = _spending(rolling[rolling["Category"].isin(categories)])
    previous_rolling_selected_total = _spending(previous_rolling[previous_rolling["Category"].isin(categories)])

    return WeeklyExpenseReport(
        period=period,
        categories=category_totals_tuple,
        selected_total=selected_total,
        average_selected_total=average_selected_total,
        rolling_selected_total=rolling_selected_total,
        previous_rolling_selected_total=previous_rolling_selected_total,
        all_expenses_total=_spending(current),
        uncategorized_count=len(find_uncategorized_transactions(transactions)),
    )


def _spending(rows: pd.DataFrame) -> float:
    """Convert signed expense amounts into net positive spending."""
    return _money(-float(rows["Amount"].sum()))


def _average_weekly_spending(rows: pd.DataFrame) -> float:
    """Return average spending across the fixed trailing week window."""
    return _money(_spending(rows) / AVERAGE_WEEKS)


def _top_vendors(rows: pd.DataFrame) -> tuple[VendorTotal, ...]:
    """Return the largest positive net vendor totals for the current week."""
    if rows.empty:
        return ()

    vendors = rows.assign(Vendor=rows["Full Description"].map(normalize_merchant_name))
    totals = vendors.groupby("Vendor", as_index=False)["Amount"].sum()
    totals["Amount"] = -totals["Amount"]
    totals = totals[totals["Amount"] > 0].sort_values(["Amount", "Vendor"], ascending=[False, True])
    return tuple(
        VendorTotal(name=str(row.Vendor), amount=_money(float(row.Amount)))
        for row in totals.head(TOP_VENDOR_COUNT).itertuples(index=False)
    )


def _money(value: float) -> float:
    """Round a monetary value and remove negative zero."""
    rounded = round(value, 2)
    return 0.0 if rounded == 0 else rounded
