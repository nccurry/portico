from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.weekly_expenses import (
    WeeklyExpenseError,
    calculate_weekly_report,
    completed_week,
    validate_selected_categories,
)


@pytest.fixture
def category_metadata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Category": ["Everyday Food", "Local Dining", "Home Utilities", "Wages"],
            "Group": ["Food", "Food", "Bills", "Income"],
            "Type": ["Expense", "Expense", "Expense", "Income"],
            "Hide From Reports": ["", "", "", ""],
        }
    )


@pytest.fixture
def report_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2026-07-26",
                    "2026-07-27",
                    "2026-07-28",
                    "2026-07-29",
                    "2026-07-30",
                    "2026-07-31",
                    "2026-08-01",
                    "2026-07-19",
                    "2026-07-20",
                    "2026-07-21",
                    "2026-07-22",
                ],
                utc=True,
            ),
            "Category": [
                "Everyday Food",
                "Everyday Food",
                "Local Dining",
                "Home Utilities",
                "Wages",
                "",
                "Needs Review",
                "Everyday Food",
                "Local Dining",
                "Wages",
                "",
            ],
            "Amount": [
                -100.0,
                20.0,
                -50.0,
                -200.0,
                1000.0,
                -40.0,
                10.0,
                -60.0,
                -70.0,
                900.0,
                -20.0,
            ],
            "Group": [
                "Food",
                "Food",
                "Food",
                "Bills",
                "Income",
                "Uncategorized",
                "Uncategorized",
                "Food",
                "Food",
                "Income",
                "Uncategorized",
            ],
            "Type": [
                "Expense",
                "Expense",
                "Expense",
                "Expense",
                "Income",
                "",
                "",
                "Expense",
                "Expense",
                "Income",
                "",
            ],
        }
    )


def test_completed_week_uses_previous_sunday_through_saturday() -> None:
    period = completed_week(dt.date(2026, 8, 2))

    assert period.start == dt.date(2026, 7, 26)
    assert period.end == dt.date(2026, 8, 1)
    assert period.comparison_start == dt.date(2026, 7, 19)
    assert period.comparison_end == dt.date(2026, 7, 25)


def test_completed_week_does_not_include_current_saturday() -> None:
    period = completed_week(dt.date(2026, 8, 1))

    assert period.end == dt.date(2026, 7, 25)


@pytest.mark.parametrize("period_end", [dt.date(2026, 7, 31), dt.date(2026, 8, 8)])
def test_period_end_must_be_a_completed_saturday(period_end: dt.date) -> None:
    with pytest.raises(WeeklyExpenseError):
        completed_week(dt.date(2026, 8, 2), period_end)


def test_report_uses_exact_categories_and_refunds_reduce_spending(
    category_metadata: pd.DataFrame,
    report_transactions: pd.DataFrame,
) -> None:
    period = completed_week(dt.date(2026, 8, 2))
    report = calculate_weekly_report(
        report_transactions,
        category_metadata,
        ("Everyday Food", "Local Dining"),
        period,
    )

    assert [item.name for item in report.categories] == ["Everyday Food", "Local Dining"]
    assert [item.amount for item in report.categories] == [80.0, 50.0]
    assert [item.previous_amount for item in report.categories] == [60.0, 70.0]
    assert [item.change for item in report.categories] == [20.0, -20.0]
    assert report.selected_total == 130.0
    assert report.previous_selected_total == 130.0
    assert report.selected_change == 0.0
    assert report.all_expenses_total == 330.0
    assert report.uncategorized.amount == 30.0
    assert report.uncategorized.previous_amount == 20.0
    assert report.uncategorized.change == 10.0
    assert report.uncategorized.count == 2
    assert report.uncategorized.previous_count == 1
    assert report.uncategorized.count_change == 1
    assert report.uncategorized.outstanding_count == 3


def test_zero_expense_week_returns_zero_totals(category_metadata: pd.DataFrame) -> None:
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime([], utc=True),
            "Category": pd.Series(dtype=str),
            "Amount": pd.Series(dtype=float),
            "Group": pd.Series(dtype=str),
            "Type": pd.Series(dtype=str),
        }
    )
    report = calculate_weekly_report(
        transactions,
        category_metadata,
        ("Everyday Food",),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert report.categories[0].amount == 0.0
    assert report.selected_total == 0.0
    assert report.all_expenses_total == 0.0
    assert report.uncategorized.amount == 0.0
    assert report.uncategorized.count == 0
    assert report.uncategorized.outstanding_count == 0


@pytest.mark.parametrize(
    ("categories", "message"),
    [
        ((), "at least one"),
        (("Everyday Food", "Everyday Food"), "duplicates"),
        (("everyday food",), "was not found"),
        (("Wages",), "Type set to Expense"),
        ((" Everyday Food",), "exact Category value"),
    ],
)
def test_selected_category_validation(
    categories: tuple[str, ...],
    message: str,
    category_metadata: pd.DataFrame,
) -> None:
    with pytest.raises(WeeklyExpenseError, match=message):
        validate_selected_categories(categories, category_metadata)


def test_duplicate_categories_sheet_values_are_rejected(category_metadata: pd.DataFrame) -> None:
    duplicated = pd.concat([category_metadata, category_metadata.iloc[[0]]], ignore_index=True)

    with pytest.raises(WeeklyExpenseError, match="duplicate Category"):
        validate_selected_categories(("Everyday Food",), duplicated)
