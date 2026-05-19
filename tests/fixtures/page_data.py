"""Page-helper and analytics test data fixtures."""
from typing import Any

import pandas as pd
import pytest

from tests._helpers import _balance_df, _transactions_df


# Fixtures moved from test_top_transactions.py
# ---------------------------------------------------------------------------

@pytest.fixture
def varied_expenses() -> pd.DataFrame:
    """Expenses with varied amounts for top-N analysis."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-05', '2024-01-10', '2024-01-15',
            '2024-01-20', '2024-01-25', '2024-02-01',
            '2024-02-10', '2024-02-15',
        ], utc=True),
        'Amount': [-50, -500, -100, -1000, -200, -300, -750, -25],
        'Type': ['Expense'] * 8,
        'Category': ['Coffee', 'Rent', 'Groceries', 'Rent', 'Dining', 'Utilities', 'Rent', 'Coffee'],
        'Group': ['Food', 'Housing', 'Food', 'Housing', 'Food', 'Bills', 'Housing', 'Food'],
        'Account': ['Checking'] * 8,
        'Month': ['2024-01'] * 5 + ['2024-02'] * 3,
        'Full Description': ['STARBUCKS', 'LANDLORD LLC', 'KROGER STORE', 'LANDLORD LLC',
                             'OLIVE GARDEN', 'DUKE ENERGY', 'LANDLORD LLC', 'STARBUCKS'],
        'Institution': ['Bank'] * 8,
        'Account #': ['1234'] * 8,
    })


# ---------------------------------------------------------------------------
# Fixtures moved from test_page_helpers.py
# ---------------------------------------------------------------------------

@pytest.fixture
def monthly_amounts_df() -> pd.DataFrame:
    """Monthly amounts with YYYY-MM index and Amount column, spanning two years."""
    data = {
        'Amount': [100, 200, 300, 150, 250, 350,
                   110, 210, 310, 160, 260, 360]
    }
    index = pd.Index([
        '2023-01', '2023-02', '2023-03', '2023-04', '2023-05', '2023-06',
        '2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06',
    ], name='Month')
    return pd.DataFrame(data, index=index)


# ---------------------------------------------------------------------------
# Fixtures moved from test_income_and_savings.py
# ---------------------------------------------------------------------------

@pytest.fixture
def income_expense_sample_df() -> pd.DataFrame:
    """Transactions with both Income and Expense types across several months."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-15', '2024-01-20', '2024-02-10', '2024-02-15',
            '2024-03-05', '2024-03-12',
        ], utc=True),
        'Amount': [3000, -1000, 4000, -2000, 5000, -1500],
        'Type': ['Income', 'Expense', 'Income', 'Expense', 'Income', 'Expense'],
        'Category': ['Salary', 'Groceries', 'Salary', 'Groceries', 'Salary', 'Groceries'],
        'Group': ['Income', 'Food', 'Income', 'Food', 'Income', 'Food'],
        'Account': ['Checking'] * 6,
        'Month': ['2024-01', '2024-01', '2024-02', '2024-02', '2024-03', '2024-03'],
        'Full Description': ['EMPLOYER PAYROLL'] * 6,
        'Institution': ['Bank'] * 6,
        'Account #': ['1234'] * 6,
    })


@pytest.fixture
def basic_filters() -> dict[str, Any]:
    """Minimal filters that pass everything through."""
    return {
        'exclude_groups': [],
        'exclude_categories': [],
        'filter_large_income': False,
        'income_threshold': 50000,
        'filter_large_expenses': False,
        'expense_threshold': 50000,
        'target_rate': 20,
    }


# ---------------------------------------------------------------------------
# Fixtures moved from test_spending_by_category.py
# ---------------------------------------------------------------------------

@pytest.fixture
def spending_transactions_df() -> pd.DataFrame:
    """Transactions with mixed types and multiple categories."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-05', '2024-01-10', '2024-01-15',
            '2024-01-20', '2024-01-25', '2024-02-01',
        ], utc=True),
        'Amount': [3000, -200, -150, -500, -50, -100],
        'Type': ['Income', 'Expense', 'Expense', 'Expense', 'Expense', 'Expense'],
        'Category': ['Salary', 'Groceries', 'Dining', 'Rent', 'Coffee', 'Groceries'],
        'Group': ['Income', 'Food', 'Food', 'Housing', 'Food', 'Food'],
        'Account': ['Checking'] * 6,
        'Month': ['2024-01', '2024-01', '2024-01', '2024-01', '2024-01', '2024-02'],
        'Full Description': ['PAY', 'KROGER', 'RESTAURANT', 'LANDLORD', 'STARBUCKS', 'KROGER'],
        'Institution': ['Bank'] * 6,
        'Account #': ['1234'] * 6,
    })


@pytest.fixture
def basic_spending_filters() -> dict[str, Any]:
    """Minimal filters that pass everything through."""
    return {
        'include_groups': [],
        'include_categories': [],
        'exclude_groups': [],
        'exclude_categories': [],
        'filter_large_expenses': False,
        'expense_threshold': 50000,
    }


@pytest.fixture
def expenses_only_df() -> pd.DataFrame:
    """DataFrame with only expense transactions for distribution stats."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-05', '2024-01-10', '2024-01-15',
            '2024-01-20', '2024-01-25',
        ], utc=True),
        'Amount': [-10, -50, -100, -300, -500],
        'Type': ['Expense'] * 5,
        'Category': ['Coffee', 'Groceries', 'Dining', 'Utilities', 'Rent'],
        'Group': ['Food', 'Food', 'Food', 'Housing', 'Housing'],
        'Account': ['Checking'] * 5,
        'Month': ['2024-01'] * 5,
        'Full Description': ['CAFE', 'STORE', 'REST', 'ELECTRIC', 'LANDLORD'],
        'Institution': ['Bank'] * 5,
        'Account #': ['1234'] * 5,
    })


