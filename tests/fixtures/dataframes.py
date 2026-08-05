"""Core spreadsheet and scrubber DataFrame fixtures."""

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest

from tests._helpers import _balance_df, _transactions_df, _ts

if TYPE_CHECKING:
    from src.spreadsheet import AccountsSpreadsheet, CategoriesSpreadsheet


# Column definitions (single source of truth for every fixture)
# ---------------------------------------------------------------------------

TRANSACTIONS_SCRUBBED_COLUMNS: list[str] = [
    "Date", "Category", "Amount", "Account", "Month",
    "Full Description", "Group", "Type", "Institution", "Account #",
]

BALANCE_HISTORY_SCRUBBED_COLUMNS: list[str] = [
    "Date", "Time", "Account", "Account #", "Account ID", "Balance ID",
    "Institution", "Balance", "Month", "Week", "Type", "Class",
    "Account Status", "Date Added", "Group", "Hide",
]

TRANSACTIONS_RAW_COLUMNS: list[str] = [
    "Unnamed: 0", "Date", "Category", "Amount", "Account", "Month",
    "Full Description", "Institution", "Account #",
    "Week", "Date Added", "Categorized Date",
]

BALANCE_HISTORY_RAW_COLUMNS: list[str] = [
    "Unnamed: 0", "Date", "Time", "Account", "Account #", "Account ID",
    "Balance ID", "Institution", "Balance", "Month", "Week", "Type",
    "Class", "Account Status", "Date Added",
]

CATEGORIES_COLUMNS: list[str] = ["Category", "Group", "Type", "Hide From Reports"]


# ---------------------------------------------------------------------------

# 2. scrubbed_transactions_df  (8 rows, Jan-Jun 2024)
# ---------------------------------------------------------------------------

@pytest.fixture
def scrubbed_transactions_df() -> pd.DataFrame:
    """Eight transactions spanning Jan-Jun 2024 with a mix of types and groups."""
    rows = [
        (_ts("2024-01-15"), "Salary",      3500.00,  "Checking",    "2024-01", "Payroll deposit",  "Income",   "Income",  "Bank of America", "1234"),
        (_ts("2024-02-03"), "Groceries",   -120.50,  "Checking",    "2024-02", "Whole Foods",      "Food",     "Expense", "Bank of America", "1234"),
        (_ts("2024-02-20"), "Electric",     -95.00,  "Checking",    "2024-02", "Duke Energy",      "Bills",    "Expense", "Bank of America", "1234"),
        (_ts("2024-03-10"), "Salary",      3500.00,  "Checking",    "2024-03", "Payroll deposit",  "Income",   "Income",  "Bank of America", "1234"),
        (_ts("2024-04-05"), "Restaurants",  -45.75,  "Credit Card", "2024-04", "Olive Garden",     "Food",     "Expense", "Chase",           "5678"),
        (_ts("2024-04-22"), "Amazon",      -200.00,  "Credit Card", "2024-04", "Amazon purchase",  "Shopping", "Expense", "Chase",           "5678"),
        (_ts("2024-05-15"), "Salary",      3500.00,  "Checking",    "2024-05", "Payroll deposit",  "Income",   "Income",  "Bank of America", "1234"),
        (_ts("2024-06-01"), "Internet",     -79.99,  "Checking",    "2024-06", "Spectrum bill",    "Bills",    "Expense", "Bank of America", "1234"),
    ]
    return pd.DataFrame(rows, columns=TRANSACTIONS_SCRUBBED_COLUMNS)


# ---------------------------------------------------------------------------
# 3. extended_transactions_df  (100 rows, deterministic)
# ---------------------------------------------------------------------------

