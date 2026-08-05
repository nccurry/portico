"""Integration-test fixture data and full pipeline factories."""
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.custom_types import IncomeExpenseFilters
from tests.custom_types import FullDatasetFactory, SpreadsheetBundle


# Fixtures moved from test_aggregation_integrity.py
# ---------------------------------------------------------------------------

@pytest.fixture
def passthrough_filters() -> IncomeExpenseFilters:
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
# Real CSV fixtures (generated anonymized data from tests/data/fixtures/)
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

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def _read_fixture_csv(name: str) -> pd.DataFrame:
    path = _FIXTURES_DIR / f"{name}.csv"
    if not path.exists():
        pytest.skip(f"committed synthetic fixture {path.name} is missing")
    return pd.read_csv(path)


@pytest.fixture(scope="session")
def real_transactions_csv_df() -> pd.DataFrame:
    """Raw-shape transactions.csv from tests/data/fixtures/."""
    return _read_fixture_csv("transactions")


@pytest.fixture(scope="session")
def real_balance_csv_df() -> pd.DataFrame:
    """Raw-shape balance_history.csv from tests/data/fixtures/."""
    return _read_fixture_csv("balance_history")


@pytest.fixture(scope="session")
def real_categories_csv_df() -> pd.DataFrame:
    """Raw categories.csv (with budget month columns) from tests/data/fixtures/."""
    return _read_fixture_csv("categories")


@pytest.fixture(scope="session")
def real_accounts_csv_df() -> pd.DataFrame:
    """Raw accounts.csv from tests/data/fixtures/."""
    return _read_fixture_csv("accounts")


@pytest.fixture(scope="session")
def reference_date() -> pd.Timestamp:
    """ISO date stored with the committed synthetic fixtures.

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
) -> FullDatasetFactory:
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

    def _factory() -> SpreadsheetBundle:
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
