"""Tests for configurable emergency, debt, and FI progress calculations."""

from datetime import date

import pandas as pd
import pytest

from src.analysis.financial_safety import build_financial_safety_summary, select_accounts
from src.config import FinancialIndependenceSettings, FinancialSafetySettings
from tests._helpers import _balance_df, _transactions_df


def _safety_settings(*, baseline_date: date | None = None) -> FinancialSafetySettings:
    return FinancialSafetySettings(
        emergency_fund_target_months=2,
        emergency_fund_included_groups=("Savings",),
        emergency_fund_included_account_patterns=(),
        emergency_fund_spending_lookback_months=3,
        emergency_fund_exclude_categories=(),
        emergency_fund_exclude_groups=("Travel",),
        debt_included_groups=("Credit Cards",),
        debt_included_account_patterns=(),
        debt_baseline_date=baseline_date,
    )


def _fi_settings() -> FinancialIndependenceSettings:
    return FinancialIndependenceSettings(
        expected_return_rate=7.0,
        target_amount=150_000,
        spending_lookback_months=3,
        projection_years=50,
        default_active_streams=("Investments", "Social Security"),
        income_from_transactions=False,
        included_account_patterns=(),
        included_groups=("Savings",),
        real_estate_included_account_patterns=(),
        real_estate_included_groups=(),
        real_estate_monthly_cash_flow=0.0,
        real_estate_appreciation_rate=3.0,
        social_security_annual_income=0.0,
        social_security_start_year=1,
        pension_annual_income=0.0,
        pension_start_year=1,
    )


def _balances() -> pd.DataFrame:
    return _balance_df(
        [
            {
                "Date": "2024-01-01",
                "Time": "2024-01-01 09:00",
                "Account": "Checking",
                "Account ID": "checking",
                "Group": "Savings",
                "Class": "Asset",
                "Balance": 1_000,
            },
            {
                "Date": "2024-03-01",
                "Time": "2024-03-01 09:00",
                "Account": "Checking",
                "Account ID": "checking",
                "Group": "Savings",
                "Class": "Asset",
                "Balance": 1_200,
            },
            {
                "Date": "2024-01-01",
                "Time": "2024-01-01 09:00",
                "Account": "Card",
                "Account ID": "card",
                "Group": "Credit Cards",
                "Class": "Liability",
                "Balance": 500,
            },
            {
                "Date": "2024-03-01",
                "Time": "2024-03-01 09:00",
                "Account": "Card",
                "Account ID": "card",
                "Group": "Credit Cards",
                "Class": "Liability",
                "Balance": 300,
            },
            {
                "Date": "2024-03-01",
                "Time": "2024-03-01 09:00",
                "Account": "Hidden savings",
                "Account ID": "hidden",
                "Group": "Savings",
                "Class": "Asset",
                "Balance": 9_999,
                "Hide": "Hide",
            },
        ]
    )


def _transactions() -> pd.DataFrame:
    return _transactions_df(
        [
            {
                "Date": "2024-01-10",
                "Month": "2024-01",
                "Type": "Expense",
                "Group": "Food",
                "Category": "Groceries",
                "Amount": -100,
                "Account": "Checking",
            },
            {
                "Date": "2024-02-10",
                "Month": "2024-02",
                "Type": "Expense",
                "Group": "Travel",
                "Category": "Flights",
                "Amount": -900,
                "Account": "Checking",
            },
            {
                "Date": "2024-02-20",
                "Month": "2024-02",
                "Type": "Expense",
                "Group": "Food",
                "Category": "Groceries",
                "Amount": -200,
                "Account": "Checking",
            },
            {
                "Date": "2024-03-10",
                "Month": "2024-03",
                "Type": "Expense",
                "Group": "Food",
                "Category": "Groceries",
                "Amount": -300,
                "Account": "Checking",
            },
        ]
    )


