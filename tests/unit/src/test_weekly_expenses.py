from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.weekly_expenses import (
    AVERAGE_WEEKS,
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
            "Full Description": [
                "KROGER STORE",
                "KROGER STORE",
                "LOCAL CAFE",
                "POWER COMPANY",
                "EMPLOYER PAYROLL",
                "MYSTERY CHARGE",
                "REVIEW CREDIT",
                "KROGER STORE",
                "LOCAL CAFE",
                "EMPLOYER PAYROLL",
                "OLD MYSTERY",
            ],
        }
    )


def test_completed_week_uses_trailing_eight_completed_weeks() -> None:
    period = completed_week(dt.date(2026, 8, 2))

    assert period.start == dt.date(2026, 7, 26)
    assert period.end == dt.date(2026, 8, 1)
    assert period.comparison_start == dt.date(2026, 5, 31)
    assert period.comparison_end == dt.date(2026, 7, 25)
    assert (period.comparison_end - period.comparison_start).days + 1 == AVERAGE_WEEKS * 7
    assert period.rolling_start == dt.date(2026, 7, 5)
    assert period.previous_rolling_start == dt.date(2026, 6, 7)
    assert period.previous_rolling_end == dt.date(2026, 7, 4)


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
    assert [item.average_amount for item in report.categories] == [7.5, 8.75]
    assert [item.change for item in report.categories] == [72.5, 41.25]
    assert [item.rolling_amount for item in report.categories] == [140.0, 120.0]
    assert [item.previous_rolling_amount for item in report.categories] == [0.0, 0.0]
    assert [item.rolling_change for item in report.categories] == [140.0, 120.0]
    assert [vendor.name for vendor in report.categories[0].top_vendors] == ["KROGER STORE"]
    assert report.categories[0].top_vendors[0].amount == 80.0
    assert report.selected_total == 130.0
    assert report.average_selected_total == 16.25
    assert report.selected_change == 113.75
    assert report.rolling_selected_total == 260.0
    assert report.previous_rolling_selected_total == 0.0
    assert report.rolling_selected_change == 260.0
    assert report.all_expenses_total == 330.0
    assert report.uncategorized_count == 3


def test_zero_expense_week_returns_zero_totals(category_metadata: pd.DataFrame) -> None:
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime([], utc=True),
            "Category": pd.Series(dtype=str),
            "Amount": pd.Series(dtype=float),
            "Group": pd.Series(dtype=str),
            "Type": pd.Series(dtype=str),
            "Full Description": pd.Series(dtype=str),
        }
    )
    report = calculate_weekly_report(
        transactions,
        category_metadata,
        ("Everyday Food",),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert report.categories[0].amount == 0.0
    assert report.categories[0].average_amount == 0.0
    assert report.categories[0].top_vendors == ()
    assert report.categories[0].rolling_amount == 0.0
    assert report.categories[0].previous_rolling_amount == 0.0
    assert report.selected_total == 0.0
    assert report.rolling_selected_total == 0.0
    assert report.previous_rolling_selected_total == 0.0
    assert report.all_expenses_total == 0.0
    assert report.uncategorized_count == 0


def test_rolling_summary_compares_adjacent_four_week_periods(
    category_metadata: pd.DataFrame,
) -> None:
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2026-08-01", "2026-07-05", "2026-07-04", "2026-06-07", "2026-06-06"],
                utc=True,
            ),
            "Category": ["Everyday Food"] * 5,
            "Amount": [-100.0, -20.0, -40.0, -10.0, -999.0],
            "Group": ["Food"] * 5,
            "Type": ["Expense"] * 5,
            "Full Description": ["MARKET"] * 5,
        }
    )

    report = calculate_weekly_report(
        transactions,
        category_metadata,
        ("Everyday Food",),
        completed_week(dt.date(2026, 8, 2)),
    )

    category = report.categories[0]
    assert category.rolling_amount == 120.0
    assert category.previous_rolling_amount == 50.0
    assert category.rolling_change == 70.0
    assert report.rolling_selected_total == 120.0
    assert report.previous_rolling_selected_total == 50.0


def test_report_limits_vendors_to_top_three(category_metadata: pd.DataFrame) -> None:
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-26"] * 5, utc=True),
            "Category": ["Everyday Food"] * 5,
            "Amount": [-60.0, -40.0, -50.0, -30.0, -20.0],
            "Group": ["Food"] * 5,
            "Type": ["Expense"] * 5,
            "Full Description": [
                "ALPHA MARKET",
                "ALPHA MARKET",
                "BRAVO MARKET",
                "CHARLIE MARKET",
                "DELTA MARKET",
            ],
        }
    )

    report = calculate_weekly_report(
        transactions,
        category_metadata,
        ("Everyday Food",),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert [(vendor.name, vendor.amount) for vendor in report.categories[0].top_vendors] == [
        ("ALPHA MARKET", 100.0),
        ("BRAVO MARKET", 50.0),
        ("CHARLIE MARKET", 30.0),
    ]


def test_selected_average_uses_combined_unrounded_spending() -> None:
    metadata = pd.DataFrame(
        {
            "Category": ["A", "B"],
            "Group": ["Group", "Group"],
            "Type": ["Expense", "Expense"],
            "Hide From Reports": ["", ""],
        }
    )
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-19", "2026-07-19"], utc=True),
            "Category": ["A", "B"],
            "Amount": [-0.04, -0.04],
            "Group": ["Group", "Group"],
            "Type": ["Expense", "Expense"],
            "Full Description": ["ALPHA", "BRAVO"],
        }
    )

    report = calculate_weekly_report(
        transactions,
        metadata,
        ("A", "B"),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert [item.average_amount for item in report.categories] == [0.01, 0.01]
    assert report.average_selected_total == 0.01


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
