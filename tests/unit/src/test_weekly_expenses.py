from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from src.config import TransactionSetSettings
from src.weekly_expenses import AVERAGE_WEEKS, WeeklyExpenseError, calculate_weekly_report, completed_week


def _set(
    key: str,
    *,
    categories: tuple[str, ...] = (),
    groups: tuple[str, ...] = (),
    includes: tuple[str, ...] = (),
    excludes: tuple[str, ...] = (),
) -> TransactionSetSettings:
    return TransactionSetSettings(
        key=key,
        label=key.replace("_", " ").title(),
        groups=groups,
        categories=categories,
        accounts=(),
        merchants=(),
        transactions_like=(),
        includes=includes,
        excludes=excludes,
    )


@pytest.fixture
def transaction_sets() -> tuple[TransactionSetSettings, ...]:
    return (
        _set("all"),
        _set("food", categories=("Everyday Food",)),
        _set("bills", groups=("Bills",)),
        _set("discretionary", includes=("all",), excludes=("bills",)),
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
                "Needs Review",
                "Everyday Food",
                "Local Dining",
                "Old Category",
                "Needs Review",
            ],
            "Amount": [-100.0, 20.0, -50.0, -200.0, -40.0, -60.0, -70.0, -30.0, -20.0],
            "Group": [
                "Food",
                "Food",
                "Food",
                "Bills",
                "Uncategorized",
                "Food",
                "Food",
                "Other",
                "Uncategorized",
            ],
            "Type": ["Expense", "Expense", "Expense", "Expense", "Expense", "Expense", "Expense", "Expense", ""],
            "Full Description": [
                "KROGER STORE",
                "KROGER STORE",
                "LOCAL CAFE",
                "POWER COMPANY",
                "MYSTERY CHARGE",
                "KROGER STORE",
                "LOCAL CAFE",
                "OLD SHOP",
                "OLD MYSTERY",
            ],
        }
    )


def test_completed_week_uses_trailing_forty_eight_completed_weeks() -> None:
    period = completed_week(dt.date(2026, 8, 2))

    assert period.start == dt.date(2026, 7, 26)
    assert period.end == dt.date(2026, 8, 1)
    assert period.comparison_start == dt.date(2025, 8, 24)
    assert period.comparison_end == dt.date(2026, 7, 25)
    assert (period.comparison_end - period.comparison_start).days + 1 == AVERAGE_WEEKS * 7
    assert period.rolling_start == dt.date(2026, 7, 5)
    assert period.previous_rolling_start == dt.date(2026, 6, 7)
    assert period.previous_rolling_end == dt.date(2026, 7, 4)


def test_completed_week_accepts_configured_windows() -> None:
    period = completed_week(dt.date(2026, 8, 2), average_weeks=12, rolling_weeks=6)

    assert period.average_weeks == 12
    assert period.rolling_weeks == 6
    assert (period.comparison_end - period.comparison_start).days + 1 == 12 * 7
    assert (period.end - period.rolling_start).days + 1 == 6 * 7


def test_completed_week_excludes_current_saturday() -> None:
    period = completed_week(dt.date(2026, 8, 1))

    assert period.end == dt.date(2026, 7, 25)


@pytest.mark.parametrize("period_end", [dt.date(2026, 7, 31), dt.date(2026, 8, 8)])
def test_period_end_must_be_a_completed_saturday(period_end: dt.date) -> None:
    with pytest.raises(WeeklyExpenseError):
        completed_week(dt.date(2026, 8, 2), period_end)


