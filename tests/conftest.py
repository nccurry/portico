"""Shared pytest fixtures for the Tiller Streamlit budgeting app."""
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from tests._helpers import _ts, _transactions_df, _balance_df


# ---------------------------------------------------------------------------
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
# 1. disable_streamlit  (autouse)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def disable_streamlit() -> Generator[None]:
    """Neuter Streamlit decorators and helpers so tests never touch a running app."""
    def _passthrough_decorator(*args: Any, **kwargs: Any) -> Any:
        """Return the function unchanged whether used as @decorator or @decorator(...)."""
        if args and callable(args[0]):
            return args[0]
        return lambda fn: fn

    with (
        patch("streamlit.cache_data", side_effect=_passthrough_decorator),
        patch("streamlit.cache_resource", side_effect=_passthrough_decorator),
        patch("streamlit.stop", MagicMock()),
    ):
        yield


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
# 9. make_transactions_spreadsheet  (factory fixture)
# ---------------------------------------------------------------------------

@pytest.fixture
def make_transactions_spreadsheet(
    scrubbed_transactions_df: pd.DataFrame,
) -> Callable[[pd.DataFrame | None], "TransactionsSpreadsheet"]:  # type: ignore[name-defined]  # noqa: UP037, F821
    """Factory that returns a TransactionsSpreadsheet with load() patched out.

    Usage::

        def test_something(make_transactions_spreadsheet):
            ts = make_transactions_spreadsheet()           # uses default 8-row df
            ts = make_transactions_spreadsheet(custom_df)  # uses caller-supplied df
    """
    from src.spreadsheet import TransactionsSpreadsheet, Spreadsheet

    def _factory(df: pd.DataFrame | None = None) -> TransactionsSpreadsheet:
        """Build a TransactionsSpreadsheet with scrubbed_df set to *df*."""
        if df is None:
            df = scrubbed_transactions_df

        with patch.object(Spreadsheet, "load", lambda self: None):
            with patch.object(TransactionsSpreadsheet, "scrub",
                              lambda self: setattr(self, "scrubbed_df", df)):
                return TransactionsSpreadsheet()

    return _factory


# ---------------------------------------------------------------------------
# 10. make_balance_spreadsheet  (factory fixture)
# ---------------------------------------------------------------------------

@pytest.fixture
def make_balance_spreadsheet(
    scrubbed_balance_df: pd.DataFrame,
) -> Callable[[pd.DataFrame | None], "BalanceHistorySpreadsheet"]:  # type: ignore[name-defined]  # noqa: UP037, F821
    """Factory that returns a BalanceHistorySpreadsheet with load() patched out.

    Usage::

        def test_something(make_balance_spreadsheet):
            bs = make_balance_spreadsheet()           # uses default balance df
            bs = make_balance_spreadsheet(custom_df)  # uses caller-supplied df
    """
    from src.spreadsheet import BalanceHistorySpreadsheet, Spreadsheet

    def _factory(df: pd.DataFrame | None = None) -> BalanceHistorySpreadsheet:
        """Build a BalanceHistorySpreadsheet with scrubbed_df set to *df*."""
        if df is None:
            df = scrubbed_balance_df

        with patch.object(Spreadsheet, "load", lambda self: None):
            with patch.object(BalanceHistorySpreadsheet, "scrub",
                              lambda self: setattr(self, "scrubbed_df", df)):
                return BalanceHistorySpreadsheet()

    return _factory


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
# 12. make_categories_spreadsheet  (factory fixture)
# ---------------------------------------------------------------------------

