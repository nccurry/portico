"""Tests for financial-independence math and spending helpers.

Math assertions reference closed-form expected values (inlined in comments next
to each assertion), so each test doubles as executable specification.
"""

import math

import pandas as pd
import pytest

from src.analysis.financial_independence import (
    IncomeStream,
    build_income_projection,
    build_runway_sensitivity,
    build_spending_coverage,
    calculate_avg_monthly_income,
    calculate_avg_monthly_spending,
    calculate_fi_metrics,
    income_for_year,
    project_portfolio,
    spending_for_year,
    summarize_spending_coverage,
)
from src.custom_types import IncomeChange, SpendingChange, TransactionFilterOptions
from src.transaction_filters import apply_transaction_filters


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

    def test_delayed_income_can_make_the_plan_sustainable(self) -> None:
        result = calculate_fi_metrics(
            120_000,
            20_000,
            0.0,
            income_streams=(IncomeStream("Social Security", 20_000, start_year=6),),
        )

        assert result["annual_income"] == 0.0
        assert result["runway_years"] is None


class TestSpendingChanges:
    @pytest.mark.parametrize(
        ("start_year", "annual_amount"),
        [(1, 20.0), (3, -1.0), (3, float("nan")), (3, float("inf"))],
    )
    def test_rejects_invalid_changes(self, start_year: int, annual_amount: float) -> None:
        with pytest.raises(ValueError):
            SpendingChange(start_year, annual_amount)

    def test_new_amount_starts_in_its_selected_year(self) -> None:
        schedule = (SpendingChange(6, 40.0), SpendingChange(11, 15.0))

        assert [spending_for_year(20.0, schedule, year) for year in (1, 5, 6, 10, 11)] == [
            20.0,
            20.0,
            40.0,
            40.0,
            15.0,
        ]

    def test_projection_and_expense_coverage_use_each_years_amount(self) -> None:
        schedule = (SpendingChange(3, 10.0),)
        projection = project_portfolio(100.0, 20.0, 0.0, 4, spending_schedule=schedule)
        income_projection = build_income_projection(0.0, (), 4)
        coverage = build_spending_coverage(income_projection, projection)

        assert projection["Spending"].tolist() == [0.0, 20.0, 20.0, 10.0, 10.0]
        assert projection["Balance"].tolist() == [100.0, 80.0, 60.0, 50.0, 40.0]
        assert coverage.groupby("Year")["Amount"].sum().tolist() == [20.0, 20.0, 10.0, 10.0]
        assert summarize_spending_coverage(coverage)["Years"].drop_duplicates().tolist() == [
            "Years 1-2",
            "Years 3-4",
        ]

    def test_later_increase_shortens_runway_but_does_not_change_year_one_target(self) -> None:
        baseline = calculate_fi_metrics(100.0, 10.0, 0.0)
        scheduled = calculate_fi_metrics(
            100.0,
            10.0,
            0.0,
            spending_schedule=(SpendingChange(3, 40.0),),
        )

        assert baseline["runway_years"] == 10.0
        assert scheduled["runway_years"] == pytest.approx(4.0)
        assert scheduled["fi_target"] == baseline["fi_target"]

    def test_later_decrease_cannot_rescue_a_plan_that_runs_out_first(self) -> None:
        result = calculate_fi_metrics(
            10.0,
            20.0,
            0.0,
            spending_schedule=(SpendingChange(3, 0.0),),
        )

        assert result["runway_years"] == pytest.approx(0.5)

    def test_spending_and_social_security_can_change_in_the_same_year(self) -> None:
        result = calculate_fi_metrics(
            100.0,
            20.0,
            0.0,
            income_streams=(IncomeStream("Social Security", 10.0, start_year=3),),
            spending_schedule=(SpendingChange(3, 40.0),),
        )

        assert result["runway_years"] == pytest.approx(4.0)

    def test_property_value_covers_a_later_spending_period(self) -> None:
        result = calculate_fi_metrics(
            10.0,
            15.0,
            0.0,
            real_estate_value=10.0,
            spending_schedule=(SpendingChange(2, 5.0),),
        )

        assert result["runway_years"] == pytest.approx(2.0)

    def test_zero_expenses_still_fund_negative_property_cash_flow(self) -> None:
        result = calculate_fi_metrics(
            10.0,
            0.0,
            0.0,
            income_streams=(IncomeStream("Real estate cash flow", -5.0),),
        )

        assert result["runway_years"] == pytest.approx(2.0)

    def test_sensitivity_adjusts_every_spending_amount(self) -> None:
        sensitivity = build_runway_sensitivity(
            100.0,
            10.0,
            0.0,
            spending_changes=(0, 20),
            return_rates=(0.0,),
            spending_schedule=(SpendingChange(2, 40.0),),
        )

        assert sensitivity["Runway_Years"].tolist() == pytest.approx([3.25, 1 + 88 / 48])


