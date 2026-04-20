"""Tests for Pages/9_Financial_Independence.py — FI math and spending helpers.

Math assertions reference closed-form expected values (inlined in comments next
to each assertion), so each test doubles as executable specification.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
import pytest

from src.filters import apply_transaction_filters
from tests._pages import financial_independence as _mod

calculate_avg_monthly_spending = _mod.calculate_avg_monthly_spending
calculate_fi_metrics = _mod.calculate_fi_metrics
project_portfolio = _mod.project_portfolio


class TestCalculateFiMetrics:
    """Closed-form math verification for calculate_fi_metrics."""

    def test_infinite_runway(self) -> None:
        # P=1_000_000, r=7%, S=50_000.
        # annual_return = 70_000, coverage = 1.4, runway = None (returns exceed spending)
        result = calculate_fi_metrics(1_000_000, 50_000, 7.0)
        assert result["annual_return"] == pytest.approx(70_000)
        assert result["coverage_ratio"] == pytest.approx(1.4)
        assert result["runway_years"] is None

    def test_exact_breakeven(self) -> None:
        # P=1_000_000, r=5%, S=50_000 → P*r == S exactly
        result = calculate_fi_metrics(1_000_000, 50_000, 5.0)
        assert result["coverage_ratio"] == pytest.approx(1.0)
        assert result["runway_years"] is None

    def test_depleting_closed_form(self) -> None:
        # P=500_000, r=5%, S=50_000.
        # annual_return = 25_000; coverage = 0.5
        # runway = log(50000 / (50000 - 500000*0.05)) / log(1.05)
        #        = log(50000 / 25000) / log(1.05) ≈ 14.2067
        result = calculate_fi_metrics(500_000, 50_000, 5.0)
        assert result["annual_return"] == pytest.approx(25_000)
        assert result["coverage_ratio"] == pytest.approx(0.5)
        expected = math.log(50_000 / 25_000) / math.log(1.05)
        assert result["runway_years"] is not None
        assert result["runway_years"] == pytest.approx(expected, rel=1e-9)
        assert result["runway_years"] == pytest.approx(14.2067, rel=1e-3)

    def test_zero_spending_returns_infinite_coverage(self) -> None:
        result = calculate_fi_metrics(100_000, 0, 7.0)
        assert math.isinf(result["coverage_ratio"])
        assert result["runway_years"] is None

    def test_zero_spending_zero_portfolio(self) -> None:
        # No spending, no portfolio → coverage 0, runway None
        result = calculate_fi_metrics(0, 0, 7.0)
        assert result["coverage_ratio"] == 0.0
        assert result["runway_years"] is None

    def test_zero_portfolio_with_spending(self) -> None:
        # Zero portfolio cannot generate return; coverage 0, runway 0
        result = calculate_fi_metrics(0, 50_000, 7.0)
        assert result["annual_return"] == 0.0
        assert result["coverage_ratio"] == 0.0
        assert result["runway_years"] == 0.0

    def test_zero_rate_runway_equals_portfolio_over_spending(self) -> None:
        # r=0 → no growth, pure division
        result = calculate_fi_metrics(100_000, 20_000, 0.0)
        assert result["annual_return"] == 0.0
        assert result["runway_years"] == pytest.approx(5.0)

    def test_summary_fields_roundtrip_inputs(self) -> None:
        result = calculate_fi_metrics(250_000, 30_000, 6.0)
        assert result["portfolio_value"] == 250_000
        assert result["annual_spending"] == 30_000


class TestProjectPortfolio:
    """Row-by-row recurrence verification for project_portfolio."""

    def test_matches_recurrence_non_depleting(self) -> None:
        # P=400_000, r=6%, S=40_000, 10 years.
        # r*P = 24_000 < 40_000 so eventually depletes but not in early years.
        P, r_pct, S, years = 400_000.0, 6.0, 40_000.0, 10
        df = project_portfolio(P, S, r_pct, years)

        r = r_pct / 100.0
        expected: list[float] = [P]
        b = P
        for _ in range(years):
            b = b * (1.0 + r) - S
            expected.append(max(0.0, b))

        assert list(df["Year"]) == list(range(years + 1))
        for idx, (actual, want) in enumerate(zip(df["Balance"], expected, strict=True)):
            assert actual == pytest.approx(want), f"row {idx} mismatch"

    def test_clamps_at_zero_when_depleted(self) -> None:
        # Small portfolio, large spending → depletes quickly.
        df = project_portfolio(10_000, 50_000, 5.0, years=20)
        assert len(df) == 21
        assert (df["Balance"] >= 0).all()
        assert df["Balance"].iloc[-1] == 0.0

    def test_infinite_growth_is_strictly_monotone(self) -> None:
        # r*P > S → portfolio grows every year.
        df = project_portfolio(1_000_000, 50_000, 7.0, years=10)
        diffs = df["Balance"].diff().dropna()
        assert (diffs > 0).all()

    def test_zero_years_returns_single_row(self) -> None:
        df = project_portfolio(100_000, 50_000, 5.0, years=0)
        assert len(df) == 1
        assert df["Balance"].iloc[0] == 100_000

    def test_first_row_is_initial_value(self) -> None:
        df = project_portfolio(123_456, 10_000, 4.0, years=5)
        assert df["Year"].iloc[0] == 0
        assert df["Balance"].iloc[0] == pytest.approx(123_456)

    def test_zero_rate_linear_decay(self) -> None:
        # r=0 → each year subtracts S exactly
        df = project_portfolio(100_000, 20_000, 0.0, years=4)
        assert list(df["Balance"]) == pytest.approx([100_000, 80_000, 60_000, 40_000, 20_000])


class TestCalculateAvgMonthlySpending:
    """Verify spending math and filter reuse via apply_transaction_filters."""

    def test_averages_expense_totals_over_window(self, fi_transactions_df: pd.DataFrame) -> None:
        # fi_transactions_df: every month has 1 x -1000 (Food) and 1 x -400 (Travel) expense
        # Including both groups: 1400/month for 12 months → avg 1400
        avg, totals = calculate_avg_monthly_spending(fi_transactions_df, "2024-01", "2024-12")
        assert avg == pytest.approx(1400.0)
        assert len(totals) == 12
        assert set(totals.columns) == {"Month", "Spending"}
        assert (totals["Spending"] == 1400.0).all()

    def test_respects_pre_applied_filters(
        self,
        fi_transactions_df: pd.DataFrame,
        fi_passthrough_filters: dict[str, Any],
    ) -> None:
        # Excluding the Travel group via apply_transaction_filters drops the
        # $400/mo rows; remaining is $1000/mo from Food.
        filters = {**fi_passthrough_filters, "exclude_groups": ["Travel"]}
        filtered = apply_transaction_filters(fi_transactions_df, filters)
        avg, totals = calculate_avg_monthly_spending(filtered, "2024-01", "2024-12")
        assert avg == pytest.approx(1000.0)
        assert len(totals) == 12

    def test_includes_only_window_months(self, fi_transactions_df: pd.DataFrame) -> None:
        # 3-month window (Jan-Mar) over 1400/mo constant → avg 1400 over 3 months
        avg, totals = calculate_avg_monthly_spending(fi_transactions_df, "2024-01", "2024-03")
        assert avg == pytest.approx(1400.0)
        assert len(totals) == 3
        assert list(totals["Month"]) == ["2024-01", "2024-02", "2024-03"]

    def test_ignores_income_rows(self, fi_transactions_df: pd.DataFrame) -> None:
        # Income rows ($3000/mo) must not affect the average even though they
        # are in the same DataFrame.
        avg, _ = calculate_avg_monthly_spending(fi_transactions_df, "2024-01", "2024-12")
        assert avg == pytest.approx(1400.0)  # not 1400 - 3000 and not 3000 - 1400

    def test_empty_df_returns_zero(self) -> None:
        df = pd.DataFrame(columns=["Date", "Amount", "Type", "Month"])
        avg, totals = calculate_avg_monthly_spending(df, "2024-01", "2024-12")
        assert avg == 0.0
        assert totals.empty

    def test_window_outside_data_returns_zero(self, fi_transactions_df: pd.DataFrame) -> None:
        avg, totals = calculate_avg_monthly_spending(fi_transactions_df, "2030-01", "2030-12")
        assert avg == 0.0
        assert totals.empty

    def test_monthly_totals_aggregate_multiple_rows(self) -> None:
        # Two expenses in the same month aggregate to a single row.
        df = pd.DataFrame({
            "Date": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-10"], utc=True),
            "Amount": [-100, -250, -500],
            "Type": ["Expense"] * 3,
            "Month": ["2024-01", "2024-01", "2024-02"],
        })
        avg, totals = calculate_avg_monthly_spending(df, "2024-01", "2024-02")
        # Jan = 350, Feb = 500, avg = 425
        assert avg == pytest.approx(425.0)
        assert list(totals["Month"]) == ["2024-01", "2024-02"]
        assert list(totals["Spending"]) == pytest.approx([350.0, 500.0])