@pytest.fixture
def make_categories_spreadsheet(
    scrubbed_categories_df: pd.DataFrame,
) -> Callable[..., "CategoriesSpreadsheet"]:  # type: ignore[name-defined]  # noqa: UP037, F821
    """Factory that returns a CategoriesSpreadsheet with load() patched out."""
    from src.spreadsheet import CategoriesSpreadsheet, Spreadsheet

    def _factory(
        df: pd.DataFrame | None = None,
        budget_df: pd.DataFrame | None = None,
    ) -> CategoriesSpreadsheet:
        """Build a CategoriesSpreadsheet with scrubbed_df and optional budget_df."""
        if df is None:
            df = scrubbed_categories_df

        def _scrub(self: CategoriesSpreadsheet) -> None:
            """Inject scrubbed_df and budget_df without hitting Google Sheets."""
            self.scrubbed_df = df
            if budget_df is not None:
                self.budget_df = budget_df
            else:
                self.budget_df = pd.DataFrame(
                    columns=["Category", "Month_Num", "Budget", "Group", "Type"]
                )

        with patch.object(Spreadsheet, "load", lambda self: None):
            with patch.object(CategoriesSpreadsheet, "scrub", _scrub):
                return CategoriesSpreadsheet()

    return _factory


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
def categories_for_scrub() -> "CategoriesSpreadsheet":  # type: ignore[name-defined]  # noqa: UP037, F821
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
def accounts_for_scrub() -> "AccountsSpreadsheet":  # type: ignore[name-defined]  # noqa: UP037, F821
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
# Fixtures moved from test_aggregation_integrity.py
# ---------------------------------------------------------------------------

@pytest.fixture
def passthrough_filters() -> dict[str, Any]:
    """Passthrough filters for aggregation integrity tests."""
    return {
        'exclude_groups': [],
        'exclude_categories': [],
        'filter_large_income': False,
        'income_threshold': 999999,
        'filter_large_expenses': False,
        'expense_threshold': 999999,
        'target_rate': 20,
    }


@pytest.fixture
def full_date_range() -> tuple[pd.Timestamp, pd.Timestamp]:
    """Full year date range for aggregation tests."""
    return (
        pd.Timestamp('2024-01-01', tz='UTC'),
        pd.Timestamp('2024-12-31', tz='UTC'),
    )


# ---------------------------------------------------------------------------
# Real CSV fixtures (committed anonymized data from tests/data/fixtures/)
# ---------------------------------------------------------------------------
#
# These drive the real Spreadsheet.scrub() pipeline end-to-end.
#
# SINGLE-SOURCE-OF-TRUTH RULE: pick ONE factory style per test.
#   - per-sheet factories (make_transactions_spreadsheet etc.) for unit
#     isolation; they patch Spreadsheet.load.
#   - make_full_dataset for integration tests; it patches all four
#     load_*_data() loaders simultaneously.
# Mixing them stacks patches in non-obvious order and produces
# "why is this dataframe empty?" bugs. See tests/data/README.md.

_FIXTURES_DIR = Path(__file__).resolve().parent / "data" / "fixtures"


@pytest.fixture(scope="session")
def real_transactions_csv_df() -> pd.DataFrame:
    """Raw-shape transactions.csv from tests/data/fixtures/."""
    return pd.read_csv(_FIXTURES_DIR / "transactions.csv")


@pytest.fixture(scope="session")
def real_balance_csv_df() -> pd.DataFrame:
    """Raw-shape balance_history.csv from tests/data/fixtures/."""
    return pd.read_csv(_FIXTURES_DIR / "balance_history.csv")


@pytest.fixture(scope="session")
def real_categories_csv_df() -> pd.DataFrame:
    """Raw categories.csv (with budget month columns) from tests/data/fixtures/."""
    return pd.read_csv(_FIXTURES_DIR / "categories.csv")


@pytest.fixture(scope="session")
def real_accounts_csv_df() -> pd.DataFrame:
    """Raw accounts.csv from tests/data/fixtures/."""
    return pd.read_csv(_FIXTURES_DIR / "accounts.csv")


