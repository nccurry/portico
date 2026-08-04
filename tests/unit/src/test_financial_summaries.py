"""Independent examples for page-level financial summaries and chart data."""

from __future__ import annotations

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
from src.analysis.spending import (
    calculate_distribution_stats,
    prepare_amount_histogram,
    prepare_category_boxplot,
    prepare_spending_trend,
)
from src.analysis.subscriptions import (
    _monthly_cost,
    _next_expected_date,
    prepare_subscription_timeline,
    summarize_subscriptions,
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


def test_distribution_stats_partition_counts_and_dollars() -> None:
    period = pd.DataFrame({"Amount": [-10.0, -25.0, -100.0, -250.0, -1_000.0]})

    stats = calculate_distribution_stats(period)

    assert (stats["small_count"], stats["medium_count"], stats["large_count"]) == (
        1,
        2,
        2,
    )
    assert stats["small_count_pct"] == pytest.approx(20.0)
    assert stats["medium_count_pct"] == pytest.approx(40.0)
    assert stats["large_count_pct"] == pytest.approx(40.0)
    assert stats["small_pct"] + stats["medium_pct"] + stats["large_pct"] == (
        pytest.approx(100.0)
    )
    assert stats["pareto_pct"] == pytest.approx(40.0)


def test_distribution_stats_empty_values_are_zero() -> None:
    stats = calculate_distribution_stats(pd.DataFrame({"Amount": []}))

    assert all(value == 0 for value in stats.values())


def test_pareto_exact_boundary_uses_smallest_reaching_prefix() -> None:
    stats = calculate_distribution_stats(pd.DataFrame({"Amount": [-80.0, -20.0]}))

    assert stats["pareto_pct"] == pytest.approx(50.0)


def test_spending_chart_data_preserves_manual_aggregates() -> None:
    period = pd.DataFrame(
        {
            "Month": ["2024-01", "2024-01", "2024-02", "2024-02"],
            "Category": ["Food", "Food", "Food", "Travel"],
            "Amount": [-10.0, -15.0, -20.0, -100.0],
        }
    )

    trend = prepare_spending_trend(period, ["Food"])
    histogram = prepare_amount_histogram(period)
    boxplot = prepare_category_boxplot(period, limit=1)

    assert trend.set_index("Month")["Amount"].to_dict() == {
        "2024-01": 25.0,
        "2024-02": 20.0,
    }
    assert int(histogram["Count"].sum()) == len(period)
    assert set(boxplot["Category"]) == {"Travel"}
    assert boxplot["Amount_Abs"].sum() == pytest.approx(100.0)


def test_histogram_top_bucket_has_no_upper_limit() -> None:
    histogram = prepare_amount_histogram(pd.DataFrame({"Amount": [-250_000.0]}))

    assert histogram.to_dict("records") == [
        {"Amount_Range": "$5K+", "Count": 1}
    ]


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


def test_subscription_summary_uses_normalized_monthly_costs() -> None:
    subscriptions = pd.DataFrame(
        {
            "Monthly_Cost": [10.0, 30.0],
            "Annual_Cost": [999.0, 999.0],
        }
    )

    summary = summarize_subscriptions(subscriptions)

    assert summary == {
        "count": 2,
        "monthly_cost": 40.0,
        "annual_cost": 480.0,
        "average_monthly_cost": 20.0,
    }
    assert summary["annual_cost"] == pytest.approx(summary["monthly_cost"] * 12)


def test_subscription_timeline_uses_matching_charge_dates() -> None:
    transactions = pd.DataFrame(
        {
            "Full Description": [
                "Stream Service Plan",
                "Stream Service Plan",
                "Stream Service Plan",
            ],
            "Type": ["Expense", "Expense", "Income"],
            "Amount": [-12.0, -12.0, 12.0],
            "Date": pd.to_datetime(
                ["2024-01-01", "2024-03-01", "2024-04-01"], utc=True
            ),
        }
    )
    subscriptions = pd.DataFrame(
        {
            "Merchant": ["STREAM SERVICE PLAN"],
            "Amount_Rounded": [12.0],
            "Monthly_Cost": [12.0],
        }
    )

    timeline = prepare_subscription_timeline(transactions, subscriptions)

    assert timeline.loc[0, "First_Date"] == pd.Timestamp("2024-01-01", tz="UTC")
    assert timeline.loc[0, "Last_Date"] == pd.Timestamp("2024-03-01", tz="UTC")
    assert timeline.loc[0, "Amount"] == pytest.approx(12.0)


def test_empty_subscription_summary_and_unmatched_timeline_are_zero() -> None:
    subscriptions = pd.DataFrame(
        columns=["Merchant", "Amount_Rounded", "Monthly_Cost", "Annual_Cost"]
    )
    transactions = pd.DataFrame(
        columns=["Full Description", "Amount", "Date"]
    )

    assert summarize_subscriptions(subscriptions) == {
        "count": 0,
        "monthly_cost": 0.0,
        "annual_cost": 0.0,
        "average_monthly_cost": 0.0,
    }
    assert prepare_subscription_timeline(transactions, subscriptions).empty

    unmatched = pd.DataFrame(
        {
            "Merchant": ["Missing Merchant"],
            "Amount_Rounded": [10.0],
            "Monthly_Cost": [10.0],
            "Annual_Cost": [120.0],
        }
    )
    other_transactions = pd.DataFrame(
        {
            "Full Description": ["Other Merchant"],
            "Amount": [-10.0],
            "Date": [pd.Timestamp("2024-01-01")],
        }
    )
    assert prepare_subscription_timeline(other_transactions, unmatched).empty


def test_subscription_cadence_normalization_and_default_next_date() -> None:
    assert _monthly_cost(pd.Series({"Median_Amount": 120.0, "Cadence": "Quarterly"})) == 40.0
    assert _monthly_cost(pd.Series({"Median_Amount": 120.0, "Cadence": "Annual"})) == 10.0
    next_date = _next_expected_date(
        pd.Series({"Last_Date": pd.Timestamp("2024-01-01"), "Cadence": "Irregular"})
    )
    assert next_date == pd.Timestamp("2024-01-31")


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
            "Account": ["Visible", "Hidden", "Checking"],
            "Group": ["savings", "Savings", "Cash"],
            "Hide": ["", "Hide", ""],
        }
    )
    assert get_savings_accounts(balances) == ["Visible"]
