"""Tests for single-entity year-over-year spending analysis."""

import pandas as pd
import pytest

from src.analysis.year_over_year import (
    HISTORY_COLUMNS,
    TOTAL_COLUMNS,
    build_year_over_year_history,
    build_year_totals,
    ordered_spending_categories,
    spending_entities,
    summarize_year_over_year,
)
from src.config import TransactionSetSettings


def _transactions(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults: dict[str, object] = {
        "Date": "2024-01-15",
        "Type": "Expense",
        "Amount": -100.0,
        "Group": "Bills",
        "Category": "Electric",
        "Full Description": "STORE PURCHASE",
    }
    return pd.DataFrame([defaults | row for row in rows])


def test_spending_entities_are_expense_only_and_sorted() -> None:
    transactions = _transactions(
        [
            {"Category": "Water"},
            {"Category": "Electric"},
            {"Category": "Salary", "Type": "Income", "Group": "Income"},
            {"Category": "  "},
        ]
    )

    assert spending_entities(transactions, "Category") == ["Electric", "Water"]
    assert spending_entities(transactions, "Group") == ["Bills"]


def test_spending_entities_rejects_unknown_dimension() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        spending_entities(_transactions([]), "Merchant")


def test_ordered_spending_categories_uses_the_rows_already_selected_by_a_transaction_set() -> None:
    transactions = _transactions(
        [
            {"Category": "Electric", "Amount": -300.0},
            {"Category": "Water Bill", "Amount": -100.0},
            {"Category": "Mortgage Payment", "Amount": -2_000.0},
            {"Category": "Internet", "Group": "Shopping", "Amount": -500.0},
            {"Category": "Rent", "Group": "Housing", "Amount": -1_200.0},
        ]
    )

    selected = transactions[transactions["Category"].isin(["Electric", "Water Bill", "Rent"])]

    assert ordered_spending_categories(selected) == [
        "Rent",
        "Electric",
        "Water Bill",
    ]


def test_configured_discretionary_history_uses_the_shared_transaction_set() -> None:
    transactions = _transactions(
        [
            {"Category": "Video Games", "Group": "Entertainment", "Amount": -50.0},
            {"Category": "Misc Shopping", "Group": "Shopping", "Amount": -200.0},
            {"Category": "Restaurants / Bars", "Group": "Food", "Amount": -150.0},
            {"Category": "Groceries", "Group": "Food", "Amount": -500.0},
            {"Category": "Flights", "Group": "Travel", "Amount": -1_000.0},
            {"Category": "Credit Card Payment", "Group": "Transfer", "Amount": -1_500.0},
            {"Category": "Given Gift", "Group": "Shopping", "Amount": -2_000.0},
            {
                "Category": "Tax Return Payment",
                "Group": "Shopping",
                "Amount": -3_000.0,
            },
        ]
    )

    transaction_sets = (
        TransactionSetSettings("all", "All", (), (), (), (), (), (), ()),
        TransactionSetSettings(
            "non_discretionary",
            "Non-discretionary",
            ("Bills", "Travel"),
            ("Given Gift", "Tax Return Payment"),
            (),
            (),
            (),
            (),
            (),
        ),
        TransactionSetSettings(
            "discretionary",
            "Discretionary",
            (),
            (),
            (),
            (),
            ("IRS", "AIRBNB"),
            ("all",),
            ("non_discretionary",),
        ),
    )

    assert ordered_spending_categories(
        transactions[transactions["Category"].isin(["Video Games", "Misc Shopping", "Restaurants / Bars", "Groceries"])]
    ) == ["Groceries", "Misc Shopping", "Restaurants / Bars", "Video Games"]

    history = build_year_over_year_history(
        transactions,
        dimension="Category",
        entity="Misc Shopping",
        transaction_set_key="discretionary",
        transaction_sets=transaction_sets,
    )

    assert history.loc[history["Month"].eq(1), "Spending"].tolist() == pytest.approx([200.0])


def test_history_zero_fills_covered_months_and_preserves_refunds() -> None:
    transactions = _transactions(
        [
            {"Date": "2023-03-05", "Category": "Other", "Group": "Shopping"},
            {"Date": "2023-06-05", "Amount": -100.0},
            {"Date": "2024-01-05", "Amount": -120.0},
            {"Date": "2024-02-05", "Amount": 20.0},
            {"Date": "2025-03-05", "Category": "Other", "Group": "Shopping"},
        ]
    )

    result = build_year_over_year_history(
        transactions,
        dimension="Category",
        entity="Electric",
    )

    assert result.loc[result["Year"].eq(2023), "Month"].tolist() == list(range(3, 13))
    assert result.loc[result["Year"].eq(2025), "Month"].tolist() == [1, 2, 3]
    indexed = result.set_index(["Year", "Month"])["Spending"]
    assert indexed.loc[2023, 6] == pytest.approx(100.0)
    assert indexed.loc[2024, 1] == pytest.approx(120.0)
    assert indexed.loc[2024, 2] == pytest.approx(-20.0)
    assert indexed.loc[2024, 3] == pytest.approx(0.0)
    assert result.loc[result["Year"].eq(2025), "Is_Current"].all()


def test_history_rejects_unknown_dimension() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        build_year_over_year_history(
            _transactions([{}]),
            dimension="Merchant",
            entity="Store",
        )


def test_empty_history_has_exact_schema() -> None:
    result = build_year_over_year_history(
        _transactions([{"Category": "Water"}]),
        dimension="Category",
        entity="Electric",
    )

    assert result.empty
    assert result.columns.tolist() == HISTORY_COLUMNS


def test_year_totals_compare_every_year_through_same_month() -> None:
    history = build_year_over_year_history(
        _transactions(
            [
                {"Date": "2023-01-05", "Amount": -80.0},
                {"Date": "2023-04-05", "Amount": -400.0},
                {"Date": "2024-01-05", "Amount": -100.0},
                {"Date": "2024-04-05", "Amount": -500.0},
            ]
        ),
        dimension="Category",
        entity="Electric",
    )

    result = build_year_totals(history, through_month=3)

    assert result.columns.tolist() == TOTAL_COLUMNS
    assert result["Year"].tolist() == [2024, 2023]
    assert result["Spending_Through_Month"].tolist() == [100.0, 80.0]
    assert result.iloc[0]["Change"] == pytest.approx(20.0)
    assert result.iloc[0]["Change_Pct"] == pytest.approx(25.0)


def test_summary_reports_matched_current_and_previous_years() -> None:
    history = build_year_over_year_history(
        _transactions(
            [
                {"Date": "2023-01-05", "Amount": -80.0},
                {"Date": "2024-01-05", "Amount": -100.0},
                {"Date": "2024-03-05", "Amount": -20.0},
            ]
        ),
        dimension="Category",
        entity="Electric",
    )

    assert summarize_year_over_year(history, through_month=3) == {
        "current_year": 2024,
        "current_total": 120.0,
        "previous_year": 2023,
        "previous_total": 80.0,
        "change": 40.0,
        "change_pct": 50.0,
        "through_month": 3,
    }


def test_summary_marks_previous_year_unavailable_for_new_category() -> None:
    history = build_year_over_year_history(
        _transactions([{"Date": "2024-03-05", "Amount": -100.0}]),
        dimension="Category",
        entity="Electric",
    )

    summary = summarize_year_over_year(history, through_month=3)

    assert summary["current_total"] == pytest.approx(100.0)
    assert summary["previous_year"] is None
    assert summary["previous_total"] is None
    assert summary["change"] is None
    assert summary["change_pct"] is None


def test_empty_totals_and_summary_are_stable() -> None:
    history = pd.DataFrame(columns=HISTORY_COLUMNS)

    assert build_year_totals(history, through_month=3).columns.tolist() == TOTAL_COLUMNS
    assert summarize_year_over_year(history, through_month=3) == {
        "current_year": 0,
        "current_total": 0.0,
        "previous_year": None,
        "previous_total": None,
        "change": None,
        "change_pct": None,
        "through_month": 3,
    }
