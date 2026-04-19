"""Shared test helpers — fully annotated DataFrame builders and timestamp utilities.

Consolidated from individual test modules to enforce typing via ruff ANN rules.
"""
from typing import Any

import pandas as pd

from src.spreadsheet import BalanceHistorySpreadsheet


def _ts(date_str: str) -> pd.Timestamp:
    """Return a UTC-aware Timestamp from a 'YYYY-MM-DD' string."""
    return pd.Timestamp(date_str, tz="UTC")


def _utc(year: int, month: int, day: int) -> pd.Timestamp:
    """Return a timezone-aware UTC datetime."""
    return pd.Timestamp(year, month, day, tz="UTC")


def _transactions_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a minimal scrubbed transactions DataFrame from a list of dicts.

    Each dict should contain Date, Category, Amount, Account, Month, Group,
    Type (and optionally Full Description, Institution, Account #).
    """
    defaults: dict[str, Any] = {
        "Full Description": "",
        "Institution": "",
        "Account #": "",
    }
    records = [{**defaults, **r} for r in rows]
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    df["Amount"] = df["Amount"].astype(float)
    return df


def _balance_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a minimal scrubbed balance-history DataFrame from a list of dicts."""
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    if "Time" in df.columns:
        df["Time"] = pd.to_datetime(df["Time"], utc=True)
    df["Balance"] = df["Balance"].astype(float)
    return df


def _make_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a transaction DataFrame from a list of dicts with sensible defaults."""
    defaults: dict[str, Any] = {
        'Type': 'Expense',
        'Category': 'Groceries',
        'Group': 'Food',
        'Account': 'Checking',
        'Month': '2024-01',
        'Full Description': 'STORE PURCHASE',
        'Institution': 'Bank',
        'Account #': '1234',
    }
    for row in rows:
        for k, v in defaults.items():
            row.setdefault(k, v)
        row['Date'] = pd.Timestamp(row['Date'], tz='UTC')
    return pd.DataFrame(rows)


def _make_merchant_df() -> pd.DataFrame:
    """Build a transaction DataFrame with multiple merchants and types."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-05', '2024-01-10', '2024-01-15',
            '2024-01-20', '2024-02-01', '2024-02-10',
            '2024-03-01',
        ], utc=True),
        'Amount': [3000, -50, -75, -200, -60, -80, -30],
        'Type': ['Income', 'Expense', 'Expense', 'Expense', 'Expense', 'Expense', 'Expense'],
        'Category': ['Salary', 'Groceries', 'Groceries', 'Dining', 'Groceries', 'Dining', 'Coffee'],
        'Group': ['Income', 'Food', 'Food', 'Food', 'Food', 'Food', 'Food'],
        'Account': ['Checking'] * 7,
        'Month': ['2024-01', '2024-01', '2024-01', '2024-01', '2024-02', '2024-02', '2024-03'],
        'Full Description': [
            'EMPLOYER PAYROLL',
            'KROGER #1234 STORE',
            'KROGER #5678 STORE',
            'CHIPOTLE RESTAURANT',
            'KROGER #1234 STORE',
            'CHIPOTLE RESTAURANT',
            'STARBUCKS COFFEE',
        ],
        'Institution': ['Bank'] * 7,
        'Account #': ['1234'] * 7,
    })


def _make_recurring_df(
    merchant: str = 'NETFLIX MONTHLY',
    amount: float = -15.99,
    category: str = 'Entertainment',
    start: str = '2024-01-15',
    months: int = 6,
) -> pd.DataFrame:
    """Build a DataFrame with monthly recurring charges for a single merchant."""
    dates = pd.date_range(start=start, periods=months, freq='MS', tz='UTC') + pd.Timedelta(days=14)
    return pd.DataFrame({
        'Date': dates,
        'Amount': [amount] * months,
        'Type': ['Expense'] * months,
        'Category': [category] * months,
        'Group': ['Entertainment'] * months,
        'Account': ['Checking'] * months,
        'Month': [d.strftime('%Y-%m') for d in dates],
        'Full Description': [merchant] * months,
        'Institution': ['Bank'] * months,
        'Account #': ['1234'] * months,
    })


def _make_row(
    date: str,
    category: str | None,
    amount: float,
    group: str | None,
    txn_type: str | None,
    *,
    account: str = "Checking",
    month: str = "2024-01",
    desc: str = "test",
    institution: str = "Test Bank",
    acct_num: str = "0000",
) -> dict[str, Any]:
    """Build a single transaction row matching TRANSACTIONS_SCRUBBED_COLUMNS."""
    return {
        "Date": pd.Timestamp(date, tz="UTC"),
        "Category": category,
        "Amount": amount,
        "Account": account,
        "Month": month,
        "Full Description": desc,
        "Group": group,
        "Type": txn_type,
        "Institution": institution,
        "Account #": acct_num,
    }


def _df_from_rows(*rows: dict[str, Any]) -> pd.DataFrame:
    """Build a DataFrame from individual row dicts."""
    return pd.DataFrame(list(rows))


def extract_categories_and_groups(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Replicate the extraction logic from configure_page."""
    all_categories = sorted([str(c) for c in df['Category'].unique()
                             if pd.notna(c) and str(c).strip()])
    all_groups = sorted([str(g) for g in df['Group'].unique()
                         if pd.notna(g) and str(g).strip() and g != 'Transfer'])
    return all_categories, all_groups


def calculate_net_worth(
    balance_spreadsheet: BalanceHistorySpreadsheet,
) -> tuple[float, dict[str, float], dict[str, str]]:
    """Replicate the net worth calculation from Home.configure_page."""
    groups = balance_spreadsheet.get_groups()
    groups = [str(g) for g in groups if pd.notna(g) and g != '']

    total_net_worth = 0.0
    group_balances: dict[str, float] = {}
    group_classes: dict[str, str] = {}

    for group in groups:
        accounts_df, total = balance_spreadsheet.get_latest_balance_by_group(group)

        account_class = "Asset"
        if not accounts_df.empty:
            df_check = balance_spreadsheet.scrubbed_df[
                balance_spreadsheet.scrubbed_df["Group"] == group
            ]
            if not df_check.empty:
                account_class = df_check.iloc[0]["Class"]

        group_classes[group] = account_class

        if account_class == "Liability":
            total_net_worth -= total
        else:
            total_net_worth += total

        group_balances[group] = total

    return total_net_worth, group_balances, group_classes
