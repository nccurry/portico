"""Pure calculations for interactive spending exploration."""

from collections.abc import Sequence

import pandas as pd

from src.analysis.merchants import normalize_merchant_name
from src.custom_types import SpendingFilters, SpendingSummary


OVERVIEW_COLUMNS = [
    "Entity",
    "Group",
    "Spending",
    "Share",
    "Average_Monthly",
    "Comparison_Spending",
    "Change",
    "Change_Pct",
    "Transactions",
    "Monthly_Trend",
]
MERCHANT_COLUMNS = [
    "Merchant",
    "Spending",
    "Share",
    "Transactions",
    "Average_Transaction",
    "Last_Transaction",
]
MONTHLY_COMPARISON_COLUMNS = [
    "Month",
    "Comparison_Month",
    "Current_Spend",
    "Comparison_Spend",
]


def _append_reason(reasons: list[str], condition: bool, message: str) -> None:
    if condition:
        reasons.append(message)


def _spending_exclusion_reason(
    *,
    group: str,
    category: str,
    amount: float,
    filters: SpendingFilters,
) -> str:
    reasons: list[str] = []
    include_groups = set(filters.get("include_groups", ()))
    include_categories = set(filters.get("include_categories", ()))
    include_mode = bool(include_groups or include_categories)

    _append_reason(reasons, group == "Transfer", "Transfer group")
    if include_mode:
        _append_reason(
            reasons,
            group not in include_groups and category not in include_categories,
            "Outside included groups/categories",
        )
    else:
        _append_reason(
            reasons,
            group in filters.get("exclude_groups", ()),
            f"Excluded group: {group}",
        )
        _append_reason(
            reasons,
            category in filters.get("exclude_categories", ()),
            f"Excluded category: {category}",
        )

    if filters.get("filter_large_expenses"):
        threshold = float(filters["expense_threshold"])
        _append_reason(
            reasons,
            abs(amount) > threshold,
            f"Expense over ${threshold:,.0f}",
        )
    return "; ".join(reasons)