@pytest.fixture(scope="session")
def reference_date() -> pd.Timestamp:
    """ISO date emitted by scripts/generate_test_fixtures.py.

    Use with @pytest.mark.uses_real_dates to keep date-sensitive logic stable
    against the committed fixture.
    """
    text = (_FIXTURES_DIR / "REFERENCE_DATE.txt").read_text(encoding="utf-8").strip()
    return pd.Timestamp(text)


@pytest.fixture
def make_full_dataset(
    real_transactions_csv_df: pd.DataFrame,
    real_balance_csv_df: pd.DataFrame,
    real_categories_csv_df: pd.DataFrame,
    real_accounts_csv_df: pd.DataFrame,
) -> Callable[..., tuple[Any, Any, Any, Any]]:
    """Factory returning (transactions, balance, categories, accounts) Spreadsheets.

    Each goes through the real scrub() pipeline with all four cross-sheet
    loaders patched simultaneously, so categories/accounts joins land
    against the same anonymized fixture data.

    Usage::

        def test_foo(make_full_dataset):
            txns, bal, cats, accts = make_full_dataset()
    """
    from src.spreadsheet import (
        AccountsSpreadsheet,
        BalanceHistorySpreadsheet,
        CategoriesSpreadsheet,
        Spreadsheet,
        TransactionsSpreadsheet,
    )

    raw_by_name = {
        "transactions": real_transactions_csv_df,
        "balance_history": real_balance_csv_df,
        "categories": real_categories_csv_df,
        "accounts": real_accounts_csv_df,
    }

    def _factory() -> tuple[
        TransactionsSpreadsheet,
        BalanceHistorySpreadsheet,
        CategoriesSpreadsheet,
        AccountsSpreadsheet,
    ]:
        """Build all four spreadsheets through the real scrub pipeline."""
        def _load(self: Spreadsheet) -> None:
            self.raw_df = raw_by_name[self.name].copy()

        with patch.object(Spreadsheet, "load", _load):
            cats = CategoriesSpreadsheet()
            accts = AccountsSpreadsheet()
            with (
                patch("src.spreadsheet.load_categories_data", return_value=cats),
                patch("src.spreadsheet.load_accounts_data", return_value=accts),
            ):
                txns = TransactionsSpreadsheet()
                bal = BalanceHistorySpreadsheet()
        return txns, bal, cats, accts

    return _factory


# ---------------------------------------------------------------------------
# freezegun integration -- pin time for tests marked @pytest.mark.uses_real_dates
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def frozen_time(
    request: pytest.FixtureRequest,
    reference_date: pd.Timestamp,
) -> Generator[None]:
    """Freeze time to REFERENCE_DATE for tests marked uses_real_dates.

    Patches both ``datetime.datetime.now`` (via freezegun) and
    ``pandas.Timestamp.now`` directly. freezegun alone cannot freeze
    ``pd.Timestamp.now()`` because pandas reads the wall clock at the C
    level and bypasses Python-side ``time.time``/``datetime`` patches.

    tz_offset=0 keeps freezegun's faked datetime aligned with UTC so it does
    not collide with tz-aware Timestamps in fixtures.
    """
    if request.node.get_closest_marker("uses_real_dates") is None:
        yield
        return

    from freezegun import freeze_time

    iso = reference_date.isoformat()
    frozen_utc = reference_date if reference_date.tz is not None else reference_date.tz_localize("UTC")

    @classmethod  # type: ignore[misc]
    def _frozen_now(
        cls: type[pd.Timestamp],
        tz: Any = None,
    ) -> pd.Timestamp:
        """Return REFERENCE_DATE in the requested tz (or naive)."""
        if tz is None:
            return frozen_utc.tz_convert("UTC").tz_localize(None)
        return frozen_utc.tz_convert(tz)

    original_now = pd.Timestamp.now
    pd.Timestamp.now = _frozen_now  # type: ignore[method-assign,assignment]
    try:
        with freeze_time(iso, tz_offset=0):
            yield
    finally:
        pd.Timestamp.now = original_now  # type: ignore[method-assign]
