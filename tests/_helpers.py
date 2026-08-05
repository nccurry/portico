"""Shared test helpers — fully annotated DataFrame builders and timestamp utilities.

Consolidated from individual test modules to enforce typing via ruff ANN rules.
"""
from datetime import date, datetime
from typing import cast

import pandas as pd

from tests.custom_types import DataFrameRow


def _ts(date_str: str) -> pd.Timestamp:
    """Return a UTC-aware Timestamp from a 'YYYY-MM-DD' string."""
    return pd.Timestamp(date_str, tz="UTC")


def _utc(year: int, month: int, day: int) -> pd.Timestamp:
    """Return a timezone-aware UTC datetime."""
    return pd.Timestamp(year, month, day, tz="UTC")


def _transactions_df(rows: list[DataFrameRow]) -> pd.DataFrame:
    """Build a minimal scrubbed transactions DataFrame from a list of dicts.

    Each dict should contain Date, Category, Amount, Account, Month, Group,
    Type (and optionally Full Description, Institution, Account #).
    """
    defaults: DataFrameRow = {
        "Full Description": "",
        "Institution": "",
        "Account #": "",
    }
    records = [{**defaults, **r} for r in rows]
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    df["Amount"] = df["Amount"].astype(float)
    return df


def _balance_df(rows: list[DataFrameRow]) -> pd.DataFrame:
    """Build a minimal scrubbed balance-history DataFrame from a list of dicts."""
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    if "Time" in df.columns:
        df["Time"] = pd.to_datetime(df["Time"], utc=True)
    df["Balance"] = df["Balance"].astype(float)
    return df


def _make_df(rows: list[DataFrameRow]) -> pd.DataFrame:
    """Build a transaction DataFrame from a list of dicts with sensible defaults."""
    defaults: DataFrameRow = {
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
        row['Date'] = pd.Timestamp(
            cast(str | float | date | datetime, row['Date']),
            tz='UTC',
        )
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
) -> DataFrameRow:
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


def _df_from_rows(*rows: DataFrameRow) -> pd.DataFrame:
    """Build a DataFrame from individual row dicts."""
    return pd.DataFrame(list(rows))

