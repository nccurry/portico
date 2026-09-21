"""Tests for reusable, composed transaction-set resolution."""

import pandas as pd

from src.config import TransactionSetSettings
from src.transaction_sets import transaction_set_mask


def _set(
    key: str,
    *,
    groups: tuple[str, ...] = (),
    categories: tuple[str, ...] = (),
    accounts: tuple[str, ...] = (),
    merchants: tuple[str, ...] = (),
    transactions_like: tuple[str, ...] = (),
    includes: tuple[str, ...] = (),
    excludes: tuple[str, ...] = (),
) -> TransactionSetSettings:
    return TransactionSetSettings(
        key=key,
        label=key.replace("_", " ").title(),
        groups=groups,
        categories=categories,
        accounts=accounts,
        merchants=merchants,
        transactions_like=transactions_like,
        includes=includes,
        excludes=excludes,
    )


def _transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Group": ["Food", "Bills", "Shopping", "Shopping", "Travel"],
            "Category": ["Groceries", "Electric", "Shopping", "Tax Return Payment", "Hotels"],
            "Account": ["Checking", "Checking", "Card", "Checking", "Travel Card"],
            "Full Description": [
                "Neighborhood Market",
                "City Electric",
                "AMAZON MKTPL*1234",
                "ACH IRS TAX PAYMENT",
                "AIRBNB RESERVATION",
            ],
        }
    )


def test_direct_selectors_use_exact_source_values_and_normalized_merchants() -> None:
    sets = (
        _set("all"),
        _set("food", groups=("Food",)),
        _set("utility", categories=("Electric",)),
        _set("card", accounts=("Card",)),
        _set("amazon", merchants=("Amazon",)),
    )

    assert transaction_set_mask(
        _transactions(),
        transaction_set_key="food",
        transaction_sets=sets,
    ).tolist() == [True, False, False, False, False]
    assert transaction_set_mask(
        _transactions(),
        transaction_set_key="utility",
        transaction_sets=sets,
    ).tolist() == [False, True, False, False, False]
    assert transaction_set_mask(
        _transactions(),
        transaction_set_key="card",
        transaction_sets=sets,
    ).tolist() == [False, False, True, False, False]
    assert transaction_set_mask(
        _transactions(),
        transaction_set_key="amazon",
        transaction_sets=sets,
        aliases={"AMAZON MKTPL": "AMAZON"},
    ).tolist() == [False, False, True, False, False]


def test_includes_union_then_excludes_subtract() -> None:
    sets = (
        _set("all"),
        _set("non_discretionary", groups=("Bills", "Travel"), transactions_like=("IRS",)),
        _set("discretionary", includes=("all",), excludes=("non_discretionary",)),
    )

    included = transaction_set_mask(
        _transactions(),
        transaction_set_key="discretionary",
        transaction_sets=sets,
    )

    assert included.tolist() == [True, False, True, False, False]


def test_transactions_like_is_case_insensitive_literal_text_not_a_regular_expression() -> None:
    transactions = pd.DataFrame(
        {
            "Group": ["Shopping", "Shopping"],
            "Category": ["Shopping", "Shopping"],
            "Account": ["Checking", "Checking"],
            "Full Description": ["ACME A.B PURCHASE", "ACME AXB PURCHASE"],
        }
    )
    sets = (_set("all"), _set("literal", transactions_like=("a.b",)))

    assert transaction_set_mask(
        transactions,
        transaction_set_key="literal",
        transaction_sets=sets,
    ).tolist() == [True, False]


def test_unknown_transaction_set_fails_clearly() -> None:
    try:
        transaction_set_mask(
            _transactions(),
            transaction_set_key="missing",
            transaction_sets=(_set("all"),),
        )
    except ValueError as error:
        assert str(error) == "Unknown transaction set: missing"
    else:
        raise AssertionError("unknown configured set should fail")