@pytest.fixture
def extended_transactions_df() -> pd.DataFrame:
    """100 random-but-reproducible transactions for stress / statistical tests."""
    rng = np.random.default_rng(42)

    n = 100
    categories =   ["Salary", "Groceries", "Electric", "Restaurants", "Amazon", "Internet"]
    groups =       ["Income", "Food",      "Bills",    "Food",        "Shopping", "Bills"]
    types =        ["Income", "Expense",   "Expense",  "Expense",     "Expense",  "Expense"]
    accounts =     ["Checking", "Credit Card"]
    institutions = ["Bank of America", "Chase"]
    account_nums = ["1234", "5678"]

    cat_idx = rng.integers(0, len(categories), size=n)
    acct_idx = rng.integers(0, len(accounts), size=n)

    # Dates spread across Jan-Jun 2024
    start = pd.Timestamp("2024-01-01", tz="UTC")
    offsets = pd.to_timedelta(rng.integers(0, 181, size=n), unit="D")
    dates = start + offsets

    amounts = np.where(
        np.array(types)[cat_idx] == "Income",
        rng.uniform(2000, 5000, size=n).round(2),
        -rng.uniform(10, 500, size=n).round(2),
    )

    months = pd.Series(dates).dt.strftime("%Y-%m").values

    df = pd.DataFrame({
        "Date": dates,
        "Category": np.array(categories)[cat_idx],
        "Amount": amounts,
        "Account": np.array(accounts)[acct_idx],
        "Month": months,
        "Full Description": [f"Txn {i}" for i in range(n)],
        "Group": np.array(groups)[cat_idx],
        "Type": np.array(types)[cat_idx],
        "Institution": np.array(institutions)[acct_idx],
        "Account #": np.array(account_nums)[acct_idx],
    })
    return df


# ---------------------------------------------------------------------------
# 4. empty_transactions_df
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_transactions_df() -> pd.DataFrame:
    """Empty DataFrame with the correct scrubbed transactions schema."""
    return pd.DataFrame(columns=TRANSACTIONS_SCRUBBED_COLUMNS).astype({
        "Date": "datetime64[ns, UTC]",
        "Category": "str",
        "Amount": "float64",
        "Account": "str",
        "Month": "str",
        "Full Description": "str",
        "Group": "str",
        "Type": "str",
        "Institution": "str",
        "Account #": "str",
    })


# ---------------------------------------------------------------------------
# 5. single_row_transactions_df
# ---------------------------------------------------------------------------

@pytest.fixture
def single_row_transactions_df() -> pd.DataFrame:
    """A single Expense transaction."""
    rows = [
        (_ts("2024-03-15"), "Groceries", -55.25, "Checking", "2024-03",
         "Trader Joes", "Food", "Expense", "Bank of America", "1234"),
    ]
    return pd.DataFrame(rows, columns=TRANSACTIONS_SCRUBBED_COLUMNS)


# ---------------------------------------------------------------------------
# 6. scrubbed_balance_df
# ---------------------------------------------------------------------------