def build_spending_ledger(
    transactions: pd.DataFrame,
    filters: SpendingFilters,
    *,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    """Return period expense rows annotated with inclusion and net spending.

    ``start_month`` is inclusive and ``end_month`` is exclusive. Purchases have
    positive ``Net_Spend`` values; positive expense refunds reduce spending.
    """
    ledger = transactions[transactions["Type"] == "Expense"].copy()
    ledger = ledger[
        (ledger["Month"].astype(str) >= start_month)
        & (ledger["Month"].astype(str) < end_month)
    ].copy()

    if ledger.empty:
        ledger["Included"] = pd.Series(dtype="bool")
        ledger["Exclusion_Reason"] = pd.Series(dtype="string")
        ledger["Net_Spend"] = pd.Series(dtype="float64")
        return ledger

    groups = ledger["Group"].fillna("Unknown").astype(str).tolist()
    categories = ledger["Category"].fillna("Unknown").astype(str).tolist()
    amounts = pd.to_numeric(ledger["Amount"], errors="coerce").fillna(0.0)
    reasons = [
        _spending_exclusion_reason(
            group=group,
            category=category,
            amount=float(amount),
            filters=filters,
        )
        for group, category, amount in zip(
            groups,
            categories,
            amounts.tolist(),
            strict=True,
        )
    ]
    ledger["Included"] = [not reason for reason in reasons]
    ledger["Exclusion_Reason"] = reasons
    ledger["Net_Spend"] = -amounts.astype(float)
    return ledger


def _included(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return ledger
    return ledger[ledger["Included"]].copy()


def _group_for_category(ledgers: Sequence[pd.DataFrame]) -> dict[str, str]:
    available = [
        ledger[["Category", "Group"]]
        for ledger in ledgers
        if not ledger.empty and {"Category", "Group"}.issubset(ledger.columns)
    ]
    if not available:
        return {}
    pairs = pd.concat(available, ignore_index=True).dropna()
    if pairs.empty:
        return {}
    return {
        str(category): str(
            values.mode().iloc[0] if not values.mode().empty else values.iloc[0]
        )
        for category, values in pairs.groupby("Category")["Group"]
    }


def build_spending_overview(
    current_ledger: pd.DataFrame,
    comparison_ledger: pd.DataFrame,
    *,
    dimension: str,
    months: Sequence[str],
) -> pd.DataFrame:
    """Return current and comparison spending by group or category."""
    if dimension not in {"Group", "Category"}:
        raise ValueError(f"Unsupported spending dimension: {dimension}")

    current = _included(current_ledger)
    comparison = _included(comparison_ledger)
    current_totals = current.groupby(dimension)["Net_Spend"].sum()
    comparison_totals = comparison.groupby(dimension)["Net_Spend"].sum()
    entities = current_totals.index.union(comparison_totals.index)
    if entities.empty:
        return pd.DataFrame(columns=OVERVIEW_COLUMNS)

    current_counts = current.groupby(dimension).size()
    month_index = list(months)
    monthly = (
        current.groupby([dimension, "Month"])["Net_Spend"]
        .sum()
        .unstack(fill_value=0)
    )
    monthly = monthly.reindex(
        index=entities,
        columns=month_index,
        fill_value=0.0,
    )
    total_spending = float(current_totals.sum())
    category_groups = _group_for_category((current, comparison))
    month_count = len(month_index)

    rows: list[dict[str, object]] = []
    for entity_value in entities:
        entity = str(entity_value)
        spending = float(current_totals.get(entity_value, 0.0))
        comparison_spending = float(comparison_totals.get(entity_value, 0.0))
        change = spending - comparison_spending
        rows.append({
            "Entity": entity,
            "Group": category_groups.get(entity, "") if dimension == "Category" else "",
            "Spending": spending,
            "Share": spending / total_spending * 100 if total_spending else 0.0,
            "Average_Monthly": spending / month_count if month_count else 0.0,
            "Comparison_Spending": comparison_spending,
            "Change": change,
            "Change_Pct": (
                change / abs(comparison_spending) * 100
                if comparison_spending
                else None
            ),
            "Transactions": int(current_counts.get(entity_value, 0)),
            "Monthly_Trend": [
                float(value) for value in monthly.loc[entity_value].tolist()
            ],
        })
    return (
        pd.DataFrame(rows, columns=OVERVIEW_COLUMNS)
        .sort_values(
            ["Spending", "Entity"],
            ascending=[False, True],
            ignore_index=True,
        )
    )


def summarize_spending(
    current_ledger: pd.DataFrame,
    comparison_ledger: pd.DataFrame,
    *,
    num_months: int,
) -> SpendingSummary:
    """Return period-level spending metrics from the annotated ledgers."""
    current = _included(current_ledger)
    comparison = _included(comparison_ledger)
    total = float(current["Net_Spend"].sum()) if not current.empty else 0.0
    comparison_total = (
        float(comparison["Net_Spend"].sum()) if not comparison.empty else 0.0
    )
    change = total - comparison_total
    return SpendingSummary(
        total_spending=total,
        average_monthly_spending=total / num_months if num_months else 0.0,
        comparison_spending=comparison_total,
        change=change,
        change_pct=change / abs(comparison_total) * 100 if comparison_total else None,
        transaction_count=len(current),
        num_months=num_months,
    )


def build_entity_monthly_comparison(
    current_ledger: pd.DataFrame,
    comparison_ledger: pd.DataFrame,
    *,
    dimension: str,
    entity: str,
    current_months: Sequence[str],
    comparison_months: Sequence[str],
) -> pd.DataFrame:
    """Align one entity's monthly spending with its comparison months."""
    current = _included(current_ledger)
    comparison = _included(comparison_ledger)
    current = current[current[dimension].astype(str) == entity]
    comparison = comparison[comparison[dimension].astype(str) == entity]
    current_values = (
        current.groupby("Month")["Net_Spend"]
        .sum()
        .reindex(list(current_months), fill_value=0.0)
    )
    comparison_values = (
        comparison.groupby("Month")["Net_Spend"]
        .sum()
        .reindex(list(comparison_months), fill_value=0.0)
    )
    rows = [
        {
            "Month": current_month,
            "Comparison_Month": comparison_month,
            "Current_Spend": float(current_values.loc[current_month]),
            "Comparison_Spend": float(comparison_values.loc[comparison_month]),
        }
        for current_month, comparison_month in zip(
            current_months,
            comparison_months,
            strict=True,
        )
    ]
    return pd.DataFrame(rows, columns=MONTHLY_COMPARISON_COLUMNS)


def build_merchant_breakdown(ledger: pd.DataFrame) -> pd.DataFrame:
    """Return merchant-level spending for included rows."""
    included = _included(ledger)
    if included.empty:
        return pd.DataFrame(columns=MERCHANT_COLUMNS)
    descriptions = included.get(
        "Full Description",
        pd.Series("Unknown", index=included.index, dtype="string"),
    )
    included["Merchant"] = descriptions.map(
        lambda description: normalize_merchant_name(description, method="first_two")
    )
    grouped = (
        included.groupby("Merchant", dropna=False)
        .agg(
            Spending=("Net_Spend", "sum"),
            Transactions=("Net_Spend", "size"),
            Last_Transaction=("Date", "max"),
        )
        .reset_index()
    )
    total = float(grouped["Spending"].sum())
    grouped["Share"] = (
        grouped["Spending"].div(total).mul(100) if total else 0.0
    )
    grouped["Average_Transaction"] = grouped["Spending"].div(
        grouped["Transactions"]
    )
    return grouped[MERCHANT_COLUMNS].sort_values(
        ["Spending", "Merchant"],
        ascending=[False, True],
        ignore_index=True,
    )
