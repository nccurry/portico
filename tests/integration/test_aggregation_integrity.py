"""Aggregation integrity tests.

Feed larger datasets through the filter + aggregate pipeline and verify
that the numbers at each stage are arithmetically consistent.
"""
import pytest

from src.filters import apply_transaction_filters
from tests._pages import income_and_savings, spending_by_category

process_income_expense_data = income_and_savings.process_income_expense_data
process_spending_data = spending_by_category.process_spending_data


# ---------------------------------------------------------------------------
# Filter pipeline integrity
# ---------------------------------------------------------------------------

class TestFilterPipelineIntegrity:
    """Verify that filtering preserves arithmetic identities."""

    def test_total_amount_preserved_without_filters(self, extended_transactions_df):
        """With no filters (except Transfer exclusion), total amount is preserved."""
        df = extended_transactions_df.copy()
        # Ensure no Transfer rows in extended fixture
        original_total = df[df['Group'] != 'Transfer']['Amount'].sum()

        filtered = apply_transaction_filters(df, {})
        assert filtered['Amount'].sum() == pytest.approx(original_total)

    def test_exclude_group_removes_correct_amount(self, extended_transactions_df):
        """Excluding a group removes exactly that group's total."""
        df = extended_transactions_df.copy()
        df = df[df['Group'] != 'Transfer']

        food_total = df[df['Group'] == 'Food']['Amount'].sum()
        non_food_total = df[df['Group'] != 'Food']['Amount'].sum()

        filtered = apply_transaction_filters(df, {'exclude_groups': ['Food']})
        assert filtered['Amount'].sum() == pytest.approx(non_food_total)
        assert filtered['Amount'].sum() == pytest.approx(
            df['Amount'].sum() - food_total
        )

    def test_include_group_keeps_only_that_group(self, extended_transactions_df):
        """Include filter keeps only the specified group."""
        df = extended_transactions_df.copy()

        food_total = df[df['Group'] == 'Food']['Amount'].sum()

        filtered = apply_transaction_filters(df, {'include_groups': ['Food']})
        assert filtered['Amount'].sum() == pytest.approx(food_total)

    def test_large_expense_filter_removes_correct_rows(self, extended_transactions_df):
        """Large expense filter removes exactly the over-threshold expenses."""
        df = extended_transactions_df.copy()
        df = df[df['Group'] != 'Transfer']
        threshold = 200

        # Manually compute what should remain
        expenses_over = df[(df['Type'] == 'Expense') & (df['Amount'].abs() > threshold)]
        expected_removed_amount = expenses_over['Amount'].sum()

        filters = {'filter_large_expenses': True, 'expense_threshold': threshold}
        filtered = apply_transaction_filters(df, filters)

        assert filtered['Amount'].sum() == pytest.approx(
            df['Amount'].sum() - expected_removed_amount
        )


# ---------------------------------------------------------------------------
# Income/Expense aggregation integrity
# ---------------------------------------------------------------------------

class TestIncomeExpenseAggregation:
    """Verify that monthly income/expense/savings aggregations are consistent."""

    def test_monthly_totals_sum_to_overall(
        self,
        extended_transactions_df,
        passthrough_filters,
        make_transactions_spreadsheet,
    ):
        """Sum of monthly Income and Expense columns equals the raw totals."""
        ts = make_transactions_spreadsheet(extended_transactions_df)
        result = process_income_expense_data(ts, passthrough_filters)

        # Raw totals (Transfer excluded by filter)
        df = extended_transactions_df[extended_transactions_df['Group'] != 'Transfer']
        raw_income = df[df['Type'] == 'Income']['Amount'].sum()
        raw_expense = df[df['Type'] == 'Expense']['Amount'].sum()

        assert result['Income'].sum() == pytest.approx(raw_income)
        assert result['Expense'].sum() == pytest.approx(raw_expense)

    def test_savings_is_income_plus_expense_every_month(
        self,
        extended_transactions_df,
        passthrough_filters,
        make_transactions_spreadsheet,
    ):
        """Savings = Income + Expense for every single month."""
        ts = make_transactions_spreadsheet(extended_transactions_df)
        result = process_income_expense_data(ts, passthrough_filters)

        for _, row in result.iterrows():
            assert row['Savings'] == pytest.approx(row['Income'] + row['Expense'])

    def test_all_months_accounted_for(
        self,
        extended_transactions_df,
        passthrough_filters,
        make_transactions_spreadsheet,
    ):
        """Every month with transactions appears in the result."""
        ts = make_transactions_spreadsheet(extended_transactions_df)
        result = process_income_expense_data(ts, passthrough_filters)

        df = extended_transactions_df[extended_transactions_df['Group'] != 'Transfer']
        expected_months = set(df['Month'].unique())
        result_months = set(result['Month'].unique())

        assert expected_months == result_months