@pytest.fixture
def scrubbed_balance_df() -> pd.DataFrame:
    """Balance history with Checking (Asset) and Credit Card (Liability) across multiple dates."""
    rows = [
        # Checking - Asset
        (_ts("2024-01-01"), _ts("2024-01-01 08:00:00"), "Checking", "1234", "acct-001", "bal-001",
         "Bank of America", 5000.00, "2024-01", "01", "Depository", "Asset", "Active",
         _ts("2023-01-01"), "Checking", None),
        (_ts("2024-02-01"), _ts("2024-02-01 08:00:00"), "Checking", "1234", "acct-001", "bal-002",
         "Bank of America", 5200.00, "2024-02", "05", "Depository", "Asset", "Active",
         _ts("2023-01-01"), "Checking", None),
        (_ts("2024-03-01"), _ts("2024-03-01 08:00:00"), "Checking", "1234", "acct-001", "bal-003",
         "Bank of America", 4800.00, "2024-03", "09", "Depository", "Asset", "Active",
         _ts("2023-01-01"), "Checking", None),
        (_ts("2024-04-01"), _ts("2024-04-01 08:00:00"), "Checking", "1234", "acct-001", "bal-004",
         "Bank of America", 5500.00, "2024-04", "14", "Depository", "Asset", "Active",
         _ts("2023-01-01"), "Checking", None),
        # Credit Card - Liability
        (_ts("2024-01-01"), _ts("2024-01-01 09:00:00"), "Credit Card", "5678", "acct-002", "bal-005",
         "Chase", 1500.00, "2024-01", "01", "Credit", "Liability", "Active",
         _ts("2023-06-01"), "Credit Card", None),
        (_ts("2024-02-01"), _ts("2024-02-01 09:00:00"), "Credit Card", "5678", "acct-002", "bal-006",
         "Chase", 1800.00, "2024-02", "05", "Credit", "Liability", "Active",
         _ts("2023-06-01"), "Credit Card", None),
        (_ts("2024-03-01"), _ts("2024-03-01 09:00:00"), "Credit Card", "5678", "acct-002", "bal-007",
         "Chase", 1200.00, "2024-03", "09", "Credit", "Liability", "Active",
         _ts("2023-06-01"), "Credit Card", None),
        (_ts("2024-04-01"), _ts("2024-04-01 09:00:00"), "Credit Card", "5678", "acct-002", "bal-008",
         "Chase", 1600.00, "2024-04", "14", "Credit", "Liability", "Active",
         _ts("2023-06-01"), "Credit Card", None),
    ]
    return pd.DataFrame(rows, columns=BALANCE_HISTORY_SCRUBBED_COLUMNS)


# ---------------------------------------------------------------------------
# 7. raw_transactions_df  (pre-scrub format)
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_transactions_df() -> pd.DataFrame:
    """Mimics what Google Sheets returns before TransactionsSpreadsheet.scrub()."""
    rows = [
        (0, "01/15/2024", "Salary",      "$3,500.00", "Checking",    "01/01/2024", "Payroll deposit",  "Bank of America", "1234", "01/15/2024", "01/10/2024", "01/16/2024"),
        (1, "02/03/2024", "Groceries",   "-$120.50",  "Checking",    "02/01/2024", "Whole Foods",      "Bank of America", "1234", "02/05/2024", "02/01/2024", "02/04/2024"),
        (2, "02/20/2024", "Electric",    "-$95.00",   "Checking",    "02/01/2024", "Duke Energy",      "Bank of America", "1234", "02/19/2024", "02/15/2024", "02/21/2024"),
        (3, "03/10/2024", "Salary",      "$3,500.00", "Checking",    "03/01/2024", "Payroll deposit",  "Bank of America", "1234", "03/11/2024", "03/05/2024", "03/11/2024"),
        (4, "04/05/2024", "Restaurants", "-$45.75",   "Credit Card", "04/01/2024", "Olive Garden",     "Chase",           "5678", "04/08/2024", "04/01/2024", "04/06/2024"),
    ]
    return pd.DataFrame(rows, columns=TRANSACTIONS_RAW_COLUMNS)


# ---------------------------------------------------------------------------
# 8. raw_balance_df  (pre-scrub format)
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_balance_df() -> pd.DataFrame:
    """Mimics what Google Sheets returns before BalanceHistorySpreadsheet.scrub()."""
    rows = [
        (0, "01/01/2024", "01/01/2024 08:00:00", "Checking",    "xxxx1234", "65440a84a14656002f35ab01", "bal-001",
         "Bank of America", "$5,000.00", "01/01/2024", "01/01/2024", "Depository", "Asset",
         "Active", "01/01/2023"),
        (1, "02/01/2024", "02/01/2024 08:00:00", "Checking",    "xxxx1234", "65440a84a14656002f35ab01", "bal-002",
         "Bank of America", "$5,200.00", "02/01/2024", "02/05/2024", "Depository", "Asset",
         "Active", "01/01/2023"),
        (2, "01/01/2024", "01/01/2024 09:00:00", "Credit Card", "xxxx5678", "65440a84a14656002f35cd02", "bal-003",
         "Chase",           "$1,500.00", "01/01/2024", "01/01/2024", "Credit",     "Liability",
         "Active", "06/01/2023"),
        (3, "02/01/2024", "02/01/2024 09:00:00", "Credit Card", "xxxx5678", "65440a84a14656002f35cd02", "bal-004",
         "Chase",           "$1,800.00", "02/01/2024", "02/05/2024", "Credit",     "Liability",
         "Active", "06/01/2023"),
    ]
    return pd.DataFrame(rows, columns=BALANCE_HISTORY_RAW_COLUMNS)


