"""Pure calculations for interactive spending exploration."""

from collections.abc import Mapping, Sequence

import pandas as pd

from src.analysis.merchants import enrich_with_merchant
from src.config import TransactionSetSettings
from src.custom_types import SpendingFilters, SpendingSummary
from src.transaction_filters import matching_transaction_terms
from src.transaction_sets import transaction_set_mask

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
    description: object,
    filters: SpendingFilters,
    transaction_set_included: bool,
    transaction_set_label: str | None,
) -> str:
    reasons: list[str] = []
    include_groups = set(filters.get("include_groups", ()))
    include_categories = set(filters.get("include_categories", ()))
    included_transactions = matching_transaction_terms(description, filters.get("include_transactions_like", ()))
    include_mode = bool(include_groups or include_categories or filters.get("include_transactions_like"))

    _append_reason(reasons, group == "Transfer", "Transfer group")
    if transaction_set_label is not None:
        _append_reason(
            reasons,
            not transaction_set_included,
            f"Outside configured set: {transaction_set_label}",
        )
    if include_mode:
        _append_reason(
            reasons,
            group not in include_groups and category not in include_categories and not included_transactions,
            "Outside included groups/categories/transactions",
        )

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
    for term in matching_transaction_terms(description, filters.get("exclude_transactions_like", ())):
        reasons.append(f"Excluded transaction like: {term}")

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
    start_month: str | None = None,
    end_month: str | None = None,
    transaction_set_key: str | None = None,
    transaction_sets: Sequence[TransactionSetSettings] = (),
    merchant_aliases: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Return period expense rows annotated with inclusion and net spending.

    When provided, ``start_month`` is inclusive and ``end_month`` is exclusive.
    Purchases have positive ``Net_Spend`` values; positive expense refunds reduce
    spending.
    """
    if (start_month is None) != (end_month is None):
        raise ValueError("start_month and end_month must be provided together")

    ledger = transactions[transactions["Type"] == "Expense"].copy()
    if start_month is not None and end_month is not None:
        ledger = ledger[(ledger["Month"].astype(str) >= start_month) & (ledger["Month"].astype(str) < end_month)].copy()

    if ledger.empty:
        ledger["Included"] = pd.Series(dtype="bool")
        ledger["Exclusion_Reason"] = pd.Series(dtype="string")
        ledger["Net_Spend"] = pd.Series(dtype="float64")
        return ledger

    transaction_set_label: str | None = None
    transaction_set_membership = pd.Series(True, index=ledger.index, dtype="bool")
    if transaction_set_key is not None:
        transaction_set_by_key = {configured.key: configured for configured in transaction_sets}
        selected_set = transaction_set_by_key.get(transaction_set_key)
        if selected_set is None:
            raise ValueError(f"Unknown transaction set: {transaction_set_key}")
        transaction_set_label = selected_set.label
        transaction_set_membership = transaction_set_mask(
            ledger,
            transaction_set_key=transaction_set_key,
            transaction_sets=transaction_sets,
            aliases=merchant_aliases,
        )

    groups = ledger["Group"].fillna("Unknown").astype(str).tolist()
    categories = ledger["Category"].fillna("Unknown").astype(str).tolist()
    descriptions = ledger["Full Description"].tolist() if "Full Description" in ledger else ["Unknown"] * len(ledger)
    amounts = pd.to_numeric(ledger["Amount"], errors="coerce").fillna(0.0)
    reasons = [
        _spending_exclusion_reason(
            group=group,
            category=category,
            amount=float(amount),
            description=description,
            filters=filters,
            transaction_set_included=transaction_set_included,
            transaction_set_label=transaction_set_label,
        )
        for group, category, amount, description, transaction_set_included in zip(
            groups,
            categories,
            amounts.tolist(),
            descriptions,
            transaction_set_membership.tolist(),
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


def included_spending_rows(
    transactions: pd.DataFrame,
    filters: SpendingFilters | None = None,
    *,
    transaction_set_key: str | None = None,
    transaction_sets: Sequence[TransactionSetSettings] = (),
    merchant_aliases: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Return all expense rows included by the shared spending policy."""
    active_filters = filters or {
        "include_groups": [],
        "include_categories": [],
        "exclude_groups": [],
        "exclude_categories": [],
        "filter_large_expenses": False,
        "expense_threshold": 0,
    }
    return _included(
        build_spending_ledger(
            transactions,
            active_filters,
            transaction_set_key=transaction_set_key,
            transaction_sets=transaction_sets,
            merchant_aliases=merchant_aliases,
        )
    )


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
        str(category): str(values.mode().iloc[0] if not values.mode().empty else values.iloc[0])
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
    monthly = current.groupby([dimension, "Month"])["Net_Spend"].sum().unstack(fill_value=0)
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
        rows.append(
            {
                "Entity": entity,
                "Group": category_groups.get(entity, "") if dimension == "Category" else "",
                "Spending": spending,
                "Share": spending / total_spending * 100 if total_spending else 0.0,
                "Average_Monthly": spending / month_count if month_count else 0.0,
                "Comparison_Spending": comparison_spending,
                "Change": change,
                "Change_Pct": (change / abs(comparison_spending) * 100 if comparison_spending else None),
                "Transactions": int(current_counts.get(entity_value, 0)),
                "Monthly_Trend": [float(value) for value in monthly.loc[entity_value].tolist()],
            }
        )
    return pd.DataFrame(rows, columns=OVERVIEW_COLUMNS).sort_values(
        ["Spending", "Entity"],
        ascending=[False, True],
        ignore_index=True,
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
    comparison_total = float(comparison["Net_Spend"].sum()) if not comparison.empty else 0.0
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
    current_values = current.groupby("Month")["Net_Spend"].sum().reindex(list(current_months), fill_value=0.0)
    comparison_values = comparison.groupby("Month")["Net_Spend"].sum().reindex(list(comparison_months), fill_value=0.0)
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


def build_merchant_breakdown(
    ledger: pd.DataFrame,
    *,
    aliases: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Return merchant-level spending for included rows."""
    included = _included(ledger)
    if included.empty:
        return pd.DataFrame(columns=MERCHANT_COLUMNS)
    included = enrich_with_merchant(
        included,
        "normalized",
        aliases=aliases,
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
    grouped["Share"] = grouped["Spending"].div(total).mul(100) if total else 0.0
    grouped["Average_Transaction"] = grouped["Spending"].div(grouped["Transactions"])
    return grouped[MERCHANT_COLUMNS].sort_values(
        ["Spending", "Merchant"],
        ascending=[False, True],
        ignore_index=True,
    )
