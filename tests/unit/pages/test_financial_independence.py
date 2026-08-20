"""Tests for financial-independence math and spending helpers.

Math assertions reference closed-form expected values (inlined in comments next
to each assertion), so each test doubles as executable specification.
"""
import math
import pandas as pd
import pytest

from src.custom_types import TransactionFilterOptions
from src.filters import apply_transaction_filters
from src.analysis.financial_independence import (
    build_runway_sensitivity,
    calculate_avg_monthly_spending,
    calculate_fi_metrics,
    project_portfolio,
)


class TestCalculateFiMetrics:
    """Closed-form math verification for calculate_fi_metrics."""

    def test_infinite_runway(self) -> None:
        # P=1_000_000, r=7%, S=50_000.
        # annual_return = 70_000, coverage = 1.4, runway = None (returns exceed spending)
        result = calculate_fi_metrics(1_000_000, 50_000, 7.0)
        assert result["annual_return"] == pytest.approx(70_000)
        assert result["annual_surplus"] == pytest.approx(20_000)
        assert result["runway_years"] is None

    def test_exact_breakeven(self) -> None:
        # P=1_000_000, r=5%, S=50_000 → P*r == S exactly
        result = calculate_fi_metrics(1_000_000, 50_000, 5.0)
        assert result["annual_surplus"] == pytest.approx(0.0)
        assert result["runway_years"] is None

    def test_depleting_closed_form(self) -> None:
        # P=500_000, r=5%, S=50_000.
        # annual_return = 25_000; coverage = 0.5
        # runway = log(50000 / (50000 - 500000*0.05)) / log(1.05)
        #        = log(50000 / 25000) / log(1.05) ≈ 14.2067
        result = calculate_fi_metrics(500_000, 50_000, 5.0)
        assert result["annual_return"] == pytest.approx(25_000)
        assert result["annual_surplus"] == pytest.approx(-25_000)
        expected = math.log(50_000 / 25_000) / math.log(1.05)
        assert result["runway_years"] is not None
        assert result["runway_years"] == pytest.approx(expected, rel=1e-9)
        assert result["runway_years"] == pytest.approx(14.2067, rel=1e-3)

    def test_zero_spending_is_sustainable(self) -> None:
        result = calculate_fi_metrics(100_000, 0, 7.0)
        assert result["annual_surplus"] == pytest.approx(7_000)
        assert result["runway_years"] is None

    def test_zero_spending_zero_portfolio(self) -> None:
        # No spending, no portfolio → coverage 0, runway None
        result = calculate_fi_metrics(0, 0, 7.0)
        assert result["annual_surplus"] == 0.0
        assert result["runway_years"] is None

    def test_zero_portfolio_with_spending(self) -> None:
        # Zero portfolio cannot generate return; coverage 0, runway 0
        result = calculate_fi_metrics(0, 50_000, 7.0)
        assert result["annual_return"] == 0.0
        assert result["annual_surplus"] == -50_000.0
        assert result["runway_years"] == 0.0

    def test_zero_rate_runway_equals_portfolio_over_spending(self) -> None:
        # r=0 → no growth, pure division
        result = calculate_fi_metrics(100_000, 20_000, 0.0)
        assert result["annual_return"] == 0.0
        assert result["runway_years"] == pytest.approx(5.0)

    def test_summary_contains_displayed_metrics(self) -> None:
        result = calculate_fi_metrics(250_000, 30_000, 6.0)
        assert result["annual_income"] == 0.0
        assert result["total_spending"] == 30_000
        assert result["annual_surplus"] == -15_000
        assert result["net_annual_spending"] == 30_000.0
        assert result["sustainable_spending"] == 10_000.0
        assert result["fi_target"] == 750_000.0
        assert result["fi_gap"] == -500_000.0

    def test_income_reduces_the_fi_target(self) -> None:
        result = calculate_fi_metrics(
            500_000,
            60_000,
            5.0,
            annual_income=20_000,
            withdrawal_rate_pct=4.0,
        )

        assert result["net_annual_spending"] == 40_000.0
        assert result["fi_target"] == 1_000_000.0
        assert result["fi_gap"] == -500_000.0

    def test_withdrawal_rate_changes_the_fi_target(self) -> None:
        result = calculate_fi_metrics(
            500_000,
            40_000,
            5.0,
            withdrawal_rate_pct=5.0,
        )

        assert result["sustainable_spending"] == 25_000.0
        assert result["fi_target"] == 800_000.0

    def test_income_covering_spending_has_no_fi_target(self) -> None:
        result = calculate_fi_metrics(
            100_000,
            50_000,
            0.0,
            annual_income=60_000,
        )

        assert result["net_annual_spending"] == 0.0
        assert result["fi_target"] == 0.0
        assert result["fi_gap"] == 100_000.0


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
        assert result["annual_surplus"] == pytest.approx(0.0)
        assert result["annual_income"] == 25_000

    def test_income_alone_covers_spending_runway_infinite(self) -> None:
        # I >= S so net_withdrawal <= 0 → runway is infinite even with zero return.
        result = calculate_fi_metrics(100_000, 50_000, 0.0, annual_income=50_000)
        assert result["runway_years"] is None
        assert result["annual_surplus"] == pytest.approx(0.0)

    def test_income_exceeds_spending_runway_infinite(self) -> None:
        # net_withdrawal negative → portfolio actually grows even with r=0.
        result = calculate_fi_metrics(100_000, 50_000, 0.0, annual_income=60_000)
        assert result["runway_years"] is None
        assert result["annual_surplus"] == pytest.approx(10_000)

    def test_income_with_zero_rate_runway_uses_net_withdrawal(self) -> None:
        # r=0 → runway = P / net_withdrawal = 100_000 / (20_000 - 5_000) = 6.6667
        result = calculate_fi_metrics(100_000, 20_000, 0.0, annual_income=5_000)
        assert result["runway_years"] == pytest.approx(100_000 / 15_000)

    def test_default_income_zero_matches_three_arg_call(self) -> None:
        a = calculate_fi_metrics(500_000, 50_000, 5.0)
        b = calculate_fi_metrics(500_000, 50_000, 5.0, annual_income=0.0)
        assert a == b


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

    def test_projection_exposes_each_annual_cash_flow(self) -> None:
        projection = project_portfolio(
            100_000,
            20_000,
            5.0,
            years=1,
            annual_income=5_000,
        )

        year_one = projection.iloc[1]
        assert set(projection.columns) == {
            "Year",
            "Starting_Balance",
            "Investment_Return",
            "Income",
            "Spending",
            "Net_Cash_Flow",
            "Balance",
        }
        assert year_one["Starting_Balance"] == 100_000.0
        assert year_one["Investment_Return"] == 5_000.0
        assert year_one["Income"] == 5_000.0
        assert year_one["Spending"] == 20_000.0
        assert year_one["Balance"] == 90_000.0

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
        fi_passthrough_filters: TransactionFilterOptions,
    ) -> None:
        # Excluding the Travel group via apply_transaction_filters drops the
        # $400/mo rows; remaining is $1000/mo from Food.
        filters: TransactionFilterOptions = {
            **fi_passthrough_filters,
            "exclude_groups": ["Travel"],
        }
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
        assert len(totals) == 12
        assert (totals["Spending"] == 0).all()

    def test_window_outside_data_returns_zero(self, fi_transactions_df: pd.DataFrame) -> None:
        avg, totals = calculate_avg_monthly_spending(fi_transactions_df, "2030-01", "2030-12")
        assert avg == 0.0
        assert len(totals) == 12
        assert (totals["Spending"] == 0).all()

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

    def test_zero_spend_months_are_included_in_the_average(self) -> None:
        df = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-05", "2024-03-05"], utc=True),
                "Amount": [-300.0, -600.0],
                "Type": ["Expense", "Expense"],
                "Month": ["2024-01", "2024-03"],
            }
        )

        average, totals = calculate_avg_monthly_spending(
            df,
            "2024-01",
            "2024-03",
        )

        assert average == pytest.approx(300.0)
        assert totals["Spending"].tolist() == [300.0, 0.0, 600.0]