# ---------------------------------------------------------------------------

# 11. scrubbed_categories_df
# ---------------------------------------------------------------------------

@pytest.fixture
def scrubbed_categories_df() -> pd.DataFrame:
    """Categories lookup table mapping Category to Group, Type, and Hide From Reports."""
    rows = [
        ("Salary",      "Income",   "Income",  ""),
        ("Groceries",   "Food",     "Expense", ""),
        ("Electric",    "Bills",    "Expense", ""),
        ("Restaurants", "Food",     "Expense", ""),
        ("Amazon",      "Shopping", "Expense", ""),
        ("Internet",    "Bills",    "Expense", ""),
        ("Rent",        "Housing",  "Expense", ""),
        ("Transfer",    "Transfer", "Transfer", "Hide"),
        ("Dining",      "Food",     "Expense", ""),
    ]
    return pd.DataFrame(rows, columns=CATEGORIES_COLUMNS)


# ---------------------------------------------------------------------------

# 13. raw_categories_with_budget_df  (for budget scrub tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_categories_with_budget_df() -> pd.DataFrame:
    """Raw Categories sheet with 4 metadata columns + 12 date-header budget columns."""
    return pd.DataFrame({
        "Category": ["Groceries", "Restaurants", "Electric", "Salary", None],
        "Group": ["Food", "Food", "Bills", "Income", "Bad"],
        "Type": ["Expense", "Expense", "Expense", "Income", "Expense"],
        "Hide From Reports": ["", "", "", "", ""],
        pd.Timestamp("2023-01-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-02-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-03-01"): [500, 250, 175, 0, 100],
        pd.Timestamp("2023-04-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-05-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-06-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-07-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-08-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-09-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-10-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-11-01"): [500, 200, 150, 0, 100],
        pd.Timestamp("2023-12-01"): [500, 200, 150, 0, 100],
    })


# ---------------------------------------------------------------------------
# Fixtures moved from test_spreadsheet.py
# ---------------------------------------------------------------------------

@pytest.fixture
def scrub_input_transactions_df() -> pd.DataFrame:
    """A raw DataFrame that TransactionsSpreadsheet.scrub() should clean."""
    return pd.DataFrame({
        "Unnamed: 0": [None, None],
        "Date": ["2024-01-15", "2024-02-20"],
        "Category": ["Groceries", "Rent"],
        "Amount": ["$1,234.56", "$2,000.00"],
        "Account": ["Checking", "Checking"],
        "Month": ["2024-01-01", "2024-02-01"],
        "Week": ["2024-01-15", "2024-02-19"],
        "Full Description": ["STORE", "LANDLORD"],
        "Institution": ["Bank", "Bank"],
        "Account #": ["1234", "5678"],
        "Date Added": ["2024-01-15", "2024-02-20"],
        "Categorized Date": ["2024-01-15", "2024-02-20"],
    })


@pytest.fixture
def scrub_input_balance_df() -> pd.DataFrame:
    """A raw DataFrame that BalanceHistorySpreadsheet.scrub() should clean."""
    return pd.DataFrame({
        "Unnamed: 0": [None, None, None],
        "Date": ["2024-01-15", "2024-02-20", "2024-03-01"],
        "Time": ["2024-01-15 10:00", "2024-02-20 11:00", "2024-03-01 09:00"],
        "Balance": ["$1,000.00", "$2,000.00", "$500.00"],
        "Account": ["Checking", "Savings", "Hidden"],
        "Account #": ["xxxx1234", "xxxx5678", "xxxx9999"],
        "Account ID": ["65440a84a14656002f35ab01", "65440a84a14656002f35cd02", "65440a84a14656002f35ef03"],
        "Institution": ["Bank", "Bank", "Bank"],
        "Class": ["Asset", "Asset", "Asset"],
        "Month": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "Week": ["2024-01-15", "2024-02-19", "2024-02-26"],
        "Date Added": ["2024-01-15", "2024-02-20", "2024-03-01"],
    })