class TestIncomeChanges:
    @pytest.mark.parametrize(
        ("start_year", "annual_amount"),
        [(1, 20.0), (3, -1.0), (3, float("nan")), (3, float("inf"))],
    )
    def test_rejects_invalid_changes(self, start_year: int, annual_amount: float) -> None:
        with pytest.raises(ValueError):
            IncomeChange(start_year, annual_amount)

    def test_income_changes_start_in_the_selected_year(self) -> None:
        schedule = (IncomeChange(6, 40.0), IncomeChange(11, 0.0))

        assert [income_for_year(20.0, schedule, year) for year in (1, 5, 6, 10, 11)] == [
            20.0,
            20.0,
            40.0,
            40.0,
            0.0,
        ]

    def test_projection_and_coverage_use_the_income_active_each_year(self) -> None:
        schedule = (IncomeChange(3, 0.0),)
        incomes = build_income_projection(20.0, (IncomeStream("Social Security", 10.0, 3),), 4, schedule)
        portfolio = project_portfolio(
            100.0,
            30.0,
            0.0,
            4,
            annual_income=20.0,
            income_streams=(IncomeStream("Social Security", 10.0, 3),),
            income_schedule=schedule,
        )
        coverage = build_spending_coverage(incomes, portfolio)

        assert incomes.loc[incomes["Stream"].eq("Income"), "Income"].tolist() == [20.0, 20.0, 0.0, 0.0]
        assert portfolio["Income"].tolist() == [0.0, 20.0, 20.0, 10.0, 10.0]
        assert portfolio["Balance"].tolist() == [100.0, 90.0, 80.0, 60.0, 40.0]
        assert coverage.loc[coverage["Stream"].eq("Income"), "Amount"].tolist() == [20.0, 20.0, 0.0, 0.0]
        assert coverage.loc[coverage["Stream"].eq("Social Security"), "Amount"].tolist() == [0.0, 0.0, 10.0, 10.0]

    def test_later_income_drop_shortens_runway_but_keeps_year_one_target(self) -> None:
        baseline = calculate_fi_metrics(100.0, 20.0, 0.0, annual_income=10.0)
        scheduled = calculate_fi_metrics(
            100.0,
            20.0,
            0.0,
            annual_income=10.0,
            income_schedule=(IncomeChange(3, 0.0),),
        )

        assert baseline["runway_years"] == pytest.approx(10.0)
        assert scheduled["runway_years"] == pytest.approx(6.0)
        assert scheduled["fi_target"] == baseline["fi_target"]

    def test_later_income_cannot_rescue_a_plan_that_runs_out_first(self) -> None:
        result = calculate_fi_metrics(
            10.0,
            20.0,
            0.0,
            income_schedule=(IncomeChange(3, 20.0),),
        )

        assert result["runway_years"] == pytest.approx(0.5)

    def test_income_and_expenses_can_change_together(self) -> None:
        result = calculate_fi_metrics(
            100.0,
            20.0,
            0.0,
            annual_income=10.0,
            spending_schedule=(SpendingChange(3, 40.0),),
            income_schedule=(IncomeChange(3, 30.0),),
        )

        assert result["runway_years"] == pytest.approx(10.0)

    def test_sensitivity_keeps_income_periods(self) -> None:
        sensitivity = build_runway_sensitivity(
            100.0,
            20.0,
            10.0,
            spending_changes=(0, 20),
            return_rates=(0.0,),
            income_schedule=(IncomeChange(3, 0.0),),
        )

        assert sensitivity["Runway_Years"].tolist() == pytest.approx([6.0, 2 + 72 / 24])


