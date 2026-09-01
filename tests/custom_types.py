"""Shared type contracts for pytest fixtures and helpers."""

from collections.abc import Callable
from typing import Protocol

import pandas as pd

from src.spreadsheet import (
    AccountsSpreadsheet,
    BalanceHistorySpreadsheet,
    CategoriesSpreadsheet,
    TransactionsSpreadsheet,
)

type DataFrameRow = dict[str, object]
type SpreadsheetBundle = tuple[
    TransactionsSpreadsheet,
    BalanceHistorySpreadsheet,
    CategoriesSpreadsheet,
    AccountsSpreadsheet,
]
type FullDatasetFactory = Callable[[], SpreadsheetBundle]


class TransactionsSpreadsheetFactory(Protocol):
    """Build a transactions spreadsheet around an optional dataframe."""

    def __call__(
        self,
        df: pd.DataFrame | None = None,
    ) -> TransactionsSpreadsheet: ...


class BalanceSpreadsheetFactory(Protocol):
    """Build a balance-history spreadsheet around an optional dataframe."""

    def __call__(
        self,
        df: pd.DataFrame | None = None,
    ) -> BalanceHistorySpreadsheet: ...


class CategoriesSpreadsheetFactory(Protocol):
    """Build a categories spreadsheet with optional category and budget data."""

    def __call__(
        self,
        df: pd.DataFrame | None = None,
        budget_df: pd.DataFrame | None = None,
    ) -> CategoriesSpreadsheet: ...