class TestRunwaySensitivity:
    def test_builds_every_spending_and_return_combination(self) -> None:
        sensitivity = build_runway_sensitivity(
            1_000_000,
            50_000,
            0.0,
            spending_changes=(-10, 0, 10),
            return_rates=(0.0, 5.0),
        )

        assert len(sensitivity) == 6
        assert set(sensitivity["Spending_Change"]) == {
            "-10%",
            "Baseline",
            "+10%",
        }
        sustainable = sensitivity[
            sensitivity["Spending_Change"].eq("-10%")
            & sensitivity["Return_Rate"].eq(5.0)
        ].iloc[0]
        assert sustainable["Runway_Label"] == "Sustainable"
        assert sustainable["Runway_Years"] == 100.0

    def test_default_grid_is_centered_on_selected_return(self) -> None:
        sensitivity = build_runway_sensitivity(
            500_000,
            50_000,
            0.0,
            baseline_return_rate=7.0,
        )

        assert set(sensitivity["Return_Rate"]) == {3.0, 5.0, 7.0, 9.0, 11.0}
        assert sensitivity.loc[
            sensitivity["Is_Baseline_Return"], "Return_Rate"
        ].unique().tolist() == [7.0]

    def test_zero_baseline_does_not_duplicate_return_scenarios(self) -> None:
        sensitivity = build_runway_sensitivity(
            500_000,
            50_000,
            0.0,
            baseline_return_rate=0.0,
        )

        assert set(sensitivity["Return_Rate"]) == {0.0, 2.0, 4.0}
        assert len(sensitivity) == 5 * 3