class TestRealEstateAssumptions:
    def test_cash_flow_and_appreciation_change_the_projection(self) -> None:
        projection = project_portfolio(
            600_000,
            50_000,
            7.0,
            years=1,
            income_streams=(IncomeStream("Real estate cash flow", 12_000),),
            real_estate_value=400_000,
            real_estate_rate_pct=3.0,
        )

        year_one = projection.iloc[1]
        assert year_one["Investment_Return"] == pytest.approx(42_000)
        assert year_one["Property_Growth"] == pytest.approx(12_000)
        assert year_one["Income"] == pytest.approx(12_000)
        assert year_one["Investments"] == pytest.approx(604_000)
        assert year_one["Real_Estate"] == pytest.approx(412_000)
        assert year_one["Balance"] == pytest.approx(1_016_000)

    def test_saved_income_earns_the_investment_rate_next_year(self) -> None:
        projection = project_portfolio(
            100.0,
            20.0,
            10.0,
            years=2,
            annual_income=30.0,
            real_estate_value=100.0,
            real_estate_rate_pct=0.0,
        )

        assert projection["Investments"].tolist() == pytest.approx([100.0, 120.0, 142.0])
        assert projection["Real_Estate"].tolist() == pytest.approx([100.0, 100.0, 100.0])
        assert projection["Balance"].tolist() == pytest.approx([200.0, 220.0, 242.0])

    def test_property_growth_applies_only_to_property(self) -> None:
        projection = project_portfolio(
            0.0,
            0.0,
            7.0,
            years=2,
            real_estate_value=100.0,
            real_estate_rate_pct=3.0,
        )

        assert projection["Investments"].tolist() == [0.0, 0.0, 0.0]
        assert projection["Real_Estate"].tolist() == pytest.approx([100.0, 103.0, 106.09])

    def test_saved_income_creates_investments_without_a_starting_balance(self) -> None:
        projection = project_portfolio(
            0.0,
            20.0,
            10.0,
            years=2,
            annual_income=30.0,
            real_estate_value=100.0,
            real_estate_rate_pct=0.0,
        )

        assert projection["Investments"].tolist() == pytest.approx([0.0, 10.0, 21.0])
        assert projection["Real_Estate"].tolist() == [100.0, 100.0, 100.0]

    def test_property_value_covers_expenses_after_investments(self) -> None:
        projection = project_portfolio(
            10.0,
            15.0,
            0.0,
            years=2,
            real_estate_value=10.0,
            real_estate_rate_pct=0.0,
        )
        summary = calculate_fi_metrics(
            10.0,
            15.0,
            0.0,
            real_estate_value=10.0,
            real_estate_rate_pct=0.0,
        )

        assert projection["Investments"].tolist() == [10.0, 0.0, 0.0]
        assert projection["Real_Estate"].tolist() == [10.0, 5.0, 0.0]
        assert summary["runway_years"] == pytest.approx(20.0 / 15.0)

    def test_remaining_property_keeps_its_own_growth_rate(self) -> None:
        projection = project_portfolio(
            10.0,
            15.0,
            0.0,
            years=2,
            real_estate_value=10.0,
            real_estate_rate_pct=10.0,
        )

        assert projection.loc[1, "Real_Estate"] == pytest.approx(6.0)
        assert projection.loc[2, "Property_Growth"] == pytest.approx(0.6)
        assert projection.loc[2, "Investments"] == 0.0

    def test_negative_property_growth_shortens_runway(self) -> None:
        summary = calculate_fi_metrics(
            0.0,
            10.0,
            7.0,
            real_estate_value=100.0,
            real_estate_rate_pct=-10.0,
        )

        assert summary["annual_return"] == pytest.approx(-10.0)
        assert summary["runway_years"] == pytest.approx(math.log(0.5) / math.log(0.9))

    def test_property_growth_does_not_change_investment_growth(self) -> None:
        summary = calculate_fi_metrics(
            100.0,
            10.0,
            7.0,
            real_estate_value=100.0,
            real_estate_rate_pct=3.0,
        )

        assert summary["annual_return"] == pytest.approx(10.0)

    def test_negative_property_equity_reduces_investments_and_runway(self) -> None:
        projection = project_portfolio(
            100.0,
            20.0,
            10.0,
            years=1,
            real_estate_value=-50.0,
            real_estate_rate_pct=0.0,
        )
        summary = calculate_fi_metrics(
            100.0,
            20.0,
            10.0,
            real_estate_value=-50.0,
            real_estate_rate_pct=0.0,
        )

        assert projection.loc[1, "Investments"] == pytest.approx(40.0)
        assert projection.loc[1, "Real_Estate"] == 0.0
        assert summary["runway_years"] == pytest.approx(1 + math.log(20 / 16) / math.log(1.1))


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
            "Property_Growth",
            "Income",
            "Spending",
            "Net_Cash_Flow",
            "Investments",
            "Real_Estate",
            "Balance",
        }
        assert year_one["Starting_Balance"] == 100_000.0
        assert year_one["Investment_Return"] == 5_000.0
        assert year_one["Income"] == 5_000.0
        assert year_one["Spending"] == 20_000.0
        assert year_one["Balance"] == 90_000.0

    def test_retirement_income_starts_in_its_configured_year(self) -> None:
        # P=100, r=0, S=20. Social Security adds 10 starting in year 3.
        # The first two years withdraw 20; later years withdraw 10.
        projection = project_portfolio(
            100.0,
            20.0,
            0.0,
            years=4,
            income_streams=(IncomeStream("Social Security", 10.0, start_year=3),),
        )

        assert projection["Income"].tolist() == pytest.approx([0.0, 0.0, 0.0, 10.0, 10.0])
        assert projection["Balance"].tolist() == pytest.approx([100.0, 80.0, 60.0, 50.0, 40.0])


