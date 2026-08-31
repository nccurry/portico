"""Pure calculations for single-entity year-over-year spending comparisons."""

import calendar
from typing import cast

import pandas as pd

from src.custom_types import YearOverYearSummary


HISTORY_COLUMNS = [
    "Year",
    "Year_Label",
    "Month",
    "Month_Label",
    "Spending",
    "Is_Current",
]
TOTAL_COLUMNS = ["Year", "Spending_Through_Month", "Change", "Change_Pct"]


def spending_entities(transactions: pd.DataFrame, dimension: str) -> list[str]:
    """Return sorted expense groups or categories available for comparison."""
    if dimension not in {"Group", "Category"}:
        raise ValueError(f"Unsupported year-over-year dimension: {dimension}")
    expenses = transactions[transactions["Type"].eq("Expense")]
    values = expenses[dimension].dropna().astype(str).str.strip()
    return sorted(value for value in values.unique() if value)


def utility_bill_categories(
    transactions: pd.DataFrame,
    *,
    group_terms: tuple[str, ...],
    category_terms: tuple[str, ...],
) -> list[str]:
    """Return utility categories ordered by total net spending."""
    expenses = transactions[transactions["Type"].eq("Expense")].copy()
    categories = expenses["Category"].fillna("").astype(str).str.strip()
    groups = expenses["Group"].fillna("").astype(str).str.strip()
    normalized_group_terms = tuple(term.casefold() for term in group_terms)
    normalized_category_terms = tuple(term.casefold() for term in category_terms)
    mask = groups.str.casefold().apply(
        lambda value: any(term in value for term in normalized_group_terms)
    ) & categories.str.casefold().apply(lambda value: any(term in value for term in normalized_category_terms))
    return _ordered_categories(expenses, categories, mask)


def discretionary_categories(
    transactions: pd.DataFrame,
    *,
    excluded_categories: tuple[str, ...],
    excluded_groups: tuple[str, ...],
) -> list[str]:
    """Return categories allowed by the discretionary spending policy."""
    expenses = transactions[transactions["Type"].eq("Expense")].copy()
    categories = expenses["Category"].fillna("").astype(str).str.strip()
    groups = expenses["Group"].fillna("").astype(str).str.strip()
    mask = ~categories.isin(excluded_categories) & ~groups.isin(excluded_groups) & groups.ne("Transfer")
    return _ordered_categories(expenses, categories, mask)


def _ordered_categories(
    expenses: pd.DataFrame,
    categories: pd.Series,
    mask: pd.Series,
) -> list[str]:
    """Order eligible categories by total net spending."""

    eligible = mask & categories.ne("")
    selected = expenses.loc[eligible].copy()
    selected["_Category"] = categories.loc[eligible]
    selected["_Spending"] = -pd.to_numeric(
        selected["Amount"],
        errors="coerce",
    )
    if selected.empty:
        return []
    totals = (
        selected.groupby("_Category", as_index=False)[["_Spending"]]
        .sum()
        .sort_values(
            ["_Spending", "_Category"],
            ascending=[False, True],
        )
    )
    return [str(value) for value in totals["_Category"]]


def _prepared_expenses(transactions: pd.DataFrame) -> pd.DataFrame:
    expenses = transactions[transactions["Type"].eq("Expense")].copy()
    expenses["Date"] = pd.to_datetime(
        expenses["Date"],
        errors="coerce",
        utc=True,
    ).dt.tz_convert(None)
    expenses["Amount"] = pd.to_numeric(expenses["Amount"], errors="coerce")
    expenses = expenses.dropna(subset=["Date", "Amount"])
    expenses["Year"] = expenses["Date"].dt.year
    expenses["Month_Number"] = expenses["Date"].dt.month
    expenses["Net_Spend"] = -expenses["Amount"].astype(float)
    return expenses


def build_year_over_year_history(
    transactions: pd.DataFrame,
    *,
    dimension: str,
    entity: str,
) -> pd.DataFrame:
    """Return comparable calendar-month spending lines for one entity.

    Months covered by the transaction dataset are zero-filled when the entity
    has no spending. Months before the dataset begins and future months after
    its latest transaction are omitted instead of being presented as zero.
    """
    if dimension not in {"Group", "Category"}:
        raise ValueError(f"Unsupported year-over-year dimension: {dimension}")

    coverage_dates = (
        pd.to_datetime(
            transactions["Date"],
            errors="coerce",
            utc=True,
        )
        .dt.tz_convert(None)
        .dropna()
    )
    expenses = _prepared_expenses(transactions)
    selected = expenses[expenses[dimension].astype(str).eq(entity)]
    if selected.empty or coverage_dates.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

    coverage_start = coverage_dates.min().to_period("M")
    coverage_end = coverage_dates.max().to_period("M")
    first_year = int(selected["Year"].min())
    current_year = coverage_end.year
    monthly = selected.groupby(["Year", "Month_Number"])["Net_Spend"].sum()

    rows = []
    for year in range(first_year, current_year + 1):
        for month in range(1, 13):
            period = pd.Period(year=year, month=month, freq="M")
            if coverage_start <= period <= coverage_end:
                rows.append(
                    {
                        "Year": year,
                        "Year_Label": str(year),
                        "Month": month,
                        "Month_Label": calendar.month_abbr[month],
                        "Spending": float(monthly.get((year, month), 0.0)),
                        "Is_Current": year == current_year,
                    }
                )
    return pd.DataFrame(rows, columns=HISTORY_COLUMNS)


def build_year_totals(
    history: pd.DataFrame,
    *,
    through_month: int,
) -> pd.DataFrame:
    """Return each year's spending through the same calendar month."""
    if history.empty:
        return pd.DataFrame(columns=TOTAL_COLUMNS)
    totals = (
        history[history["Month"] <= through_month]
        .groupby("Year", as_index=False)[["Spending"]]
        .sum()
        .rename(columns={"Spending": "Spending_Through_Month"})
        .sort_values("Year")
    )
    totals["Change"] = totals["Spending_Through_Month"].diff()
    prior = totals["Spending_Through_Month"].shift(1)
    totals["Change_Pct"] = totals["Change"].div(prior.abs()).mul(100)
    totals.loc[prior.eq(0), "Change_Pct"] = pd.NA
    return totals[TOTAL_COLUMNS].sort_values("Year", ascending=False).reset_index(drop=True)


def summarize_year_over_year(
    history: pd.DataFrame,
    *,
    through_month: int,
) -> YearOverYearSummary:
    """Return current-year and previous-year matched-period totals."""
    if history.empty:
        return YearOverYearSummary(
            current_year=0,
            current_total=0.0,
            previous_year=None,
            previous_total=None,
            change=None,
            change_pct=None,
            through_month=through_month,
        )
    current_year = int(history["Year"].max())
    totals = build_year_totals(history, through_month=through_month).set_index("Year")
    current_total = float(cast(float, totals.loc[current_year, "Spending_Through_Month"]))
    previous_year = current_year - 1
    if previous_year not in totals.index:
        return YearOverYearSummary(
            current_year=current_year,
            current_total=current_total,
            previous_year=None,
            previous_total=None,
            change=None,
            change_pct=None,
            through_month=through_month,
        )
    previous_total = float(cast(float, totals.loc[previous_year, "Spending_Through_Month"]))
    change = current_total - previous_total
    return YearOverYearSummary(
        current_year=current_year,
        current_total=current_total,
        previous_year=previous_year,
        previous_total=previous_total,
        change=change,
        change_pct=(change / abs(previous_total) * 100 if previous_total else None),
        through_month=through_month,
    )
