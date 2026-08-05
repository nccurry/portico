"""Budget comparison calculations shared by the Budget page and tests."""

from collections.abc import Sequence

import pandas as pd

from src.custom_types import BudgetFilters, BudgetSummary
from src.filters import apply_transaction_filters


def get_default_budget_groups(
    budget_df: pd.DataFrame,
    month_str: str,
    available_groups: Sequence[str],
) -> list[str]:
    """Return available expense groups with a positive budget for the month."""
    if budget_df.empty:
        return []
    monthly = budget_df[
        (budget_df["Month"] == month_str)
        & (budget_df["Type"] == "Expense")
        & (pd.to_numeric(budget_df["Budget"], errors="coerce").fillna(0) > 0)
    ]
    budgeted_groups = set(monthly["Group"].dropna())
    return [group for group in available_groups if group in budgeted_groups]


def _period_months(month_str: str, *, ytd: bool) -> list[str]:
    """Return the selected month or its year-to-date month range."""
    if not ytd:
        return [month_str]
    year, month = (int(part) for part in month_str.split("-"))
    return [f"{year}-{number:02d}" for number in range(1, month + 1)]


def _budget_rows(
    budget_df: pd.DataFrame,
    months: Sequence[str],
    filters: BudgetFilters,
    groups: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Filter budget rows to the selected period and analytical scope."""
    budgets = budget_df[budget_df["Month"].isin(months)].copy()
    budgets = budgets[budgets["Type"] == "Expense"]
    if groups is not None:
        budgets = budgets[budgets["Group"].isin(groups)]
    if filters.get("exclude_groups"):
        budgets = budgets[~budgets["Group"].isin(filters["exclude_groups"])]
    if filters.get("exclude_categories"):
        budgets = budgets[~budgets["Category"].isin(filters["exclude_categories"])]
    return budgets


def filter_budget_transactions(
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
    *,
    groups: Sequence[str] | None = None,
    ytd: bool = False,
) -> pd.DataFrame:
    """Return expense transactions used by a monthly or YTD budget view."""
    months = _period_months(month_str, ytd=ytd)
    transactions = transactions_df[transactions_df["Month"].isin(months)].copy()
    transactions = apply_transaction_filters(transactions, filters)
    transactions = transactions[transactions["Type"] == "Expense"]
    if groups is not None:
        transactions = transactions[transactions["Group"].isin(groups)]
    return transactions


def _budget_comparison(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
    *,
    ytd: bool,
) -> pd.DataFrame:
    """Compare category budgets and actuals for one period."""
    months = _period_months(month_str, ytd=ytd)
    budgets = _budget_rows(budget_df, months, filters)
    budgets = budgets.groupby(["Category", "Group", "Type"])["Budget"].sum().reset_index()
    transactions = filter_budget_transactions(
        transactions_df,
        month_str,
        filters,
        ytd=ytd,
    )

    actuals = (
        transactions.groupby("Category")["Amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"Amount": "Spent"})
    )

    result = budgets.merge(actuals, on="Category", how="outer")
    result["Budget"] = pd.to_numeric(result["Budget"], errors="coerce").fillna(0)
    result["Spent"] = pd.to_numeric(result["Spent"], errors="coerce").fillna(0)

    if not transactions.empty:
        metadata = transactions[["Category", "Group", "Type"]].drop_duplicates("Category")
        missing = result["Group"].isna()
        if missing.any():
            filled = result.loc[missing, ["Category"]].merge(metadata, on="Category", how="left")
            result.loc[missing, "Group"] = filled["Group"].values
            result.loc[missing, "Type"] = filled["Type"].values

    result["Remaining"] = result["Budget"] - result["Spent"]
    result["Pct_Used"] = _pct_used(result["Spent"], result["Budget"])

    if not filters.get("show_zero_budget", False):
        result = result[result["Budget"] > 0]

    return result.sort_values("Pct_Used", ascending=False).reset_index(drop=True)


def _group_budget_comparison(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
    groups: Sequence[str],
    *,
    ytd: bool,
) -> pd.DataFrame:
    """Compare group budgets to all group spending, including unbudgeted categories."""
    months = _period_months(month_str, ytd=ytd)
    budgets = _budget_rows(budget_df, months, filters, groups)
    budgets = budgets.groupby("Group")["Budget"].sum().reset_index()
    transactions = filter_budget_transactions(
        transactions_df,
        month_str,
        filters,
        groups=groups,
        ytd=ytd,
    )
    actuals = (
        transactions.groupby("Group")["Amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"Amount": "Spent"})
    )

    selected_groups = pd.DataFrame({"Group": list(groups)})
    result = selected_groups.merge(budgets, on="Group", how="left").merge(actuals, on="Group", how="left")
    for column in ["Budget", "Spent"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0).astype(float)
    result["Remaining"] = result["Budget"] - result["Spent"]
    result["Pct_Used"] = _pct_used(result["Spent"], result["Budget"])
    return result.sort_values("Pct_Used", ascending=False).reset_index(drop=True)


def _pct_used(spent: pd.Series, budget: pd.Series) -> pd.Series:
    """Return percent-used values, using infinity for unbudgeted spending."""
    result = pd.Series(0.0, index=spent.index)
    budgeted = budget > 0
    result.loc[budgeted] = spent.loc[budgeted] / budget.loc[budgeted] * 100
    result.loc[(~budgeted) & (spent > 0)] = float("inf")
    return result


def get_budget_vs_actual(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
) -> pd.DataFrame:
    """Compare monthly category budgets to actual spending."""
    return _budget_comparison(budget_df, transactions_df, month_str, filters, ytd=False)


def get_ytd_budget_vs_actual(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
) -> pd.DataFrame:
    """Compare YTD category budgets to actual spending."""
    return _budget_comparison(budget_df, transactions_df, month_str, filters, ytd=True)


def get_group_budget_vs_actual(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
    groups: Sequence[str],
) -> pd.DataFrame:
    """Compare monthly group budgets to all actual spending in those groups."""
    return _group_budget_comparison(
        budget_df,
        transactions_df,
        month_str,
        filters,
        groups,
        ytd=False,
    )


def get_ytd_group_budget_vs_actual(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
    groups: Sequence[str],
) -> pd.DataFrame:
    """Compare YTD group budgets to all actual spending in those groups."""
    return _group_budget_comparison(
        budget_df,
        transactions_df,
        month_str,
        filters,
        groups,
        ytd=True,
    )


def get_trailing_group_guidance(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
    groups: Sequence[str],
    *,
    lookback_months: int = 12,
) -> pd.DataFrame:
    """Compare current targets with average spending in prior complete months."""
    selected_period = pd.Period(month_str, freq="M")
    periods = pd.period_range(end=selected_period - 1, periods=lookback_months, freq="M")
    months = periods.astype(str).tolist()

    budgets = _budget_rows(budget_df, [month_str], filters, groups)
    targets = budgets.groupby("Group")["Budget"].sum().rename("Monthly_Target")

    transactions = transactions_df[transactions_df["Month"].isin(months)].copy()
    transactions = apply_transaction_filters(transactions, filters)
    transactions = transactions[
        (transactions["Type"] == "Expense") & transactions["Group"].isin(groups)
    ]
    averages = (
        transactions.groupby("Group")["Amount"].sum().abs().div(lookback_months).rename("Monthly_Average")
    )

    result = pd.DataFrame({"Group": list(groups)}).set_index("Group")
    result = result.join(targets).join(averages).fillna(0.0).reset_index()
    result["Monthly_Reduction"] = result["Monthly_Average"] - result["Monthly_Target"]
    result["Annualized_Reduction"] = result["Monthly_Reduction"] * 12
    return result.sort_values("Monthly_Reduction", ascending=False).reset_index(drop=True)


def build_group_budget_table(
    gross_monthly: pd.DataFrame,
    adjusted_monthly: pd.DataFrame,
    gross_ytd: pd.DataFrame,
    adjusted_ytd: pd.DataFrame,
) -> pd.DataFrame:
    """Combine gross and adjusted monthly/YTD group results for display."""
    monthly = gross_monthly[["Group", "Budget", "Spent"]].rename(
        columns={"Budget": "Monthly_Budget", "Spent": "Monthly_Gross"}
    )
    monthly_adjusted = adjusted_monthly[["Group", "Spent"]].rename(columns={"Spent": "Monthly_Adjusted"})
    ytd = gross_ytd[["Group", "Budget", "Spent"]].rename(
        columns={"Budget": "YTD_Budget", "Spent": "YTD_Gross"}
    )
    ytd_adjusted = adjusted_ytd[["Group", "Spent"]].rename(columns={"Spent": "YTD_Adjusted"})

    result = monthly.merge(monthly_adjusted, on="Group", how="outer")
    result = result.merge(ytd, on="Group", how="outer").merge(ytd_adjusted, on="Group", how="outer")
    numeric_columns = [column for column in result.columns if column != "Group"]
    result[numeric_columns] = result[numeric_columns].fillna(0.0)
    result["Monthly_Excluded"] = result["Monthly_Gross"] - result["Monthly_Adjusted"]
    result["YTD_Excluded"] = result["YTD_Gross"] - result["YTD_Adjusted"]
    result["Monthly_Pct"] = _pct_used(result["Monthly_Adjusted"], result["Monthly_Budget"])
    result["YTD_Pct"] = _pct_used(result["YTD_Adjusted"], result["YTD_Budget"])
    return result.sort_values("YTD_Pct", ascending=False).reset_index(drop=True)


def build_unified_budget_table(
    monthly_df: pd.DataFrame,
    ytd_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge monthly and YTD category comparisons into one display table."""
    monthly = monthly_df[["Category", "Group", "Budget", "Spent", "Pct_Used"]].rename(
        columns={"Budget": "Mo_Budget", "Spent": "Mo_Spent", "Pct_Used": "Mo_Pct"}
    )
    ytd = ytd_df[["Category", "Budget", "Spent", "Pct_Used"]].rename(
        columns={"Budget": "YTD_Budget", "Spent": "YTD_Spent", "Pct_Used": "YTD_Pct"}
    )

    merged = monthly.merge(ytd, on="Category", how="outer")
    for column in ["Mo_Budget", "Mo_Spent", "Mo_Pct", "YTD_Budget", "YTD_Spent", "YTD_Pct"]:
        merged[column] = merged[column].fillna(0)
    merged["Group"] = merged["Group"].fillna("")
    return merged.sort_values("Mo_Pct", ascending=False).reset_index(drop=True)


def calculate_projected_spend(spent: float, days_elapsed: int, days_in_month: int) -> float:
    """Project end-of-month spend based on current pace."""
    if days_elapsed <= 0:
        return 0.0
    return spent / days_elapsed * days_in_month


def summarize_budget(comparison: pd.DataFrame) -> BudgetSummary:
    """Return aggregate budget, spending, remaining, and utilization."""
    budget = float(comparison["Budget"].sum()) if not comparison.empty else 0.0
    spent = float(comparison["Spent"].sum()) if not comparison.empty else 0.0
    return BudgetSummary(
        budget=budget,
        spent=spent,
        remaining=budget - spent,
        pct_used=spent / budget * 100 if budget > 0 else 0.0,
    )


def calculate_category_projections(
    comparison: pd.DataFrame,
    days_elapsed: int,
    days_in_month: int,
) -> pd.DataFrame:
    """Return budgeted categories with projected end-of-month spending."""
    budgeted = comparison[comparison["Budget"] > 0][["Category", "Budget", "Spent"]].copy()
    budgeted["Projected"] = budgeted["Spent"].apply(
        lambda spent: calculate_projected_spend(float(spent), days_elapsed, days_in_month)
    )
    budgeted["Over_Budget"] = budgeted["Projected"] > budgeted["Budget"]
    return budgeted
