"""Pure calculations for transaction exploration and largest expenses."""

from collections.abc import Mapping, Sequence

import pandas as pd

from src.analysis.merchants import enrich_with_merchant, normalize_merchant_name
from src.custom_types import TransactionExplorerSummary, TopTransactionsStats


FOCUS_OPTIONS = (
    "All transactions",
    "Largest",
    "One-off merchants",
    "Unusual amounts",
    "Refunds / reversals",
)
BREAKDOWN_DIMENSIONS = ("Group", "Category", "Merchant", "Account", "Type")


def _as_utc(value: pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def build_transaction_inventory(
    transactions: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    *,
    transaction_types: Sequence[str] = (),
    groups: Sequence[str] = (),
    categories: Sequence[str] = (),
    accounts: Sequence[str] = (),
    search: str = "",
    minimum_magnitude: float = 0.0,
    maximum_magnitude: float | None = None,
    aliases: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Return transactions annotated for filtering and anomaly exploration."""
    inventory = transactions.copy()
    inventory["Date"] = pd.to_datetime(
        inventory["Date"], errors="coerce", utc=True
    )
    inventory["Amount"] = pd.to_numeric(inventory["Amount"], errors="coerce")
    inventory = inventory.dropna(subset=["Date", "Amount"])
    inventory = inventory[
        inventory["Date"].between(_as_utc(start_date), _as_utc(end_date))
    ].copy()

    if transaction_types:
        inventory = inventory[inventory["Type"].isin(transaction_types)]
    if groups:
        inventory = inventory[inventory["Group"].isin(groups)]
    if categories:
        inventory = inventory[inventory["Category"].isin(categories)]
    if accounts:
        inventory = inventory[inventory["Account"].isin(accounts)]

    inventory["Magnitude"] = inventory["Amount"].abs()
    inventory = inventory[inventory["Magnitude"] >= minimum_magnitude]
    if maximum_magnitude is not None:
        inventory = inventory[inventory["Magnitude"] <= maximum_magnitude]

    inventory = enrich_with_merchant(
        inventory,
        "normalized",
        aliases=aliases,
    )
    query = search.strip()
    if query:
        searchable = [
            column
            for column in [
                "Full Description",
                "Merchant",
                "Type",
                "Group",
                "Category",
                "Account",
                "Institution",
            ]
            if column in inventory
        ]
        matches = pd.Series(False, index=inventory.index)
        for column in searchable:
            matches |= inventory[column].astype(str).str.contains(
                query,
                case=False,
                na=False,
                regex=False,
            )
        inventory = inventory[matches].copy()

    if inventory.empty:
        inventory["Occurrences"] = pd.Series(dtype="int64")
        inventory["Is_One_Off"] = pd.Series(dtype="bool")
        inventory["Is_Unusual"] = pd.Series(dtype="bool")
        inventory["Is_Reversal"] = pd.Series(dtype="bool")
        return inventory

    merchant_groups = inventory.groupby("Merchant")["Magnitude"]
    inventory["Occurrences"] = merchant_groups.transform("size").astype(int)
    inventory["Is_One_Off"] = inventory["Occurrences"].eq(1)

    median = merchant_groups.transform("median")
    deviation = (inventory["Magnitude"] - median).abs()
    mad = deviation.groupby(inventory["Merchant"]).transform("median")
    robust_threshold = mad * 1.4826 * 3.0
    flat_threshold = (median * 0.5).clip(lower=25.0)
    threshold = robust_threshold.where(mad.gt(0), flat_threshold)
    inventory["Is_Unusual"] = (
        inventory["Occurrences"].ge(3)
        & deviation.gt(0)
        & deviation.ge(threshold)
    )
    inventory["Is_Reversal"] = (
        inventory["Type"].eq("Expense") & inventory["Amount"].gt(0)
    ) | (
        inventory["Type"].eq("Income") & inventory["Amount"].lt(0)
    )
    return inventory.sort_values(
        ["Magnitude", "Date"],
        ascending=[False, False],
    ).reset_index(drop=True)


def filter_transaction_focus(
    inventory: pd.DataFrame,
    focus: str,
    *,
    largest_count: int = 25,
) -> pd.DataFrame:
    """Apply one quick-focus mode to an annotated transaction inventory."""
    if focus not in FOCUS_OPTIONS:
        raise ValueError(f"Unsupported transaction focus: {focus}")
    if inventory.empty or focus == "All transactions":
        return inventory.copy()
    if focus == "Largest":
        return inventory.head(largest_count).copy()
    column = {
        "One-off merchants": "Is_One_Off",
        "Unusual amounts": "Is_Unusual",
        "Refunds / reversals": "Is_Reversal",
    }[focus]
    return inventory[inventory[column]].copy()


def summarize_transaction_inventory(
    transactions: pd.DataFrame,
) -> TransactionExplorerSummary:
    """Return cash-direction totals for the current result set."""
    if transactions.empty:
        return TransactionExplorerSummary(
            transaction_count=0,
            inflow=0.0,
            outflow=0.0,
            net_amount=0.0,
            median_magnitude=0.0,
        )
    amounts = pd.to_numeric(transactions["Amount"], errors="coerce").fillna(0.0)
    magnitudes = amounts.abs()
    return TransactionExplorerSummary(
        transaction_count=len(transactions),
        inflow=float(amounts.clip(lower=0).sum()),
        outflow=float(-amounts.clip(upper=0).sum()),
        net_amount=float(amounts.sum()),
        median_magnitude=float(magnitudes.median()),
    )


def build_transaction_breakdown(
    transactions: pd.DataFrame,
    dimension: str,
) -> pd.DataFrame:
    """Summarize the current results by one transaction dimension."""
    columns = [
        "Entity",
        "Transactions",
        "Inflow",
        "Outflow",
        "Net_Amount",
        "Magnitude",
        "Share",
    ]
    if dimension not in BREAKDOWN_DIMENSIONS:
        raise ValueError(f"Unsupported transaction breakdown: {dimension}")
    if transactions.empty:
        return pd.DataFrame(columns=columns)

    prepared = transactions.copy()
    prepared["_Inflow"] = prepared["Amount"].clip(lower=0)
    prepared["_Outflow"] = -prepared["Amount"].clip(upper=0)
    prepared["_Magnitude"] = prepared["Amount"].abs()
    grouped = (
        prepared.groupby(dimension, dropna=False)
        .agg(
            Transactions=("Amount", "size"),
            Inflow=("_Inflow", "sum"),
            Outflow=("_Outflow", "sum"),
            Net_Amount=("Amount", "sum"),
            Magnitude=("_Magnitude", "sum"),
        )
        .reset_index()
        .rename(columns={dimension: "Entity"})
    )
    grouped["Entity"] = grouped["Entity"].fillna("Unspecified").astype(str)
    total = float(grouped["Magnitude"].sum())
    grouped["Share"] = grouped["Magnitude"].div(total).mul(100) if total else 0.0
    return grouped[columns].sort_values(
        ["Magnitude", "Entity"],
        ascending=[False, True],
    ).reset_index(drop=True)


def get_top_transactions(
    transactions: pd.DataFrame,
    n: int,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, TopTransactionsStats]:
    """Return the largest expenses and their share of all period spending."""
    expenses = transactions[
        (transactions["Type"] == "Expense")
        & (transactions["Date"] >= start_date)
        & (transactions["Date"] <= end_date)
    ].copy()
    if expenses.empty:
        return pd.DataFrame(), TopTransactionsStats(
            total_top_n=0.0,
            total_spending=0.0,
            pct_of_total=0.0,
            num_transactions=0,
        )

    expenses["Abs_Amount"] = expenses["Amount"].abs()
    total_spending = float(expenses["Abs_Amount"].sum())
    expenses = expenses.sort_values(
        ["Abs_Amount", "Date"], ascending=[False, True]
    )
    top = expenses.head(n)
    top_total = float(top["Abs_Amount"].sum())
    return top, TopTransactionsStats(
        total_top_n=top_total,
        total_spending=total_spending,
        pct_of_total=top_total / total_spending * 100 if total_spending else 0.0,
        num_transactions=len(expenses),
    )


def get_category_breakdown(top_transactions: pd.DataFrame) -> pd.DataFrame:
    """Return absolute top-transaction totals and counts by category."""
    if top_transactions.empty:
        return pd.DataFrame(columns=["Category", "Total", "Count"])
    return (
        top_transactions.groupby("Category")
        .agg(Total=("Abs_Amount", "sum"), Count=("Abs_Amount", "count"))
        .reset_index()
        .sort_values("Total", ascending=False)
    )


def find_recurring_large_expenses(top_transactions: pd.DataFrame) -> pd.DataFrame:
    """Return merchants appearing at least twice among the largest expenses."""
    if top_transactions.empty:
        return pd.DataFrame(columns=["Merchant", "Count", "Total"])
    transactions = top_transactions.copy()
    transactions["Merchant"] = transactions["Full Description"].apply(
        lambda description: normalize_merchant_name(
            description,
            method="first_three",
        )
    )
    recurring = (
        transactions.groupby("Merchant")
        .agg(Count=("Abs_Amount", "count"), Total=("Abs_Amount", "sum"))
        .reset_index()
    )
    return recurring[recurring["Count"] >= 2].sort_values(
        "Total", ascending=False
    )
