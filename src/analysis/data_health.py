"""Data-quality checks for imported Tiller sheets."""

from typing import TypedDict

import pandas as pd


class DataHealthReport(TypedDict):
    """Collection of data-quality findings."""

    uncategorized_transactions: pd.DataFrame
    sign_anomalies: pd.DataFrame
    missing_account_mappings: pd.DataFrame
    stale_accounts: pd.DataFrame
    categories_without_budget: pd.DataFrame


def build_data_health_report(
    transactions_df: pd.DataFrame,
    balance_history_df: pd.DataFrame,
    budget_df: pd.DataFrame,
    *,
    as_of: pd.Timestamp | None = None,
    stale_days: int = 7,
) -> DataHealthReport:
    """Run data-quality checks across transactions, balances, and budgets."""
    if as_of is None:
        as_of = _latest_timestamp(balance_history_df, "Date") or pd.Timestamp.now(tz="UTC")

    return DataHealthReport(
        uncategorized_transactions=find_uncategorized_transactions(transactions_df),
        sign_anomalies=find_sign_anomalies(transactions_df),
        missing_account_mappings=find_missing_account_mappings(balance_history_df),
        stale_accounts=find_stale_accounts(balance_history_df, as_of=as_of, stale_days=stale_days),
        categories_without_budget=find_categories_without_budget(transactions_df, budget_df),
    )


def find_uncategorized_transactions(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """Return transactions with missing category/group/type metadata."""
    if transactions_df.empty:
        return transactions_df.copy()

    category_missing = transactions_df["Category"].isna() | (transactions_df["Category"].astype(str).str.strip() == "")
    group_missing = (
        transactions_df["Group"].isna() |
        (transactions_df["Group"].astype(str).str.strip() == "") |
        (transactions_df["Group"] == "Uncategorized")
    )
    type_missing = transactions_df["Type"].isna() | (transactions_df["Type"].astype(str).str.strip() == "")
    return transactions_df[category_missing | group_missing | type_missing].copy()


def find_sign_anomalies(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """Return income/expense rows whose amount sign does not match the type."""
    if transactions_df.empty:
        return transactions_df.copy()

    positive_expense = (transactions_df["Type"] == "Expense") & (transactions_df["Amount"] > 0)
    negative_income = (transactions_df["Type"] == "Income") & (transactions_df["Amount"] < 0)
    return transactions_df[positive_expense | negative_income].copy()


def find_missing_account_mappings(balance_history_df: pd.DataFrame) -> pd.DataFrame:
    """Return latest balance rows whose account metadata has no group mapping."""
    latest = _latest_account_rows(balance_history_df)
    if latest.empty or "Group" not in latest.columns:
        return latest

    missing = latest["Group"].isna() | (latest["Group"].astype(str).str.strip() == "")
    return latest[missing].copy()


def find_stale_accounts(
    balance_history_df: pd.DataFrame,
    *,
    as_of: pd.Timestamp,
    stale_days: int = 7,
) -> pd.DataFrame:
    """Return accounts with no balance update within ``stale_days``."""
    latest = _latest_account_rows(balance_history_df)
    if latest.empty:
        return latest

    latest = latest.copy()
    latest["Days_Stale"] = (as_of - latest["Date"]).dt.days
    return latest[latest["Days_Stale"] > stale_days].sort_values("Days_Stale", ascending=False)


def find_categories_without_budget(
    transactions_df: pd.DataFrame,
    budget_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return expense categories with spending but no positive monthly budget."""
    if transactions_df.empty:
        return pd.DataFrame(columns=["Category", "Group", "Spent"])

    expenses = transactions_df[transactions_df["Type"] == "Expense"].copy()
    if expenses.empty:
        return pd.DataFrame(columns=["Category", "Group", "Spent"])

    if budget_df.empty or not {"Budget", "Category"}.issubset(budget_df.columns):
        budgeted: set[object] = set()
    else:
        budgeted = set(
            budget_df.loc[pd.to_numeric(budget_df["Budget"], errors="coerce").fillna(0) > 0, "Category"]
        )

    spending = (
        expenses.groupby(["Category", "Group"])["Amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"Amount": "Spent"})
    )
    result = spending[~spending["Category"].isin(budgeted)]
    return result.sort_values("Spent", ascending=False).reset_index(drop=True)


def _latest_account_rows(balance_history_df: pd.DataFrame) -> pd.DataFrame:
    """Return one latest row per account ID."""
    if balance_history_df.empty:
        return balance_history_df.copy()

    sort_cols = ["Date"]
    if "Time" in balance_history_df.columns:
        sort_cols.append("Time")
    id_col = "Account ID" if "Account ID" in balance_history_df.columns else "Account"
    return balance_history_df.sort_values(sort_cols).drop_duplicates(id_col, keep="last")


def _latest_timestamp(df: pd.DataFrame, column: str) -> pd.Timestamp | None:
    """Return latest timestamp in a column."""
    if df.empty or column not in df.columns:
        return None
    values = pd.to_datetime(df[column], errors="coerce", utc=True).dropna()
    if values.empty:
        return None
    return pd.Timestamp(values.max())
