"""Tests for Pages/2_Spending_by_Category.py - process_spending_data and calculate_distribution_stats."""
import pytest
import pandas as pd

from importlib import import_module

_mod = import_module('Pages.2_Spending_by_Category')
process_spending_data = _mod.process_spending_data
calculate_distribution_stats = _mod.calculate_distribution_stats


@pytest.fixture
def spending_transactions_df():
    """Transactions with mixed types and multiple categories."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-05', '2024-01-10', '2024-01-15',
            '2024-01-20', '2024-01-25', '2024-02-01',
        ], utc=True),
        'Amount': [3000, -200, -150, -500, -50, -100],
        'Type': ['Income', 'Expense', 'Expense', 'Expense', 'Expense', 'Expense'],
        'Category': ['Salary', 'Groceries', 'Dining', 'Rent', 'Coffee', 'Groceries'],
        'Group': ['Income', 'Food', 'Food', 'Housing', 'Food', 'Food'],
        'Account': ['Checking'] * 6,
        'Month': ['2024-01', '2024-01', '2024-01', '2024-01', '2024-01', '2024-02'],
        'Full Description': ['PAY', 'KROGER', 'RESTAURANT', 'LANDLORD', 'STARBUCKS', 'KROGER'],
        'Institution': ['Bank'] * 6,
        'Account #': ['1234'] * 6,
    })


@pytest.fixture
def basic_spending_filters():
    """Minimal filters that pass everything through."""
    return {
        'include_groups': [],
        'include_categories': [],
        'exclude_groups': [],
        'exclude_categories': [],
        'filter_large_expenses': False,
        'expense_threshold': 50000,
    }


@pytest.fixture
def expenses_only_df():
    """DataFrame with only expense transactions for distribution stats."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-05', '2024-01-10', '2024-01-15',
            '2024-01-20', '2024-01-25',
        ], utc=True),
        'Amount': [-10, -50, -100, -300, -500],
        'Type': ['Expense'] * 5,
        'Category': ['Coffee', 'Groceries', 'Dining', 'Utilities', 'Rent'],
        'Group': ['Food', 'Food', 'Food', 'Housing', 'Housing'],
        'Account': ['Checking'] * 5,
        'Month': ['2024-01'] * 5,
        'Full Description': ['CAFE', 'STORE', 'REST', 'ELECTRIC', 'LANDLORD'],
        'Institution': ['Bank'] * 5,
        'Account #': ['1234'] * 5,
    })


class TestProcessSpendingData:

    def test_filters_to_expenses_only(self, spending_transactions_df, basic_spending_filters, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        df_period, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        # df_period should contain only expenses
        assert (df_period['Type'] == 'Expense').all()

    def test_category_grouping_with_abs_amounts(self, spending_transactions_df, basic_spending_filters, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        _, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        # All amounts should be positive (absolute values)
        assert (df_by_category['Amount'] >= 0).all()

        # Groceries should have 200 + 100 = 300
        groceries_row = df_by_category[df_by_category['Category'] == 'Groceries']
        assert groceries_row['Amount'].values[0] == pytest.approx(300)

    def test_percentages_sum_to_100(self, spending_transactions_df, basic_spending_filters, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        _, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        total_pct = df_by_category['Percentage'].sum()
        assert total_pct == pytest.approx(100.0, abs=0.5)


class TestCalculateDistributionStats:

    def test_percentiles_correct(self, expenses_only_df):
        stats = calculate_distribution_stats(expenses_only_df)
        amounts = expenses_only_df['Amount'].abs()

        assert stats['median'] == pytest.approx(amounts.quantile(0.50))
        assert stats['p25'] == pytest.approx(amounts.quantile(0.25))
        assert stats['p75'] == pytest.approx(amounts.quantile(0.75))
        assert stats['mean'] == pytest.approx(amounts.mean())

    def test_size_bucket_counts(self, expenses_only_df):
        stats = calculate_distribution_stats(expenses_only_df)

        # Amounts are 10, 50, 100, 300, 500
        # small (<25): 10 -> 1
        # medium (25-250): 50, 100 -> 2
        # large (>=250): 300, 500 -> 2
        assert stats['small_count'] == 1
        assert stats['medium_count'] == 2
        assert stats['large_count'] == 2

    def test_pareto_off_by_one(self, expenses_only_df):
        """The count should include the transaction that pushes cumulative sum past 80%."""
        stats = calculate_distribution_stats(expenses_only_df)

        # Amounts sorted desc: 500, 300, 100, 50, 10 -> total = 960
        # 80% threshold = 768
        # cumsum: 500, 800, 900, 950, 960
        # Transaction at cumsum=800 pushes past 768, so 2 transactions account for 80%
        # Expected pareto_pct = 2/5 * 100 = 40%
        # Bug: line 295 uses cumsum <= threshold, so it counts only those STRICTLY
        # at or below 768, which is just the first (500). That gives 1/5 = 20%.
        assert stats['pareto_pct'] == pytest.approx(40.0)