class TestIncomeStreams:
    def test_builds_a_year_by_year_income_schedule(self) -> None:
        projection = build_income_projection(
            12_000.0,
            (IncomeStream("Social Security", 18_000.0, start_year=2),),
            years=3,
        )

        income_by_stream = projection.pivot(index="Year", columns="Stream", values="Income")
        assert income_by_stream["Income"].tolist() == pytest.approx([12_000.0, 12_000.0, 12_000.0])
        assert income_by_stream["Social Security"].tolist() == pytest.approx([0.0, 18_000.0, 18_000.0])

    def test_splits_spending_between_income_and_withdrawals(self) -> None:
        streams = (IncomeStream("Social Security", 20_000.0, start_year=2),)
        income_projection = build_income_projection(
            10_000.0,
            streams,
            years=2,
        )
        portfolio_projection = project_portfolio(100_000.0, 50_000.0, 0.0, 2, 10_000.0, streams)

        coverage = build_spending_coverage(income_projection, portfolio_projection)
        coverage_by_stream = coverage.pivot(index="Year", columns="Stream", values="Amount").fillna(0.0)

        assert coverage_by_stream.loc[1, "Income"] == pytest.approx(10_000.0)
        assert coverage_by_stream.loc[1, "Social Security"] == pytest.approx(0.0)
        assert coverage_by_stream.loc[1, "From assets"] == pytest.approx(40_000.0)
        assert coverage_by_stream.loc[2, "Social Security"] == pytest.approx(20_000.0)
        assert coverage_by_stream.loc[2, "From assets"] == pytest.approx(20_000.0)
        assert coverage_by_stream["Not covered"].tolist() == [0.0, 0.0]

    def test_shows_uncovered_expenses_after_assets_run_out(self) -> None:
        streams = (IncomeStream("Social Security", 10.0, start_year=3),)
        income_projection = build_income_projection(0.0, streams, years=4)
        portfolio_projection = project_portfolio(10.0, 20.0, 0.0, 4, income_streams=streams)

        coverage = build_spending_coverage(income_projection, portfolio_projection)
        by_stream = coverage.pivot(index="Year", columns="Stream", values="Amount").fillna(0.0)

        assert by_stream["From assets"].tolist() == [10.0, 0.0, 0.0, 0.0]
        assert by_stream["Not covered"].tolist() == [10.0, 20.0, 10.0, 10.0]
        assert by_stream["Social Security"].tolist() == [0.0, 0.0, 10.0, 10.0]
        assert by_stream.sum(axis=1).tolist() == [20.0] * 4

        periods = summarize_spending_coverage(coverage)
        assert periods["Years"].drop_duplicates().tolist() == ["Year 1", "Year 2", "Years 3-4"]

    def test_income_above_expenses_is_saved_instead_of_plotted_as_coverage(self) -> None:
        income_projection = build_income_projection(30.0, (), years=1)
        portfolio_projection = project_portfolio(0.0, 20.0, 7.0, 1, annual_income=30.0)

        coverage = build_spending_coverage(income_projection, portfolio_projection)
        by_stream = coverage.set_index("Stream")["Amount"]

        assert by_stream["Income"] == 20.0
        assert by_stream["From assets"] == 0.0
        assert by_stream["Not covered"] == 0.0
        assert portfolio_projection.loc[1, "Investments"] == 10.0

    def test_negative_property_cash_flow_increases_the_amount_needed(self) -> None:
        streams = (IncomeStream("Real estate cash flow", -5.0),)
        income_projection = build_income_projection(0.0, streams, years=1)
        portfolio_projection = project_portfolio(0.0, 20.0, 0.0, 1, income_streams=streams)

        coverage = build_spending_coverage(income_projection, portfolio_projection)
        by_stream = coverage.set_index("Stream")["Amount"]

        assert coverage["Needed"].unique().tolist() == [25.0]
        assert by_stream["Real estate cash flow"] == 0.0
        assert by_stream["Not covered"] == 25.0


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
        df = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-10"], utc=True),
                "Amount": [-100, -250, -500],
                "Type": ["Expense"] * 3,
                "Month": ["2024-01", "2024-01", "2024-02"],
            }
        )
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


