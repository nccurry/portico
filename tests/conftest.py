"""Shared pytest fixtures for the Tiller Streamlit budgeting app."""
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Column definitions (single source of truth for every fixture)
# ---------------------------------------------------------------------------

TRANSACTIONS_SCRUBBED_COLUMNS = [
    "Date", "Category", "Amount", "Account", "Month",
    "Full Description", "Group", "Type", "Institution", "Account #",
]

BALANCE_HISTORY_SCRUBBED_COLUMNS = [
    "Date", "Time", "Account", "Account #", "Account ID", "Balance ID",
    "Institution", "Balance", "Month", "Week", "Type", "Class",
    "Account Status", "Date Added", "Group", "Hide",
]

TRANSACTIONS_RAW_COLUMNS = [
    "Unnamed: 0", "Date", "Category", "Amount", "Account", "Month",
    "Full Description", "Group", "Type", "Institution", "Account #",
    "Week", "Date Added", "Categorized Date",
]

BALANCE_HISTORY_RAW_COLUMNS = [
    "Unnamed: 0", "Date", "Time", "Account", "Account #", "Account ID",
    "Balance ID", "Institution", "Balance", "Month", "Week", "Type",
    "Class", "Account Status", "Date Added", "Group", "Hide",
]


# ---------------------------------------------------------------------------
# Helper: quick UTC timestamp
# ---------------------------------------------------------------------------

def _ts(date_str: str) -> pd.Timestamp:
    """Return a UTC-aware Timestamp from a 'YYYY-MM-DD' string."""
    return pd.Timestamp(date_str, tz="UTC")


# ---------------------------------------------------------------------------
# 1. disable_streamlit  (autouse)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def disable_streamlit():
    """Neuter Streamlit decorators and helpers so tests never touch a running app."""
    def _passthrough_decorator(*args, **kwargs):
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
        (0, "01/15/2024", "Salary",      "$3,500.00", "Checking",    "01/01/2024", "Payroll deposit",  "Income",   "Income",  "Bank of America", "1234", "01/15/2024", "01/10/2024", "01/16/2024"),
        (1, "02/03/2024", "Groceries",   "-$120.50",  "Checking",    "02/01/2024", "Whole Foods",      "Food",     "Expense", "Bank of America", "1234", "02/05/2024", "02/01/2024", "02/04/2024"),
        (2, "02/20/2024", "Electric",    "-$95.00",   "Checking",    "02/01/2024", "Duke Energy",      "Bills",    "Expense", "Bank of America", "1234", "02/19/2024", "02/15/2024", "02/21/2024"),
        (3, "03/10/2024", "Salary",      "$3,500.00", "Checking",    "03/01/2024", "Payroll deposit",  "Income",   "Income",  "Bank of America", "1234", "03/11/2024", "03/05/2024", "03/11/2024"),
        (4, "04/05/2024", "Restaurants", "-$45.75",   "Credit Card", "04/01/2024", "Olive Garden",     "Food",     "Expense", "Chase",           "5678", "04/08/2024", "04/01/2024", "04/06/2024"),
    ]
    return pd.DataFrame(rows, columns=TRANSACTIONS_RAW_COLUMNS)


# ---------------------------------------------------------------------------
# 8. raw_balance_df  (pre-scrub format)
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_balance_df() -> pd.DataFrame:
    """Mimics what Google Sheets returns before BalanceHistorySpreadsheet.scrub()."""
    rows = [
        (0, "01/01/2024", "01/01/2024 08:00:00", "Checking",    "1234", "acct-001", "bal-001",
         "Bank of America", "$5,000.00", "01/01/2024", "01/01/2024", "Depository", "Asset",
         "Active", "01/01/2023", "Checking", None),
        (1, "02/01/2024", "02/01/2024 08:00:00", "Checking",    "1234", "acct-001", "bal-002",
         "Bank of America", "$5,200.00", "02/01/2024", "02/05/2024", "Depository", "Asset",
         "Active", "01/01/2023", "Checking", None),
        (2, "01/01/2024", "01/01/2024 09:00:00", "Credit Card", "5678", "acct-002", "bal-003",
         "Chase",           "$1,500.00", "01/01/2024", "01/01/2024", "Credit",     "Liability",
         "Active", "06/01/2023", "Credit Card", None),
        (3, "02/01/2024", "02/01/2024 09:00:00", "Credit Card", "5678", "acct-002", "bal-004",
         "Chase",           "$1,800.00", "02/01/2024", "02/05/2024", "Credit",     "Liability",
         "Active", "06/01/2023", "Credit Card", "Hide"),
    ]
    return pd.DataFrame(rows, columns=BALANCE_HISTORY_RAW_COLUMNS)


# ---------------------------------------------------------------------------
# 9. make_transactions_spreadsheet  (factory fixture)
# ---------------------------------------------------------------------------

@pytest.fixture
def make_transactions_spreadsheet(scrubbed_transactions_df):
    """Factory that returns a TransactionsSpreadsheet with load() patched out.

    Usage::

        def test_something(make_transactions_spreadsheet):
            ts = make_transactions_spreadsheet()           # uses default 8-row df
            ts = make_transactions_spreadsheet(custom_df)  # uses caller-supplied df
    """
    from src.spreadsheet import TransactionsSpreadsheet, Spreadsheet

    def _factory(df: pd.DataFrame | None = None):
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
def make_balance_spreadsheet(scrubbed_balance_df):
    """Factory that returns a BalanceHistorySpreadsheet with load() patched out.

    Usage::

        def test_something(make_balance_spreadsheet):
            bs = make_balance_spreadsheet()           # uses default balance df
            bs = make_balance_spreadsheet(custom_df)  # uses caller-supplied df
    """
    from src.spreadsheet import BalanceHistorySpreadsheet, Spreadsheet

    def _factory(df: pd.DataFrame | None = None):
        if df is None:
            df = scrubbed_balance_df

        with patch.object(Spreadsheet, "load", lambda self: None):
            with patch.object(BalanceHistorySpreadsheet, "scrub",
                              lambda self: setattr(self, "scrubbed_df", df)):
                return BalanceHistorySpreadsheet()

    return _factory
