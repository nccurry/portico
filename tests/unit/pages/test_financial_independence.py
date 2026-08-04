"""Tests for financial-independence math and spending helpers.

Math assertions reference closed-form expected values (inlined in comments next
to each assertion), so each test doubles as executable specification.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
import pytest

from src.filters import apply_transaction_filters
from src.analysis.financial_independence import (
    calculate_avg_monthly_spending,
    calculate_fi_metrics,
    project_portfolio,
    resolve_annual_spending,
    resolve_portfolio_value,
)


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
        assert result["supplemental_income"] == 0.0
        assert result["supplemental_spending"] == 0.0


class TestCalculateFiMetricsWithSupplementalIncome:
    """Verify supplemental income offsets withdrawals and feeds coverage."""

    def test_income_extends_runway(self) -> None:
        # Same depleting case as test_depleting_closed_form but with $10k income.
        # net_withdrawal = 50_000 - 10_000 = 40_000
        # P*r = 25_000 < 40_000 still depleting.
        # runway = log(40_000 / (40_000 - 500_000*0.05)) / log(1.05)
        #        = log(40_000 / 15_000) / log(1.05) ≈ 20.0928
        result = calculate_fi_metrics(500_000, 50_000, 5.0, annual_income=10_000)
        baseline = calculate_fi_metrics(500_000, 50_000, 5.0)
        expected = math.log(40_000 / 15_000) / math.log(1.05)
        assert result["runway_years"] is not None
        assert result["runway_years"] == pytest.approx(expected, rel=1e-9)
        assert baseline["runway_years"] is not None
        assert result["runway_years"] > baseline["runway_years"]

    def test_income_pushes_coverage_up(self) -> None:
        # Coverage = (return + income) / spending = (25_000 + 25_000) / 50_000 = 1.0
        result = calculate_fi_metrics(500_000, 50_000, 5.0, annual_income=25_000)
        assert result["coverage_ratio"] == pytest.approx(1.0)
        assert result["supplemental_income"] == 25_000

    def test_income_alone_covers_spending_runway_infinite(self) -> None:
        # I >= S so net_withdrawal <= 0 → runway is infinite even with zero return.
        result = calculate_fi_metrics(100_000, 50_000, 0.0, annual_income=50_000)
        assert result["runway_years"] is None
        assert result["coverage_ratio"] == pytest.approx(1.0)

    def test_income_exceeds_spending_runway_infinite(self) -> None:
        # net_withdrawal negative → portfolio actually grows even with r=0.
        result = calculate_fi_metrics(100_000, 50_000, 0.0, annual_income=60_000)
        assert result["runway_years"] is None
        assert result["coverage_ratio"] == pytest.approx(1.2)

    def test_income_with_zero_rate_runway_uses_net_withdrawal(self) -> None:
        # r=0 → runway = P / net_withdrawal = 100_000 / (20_000 - 5_000) = 6.6667
        result = calculate_fi_metrics(100_000, 20_000, 0.0, annual_income=5_000)
        assert result["runway_years"] == pytest.approx(100_000 / 15_000)

    def test_default_income_zero_matches_three_arg_call(self) -> None:
        a = calculate_fi_metrics(500_000, 50_000, 5.0)
        b = calculate_fi_metrics(500_000, 50_000, 5.0, annual_income=0.0)
        assert a == b


class TestCalculateFiMetricsWithAdditionalSpending:
    """Verify additional_annual_spending adds to baseline spending."""

    def test_additional_spending_shrinks_runway(self) -> None:
        # Baseline depleting case (P=500k, r=5%, S=50k, runway ≈ 14.21).
        # Add S'=10k → total = 60k, net_withdrawal = 60k.
        # runway = log(60k / (60k - 25k)) / log(1.05) ≈ 11.0359
        result = calculate_fi_metrics(500_000, 50_000, 5.0, additional_annual_spending=10_000)
        baseline = calculate_fi_metrics(500_000, 50_000, 5.0)
        expected = math.log(60_000 / 35_000) / math.log(1.05)
        assert result["runway_years"] is not None
        assert baseline["runway_years"] is not None
        assert result["runway_years"] == pytest.approx(expected, rel=1e-9)
        assert result["runway_years"] < baseline["runway_years"]

    def test_additional_spending_lowers_coverage(self) -> None:
        # P=1M, r=7% → return=70k. Baseline S=50k → coverage=1.4.
        # Add S'=20k → total spending=70k → coverage = 70k/70k = 1.0.
        result = calculate_fi_metrics(
            1_000_000, 50_000, 7.0, additional_annual_spending=20_000
        )
        assert result["coverage_ratio"] == pytest.approx(1.0)
        assert result["supplemental_spending"] == 20_000

    def test_additional_spending_can_break_infinite_runway(self) -> None:
        # Same P/r/S as test_infinite_runway (returns cover spending), but
        # additional spending tips it into depletion.
        infinite = calculate_fi_metrics(1_000_000, 50_000, 7.0)
        finite = calculate_fi_metrics(
            1_000_000, 50_000, 7.0, additional_annual_spending=30_000
        )
        assert infinite["runway_years"] is None
        assert finite["runway_years"] is not None
        assert finite["runway_years"] > 0

    def test_additional_spending_offset_by_equal_income(self) -> None:
        # net_withdrawal = (S + S') - I = 50k + 20k - 20k = 50k → identical
        # to the baseline depleting case.
        with_offsets = calculate_fi_metrics(
            500_000, 50_000, 5.0, annual_income=20_000, additional_annual_spending=20_000
        )
        baseline = calculate_fi_metrics(500_000, 50_000, 5.0)
        assert with_offsets["runway_years"] == pytest.approx(baseline["runway_years"])

    def test_default_additional_spending_matches_no_additional(self) -> None:
        a = calculate_fi_metrics(500_000, 50_000, 5.0)
        b = calculate_fi_metrics(500_000, 50_000, 5.0, additional_annual_spending=0.0)
        assert a == b

    def test_baseline_zero_with_additional_only(self) -> None:
        # Data-derived baseline is zero; only additional spending matters.
        # P=200k, r=5%, S=0, S'=15k → net_withdrawal=15k, return=10k
        # runway = log(15k / (15k - 10k)) / log(1.05)
        result = calculate_fi_metrics(
            200_000, 0, 5.0, additional_annual_spending=15_000
        )
        expected = math.log(15_000 / 5_000) / math.log(1.05)
        assert result["runway_years"] == pytest.approx(expected, rel=1e-9)
        assert result["coverage_ratio"] == pytest.approx(10_000 / 15_000)


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

    def test_income_offsets_withdrawal_each_year(self) -> None:
        # r=0, S=20_000, I=5_000 → each year subtracts net 15_000
        df = project_portfolio(100_000, 20_000, 0.0, years=4, annual_income=5_000)
        assert list(df["Balance"]) == pytest.approx([100_000, 85_000, 70_000, 55_000, 40_000])

    def test_income_exceeding_spending_grows_portfolio(self) -> None:
        # I > S → portfolio grows even at 0% return
        df = project_portfolio(100_000, 20_000, 0.0, years=3, annual_income=30_000)
        assert list(df["Balance"]) == pytest.approx([100_000, 110_000, 120_000, 130_000])

    def test_default_income_matches_no_income(self) -> None:
        a = project_portfolio(400_000, 40_000, 6.0, years=10)
        b = project_portfolio(400_000, 40_000, 6.0, years=10, annual_income=0.0)
        assert list(a["Balance"]) == pytest.approx(list(b["Balance"]))

    def test_additional_spending_increases_withdrawal(self) -> None:
        # r=0, S=20k, S'=5k → net 25k subtracted each year
        df = project_portfolio(
            100_000, 20_000, 0.0, years=4, additional_annual_spending=5_000
        )
        assert list(df["Balance"]) == pytest.approx(
            [100_000, 75_000, 50_000, 25_000, 0]
        )

    def test_income_and_additional_spending_offset(self) -> None:
        # net_withdrawal = (S + S') - I = 20k + 5k - 5k = 20k → matches
        # the baseline test_zero_rate_linear_decay (100k → 80k → ...).
        a = project_portfolio(100_000, 20_000, 0.0, years=4)
        b = project_portfolio(
            100_000, 20_000, 0.0, years=4,
            annual_income=5_000, additional_annual_spending=5_000,
        )
        assert list(a["Balance"]) == pytest.approx(list(b["Balance"]))

    def test_default_additional_spending_matches_no_additional(self) -> None:
        a = project_portfolio(400_000, 40_000, 6.0, years=10)
        b = project_portfolio(
            400_000, 40_000, 6.0, years=10, additional_annual_spending=0.0
        )
        assert list(a["Balance"]) == pytest.approx(list(b["Balance"]))


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


class TestResolveAnnualSpending:
    """Spending override replaces the calculated baseline when set."""

    def test_no_override_uses_monthly_times_twelve(self) -> None:
        assert resolve_annual_spending(1000.0, None) == 12_000.0

    def test_override_replaces_monthly_calculation(self) -> None:
        # Monthly avg of $1000 would give $12k, but override of $50k wins.
        assert resolve_annual_spending(1000.0, 50_000.0) == 50_000.0

    def test_override_zero_is_respected(self) -> None:
        # Explicit 0 override means "no spending baseline" — not "no override".
        assert resolve_annual_spending(1000.0, 0.0) == 0.0

    def test_override_with_zero_monthly_avg(self) -> None:
        assert resolve_annual_spending(0.0, 100_000.0) == 100_000.0

    def test_no_override_with_zero_monthly_avg(self) -> None:
        assert resolve_annual_spending(0.0, None) == 0.0

    def test_override_returns_float_even_for_int_input(self) -> None:
        result = resolve_annual_spending(1000.0, 50_000)  # int override
        assert isinstance(result, float)
        assert result == 50_000.0


class TestResolvePortfolioValue:
    """Portfolio override replaces the calculated total when set."""

    def test_no_override_uses_calculated_value(self) -> None:
        assert resolve_portfolio_value(750_000.0, None) == 750_000.0

    def test_override_replaces_calculated(self) -> None:
        assert resolve_portfolio_value(750_000.0, 1_000_000.0) == 1_000_000.0

    def test_override_zero_is_respected(self) -> None:
        # Explicit 0 means "model an empty portfolio" — not "no override".
        assert resolve_portfolio_value(750_000.0, 0.0) == 0.0

    def test_override_with_zero_calculated(self) -> None:
        # User has no selected accounts but plugs in a hypothetical balance.
        assert resolve_portfolio_value(0.0, 500_000.0) == 500_000.0

    def test_no_override_with_zero_calculated(self) -> None:
        assert resolve_portfolio_value(0.0, None) == 0.0

    def test_override_returns_float_even_for_int_input(self) -> None:
        result = resolve_portfolio_value(750_000.0, 1_000_000)  # int override
        assert isinstance(result, float)
        assert result == 1_000_000.0
