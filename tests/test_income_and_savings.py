"""Tests for Pages/1_Income_and_Savings.py - process_income_expense_data."""
import pytest
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Pages'))

from importlib import import_module

# Import the module from Pages directory
_mod = import_module('Pages.1_Income_and_Savings')
process_income_expense_data = _mod.process_income_expense_data


@pytest.fixture
def sample_transactions_df():
    """Transactions with both Income and Expense types across several months."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-15', '2024-01-20', '2024-02-10', '2024-02-15',
            '2024-03-05', '2024-03-12',
        ], utc=True),
        'Amount': [3000, -1000, 4000, -2000, 5000, -1500],
        'Type': ['Income', 'Expense', 'Income', 'Expense', 'Income', 'Expense'],
        'Category': ['Salary', 'Groceries', 'Salary', 'Groceries', 'Salary', 'Groceries'],
        'Group': ['Income', 'Food', 'Income', 'Food', 'Income', 'Food'],
        'Account': ['Checking'] * 6,
        'Month': ['2024-01', '2024-01', '2024-02', '2024-02', '2024-03', '2024-03'],
        'Full Description': ['EMPLOYER PAYROLL'] * 6,
        'Institution': ['Bank'] * 6,
        'Account #': ['1234'] * 6,
    })


@pytest.fixture
def basic_filters():
    """Minimal filters that pass everything through."""
    return {
        'exclude_groups': [],
        'exclude_categories': [],
        'filter_large_income': False,
        'income_threshold': 50000,
        'filter_large_expenses': False,
        'expense_threshold': 50000,
        'target_rate': 20,
    }


class TestProcessIncomeExpenseData:

    def test_separates_income_expense(self, sample_transactions_df, basic_filters, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = process_income_expense_data(ts, basic_filters)

        # Should have Income and Expense columns
        assert 'Income' in result.columns
        assert 'Expense' in result.columns
        # Income values should be positive, Expense values negative
        assert (result['Income'] >= 0).all()
        assert (result['Expense'] <= 0).all()

    def test_savings_equals_income_plus_expense(self, sample_transactions_df, basic_filters, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = process_income_expense_data(ts, basic_filters)

        for _, row in result.iterrows():
            assert row['Savings'] == pytest.approx(row['Income'] + row['Expense'])

    def test_savings_rate_calculation(self, sample_transactions_df, basic_filters, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = process_income_expense_data(ts, basic_filters)

        for _, row in result.iterrows():
            if row['Income_Display'] > 0.01:
                expected_rate = row['Savings'] / row['Income_Display'] * 100
                assert row['Savings_Rate'] == pytest.approx(expected_rate)

    def test_savings_rate_zero_income(self, basic_filters, make_transactions_spreadsheet):
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

    def test_output_sorted_by_month(self, sample_transactions_df, basic_filters, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = process_income_expense_data(ts, basic_filters)

        months = result['Month'].tolist()
        assert months == sorted(months)
