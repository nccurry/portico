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
        withdrawal_rate=4.0,
        target_amount=150_000,
        spending_lookback_months=3,
        projection_years=50,
        included_account_patterns=(),
        included_groups=("Savings",),
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
