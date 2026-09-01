"""Budget comparison calculations shared by the Budget page and tests."""

from collections.abc import Sequence
from typing import Literal, cast

import pandas as pd

from src.custom_types import BudgetFilters, BudgetSummary
from src.filters import apply_transaction_filters

type BudgetDimension = Literal["Group", "Category"]

BUDGET_HISTORY_COLUMNS = [
    "Month",
    "Entity",
    "Budget",
    "Tracked_Spent",
    "Outside_Plan",
    "Spent",
]
BUDGET_PERFORMANCE_COLUMNS = [
    "Entity",
    "Budget",
    "Tracked_Spent",
    "Outside_Plan",
    "Spent",
    "Remaining",
    "Pct_Used",
    "Typical_Spend",
    "Vs_Typical",
    "Budget_Variance",
    "Months_Within_Budget",
    "Months_Budgeted",
    "Success_Rate",
    "Trend",
]


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


def build_budget_history(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: BudgetFilters,
    groups: Sequence[str],
    *,
    dimension: BudgetDimension = "Group",
    lookback_months: int = 12,
) -> pd.DataFrame:
    """Return complete monthly budget and spending history for one scope."""
    selected_period = pd.Period(month_str, freq="M")
    excluded_groups = set(filters.get("exclude_groups", []))
    effective_groups = [group for group in groups if group not in excluded_groups]
    if not effective_groups:
        return pd.DataFrame(columns=BUDGET_HISTORY_COLUMNS)

    observed_months = pd.concat(
        [
            budget_df.loc[budget_df["Group"].isin(effective_groups), "Month"],
            transactions_df.loc[transactions_df["Group"].isin(effective_groups), "Month"],
        ],
        ignore_index=True,
    ).dropna()
    observed_periods = [
        period for period in pd.PeriodIndex(observed_months.astype(str), freq="M") if period <= selected_period
    ]
    requested_start = selected_period - lookback_months
    history_start = max(requested_start, min(observed_periods)) if observed_periods else selected_period
    periods = pd.period_range(start=history_start, end=selected_period, freq="M")
    months = periods.astype(str).tolist()

    budgets = _budget_rows(budget_df, months, filters, effective_groups).copy()
    budgets["Budget"] = pd.to_numeric(budgets["Budget"], errors="coerce").fillna(0.0)
    budgets["Entity"] = budgets[dimension].astype(str)
    budget_totals = budgets.groupby(["Month", "Entity"], dropna=False)["Budget"].sum().reset_index()
    tracked_categories = budgets.loc[
        budgets["Budget"] > 0,
        ["Month", "Category"],
    ].drop_duplicates()
    tracked_categories["Tracked"] = True

    transactions = transactions_df[transactions_df["Month"].isin(months)].copy()
    transactions = apply_transaction_filters(transactions, filters)
    transactions = transactions[
        transactions["Type"].eq("Expense") & transactions["Group"].isin(effective_groups)
    ].copy()
    transactions["Entity"] = transactions[dimension].astype(str)
    transactions["Net_Spend"] = -pd.to_numeric(transactions["Amount"], errors="coerce").fillna(0.0)
    transactions = transactions.merge(
        tracked_categories,
        on=["Month", "Category"],
        how="left",
    )
    is_tracked = transactions["Tracked"].fillna(False).astype(bool)
    transactions["Tracked_Spent"] = transactions["Net_Spend"].where(is_tracked, 0.0)
    transactions["Outside_Plan"] = transactions["Net_Spend"].where(~is_tracked, 0.0)
    actuals = (
        transactions.groupby(["Month", "Entity"], dropna=False)[["Tracked_Spent", "Outside_Plan"]].sum().reset_index()
    )

    if dimension == "Group":
        entities = effective_groups
    else:
        current_budget_entities = budgets.loc[budgets["Month"].eq(month_str), "Entity"]
        current_spending_entities = transactions.loc[transactions["Month"].eq(month_str), "Entity"]
        entities = sorted(set(current_budget_entities) | set(current_spending_entities))
    if not entities:
        return pd.DataFrame(columns=BUDGET_HISTORY_COLUMNS)

    grid = pd.MultiIndex.from_product([months, entities], names=["Month", "Entity"]).to_frame(index=False)
    history = grid.merge(budget_totals, on=["Month", "Entity"], how="left").merge(
        actuals, on=["Month", "Entity"], how="left"
    )
    numeric_columns = ["Budget", "Tracked_Spent", "Outside_Plan"]
    history[numeric_columns] = history[numeric_columns].fillna(0.0).astype(float)
    history["Spent"] = history["Tracked_Spent"] + history["Outside_Plan"]
    return history[BUDGET_HISTORY_COLUMNS]


def build_budget_performance(
    history: pd.DataFrame,
    month_str: str,
) -> pd.DataFrame:
    """Summarize current budget performance against trailing complete months."""
    if history.empty:
        return pd.DataFrame(columns=BUDGET_PERFORMANCE_COLUMNS)

    current = history[history["Month"].eq(month_str)].copy()
    prior = history[history["Month"].lt(month_str)].copy()
    records: list[dict[str, object]] = []
    for row in current.itertuples(index=False):
        entity = str(row.Entity)
        entity_history = prior[prior["Entity"].eq(entity)]
        budgeted = entity_history[entity_history["Budget"] > 0]
        months_budgeted = len(budgeted)
        months_within = int((budgeted["Spent"] <= budgeted["Budget"]).sum())
        typical = float(entity_history["Spent"].median()) if not entity_history.empty else 0.0
        budget = float(cast(float, row.Budget))
        spent = float(cast(float, row.Spent))
        records.append(
            {
                "Entity": entity,
                "Budget": budget,
                "Tracked_Spent": float(cast(float, row.Tracked_Spent)),
                "Outside_Plan": float(cast(float, row.Outside_Plan)),
                "Spent": spent,
                "Remaining": budget - spent,
                "Pct_Used": spent / budget * 100 if budget > 0 else float("inf"),
                "Typical_Spend": typical,
                "Vs_Typical": spent - typical,
                "Budget_Variance": spent - budget,
                "Months_Within_Budget": months_within,
                "Months_Budgeted": months_budgeted,
                "Success_Rate": (months_within / months_budgeted * 100 if months_budgeted else float("nan")),
                "Trend": [*entity_history["Spent"].tolist(), spent],
            }
        )
    return (
        pd.DataFrame(records, columns=BUDGET_PERFORMANCE_COLUMNS)
        .sort_values(["Spent", "Entity"], ascending=[False, True])
        .reset_index(drop=True)
    )


def summarize_budget_history(
    history: pd.DataFrame,
    month_str: str,
) -> dict[str, float]:
    """Return a reconciled pulse for the selected month and scope."""
    current = history[history["Month"].eq(month_str)]
    prior = history[history["Month"].lt(month_str)]
    budget = float(current["Budget"].sum())
    tracked = float(current["Tracked_Spent"].sum())
    outside = float(current["Outside_Plan"].sum())
    spent = tracked + outside
    typical = float(prior.groupby("Month")["Spent"].sum().median()) if not prior.empty else 0.0
    return {
        "budget": budget,
        "tracked_spent": tracked,
        "outside_plan": outside,
        "spent": spent,
        "remaining": budget - spent,
        "pct_used": spent / budget * 100 if budget > 0 else 0.0,
        "typical_spend": typical,
        "vs_typical": spent - typical,
    }


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
    actuals = transactions.groupby("Group")["Amount"].sum().abs().reset_index().rename(columns={"Amount": "Spent"})

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
