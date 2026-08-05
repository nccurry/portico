"""Pure calculations for the largest-expenses page."""

import pandas as pd

from src.analysis.merchants import normalize_merchant_name
from src.custom_types import TopTransactionsStats


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