def test_report_uses_named_transaction_sets_without_double_counting(
    transaction_sets: tuple[TransactionSetSettings, ...],
    report_transactions: pd.DataFrame,
) -> None:
    report = calculate_weekly_report(
        report_transactions,
        transaction_sets,
        ("food", "discretionary"),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert [item.name for item in report.categories] == ["Everyday Food", "Local Dining"]
    assert [item.amount for item in report.categories] == [80.0, 50.0]
    assert [item.average_amount for item in report.categories] == [1.25, 1.46]
    assert [item.change for item in report.categories] == [78.75, 48.54]
    assert [item.rolling_amount for item in report.categories] == [140.0, 120.0]
    assert [item.previous_rolling_amount for item in report.categories] == [0.0, 0.0]
    assert [vendor.name for vendor in report.categories[0].top_vendors] == ["KROGER STORE"]
    assert report.categories[0].top_vendors[0].amount == 80.0
    assert report.selected_total == 130.0
    assert report.average_selected_total == 3.33
    assert report.rolling_selected_total == 290.0
    assert report.previous_rolling_selected_total == 0.0
    assert report.all_expenses_total == 370.0
    assert report.uncategorized_count == 2
    assert report.uncategorized_total == 60.0


def test_uncategorized_total_counts_each_outstanding_transaction_amount(
    transaction_sets: tuple[TransactionSetSettings, ...],
) -> None:
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-26", "2026-07-27", "2026-07-28"], utc=True),
            "Category": ["Missing charge", "Missing refund", "Missing income"],
            "Amount": [-120.0, 25.0, 100.0],
            "Group": ["Uncategorized"] * 3,
            "Type": ["", "", "Income"],
            "Full Description": ["CHARGE", "REFUND", "PAYMENT"],
        }
    )

    report = calculate_weekly_report(
        transactions,
        transaction_sets,
        ("all",),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert report.uncategorized_count == 3
    assert report.uncategorized_total == 245.0


def test_report_only_lists_categories_with_current_week_activity(
    transaction_sets: tuple[TransactionSetSettings, ...],
    report_transactions: pd.DataFrame,
) -> None:
    report = calculate_weekly_report(
        report_transactions,
        transaction_sets,
        ("discretionary",),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert "Old Category" not in [item.name for item in report.categories]
    assert report.average_selected_total == 3.33


def test_zero_expense_week_returns_zero_totals(transaction_sets: tuple[TransactionSetSettings, ...]) -> None:
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
        transaction_sets,
        ("discretionary",),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert report.categories == ()
    assert report.selected_total == 0.0
    assert report.rolling_selected_total == 0.0
    assert report.previous_rolling_selected_total == 0.0
    assert report.all_expenses_total == 0.0
    assert report.uncategorized_count == 0
    assert report.uncategorized_total == 0.0


def test_rolling_summary_compares_adjacent_four_week_periods(
    transaction_sets: tuple[TransactionSetSettings, ...],
) -> None:
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-08-01", "2026-07-05", "2026-07-04", "2026-06-07"], utc=True),
            "Category": ["Everyday Food"] * 4,
            "Amount": [-100.0, -20.0, -40.0, -10.0],
            "Group": ["Food"] * 4,
            "Type": ["Expense"] * 4,
            "Full Description": ["MARKET"] * 4,
        }
    )

    report = calculate_weekly_report(
        transactions,
        transaction_sets,
        ("discretionary",),
        completed_week(dt.date(2026, 8, 2)),
    )

    assert report.categories[0].rolling_amount == 120.0
    assert report.categories[0].previous_rolling_amount == 50.0
    assert report.categories[0].rolling_change == 70.0
    assert report.rolling_selected_total == 120.0
    assert report.previous_rolling_selected_total == 50.0


def test_report_condenses_top_vendors_with_merchant_aliases(
    transaction_sets: tuple[TransactionSetSettings, ...],
) -> None:
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-26", "2026-07-27"], utc=True),
            "Category": ["Everyday Food", "Everyday Food"],
            "Amount": [-40.0, -60.0],
            "Group": ["Food", "Food"],
            "Type": ["Expense", "Expense"],
            "Full Description": ["AMAZON MKTPL*1234", "AMAZON COM"],
        }
    )

    report = calculate_weekly_report(
        transactions,
        transaction_sets,
        ("discretionary",),
        completed_week(dt.date(2026, 8, 2)),
        merchant_aliases={"AMAZON MKTPL": "AMAZON", "AMAZON COM": "AMAZON"},
    )

    assert [(vendor.name, vendor.amount) for vendor in report.categories[0].top_vendors] == [("AMAZON", 100.0)]


def test_report_limits_vendors_to_the_configured_count(transaction_sets: tuple[TransactionSetSettings, ...]) -> None:
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-26"] * 5, utc=True),
            "Category": ["Everyday Food"] * 5,
            "Amount": [-60.0, -40.0, -50.0, -30.0, -20.0],
            "Group": ["Food"] * 5,
            "Type": ["Expense"] * 5,
            "Full Description": ["ALPHA MARKET", "ALPHA MARKET", "BRAVO MARKET", "CHARLIE MARKET", "DELTA MARKET"],
        }
    )

    report = calculate_weekly_report(
        transactions,
        transaction_sets,
        ("discretionary",),
        completed_week(dt.date(2026, 8, 2)),
    )
    limited_report = calculate_weekly_report(
        transactions,
        transaction_sets,
        ("discretionary",),
        completed_week(dt.date(2026, 8, 2)),
        top_merchant_count=1,
    )

    assert [(vendor.name, vendor.amount) for vendor in report.categories[0].top_vendors] == [
        ("ALPHA MARKET", 100.0),
        ("BRAVO MARKET", 50.0),
        ("CHARLIE MARKET", 30.0),
    ]
    assert [(vendor.name, vendor.amount) for vendor in limited_report.categories[0].top_vendors] == [
        ("ALPHA MARKET", 100.0)
    ]


def test_selected_average_uses_combined_unrounded_spending() -> None:
    transaction_sets = (_set("all"),)
    transactions = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-19", "2026-07-19", "2026-07-26", "2026-07-26"], utc=True),
            "Category": ["A", "B", "A", "B"],
            "Amount": [-0.04, -0.04, -1.0, -1.0],
            "Group": ["Group"] * 4,
            "Type": ["Expense"] * 4,
            "Full Description": ["ALPHA", "BRAVO", "ALPHA", "BRAVO"],
        }
    )

    report = calculate_weekly_report(
        transactions,
        transaction_sets,
        ("all",),
        completed_week(dt.date(2026, 8, 2), average_weeks=8),
    )

    assert [item.average_amount for item in report.categories] == [0.01, 0.01]
    assert report.average_selected_total == 0.01


def test_unknown_watched_transaction_set_fails_clearly(
    transaction_sets: tuple[TransactionSetSettings, ...],
    report_transactions: pd.DataFrame,
) -> None:
    with pytest.raises(WeeklyExpenseError, match="Unknown transaction set: missing"):
        calculate_weekly_report(
            report_transactions,
            transaction_sets,
            ("missing",),
            completed_week(dt.date(2026, 8, 2)),
        )