# ---------------------------------------------------------------------------
# Spending aggregation integrity
# ---------------------------------------------------------------------------

class TestSpendingAggregation:
    """Verify that spending category aggregations are consistent."""

    def test_category_totals_sum_to_overall(
        self,
        extended_transactions_df,
        full_date_range,
        make_transactions_spreadsheet,
    ):
        ts = make_transactions_spreadsheet(extended_transactions_df)
        filters = {
            'include_groups': [],
            'include_categories': [],
            'exclude_groups': [],
            'exclude_categories': [],
            'filter_large_expenses': False,
            'expense_threshold': 999999,
        }
        start, end = full_date_range
        df_period, df_by_category = process_spending_data(ts, filters, start, end)

        # Sum of category amounts should equal total period spending
        assert df_by_category['Amount'].sum() == pytest.approx(
            df_period['Amount'].abs().sum()
        )

    def test_percentages_sum_to_100(
        self,
        extended_transactions_df,
        full_date_range,
        make_transactions_spreadsheet,
    ):
        ts = make_transactions_spreadsheet(extended_transactions_df)
        filters = {
            'include_groups': [],
            'include_categories': [],
            'exclude_groups': [],
            'exclude_categories': [],
            'filter_large_expenses': False,
            'expense_threshold': 999999,
        }
        start, end = full_date_range
        _, df_by_category = process_spending_data(ts, filters, start, end)

        total_pct = df_by_category['Percentage'].sum()
        assert total_pct == pytest.approx(100.0, abs=0.5)

    def test_no_income_in_spending(
        self,
        extended_transactions_df,
        full_date_range,
        make_transactions_spreadsheet,
    ):
        """Spending data should never include income transactions."""
        ts = make_transactions_spreadsheet(extended_transactions_df)
        filters = {
            'include_groups': [],
            'include_categories': [],
            'exclude_groups': [],
            'exclude_categories': [],
            'filter_large_expenses': False,
            'expense_threshold': 999999,
        }
        start, end = full_date_range
        df_period, _ = process_spending_data(ts, filters, start, end)

        assert (df_period['Type'] == 'Expense').all()


# ---------------------------------------------------------------------------
# Monthly amounts aggregation (spreadsheet methods)
# ---------------------------------------------------------------------------

class TestMonthlyAmountsAggregation:
    """Verify that get_monthly_amounts_by_* methods sum correctly."""

    def test_monthly_category_sums_match_raw(
        self,
        extended_transactions_df,
        make_transactions_spreadsheet,
    ):
        """Monthly amounts by category should sum to the raw category total."""
        ts = make_transactions_spreadsheet(extended_transactions_df)

        for category in extended_transactions_df['Category'].unique():
            monthly = ts.get_monthly_amounts_by_category(category)
            raw_total = extended_transactions_df[
                extended_transactions_df['Category'] == category
            ]['Amount'].sum()

            assert monthly['Amount'].sum() == pytest.approx(raw_total)

    def test_monthly_group_sums_match_raw(
        self,
        extended_transactions_df,
        make_transactions_spreadsheet,
    ):
        """Monthly amounts by group should sum to the raw group total."""
        ts = make_transactions_spreadsheet(extended_transactions_df)

        for group in extended_transactions_df['Group'].unique():
            monthly = ts.get_monthly_amounts_by_group(group)
            raw_total = extended_transactions_df[
                extended_transactions_df['Group'] == group
            ]['Amount'].sum()

            assert monthly['Amount'].sum() == pytest.approx(raw_total)

    def test_inverted_amounts_negate(
        self,
        extended_transactions_df,
        make_transactions_spreadsheet,
    ):
        """Inverted amounts should be the negative of non-inverted."""
        ts = make_transactions_spreadsheet(extended_transactions_df)

        for category in ['Groceries', 'Salary']:
            normal = ts.get_monthly_amounts_by_category(category)
            inverted = ts.get_monthly_amounts_by_category(category, invert_amount=True)

            if not normal.empty:
                assert inverted['Amount'].sum() == pytest.approx(-normal['Amount'].sum())