def test_financial_safety_progress_uses_configured_scopes_and_exclusions() -> None:
    summary = build_financial_safety_summary(
        _balances(),
        _transactions(),
        _safety_settings(),
        _fi_settings(),
        as_of=pd.Timestamp("2024-04-01", tz="UTC"),
    )

    assert summary["emergency_fund_balance"] == pytest.approx(1_200)
    assert summary["emergency_fund_average_monthly_spending"] == pytest.approx(200)
    assert summary["emergency_fund_target"] == pytest.approx(400)
    assert summary["emergency_fund_months_covered"] == pytest.approx(6)
    assert summary["debt_baseline_balance"] == pytest.approx(500)
    assert summary["debt_balance"] == pytest.approx(300)
    assert summary["debt_paid_down"] == pytest.approx(200)
    assert summary["debt_progress_pct"] == pytest.approx(40)
    assert summary["debt_baseline_label"] == "Jan 2024"
    assert summary["fi_portfolio_value"] == pytest.approx(1_200)
    assert summary["fi_target"] == pytest.approx(150_000)
    assert summary["fi_progress_pct"] == pytest.approx(0.8)


def test_financial_safety_uses_the_configured_debt_baseline_date() -> None:
    balances = _balances()
    balances.loc[
        (balances["Account"] == "Card") & (balances["Date"] == pd.Timestamp("2024-03-01", tz="UTC")), "Date"
    ] = pd.Timestamp(
        "2024-02-20",
        tz="UTC",
    )
    summary = build_financial_safety_summary(
        balances,
        _transactions(),
        _safety_settings(baseline_date=date(2024, 2, 1)),
        _fi_settings(),
        as_of=pd.Timestamp("2024-04-01", tz="UTC"),
    )

    assert summary["debt_baseline_balance"] == pytest.approx(500)
    assert summary["debt_baseline_label"] == "Feb 2024"


@pytest.mark.parametrize(
    ("start", "end", "opening", "closing", "progress"),
    [
        ("2024-02-01", "2024-02-15", 500, 500, 0.0),
        ("2024-02-01", "2024-03-20", 500, 300, 40.0),
        ("2024-03-01", "2024-04-15", 300, 900, -200.0),
        ("2024-01-01", "2024-04-15", 500, 900, -80.0),
        ("2023-12-01", "2024-01-15", 0, 500, None),
        ("2023-11-01", "2023-12-01", 0, 0, None),
    ],
)
def test_debt_range_uses_latest_balances_at_each_boundary(
    start: str, end: str, opening: float, closing: float, progress: float | None
) -> None:
    extra = _balance_df(
        [
            {
                "Date": day,
                "Time": f"{day} 09:00",
                "Account": account,
                "Account ID": account.lower(),
                "Group": "Credit Cards",
                "Class": "Liability",
                "Balance": balance,
                "Hide": hide,
            }
            for day, account, balance, hide in [
                ("2024-04-01", "Card", 700, ""),
                ("2024-04-10", "New loan", 200, ""),
                ("2024-03-01", "Hidden loan", 10_000, "Hide"),
                ("2024-05-01", "Card", 900, ""),
                ("2024-05-01", "Future loan", 20_000, ""),
            ]
        ]
    )
    summary = build_financial_safety_summary(
        pd.concat([_balances(), extra], ignore_index=True),
        _transactions(),
        _safety_settings(baseline_date=date(2024, 4, 1)),
        _fi_settings(),
        as_of=pd.Timestamp("2024-05-01", tz="UTC"),
        debt_start_date=pd.Timestamp(start, tz="UTC"),
        debt_end_date=pd.Timestamp(end, tz="UTC"),
    )

    assert summary["debt_baseline_balance"] == opening
    assert summary["debt_balance"] == closing
    assert summary["debt_paid_down"] == opening - closing
    assert summary["debt_progress_pct"] == progress
    assert summary["debt_baseline_label"] == (pd.Timestamp(start).strftime("%b %d, %Y") if closing else None)


def test_select_accounts_matches_groups_or_name_fragments_and_hides_accounts() -> None:
    selected = select_accounts(_balances(), (), ("card",))

    assert selected == ["Card"]


def test_financial_safety_excludes_the_partial_current_month_from_emergency_spending() -> None:
    summary = build_financial_safety_summary(
        _balances(),
        _transactions(),
        _safety_settings(),
        _fi_settings(),
        as_of=pd.Timestamp("2024-03-20", tz="UTC"),
    )

    assert summary["emergency_fund_average_monthly_spending"] == pytest.approx(100)
    assert summary["emergency_fund_target"] == pytest.approx(200)
