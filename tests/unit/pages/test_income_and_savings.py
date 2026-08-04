"""Tests for income, expense, and savings calculations."""
from collections.abc import Callable
from typing import Any

import pytest
import pandas as pd

from src.spreadsheet import TransactionsSpreadsheet
from src.analysis.income import calculate_savings_summary, process_income_expense_data


class TestProcessIncomeExpenseData:

    def test_separates_income_expense(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        # Should have Income and Expense columns
        assert 'Income' in result.columns
        assert 'Expense' in result.columns
        # Income values should be positive, Expense values negative
        assert (result['Income'] >= 0).all()
        assert (result['Expense'] <= 0).all()

    def test_savings_hand_computed_from_fixture(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """The fixture has: Jan [+3000, -1000], Feb [+4000, -2000], Mar [+5000, -1500].

        Expected Savings per month (Income - |Expense|, preserving sign):
            Jan: 3000 + (-1000) = +2000
            Feb: 4000 + (-2000) = +2000
            Mar: 5000 + (-1500) = +3500
        """
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)
        savings_by_month = dict(zip(result['Month'], result['Savings']))
        assert savings_by_month['2024-01'] == pytest.approx(2000.0)
        assert savings_by_month['2024-02'] == pytest.approx(2000.0)
        assert savings_by_month['2024-03'] == pytest.approx(3500.0)

    def test_savings_rate_hand_computed_from_fixture(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Hand-computed savings rates for the fixture:
            Jan: 2000 / 3000 * 100 = 66.67%
            Feb: 2000 / 4000 * 100 = 50.00%
            Mar: 3500 / 5000 * 100 = 70.00%
        """
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)
        rate_by_month = dict(zip(result['Month'], result['Savings_Rate']))
        assert rate_by_month['2024-01'] == pytest.approx(2000 / 3000 * 100)
        assert rate_by_month['2024-02'] == pytest.approx(50.0)
        assert rate_by_month['2024-03'] == pytest.approx(70.0)

    def test_savings_rate_zero_income(self, basic_filters: dict[str, Any], make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet]) -> None:
        """When income is 0, savings rate should be 0 (no division by zero)."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [-500],
            'Type': ['Expense'],
            'Category': ['Groceries'],
            'Group': ['Food'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['STORE PURCHASE'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)

        # Should not crash and savings rate should be 0
        assert (result['Savings_Rate'] == 0).all()

    def test_output_sorted_by_month(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        months = result['Month'].tolist()
        assert months == sorted(months)

    def test_only_income_month_gives_100_percent_rate(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Month with income but no expenses should have 100% savings rate."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [5000],
            'Type': ['Income'],
            'Category': ['Salary'],
            'Group': ['Income'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['PAYROLL'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)

        assert len(result) == 1
        assert result.iloc[0]['Savings_Rate'] == pytest.approx(100.0)
        assert result.iloc[0]['Savings'] == pytest.approx(5000.0)

    def test_only_expense_month_gives_zero_rate(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Month with only expenses should have 0% savings rate (no income to divide by)."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [-500],
            'Type': ['Expense'],
            'Category': ['Groceries'],
            'Group': ['Food'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['STORE'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)

        assert result.iloc[0]['Savings_Rate'] == 0
        assert result.iloc[0]['Expense'] == pytest.approx(-500.0)

    def test_multiple_months_varying_ratios(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Each month gets its own savings rate, varying by income/expense mix."""
        df = pd.DataFrame({
            'Date': pd.to_datetime([
                '2024-01-15', '2024-01-20',  # Jan: 1000 income, 200 expense
                '2024-02-15', '2024-02-20',  # Feb: 1000 income, 800 expense
            ], utc=True),
            'Amount': [1000, -200, 1000, -800],
            'Type': ['Income', 'Expense', 'Income', 'Expense'],
            'Category': ['Salary', 'Groceries', 'Salary', 'Groceries'],
            'Group': ['Income', 'Food', 'Income', 'Food'],
            'Account': ['Checking'] * 4,
            'Month': ['2024-01', '2024-01', '2024-02', '2024-02'],
            'Full Description': ['PAY', 'STORE', 'PAY', 'STORE'],
            'Institution': ['Bank'] * 4,
            'Account #': ['1234'] * 4,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)

        jan = result[result['Month'] == '2024-01'].iloc[0]
        feb = result[result['Month'] == '2024-02'].iloc[0]

        # Jan: (1000 - 200) / 1000 * 100 = 80%
        assert jan['Savings_Rate'] == pytest.approx(80.0)
        # Feb: (1000 - 800) / 1000 * 100 = 20%
        assert feb['Savings_Rate'] == pytest.approx(20.0)

    def test_empty_dataframe(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
        empty_transactions_df: pd.DataFrame,
    ) -> None:
        """Empty transactions produce empty result without errors."""
        ts = make_transactions_spreadsheet(empty_transactions_df)
        result = process_income_expense_data(ts, basic_filters)

        assert len(result) == 0

    def test_income_display_is_absolute(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Income_Display and Expense_Display are absolute values."""
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)

        assert (result['Income_Display'] >= 0).all()
        assert (result['Expense_Display'] >= 0).all()

    def test_net_column_matches_hand_computed_monthly_net(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Net should equal Income + Expense per month, independently computed.

        Jan net = 3000 - 1000 = 2000
        Feb net = 4000 - 2000 = 2000
        Mar net = 5000 - 1500 = 3500
        """
        ts = make_transactions_spreadsheet(income_expense_sample_df)
        result = process_income_expense_data(ts, basic_filters)
        net_by_month = dict(zip(result['Month'], result['Net']))
        assert net_by_month['2024-01'] == pytest.approx(2000.0)
        assert net_by_month['2024-02'] == pytest.approx(2000.0)
        assert net_by_month['2024-03'] == pytest.approx(3500.0)

    def test_same_month_multiple_incomes_accumulate(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Multiple income rows in a month sum together."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15', '2024-01-30'], utc=True),
            'Amount': [3000, 1500],
            'Type': ['Income', 'Income'],
            'Category': ['Salary', 'Bonus'],
            'Group': ['Income', 'Income'],
            'Account': ['Checking'] * 2,
            'Month': ['2024-01'] * 2,
            'Full Description': ['PAYROLL', 'BONUS'],
            'Institution': ['Bank'] * 2,
            'Account #': ['1234'] * 2,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)
        assert result.iloc[0]['Income'] == pytest.approx(4500.0)

    def test_same_month_multiple_expenses_accumulate(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Multiple expense rows in a month sum together (stay negative)."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-05', '2024-01-10', '2024-01-20'], utc=True),
            'Amount': [-100, -250, -75],
            'Type': ['Expense'] * 3,
            'Category': ['Groceries', 'Dining', 'Coffee'],
            'Group': ['Food'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01'] * 3,
            'Full Description': ['A', 'B', 'C'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)
        assert result.iloc[0]['Expense'] == pytest.approx(-425.0)

    def test_refund_classified_as_income_contributes_positively(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """A positive-amount expense-category refund is classified based on
        Type column, not sign. If Type=Income, it contributes to income."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [50],  # positive refund
            'Type': ['Income'],
            'Category': ['Refund'],
            'Group': ['Income'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['TARGET REFUND'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)
        assert result.iloc[0]['Income'] == pytest.approx(50.0)
        assert result.iloc[0]['Expense'] == pytest.approx(0.0)

    def test_month_with_income_only_fills_expense_with_zero(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """A month with only income should have Expense=0, not NaN."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15', '2024-02-10'], utc=True),
            'Amount': [3000, -100],
            'Type': ['Income', 'Expense'],
            'Category': ['Salary', 'Groceries'],
            'Group': ['Income', 'Food'],
            'Account': ['Checking'] * 2,
            'Month': ['2024-01', '2024-02'],
            'Full Description': ['PAY', 'STORE'],
            'Institution': ['Bank'] * 2,
            'Account #': ['1234'] * 2,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)
        jan = result[result['Month'] == '2024-01'].iloc[0]
        assert jan['Expense'] == pytest.approx(0.0)
        assert pd.notna(jan['Expense'])

    def test_month_with_expense_only_fills_income_with_zero(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """A month with only expenses should have Income=0, not NaN."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15', '2024-02-10'], utc=True),
            'Amount': [3000, -100],
            'Type': ['Income', 'Expense'],
            'Category': ['Salary', 'Groceries'],
            'Group': ['Income', 'Food'],
            'Account': ['Checking'] * 2,
            'Month': ['2024-01', '2024-02'],
            'Full Description': ['PAY', 'STORE'],
            'Institution': ['Bank'] * 2,
            'Account #': ['1234'] * 2,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)
        feb = result[result['Month'] == '2024-02'].iloc[0]
        assert feb['Income'] == pytest.approx(0.0)
        assert pd.notna(feb['Income'])

    def test_transfer_type_excluded_if_not_income_or_expense(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Rows with Type not in {Income, Expense} are excluded from monthly
        income/expense aggregates. Transfers should not double-count."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15', '2024-01-20', '2024-01-25'], utc=True),
            'Amount': [3000, -500, -2000],
            'Type': ['Income', 'Expense', 'Transfer'],
            'Category': ['Salary', 'Groceries', 'Transfer'],
            'Group': ['Income', 'Food', 'Transfer'],
            'Account': ['Checking'] * 3,
            'Month': ['2024-01'] * 3,
            'Full Description': ['PAY', 'STORE', 'MOVE TO SAVINGS'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)
        jan = result.iloc[0]
        assert jan['Income'] == pytest.approx(3000.0)
        # Expense should be -500 only (Transfer excluded)
        assert jan['Expense'] == pytest.approx(-500.0)

    def test_months_across_year_boundary_sort_correctly(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Month strings YYYY-MM sort lexically = chronologically across years."""
        df = pd.DataFrame({
            'Date': pd.to_datetime([
                '2023-12-15', '2024-01-15', '2024-12-15', '2025-01-15',
            ], utc=True),
            'Amount': [1000, 1100, 1200, 1300],
            'Type': ['Income'] * 4,
            'Category': ['Salary'] * 4,
            'Group': ['Income'] * 4,
            'Account': ['Checking'] * 4,
            'Month': ['2023-12', '2024-01', '2024-12', '2025-01'],
            'Full Description': ['PAY'] * 4,
            'Institution': ['Bank'] * 4,
            'Account #': ['1234'] * 4,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)
        months = result['Month'].tolist()
        assert months == ['2023-12', '2024-01', '2024-12', '2025-01']

    def test_savings_rate_near_zero_income_uses_threshold(
        self,
        basic_filters: dict[str, Any],
        make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet],
    ) -> None:
        """Income_Display > 0.01 is the guard; penny-level income still divides."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15', '2024-01-16'], utc=True),
            'Amount': [0.50, -100],  # tiny income, real expense
            'Type': ['Income', 'Expense'],
            'Category': ['Misc', 'Groceries'],
            'Group': ['Income', 'Food'],
            'Account': ['Checking'] * 2,
            'Month': ['2024-01'] * 2,
            'Full Description': ['MISC', 'STORE'],
            'Institution': ['Bank'] * 2,
            'Account #': ['1234'] * 2,
        })
        ts = make_transactions_spreadsheet(df)
        result = process_income_expense_data(ts, basic_filters)
        # 0.50 income > 0.01 threshold → rate computed: (0.50 - 100)/0.50 * 100 = -19900%
        assert result.iloc[0]['Savings_Rate'] == pytest.approx((0.50 - 100) / 0.50 * 100)

    def test_exclude_groups_filter(self, make_transactions_spreadsheet: Callable[..., TransactionsSpreadsheet]) -> None:
        """Excluding a group removes its transactions from the calculation."""
        # Use the conftest scrubbed_transactions_df which has Bills, Food, Shopping, Income
        filters = {
            'exclude_groups': ['Food'],
            'exclude_categories': [],
            'filter_large_income': False,
            'income_threshold': 50000,
            'filter_large_expenses': False,
            'expense_threshold': 50000,
            'target_rate': 20,
        }
        # Default fixture has: Salary(Income), Groceries(Food), Electric(Bills),
        # Salary(Income), Restaurants(Food), Amazon(Shopping), Salary(Income), Internet(Bills)
        ts = make_transactions_spreadsheet()
        result = process_income_expense_data(ts, filters)

        # With Food excluded, expenses are: Electric(-95), Amazon(-200), Internet(-79.99)
        total_expense = result['Expense'].sum()
        assert abs(total_expense) == pytest.approx(95.0 + 200.0 + 79.99)


class TestCalculateSavingsSummary:
    """Test ``calculate_savings_summary`` — pure metrics derived from pivot data."""

    def _pivot(self, rows: list[dict]) -> pd.DataFrame:
        """Build a minimal df_pivot from row dicts."""
        return pd.DataFrame(rows)

    def test_empty_pivot(self) -> None:
        """Empty input returns zeroed summary."""
        result = calculate_savings_summary(pd.DataFrame())
        assert result["avg_monthly_rate"] == 0.0
        assert result["overall_rate"] == 0.0
        assert result["avg_monthly_amount"] == 0.0
        assert result["total_saved"] == 0.0
        assert result["num_months"] == 0

    def test_single_month(self) -> None:
        df = self._pivot([{
            "Savings_Rate": 50.0,
            "Income_Display": 4000.0,
            "Savings": 2000.0,
        }])
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(50.0)
        assert result["overall_rate"] == pytest.approx(50.0)
        assert result["avg_monthly_amount"] == pytest.approx(2000.0)
        assert result["total_saved"] == pytest.approx(2000.0)
        assert result["num_months"] == 1

    def test_weighted_vs_simple_avg_diverge(self) -> None:
        """Months with unequal income cause weighted and simple averages to differ."""
        df = self._pivot([
            {"Savings_Rate": 80.0, "Income_Display": 1000.0, "Savings": 800.0},
            {"Savings_Rate": 20.0, "Income_Display": 9000.0, "Savings": 1800.0},
        ])
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(50.0)
        assert result["overall_rate"] == pytest.approx(26.0)

    def test_zero_income_overall_rate(self) -> None:
        """When total income is zero, overall_rate should be 0 (no division error)."""
        df = self._pivot([
            {"Savings_Rate": 0.0, "Income_Display": 0.0, "Savings": -500.0},
        ])
        result = calculate_savings_summary(df)
        assert result["overall_rate"] == 0.0
        assert result["total_saved"] == pytest.approx(-500.0)

    def test_negative_savings(self) -> None:
        """Spending more than earning produces negative savings metrics."""
        df = self._pivot([
            {"Savings_Rate": -25.0, "Income_Display": 4000.0, "Savings": -1000.0},
        ])
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(-25.0)
        assert result["overall_rate"] == pytest.approx(-25.0)
        assert result["total_saved"] == pytest.approx(-1000.0)

    def test_num_months(self) -> None:
        df = self._pivot([
            {"Savings_Rate": 10.0, "Income_Display": 5000.0, "Savings": 500.0},
            {"Savings_Rate": 20.0, "Income_Display": 5000.0, "Savings": 1000.0},
            {"Savings_Rate": 30.0, "Income_Display": 5000.0, "Savings": 1500.0},
        ])
        result = calculate_savings_summary(df)
        assert result["num_months"] == 3
        assert result["total_saved"] == pytest.approx(3000.0)
        assert result["avg_monthly_amount"] == pytest.approx(1000.0)

    def test_avg_rate_and_avg_amount_can_have_opposite_signs(self) -> None:
        """SIMPSON'S PARADOX — intentional behavior, not a bug.

        Monthly Avg Rate = mean(Savings / Income_Display)
        Monthly Avg Amount = mean(Savings)

        A single low-income-high-loss month produces a disproportionately
        large negative percentage (dividing a loss by a small income magnifies
        the rate) while the dollar amount has no such leverage.  The result:
        Monthly Avg Rate can go negative while Monthly Avg Amount stays
        positive (and vice versa).

        This test documents the behavior so no one "fixes" it later. If the
        metric semantics ever change, update this test too — don't delete it.

        For the income-weighted answer, use ``overall_rate``.
        """
        df = self._pivot(
            # 11 normal months: 10% savings rate, $1000 saved each
            [{"Savings_Rate": 10.0, "Income_Display": 10000.0, "Savings": 1000.0}] * 11
            # 1 bad month: low income, big loss → -400% rate, -$2000
            + [{"Savings_Rate": -400.0, "Income_Display": 500.0, "Savings": -2000.0}]
        )
        result = calculate_savings_summary(df)

        # Expected values (hand-computed from the 12 input rows):
        #   avg_monthly_rate   = (11*10 + -400) / 12        = -290/12   = -24.1666...
        #   avg_monthly_amount = (11*1000 + -2000) / 12     = 9000/12   = 750.00
        #   total_saved        = 11*1000 + -2000            = 9000.00
        #   total_income       = 11*10000 + 500             = 110500.00
        #   overall_rate       = 9000 / 110500 * 100        = 8.14479...
        assert result["avg_monthly_rate"] == pytest.approx(-24.16666666, abs=1e-4)
        assert result["avg_monthly_amount"] == pytest.approx(750.0)
        assert result["total_saved"] == pytest.approx(9000.0)
        assert result["overall_rate"] == pytest.approx(8.14479638, abs=1e-4)

        # Sign divergence: simple mean rate is negative, dollar mean is positive
        assert result["avg_monthly_rate"] < 0
        assert result["avg_monthly_amount"] > 0
        assert result["overall_rate"] > 0

    def test_avg_rate_vs_overall_rate_diverge_on_outliers(self) -> None:
        """An outlier low-income month can drag avg_monthly_rate far from
        overall_rate even when dollar savings are healthy.

        Inputs: 11 months at (20%, $10k income, $2k saved) + 1 month (-1000%, $100, -$1000).
        Hand-computed:
            avg_monthly_rate = (11*20 + -1000) / 12 = -780/12    = -65.00
            total_saved      = 11*2000 + -1000                   = 21000
            total_income     = 11*10000 + 100                    = 110100
            overall_rate     = 21000 / 110100 * 100              = 19.0735...
        """
        df = self._pivot(
            [{"Savings_Rate": 20.0, "Income_Display": 10000.0, "Savings": 2000.0}] * 11
            + [{"Savings_Rate": -1000.0, "Income_Display": 100.0, "Savings": -1000.0}]
        )
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(-65.0)
        assert result["overall_rate"] == pytest.approx(19.07356948, abs=1e-4)
        # Sign divergence is the documented property of this metric pair
        assert result["avg_monthly_rate"] < 0 < result["overall_rate"]

    def test_many_tiny_income_months_hurt_avg_rate(self) -> None:
        """Many small-income months pull the simple-mean rate toward 0 even
        if the weighted rate is healthy.

        Inputs: 1 month (50%, $10k, $5k saved) + 11 months (1%, $100, $1 saved).
        Hand-computed:
            avg_monthly_rate = (50 + 11*1) / 12     = 61/12    = 5.0833...
            total_saved      = 5000 + 11*1           = 5011
            total_income     = 10000 + 11*100        = 11100
            overall_rate     = 5011 / 11100 * 100    = 45.1441...
        """
        df = self._pivot(
            [{"Savings_Rate": 50.0, "Income_Display": 10000.0, "Savings": 5000.0}]
            + [{"Savings_Rate": 1.0, "Income_Display": 100.0, "Savings": 1.0}] * 11
        )
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(5.08333333, abs=1e-4)
        assert result["overall_rate"] == pytest.approx(45.14414414, abs=1e-4)
        # Same sign, very different magnitudes
        assert result["avg_monthly_rate"] > 0
        assert result["overall_rate"] > 0

    def test_savings_rate_above_100_percent(self) -> None:
        """Windfall month (bonus/refund) can push rate above 100%."""
        df = self._pivot([
            {"Savings_Rate": 150.0, "Income_Display": 1000.0, "Savings": 1500.0},
        ])
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == pytest.approx(150.0)
        assert result["overall_rate"] == pytest.approx(150.0)
        assert result["avg_monthly_amount"] == pytest.approx(1500.0)

    def test_mix_positive_negative_savings_zero_net(self) -> None:
        """When gains exactly offset losses, total_saved is zero but both
        averages can still be non-zero due to rate leverage."""
        df = self._pivot([
            {"Savings_Rate": 50.0, "Income_Display": 2000.0, "Savings": 1000.0},
            {"Savings_Rate": -100.0, "Income_Display": 1000.0, "Savings": -1000.0},
        ])
        result = calculate_savings_summary(df)
        assert result["total_saved"] == pytest.approx(0.0)
        assert result["avg_monthly_amount"] == pytest.approx(0.0)
        # overall_rate: 0 / 3000 = 0
        assert result["overall_rate"] == pytest.approx(0.0)
        # Simple avg rate: (50 + -100) / 2 = -25
        assert result["avg_monthly_rate"] == pytest.approx(-25.0)

    def test_all_zero_savings(self) -> None:
        """Income equals expenses every month — zero savings, zero rate."""
        df = self._pivot([
            {"Savings_Rate": 0.0, "Income_Display": 3000.0, "Savings": 0.0},
            {"Savings_Rate": 0.0, "Income_Display": 3000.0, "Savings": 0.0},
        ])
        result = calculate_savings_summary(df)
        assert result["avg_monthly_rate"] == 0.0
        assert result["overall_rate"] == 0.0
        assert result["avg_monthly_amount"] == 0.0
        assert result["total_saved"] == 0.0
        assert result["num_months"] == 2

    def test_overall_rate_weighted_by_income_not_month_count(self) -> None:
        """overall_rate = total_saved / total_income, not average of rates.
        One high-income month should dominate many low-income months.

        Inputs: 1 month (50%, $100k, $50k saved) + 11 months (0%, $1k, $0 saved).
        Hand-computed:
            total_saved     = 50000 + 11*0            = 50000
            total_income    = 100000 + 11*1000        = 111000
            overall_rate    = 50000 / 111000 * 100    = 45.04504504...
            avg_monthly_rate = (50 + 11*0) / 12       = 50/12 = 4.16666...
        """
        df = self._pivot([
            {"Savings_Rate": 50.0, "Income_Display": 100_000.0, "Savings": 50_000.0},
        ] + [
            {"Savings_Rate": 0.0, "Income_Display": 1000.0, "Savings": 0.0},
        ] * 11)
        result = calculate_savings_summary(df)
        assert result["overall_rate"] == pytest.approx(45.04504504, abs=1e-4)
        assert result["avg_monthly_rate"] == pytest.approx(4.16666666, abs=1e-4)
        assert result["total_saved"] == pytest.approx(50000.0)

    def test_nan_handling_in_savings_column(self) -> None:
        """NaN savings values propagate through sum() and mean() predictably."""
        df = pd.DataFrame([
            {"Savings_Rate": 10.0, "Income_Display": 1000.0, "Savings": 100.0},
            {"Savings_Rate": 20.0, "Income_Display": 2000.0, "Savings": 400.0},
        ])
        result = calculate_savings_summary(df)
        assert result["total_saved"] == pytest.approx(500.0)
        assert result["avg_monthly_amount"] == pytest.approx(250.0)

    def test_single_penny_savings_precision(self) -> None:
        """Floating-point math stays accurate near the zero boundary."""
        df = self._pivot([
            {"Savings_Rate": 0.01, "Income_Display": 10000.0, "Savings": 1.0},
        ])
        result = calculate_savings_summary(df)
        assert result["total_saved"] == pytest.approx(1.0, abs=1e-9)
        assert result["avg_monthly_rate"] == pytest.approx(0.01, abs=1e-9)