class TestCalculateAvgMonthlyIncome:
    def test_averages_income_totals_over_the_window(self, fi_transactions_df: pd.DataFrame) -> None:
        average, totals = calculate_avg_monthly_income(fi_transactions_df, "2024-01", "2024-12")

        assert average == pytest.approx(3_000.0)
        assert totals["Income"].tolist() == pytest.approx([3_000.0] * 12)

    def test_zero_income_months_are_included_in_the_average(self) -> None:
        df = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-05", "2024-03-05"], utc=True),
                "Amount": [300.0, 600.0],
                "Type": ["Income", "Income"],
                "Month": ["2024-01", "2024-03"],
            }
        )

        average, totals = calculate_avg_monthly_income(df, "2024-01", "2024-03")

        assert average == pytest.approx(300.0)
        assert totals["Income"].tolist() == [300.0, 0.0, 600.0]


class TestRunwaySensitivity:
    def test_investment_rate_scenarios_leave_property_growth_unchanged(self) -> None:
        sensitivity = build_runway_sensitivity(
            0.0,
            10.0,
            0.0,
            spending_changes=(0,),
            return_rates=(0.0, 20.0),
            real_estate_value=100.0,
            real_estate_rate_pct=0.0,
        )

        assert sensitivity["Runway_Years"].tolist() == pytest.approx([10.0, 10.0])

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
        sustainable = sensitivity[sensitivity["Spending_Change"].eq("-10%") & sensitivity["Return_Rate"].eq(5.0)].iloc[
            0
        ]
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
        assert sensitivity.loc[sensitivity["Is_Baseline_Return"], "Return_Rate"].unique().tolist() == [7.0]

    def test_zero_baseline_does_not_duplicate_return_scenarios(self) -> None:
        sensitivity = build_runway_sensitivity(
            500_000,
            50_000,
            0.0,
            baseline_return_rate=0.0,
        )

        assert set(sensitivity["Return_Rate"]) == {0.0, 2.0, 4.0}
        assert len(sensitivity) == 5 * 3

    def test_negative_baseline_includes_the_selected_return(self) -> None:
        sensitivity = build_runway_sensitivity(
            500_000,
            50_000,
            0.0,
            baseline_return_rate=-5.0,
        )

        assert set(sensitivity["Return_Rate"]) == {-9.0, -7.0, -5.0, -3.0, -1.0}
        assert sensitivity.loc[sensitivity["Is_Baseline_Return"], "Return_Rate"].unique().tolist() == [-5.0]

    def test_uses_delayed_income_streams(self) -> None:
        sensitivity = build_runway_sensitivity(
            120_000,
            20_000,
            0.0,
            spending_changes=(0,),
            return_rates=(0.0,),
            income_streams=(IncomeStream("Social Security", 20_000, start_year=6),),
        )

        result = sensitivity.iloc[0]
        assert result["Runway_Label"] == "Sustainable"
        assert result["Runway_Years"] == 100.0
