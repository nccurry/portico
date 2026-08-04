"""Budget comparison calculations shared by the Budget page and tests."""

from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.custom_types import BudgetSummary
from src.filters import apply_transaction_filters


def _budget_comparison(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: Mapping[str, Any],
    *,
    ytd: bool,
) -> pd.DataFrame:
    year = month_str.split("-")[0]
    month_num = int(month_str.split("-")[1])

    if ytd:
        budgets = budget_df[budget_df["Month_Num"].between(1, month_num)].copy()
        budgets = budgets.groupby(["Category", "Group", "Type"])["Budget"].sum().reset_index()
        months = [f"{year}-{m:02d}" for m in range(1, month_num + 1)]
        txns = transactions_df[transactions_df["Month"].isin(months)].copy()
    else:
        budgets = budget_df[budget_df["Month_Num"] == month_num][
            ["Category", "Group", "Type", "Budget"]
        ].copy()
        txns = transactions_df[transactions_df["Month"] == month_str].copy()

    txns = apply_transaction_filters(txns, filters)
    txns = txns[txns["Type"] == "Expense"]

    actuals = (
        txns.groupby("Category")["Amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"Amount": "Spent"})
    )

    result = budgets.merge(actuals, on="Category", how="outer")
    result["Budget"] = pd.to_numeric(result["Budget"], errors="coerce").fillna(0)
    result["Spent"] = pd.to_numeric(result["Spent"], errors="coerce").fillna(0)

    if not txns.empty:
        txn_meta = txns[["Category", "Group", "Type"]].drop_duplicates("Category")
        missing = result["Group"].isna()
        if missing.any():
            filled = result.loc[missing, ["Category"]].merge(txn_meta, on="Category", how="left")
            result.loc[missing, "Group"] = filled["Group"].values
            result.loc[missing, "Type"] = filled["Type"].values

    if filters.get("exclude_groups"):
        result = result[~result["Group"].isin(filters["exclude_groups"])]
    if filters.get("exclude_categories"):
        result = result[~result["Category"].isin(filters["exclude_categories"])]

    result["Remaining"] = result["Budget"] - result["Spent"]
    result["Pct_Used"] = _pct_used(result["Spent"], result["Budget"])

    if not filters.get("show_zero_budget", False):
        result = result[(result["Budget"] > 0) | (result["Spent"] > 0)]
        result = result[result["Budget"] > 0]

    return result.sort_values("Pct_Used", ascending=False).reset_index(drop=True)


def _pct_used(spent: pd.Series, budget: pd.Series) -> pd.Series:
    """Return percent-used values, using inf for unbudgeted spending."""
    result = pd.Series(0.0, index=spent.index)
    budgeted = budget > 0
    result.loc[budgeted] = spent.loc[budgeted] / budget.loc[budgeted] * 100
    result.loc[(~budgeted) & (spent > 0)] = float("inf")
    return result


def get_budget_vs_actual(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: Mapping[str, Any],
) -> pd.DataFrame:
    """Compare monthly budget to actual spending for ``month_str``."""
    return _budget_comparison(budget_df, transactions_df, month_str, filters, ytd=False)


def get_ytd_budget_vs_actual(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: Mapping[str, Any],
) -> pd.DataFrame:
    """Compare YTD cumulative budget to actual spending through ``month_str``."""
    return _budget_comparison(budget_df, transactions_df, month_str, filters, ytd=True)


def build_unified_budget_table(
    monthly_df: pd.DataFrame,
    ytd_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge monthly and YTD budget comparisons into one display table."""
    monthly = monthly_df[["Category", "Group", "Budget", "Spent", "Pct_Used"]].rename(
        columns={"Budget": "Mo_Budget", "Spent": "Mo_Spent", "Pct_Used": "Mo_Pct"}
    )
    ytd = ytd_df[["Category", "Budget", "Spent", "Pct_Used"]].rename(
        columns={"Budget": "YTD_Budget", "Spent": "YTD_Spent", "Pct_Used": "YTD_Pct"}
    )

    merged = monthly.merge(ytd, on="Category", how="outer")

    for col in ["Mo_Budget", "Mo_Spent", "Mo_Pct", "YTD_Budget", "YTD_Spent", "YTD_Pct"]:
        merged[col] = merged[col].fillna(0)
    merged["Group"] = merged["Group"].fillna("")

    return merged.sort_values("Mo_Pct", ascending=False).reset_index(drop=True)


def calculate_projected_spend(
    spent: float,
    days_elapsed: int,
    days_in_month: int,
) -> float:
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
    budgeted = comparison[comparison["Budget"] > 0][
        ["Category", "Budget", "Spent"]
    ].copy()
    budgeted["Projected"] = budgeted["Spent"].apply(
        lambda spent: calculate_projected_spend(
            float(spent),
            days_elapsed,
            days_in_month,
        )
    )
    budgeted["Over_Budget"] = budgeted["Projected"] > budgeted["Budget"]
    return budgeted
