"""Data-quality checks for imported Tiller sheets."""

from typing import TypedDict

import pandas as pd


class DataHealthReport(TypedDict):
    """Collection of data-quality findings."""

    uncategorized_transactions: pd.DataFrame
    incomplete_transactions: pd.DataFrame
    cash_flow_reversals: pd.DataFrame
    missing_account_mappings: pd.DataFrame
    stale_accounts: pd.DataFrame


def build_data_health_report(
    transactions_df: pd.DataFrame,
    balance_history_df: pd.DataFrame,
    *,
    as_of: pd.Timestamp | None = None,
    stale_days: int = 7,
) -> DataHealthReport:
    """Run data-quality checks across transactions, balances, and budgets."""
    if as_of is None:
        as_of = _latest_timestamp(balance_history_df, "Date") or pd.Timestamp.now(tz="UTC")

    return DataHealthReport(
        uncategorized_transactions=find_uncategorized_transactions(transactions_df),
        incomplete_transactions=find_incomplete_transactions(transactions_df),
        cash_flow_reversals=find_cash_flow_reversals(transactions_df),
        missing_account_mappings=find_missing_account_mappings(balance_history_df),
        stale_accounts=find_stale_accounts(balance_history_df, as_of=as_of, stale_days=stale_days),
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


def find_incomplete_transactions(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """Return transactions missing fields needed to identify and analyze them."""
    if transactions_df.empty:
        return transactions_df.copy()

    missing = pd.Series(False, index=transactions_df.index)
    reasons: list[pd.Series] = []
    for column in ("Date", "Amount", "Account", "Full Description"):
        if column not in transactions_df.columns:
            column_missing = pd.Series(True, index=transactions_df.index)
        elif column in {"Date", "Amount"}:
            column_missing = transactions_df[column].isna()
        else:
            column_missing = transactions_df[column].isna() | (
                transactions_df[column].astype(str).str.strip() == ""
            )
        missing |= column_missing
        reasons.append(column_missing.map({True: column, False: ""}))

    result = transactions_df[missing].copy()
    if result.empty:
        return result

    reason_frame = pd.concat(reasons, axis=1).loc[result.index]
    result["Missing_Fields"] = reason_frame.apply(
        lambda row: ", ".join(value for value in row if value),
        axis=1,
    )
    return result


def find_cash_flow_reversals(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """Return expense refunds and income reversals that merit review."""
    if transactions_df.empty:
        return transactions_df.copy()

    positive_expense = (transactions_df["Type"] == "Expense") & (transactions_df["Amount"] > 0)
    negative_income = (transactions_df["Type"] == "Income") & (transactions_df["Amount"] < 0)
    result = transactions_df[positive_expense | negative_income].copy()
    if result.empty:
        return result
    result["Review_Reason"] = "Income reversal"
    result.loc[positive_expense, "Review_Reason"] = "Expense refund"
    return result


def find_missing_account_mappings(balance_history_df: pd.DataFrame) -> pd.DataFrame:
    """Return latest balance rows missing identity, group, or class metadata."""
    latest = _latest_account_rows(balance_history_df)
    if latest.empty:
        return latest

    missing = pd.Series(False, index=latest.index)
    reason_parts: list[pd.Series] = []
    for column in ("Account ID", "Group", "Class"):
        if column not in latest.columns:
            column_missing = pd.Series(True, index=latest.index)
        else:
            column_missing = latest[column].isna() | (
                latest[column].astype(str).str.strip() == ""
            )
            if column == "Class":
                column_missing |= ~latest[column].isin(["Asset", "Liability"])
        missing |= column_missing
        reason_parts.append(column_missing.map({True: column, False: ""}))

    result = latest[missing].copy()
    if result.empty:
        return result
    reason_frame = pd.concat(reason_parts, axis=1).loc[result.index]
    result["Missing_Fields"] = reason_frame.apply(
        lambda row: ", ".join(value for value in row if value),
        axis=1,
    )
    return result


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


def _latest_account_rows(balance_history_df: pd.DataFrame) -> pd.DataFrame:
    """Return one latest row per account ID."""
    if balance_history_df.empty:
        return balance_history_df.copy()

    sort_cols = ["Date"]
    if "Time" in balance_history_df.columns:
        sort_cols.append("Time")
    latest = balance_history_df.sort_values(sort_cols).copy()
    accounts = latest.get(
        "Account",
        pd.Series("", index=latest.index, dtype="string"),
    ).fillna("").astype(str).str.strip()
    account_ids = latest.get(
        "Account ID",
        pd.Series("", index=latest.index, dtype="string"),
    ).fillna("").astype(str).str.strip()
    fallback = "account:" + accounts
    row_fallback = pd.Series(
        "row:" + latest.index.astype(str),
        index=latest.index,
        dtype="string",
    )
    fallback = fallback.where(accounts.ne(""), row_fallback)
    latest["_Account_Key"] = account_ids.where(account_ids.ne(""), fallback)
    return latest.drop_duplicates("_Account_Key", keep="last").drop(columns="_Account_Key")


def _latest_timestamp(df: pd.DataFrame, column: str) -> pd.Timestamp | None:
    """Return latest timestamp in a column."""
    if df.empty or column not in df.columns:
        return None
    values = pd.to_datetime(df[column], errors="coerce", utc=True).dropna()
    if values.empty:
        return None
    return pd.Timestamp(values.max())