# ---------------------------------------------------------------------------
# Fixtures for Financial Independence page
# ---------------------------------------------------------------------------

@pytest.fixture
def fi_balance_df() -> pd.DataFrame:
    """Scrubbed balance history covering every branch of get_portfolio_value.

    Exercises: multi-date latest-wins per Account ID, signed aggregation via
    Class, Hide="Hide" exclusion, and same-date/different-Time tie-break
    (Brokerage has two observations on 2024-02-01 with different Time values).
    """
    return _balance_df([
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Brokerage",   "Account ID": "b1", "Institution": "Bank", "Group": "Investments", "Class": "Asset",     "Balance": 100000, "Hide": ""},
        {"Date": "2024-02-01", "Time": "2024-02-01 08:00:00", "Account": "Brokerage",   "Account ID": "b1", "Institution": "Bank", "Group": "Investments", "Class": "Asset",     "Balance": 115000, "Hide": ""},
        {"Date": "2024-02-01", "Time": "2024-02-01 20:00:00", "Account": "Brokerage",   "Account ID": "b1", "Institution": "Bank", "Group": "Investments", "Class": "Asset",     "Balance": 120000, "Hide": ""},
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "401k",        "Account ID": "r1", "Institution": "Fido", "Group": "Retirement",  "Class": "Asset",     "Balance": 200000, "Hide": ""},
        {"Date": "2024-02-01", "Time": "2024-02-01 08:00:00", "Account": "401k",        "Account ID": "r1", "Institution": "Fido", "Group": "Retirement",  "Class": "Asset",     "Balance": 220000, "Hide": ""},
        {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "HSA",         "Account ID": "h1", "Institution": "Bank", "Group": "Investments", "Class": "Asset",     "Balance":  15000, "Hide": ""},
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Savings",     "Account ID": "s1", "Institution": "Bank", "Group": "Savings",     "Class": "Asset",     "Balance":  10000, "Hide": ""},
        {"Date": "2024-02-01", "Time": "2024-02-01 08:00:00", "Account": "Savings",     "Account ID": "s1", "Institution": "Bank", "Group": "Savings",     "Class": "Asset",     "Balance":  11000, "Hide": ""},
        {"Date": "2024-02-01", "Time": "2024-02-01 08:00:00", "Account": "Margin Loan", "Account ID": "m1", "Institution": "Bank", "Group": "Investments", "Class": "Liability", "Balance":   5000, "Hide": ""},
        {"Date": "2024-02-01", "Time": "2024-02-01 08:00:00", "Account": "Hidden Acct", "Account ID": "x1", "Institution": "Bank", "Group": "Investments", "Class": "Asset",     "Balance":  99000, "Hide": "Hide"},
    ])


@pytest.fixture
def fi_transactions_df() -> pd.DataFrame:
    """Transactions spanning 12 months with a stable $1000/mo Expense baseline.

    Each month has one $1000 expense plus one $3000 income row. Excluded group
    "Travel" has a $400/mo row so filter reuse can be verified by dropping it.
    """
    rows: list[dict[str, Any]] = []
    for m in range(1, 13):
        month_str = f"2024-{m:02d}"
        rows.append({
            "Date": f"2024-{m:02d}-10", "Category": "Groceries", "Amount": -1000,
            "Account": "Checking", "Month": month_str, "Full Description": "STORE",
            "Group": "Food", "Type": "Expense", "Institution": "Bank", "Account #": "1234",
        })
        rows.append({
            "Date": f"2024-{m:02d}-15", "Category": "Flight", "Amount": -400,
            "Account": "Credit", "Month": month_str, "Full Description": "AIRLINE",
            "Group": "Travel", "Type": "Expense", "Institution": "Chase", "Account #": "5678",
        })
        rows.append({
            "Date": f"2024-{m:02d}-01", "Category": "Salary", "Amount": 3000,
            "Account": "Checking", "Month": month_str, "Full Description": "PAYROLL",
            "Group": "Income", "Type": "Income", "Institution": "Bank", "Account #": "1234",
        })
    return _transactions_df(rows)


@pytest.fixture
def fi_passthrough_filters() -> dict[str, Any]:
    """Spending-side filter dict that passes every transaction through."""
    return {
        "exclude_groups": [],
        "exclude_categories": [],
        "filter_large_expenses": False,
        "expense_threshold": 999999,
    }


# ---------------------------------------------------------------------------
