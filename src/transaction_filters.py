"""Pure transaction filtering shared by financial calculations."""

from collections.abc import Sequence

import pandas as pd

from src.config import get_settings
from src.custom_types import TransactionFilterOptions


def matching_transaction_terms(transaction_name: object, terms: Sequence[str]) -> tuple[str, ...]:
    """Return literal text fragments that match a transaction description."""
    if not isinstance(transaction_name, str):
        return ()
    normalized_name = " ".join(transaction_name.casefold().split())
    matches: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = term.strip()
        normalized_term = " ".join(cleaned.casefold().split())
        if normalized_term and normalized_term not in seen and normalized_term in normalized_name:
            matches.append(cleaned)
            seen.add(normalized_term)
    return tuple(matches)


def _transaction_match_mask(df: pd.DataFrame, terms: Sequence[str]) -> pd.Series:
    """Return rows whose Full Description matches at least one text fragment."""
    if not terms or "Full Description" not in df:
        return pd.Series(False, index=df.index, dtype="bool")
    return df["Full Description"].map(lambda name: bool(matching_transaction_terms(name, terms)))


def apply_transaction_filters(
    df: pd.DataFrame,
    filters: TransactionFilterOptions,
) -> pd.DataFrame:
    """Apply standard filters to a transaction dataframe."""
    df = df[df["Group"] != "Transfer"]

    include_groups = filters.get("include_groups", ())
    include_categories = filters.get("include_categories", ())
    include_transactions_like = filters.get("include_transactions_like", ())
    if include_groups or include_categories or include_transactions_like:
        masks: list[pd.Series] = []
        if include_groups:
            masks.append(df["Group"].isin(include_groups))
        if include_categories:
            masks.append(df["Category"].isin(include_categories))
        if include_transactions_like:
            masks.append(_transaction_match_mask(df, include_transactions_like))
        combined = masks[0]
        for mask in masks[1:]:
            combined = combined | mask
        df = df[combined]

    if filters.get("exclude_groups"):
        df = df[~df["Group"].isin(filters["exclude_groups"])]
    if filters.get("exclude_categories"):
        df = df[~df["Category"].isin(filters["exclude_categories"])]
    if filters.get("exclude_transactions_like"):
        df = df[~_transaction_match_mask(df, filters["exclude_transactions_like"])]

    if filters.get("filter_large_expenses"):
        threshold = filters.get("expense_threshold", get_settings().thresholds.expense)
        df = df[(df["Type"] != "Expense") | (df["Amount"].abs() <= threshold)]

    if filters.get("filter_large_income"):
        threshold = filters.get("income_threshold", get_settings().thresholds.income)
        df = df[(df["Type"] != "Income") | (df["Amount"].abs() <= threshold)]

    return df
