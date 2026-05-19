"""Spreadsheet object factory fixtures."""
from collections.abc import Callable
from unittest.mock import patch

import pandas as pd
import pytest


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