@pytest.fixture
def categories_for_scrub() -> CategoriesSpreadsheet:
    """Categories lookup for scrub tests."""
    from src.spreadsheet import CategoriesSpreadsheet
    cat = CategoriesSpreadsheet.__new__(CategoriesSpreadsheet)
    cat.scrubbed_df = pd.DataFrame({
        "Category": ["Groceries", "Rent"],
        "Group": ["Food", "Housing"],
        "Type": ["Expense", "Expense"],
        "Hide From Reports": ["", ""],
    })
    return cat


@pytest.fixture
def accounts_for_scrub() -> AccountsSpreadsheet:
    """Accounts lookup for scrub tests. Keys match the composite key format."""
    from src.spreadsheet import AccountsSpreadsheet
    acct = AccountsSpreadsheet.__new__(AccountsSpreadsheet)
    acct.scrubbed_df = pd.DataFrame({
        "Account": [
            "Checking - xxxx1234 (AB01)",
            "SAVINGS - xxxx5678 (CD02)",
            "Hidden - xxxx9999 (EF03)",
        ],
        "Group": ["Assets", "Assets", "Secret"],
        "Hide": ["", "", "Hide"],
    })
    return acct


@pytest.fixture
def sample_transactions_df() -> pd.DataFrame:
    """Canonical scrubbed-format sample transactions for spreadsheet method tests."""
    return _transactions_df([
        {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,  "Account": "Checking", "Month": "2024-01", "Group": "Food",      "Type": "Expense"},
        {"Date": "2024-01-20", "Category": "Rent",      "Amount": -1200,"Account": "Checking", "Month": "2024-01", "Group": "Housing",   "Type": "Expense"},
        {"Date": "2024-02-05", "Category": "Groceries", "Amount": -60,  "Account": "Checking", "Month": "2024-02", "Group": "Food",      "Type": "Expense"},
        {"Date": "2024-02-15", "Category": "Salary",    "Amount": 3000, "Account": "Checking", "Month": "2024-02", "Group": "Income",    "Type": "Income"},
        {"Date": "2024-03-01", "Category": "Dining",    "Amount": -30,  "Account": "Credit",   "Month": "2024-03", "Group": "Food",      "Type": "Expense"},
        {"Date": "2024-03-10", "Category": "Transfer",  "Amount": 500,  "Account": "Savings",  "Month": "2024-03", "Group": "Transfers", "Type": "Transfer"},
    ])


@pytest.fixture
def sample_balance_df() -> pd.DataFrame:
    """Scrubbed-format balance history sample for spreadsheet method tests."""
    return _balance_df([
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1", "Institution": "Bank", "Group": "Assets",      "Class": "Asset",     "Balance": 5000, "Hide": ""},
        {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "Checking", "Account ID": "a1", "Institution": "Bank", "Group": "Assets",      "Class": "Asset",     "Balance": 4500, "Hide": ""},
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Savings",  "Account ID": "a2", "Institution": "Bank", "Group": "Assets",      "Class": "Asset",     "Balance": 10000,"Hide": ""},
        {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "Savings",  "Account ID": "a2", "Institution": "Bank", "Group": "Assets",      "Class": "Asset",     "Balance": 10500,"Hide": ""},
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Mortgage",  "Account ID": "a3", "Institution": "Lender","Group": "Liabilities","Class": "Liability", "Balance": 200000,"Hide": ""},
        {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "Mortgage",  "Account ID": "a3", "Institution": "Lender","Group": "Liabilities","Class": "Liability", "Balance": 199500,"Hide": ""},
    ])


# ---------------------------------------------------------------------------
