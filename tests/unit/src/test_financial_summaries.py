"""Independent examples for page-level financial summaries and chart data."""

import pandas as pd
import pytest

from src.analysis.budget import summarize_budget
from src.analysis.duplicates import (
    summarize_duplicates,
    summarize_duplicates_by_month,
)
from src.analysis.financial_independence import calculate_fi_metrics, get_accounts_in_groups
from src.analysis.merchants import _mode_or_first, normalize_merchant_name


def test_duplicate_summaries_use_pair_amounts_and_unique_months() -> None:
    duplicates = pd.DataFrame(
        {
            "Month": ["2024-01", "2024-01", "2024-02"],
            "Amount": [-50.0, -75.0, -20.0],
        }
    )

    summary = summarize_duplicates(duplicates)
    monthly = summarize_duplicates_by_month(duplicates)

    assert summary == {
        "pair_count": 3,
        "total_amount": 145.0,
        "affected_months": 2,
    }
    assert monthly.iloc[0].to_dict() == {
        "Month": "2024-02",
        "Count": 1,
        "Total_Amount": 20.0,
    }
    assert monthly["Total_Amount"].sum() == pytest.approx(145.0)


def test_empty_duplicate_summaries_have_stable_shapes() -> None:
    duplicates = pd.DataFrame(columns=["Month", "Amount"])

    assert summarize_duplicates(duplicates) == {
        "pair_count": 0,
        "total_amount": 0.0,
        "affected_months": 0,
    }
    assert list(summarize_duplicates_by_month(duplicates).columns) == [
        "Month",
        "Count",
        "Total_Amount",
    ]


def test_merchant_normalization_and_mode_fallbacks() -> None:
    assert normalize_merchant_name(None) == "Unknown"
    assert normalize_merchant_name("POS PURCHASE") == "Unknown"
    aliases = {"OTHER": "OTHER", "ACME": "ACME"}
    assert normalize_merchant_name("Acme Grocery", aliases=aliases) == "ACME"
    assert normalize_merchant_name("Alpha Beta Gamma", method="first_word") == "ALPHA"
    assert normalize_merchant_name("Alpha Beta Gamma", method="first_two") == "ALPHA BETA"
    assert _mode_or_first(pd.Series([pd.NA], dtype="object")) is pd.NA
    assert _mode_or_first(pd.Series(dtype="object")) == "Unknown"


def test_budget_summary_follows_period_identities() -> None:
    comparison = pd.DataFrame(
        {
            "Category": ["Food", "Travel", "Unbudgeted"],
            "Budget": [600.0, 300.0, 0.0],
            "Spent": [300.0, 450.0, 25.0],
        }
    )

    summary = summarize_budget(comparison)
    assert summary == {
        "budget": 900.0,
        "spent": 775.0,
        "remaining": 125.0,
        "pct_used": pytest.approx(86.111111),
    }


def test_fi_summary_exposes_displayed_totals_and_annual_surplus() -> None:
    summary = calculate_fi_metrics(
        portfolio_value=500_000.0,
        annual_spending=50_000.0,
        rate_pct=5.0,
        annual_income=10_000.0,
    )

    assert summary["annual_return"] == pytest.approx(25_000.0)
    assert summary["annual_income"] == pytest.approx(10_000.0)
    assert summary["total_spending"] == pytest.approx(50_000.0)
    assert summary["annual_surplus"] == pytest.approx(-15_000.0)


def test_savings_account_selection_handles_missing_and_hidden_groups() -> None:
    groups = ("Saving", "Savings")
    assert get_accounts_in_groups(pd.DataFrame({"Account": ["A"]}), groups) == []
    assert get_accounts_in_groups(
        pd.DataFrame({"Account": ["Savings"], "Group": ["Savings"]}),
        groups,
    ) == ["Savings"]
    balances = pd.DataFrame(
        {
            "Account": ["Visible Singular", "Visible Plural", "Hidden", "Checking"],
            "Group": ["saving", "Savings", "Savings", "Cash"],
            "Hide": ["", "", "Hide", ""],
        }
    )
    assert get_accounts_in_groups(balances, groups) == ["Visible Plural", "Visible Singular"]
