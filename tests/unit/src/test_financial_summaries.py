"""Independent examples for page-level financial summaries and chart data."""

import pandas as pd
import pytest

from src.analysis.budget import calculate_category_projections, summarize_budget
from src.analysis.duplicates import (
    summarize_duplicates,
    summarize_duplicates_by_month,
)
from src.analysis.financial_independence import calculate_fi_metrics, get_savings_accounts
from src.analysis.income import summarize_filtered_transactions
from src.analysis.merchants import (
    _mode_or_first,
    normalize_merchant_name,
    prepare_merchant_timeline,
    summarize_merchants,
)


def test_filtered_transaction_summary_reports_gross_excluded_amount() -> None:
    transactions = pd.DataFrame(
        {
            "Type": ["Income", "Expense", "Expense"],
            "Amount": [1_000.0, -400.0, -200.0],
        }
    )

    summary = summarize_filtered_transactions(transactions)

    assert summary == {
        "count": 3,
        "total_amount": 1_600.0,
        "income_amount": 1_000.0,
        "expense_amount": 600.0,
    }
    assert summary["total_amount"] == (
        summary["income_amount"] + summary["expense_amount"]
    )


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


def test_merchant_summary_and_timeline_match_manual_totals() -> None:
    merchant_stats = pd.DataFrame(
        {
            "Merchant": ["A", "B"],
            "Total_Spent": [300.0, 100.0],
        }
    )
    transactions = pd.DataFrame(
        {
            "Merchant": ["A", "A", "B", "A"],
            "Month": ["2024-01", "2024-01", "2024-01", "2024-02"],
            "Type": ["Expense", "Expense", "Expense", "Income"],
            "Amount": [-100.0, -200.0, -100.0, 50.0],
        }
    )

    summary = summarize_merchants(merchant_stats)
    timeline = prepare_merchant_timeline(transactions, merchant_stats, top_n=1)

    assert summary == {
        "count": 2,
        "total_spent": 400.0,
        "top_merchant": "A",
        "top_merchant_spent": 300.0,
        "average_spent": 200.0,
    }
    assert timeline.to_dict("records") == [
        {"Merchant": "A", "Month": "2024-01", "Amount_Abs": 300.0}
    ]


def test_empty_merchant_summary_and_timeline_are_zero() -> None:
    assert summarize_merchants(pd.DataFrame()) == {
        "count": 0,
        "total_spent": 0.0,
        "top_merchant": "",
        "top_merchant_spent": 0.0,
        "average_spent": 0.0,
    }
    transactions = pd.DataFrame(columns=["Merchant", "Month", "Type", "Amount"])
    merchant_stats = pd.DataFrame(columns=["Merchant", "Total_Spent"])
    assert prepare_merchant_timeline(transactions, merchant_stats).empty


def test_merchant_normalization_and_mode_fallbacks() -> None:
    assert normalize_merchant_name(None) == "Unknown"
    assert normalize_merchant_name("POS PURCHASE") == "Unknown"
    aliases = {"OTHER": "OTHER", "ACME": "ACME"}
    assert normalize_merchant_name("Acme Grocery", aliases=aliases) == "ACME"
    assert normalize_merchant_name("Alpha Beta Gamma", method="first_word") == "ALPHA"
    assert normalize_merchant_name("Alpha Beta Gamma", method="first_two") == "ALPHA BETA"
    assert _mode_or_first(pd.Series([pd.NA], dtype="object")) is pd.NA
    assert _mode_or_first(pd.Series(dtype="object")) == "Unknown"


def test_budget_summary_and_projections_follow_period_identities() -> None:
    comparison = pd.DataFrame(
        {
            "Category": ["Food", "Travel", "Unbudgeted"],
            "Budget": [600.0, 300.0, 0.0],
            "Spent": [300.0, 450.0, 25.0],
        }
    )

    summary = summarize_budget(comparison)
    projections = calculate_category_projections(comparison, 15, 30)

    assert summary == {
        "budget": 900.0,
        "spent": 775.0,
        "remaining": 125.0,
        "pct_used": pytest.approx(86.111111),
    }
    assert projections.set_index("Category")["Projected"].to_dict() == {
        "Food": 600.0,
        "Travel": 900.0,
    }
    assert projections.set_index("Category")["Over_Budget"].to_dict() == {
        "Food": False,
        "Travel": True,
    }


def test_fi_summary_exposes_displayed_totals_and_cashflow_gap() -> None:
    summary = calculate_fi_metrics(
        portfolio_value=500_000.0,
        annual_spending=50_000.0,
        rate_pct=5.0,
        annual_income=10_000.0,
        additional_annual_spending=5_000.0,
    )

    assert summary["annual_return"] == pytest.approx(25_000.0)
    assert summary["total_spending"] == pytest.approx(55_000.0)
    assert summary["total_inflow"] == pytest.approx(35_000.0)
    assert summary["cashflow_gap"] == pytest.approx(-20_000.0)
    assert summary["coverage_ratio"] == pytest.approx(35_000 / 55_000)


def test_savings_account_selection_handles_missing_and_hidden_groups() -> None:
    assert get_savings_accounts(pd.DataFrame({"Account": ["A"]})) == []
    assert get_savings_accounts(
        pd.DataFrame({"Account": ["Savings"], "Group": ["Savings"]})
    ) == ["Savings"]
    balances = pd.DataFrame(
        {
            "Account": ["Visible Singular", "Visible Plural", "Hidden", "Checking"],
            "Group": ["saving", "Savings", "Savings", "Cash"],
            "Hide": ["", "", "Hide", ""],
        }
    )
    assert get_savings_accounts(balances) == ["Visible Plural", "Visible Singular"]
