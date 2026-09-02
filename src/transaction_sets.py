"""Resolve configured transaction sets against scrubbed transaction rows."""

from collections.abc import Mapping, Sequence

import pandas as pd

from src.analysis.merchants import normalize_merchant_name
from src.config import TransactionSetSettings
from src.transaction_filters import matching_transaction_terms


def _exact_mask(transactions: pd.DataFrame, column: str, values: Sequence[str]) -> pd.Series:
    """Return rows whose source value exactly equals one configured value."""
    if not values or column not in transactions:
        return pd.Series(False, index=transactions.index, dtype="bool")
    return transactions[column].fillna("").astype(str).isin(values)


def _merchant_mask(
    transactions: pd.DataFrame,
    merchants: Sequence[str],
    aliases: Mapping[str, str] | None,
) -> pd.Series:
    """Return rows whose normalized merchant equals one configured merchant."""
    if not merchants or "Full Description" not in transactions:
        return pd.Series(False, index=transactions.index, dtype="bool")
    configured = {normalize_merchant_name(merchant, aliases=aliases) for merchant in merchants}
    normalized = transactions["Full Description"].map(
        lambda description: normalize_merchant_name(description, aliases=aliases)
    )
    return normalized.isin(configured)


def _transaction_text_mask(transactions: pd.DataFrame, fragments: Sequence[str]) -> pd.Series:
    """Return rows whose description contains a configured literal fragment."""
    if not fragments or "Full Description" not in transactions:
        return pd.Series(False, index=transactions.index, dtype="bool")
    return transactions["Full Description"].map(
        lambda description: bool(matching_transaction_terms(description, fragments))
    )


def _direct_mask(
    transactions: pd.DataFrame,
    transaction_set: TransactionSetSettings,
    aliases: Mapping[str, str] | None,
) -> tuple[pd.Series, bool]:
    """Return direct selector matches and whether the set has direct selectors."""
    masks = [
        _exact_mask(transactions, "Group", transaction_set.groups),
        _exact_mask(transactions, "Category", transaction_set.categories),
        _exact_mask(transactions, "Account", transaction_set.accounts),
        _merchant_mask(transactions, transaction_set.merchants, aliases),
        _transaction_text_mask(transactions, transaction_set.transactions_like),
    ]
    has_direct_selectors = any(
        (
            transaction_set.groups,
            transaction_set.categories,
            transaction_set.accounts,
            transaction_set.merchants,
            transaction_set.transactions_like,
        )
    )
    combined = pd.Series(False, index=transactions.index, dtype="bool")
    for mask in masks:
        combined |= mask
    return combined, has_direct_selectors


def transaction_set_mask(
    transactions: pd.DataFrame,
    *,
    transaction_set_key: str,
    transaction_sets: Sequence[TransactionSetSettings],
    aliases: Mapping[str, str] | None = None,
) -> pd.Series:
    """Return rows included by one composed transaction set.

    Direct selectors and included sets are unioned. Excluded sets are removed
    last. A set with no direct selectors or inclusions starts with every input
    row, which makes the empty ``all`` set explicit and useful.
    """
    sets_by_key = {configured.key: configured for configured in transaction_sets}
    if transaction_set_key not in sets_by_key:
        raise ValueError(f"Unknown transaction set: {transaction_set_key}")

    cache: dict[str, pd.Series] = {}

    def resolve(key: str) -> pd.Series:
        cached = cache.get(key)
        if cached is not None:
            return cached
        configured = sets_by_key[key]
        included, has_direct_selectors = _direct_mask(transactions, configured, aliases)
        if not has_direct_selectors and not configured.includes:
            included = pd.Series(True, index=transactions.index, dtype="bool")
        for included_key in configured.includes:
            included |= resolve(included_key)
        for excluded_key in configured.excludes:
            included &= ~resolve(excluded_key)
        cache[key] = included
        return included

    return resolve(transaction_set_key)
