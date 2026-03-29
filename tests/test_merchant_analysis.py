"""Tests for Pages/6_Merchant_Analysis.py - extract_merchant_name and analyze_merchants."""
import pytest
import pandas as pd
import numpy as np

from importlib import import_module

_mod = import_module('Pages.6_Merchant_Analysis')
extract_merchant_name = _mod.extract_merchant_name
analyze_merchants = _mod.analyze_merchants


class TestExtractMerchantName:

    def test_first_word(self):
        assert extract_merchant_name('KROGER #1234 STORE', 'first_word') == 'KROGER'

    def test_first_two(self):
        assert extract_merchant_name('KROGER #1234 STORE', 'first_two') == 'KROGER #1234'

    def test_first_three(self):
        assert extract_merchant_name('KROGER #1234 STORE', 'first_three') == 'KROGER #1234 STORE'

    def test_nan_returns_unknown(self):
        assert extract_merchant_name(np.nan, 'first_word') == 'Unknown'

    def test_empty_returns_unknown(self):
        assert extract_merchant_name('', 'first_word') == 'Unknown'


def _make_merchant_df():
    """Build a transaction DataFrame with multiple merchants and types."""
    return pd.DataFrame({
        'Date': pd.to_datetime([
            '2024-01-05', '2024-01-10', '2024-01-15',
            '2024-01-20', '2024-02-01', '2024-02-10',
            '2024-03-01',
        ], utc=True),
        'Amount': [3000, -50, -75, -200, -60, -80, -30],
        'Type': ['Income', 'Expense', 'Expense', 'Expense', 'Expense', 'Expense', 'Expense'],
        'Category': ['Salary', 'Groceries', 'Groceries', 'Dining', 'Groceries', 'Dining', 'Coffee'],
        'Group': ['Income', 'Food', 'Food', 'Food', 'Food', 'Food', 'Food'],
        'Account': ['Checking'] * 7,
        'Month': ['2024-01', '2024-01', '2024-01', '2024-01', '2024-02', '2024-02', '2024-03'],
        'Full Description': [
            'EMPLOYER PAYROLL',
            'KROGER #1234 STORE',
            'KROGER #5678 STORE',
            'CHIPOTLE RESTAURANT',
            'KROGER #1234 STORE',
            'CHIPOTLE RESTAURANT',
            'STARBUCKS COFFEE',
        ],
        'Institution': ['Bank'] * 7,
        'Account #': ['1234'] * 7,
    })


class TestAnalyzeMerchants:

    def test_groups_by_merchant(self):
        df = _make_merchant_df()
        result = analyze_merchants(df, extraction_method='first_word', min_transactions=1)

        merchants = result['Merchant'].tolist()
        assert 'KROGER' in merchants
        assert 'CHIPOTLE' in merchants

    def test_expenses_only(self):
        df = _make_merchant_df()
        result = analyze_merchants(df, extraction_method='first_word', min_transactions=1)

        # Income merchant (EMPLOYER) should not appear since analyze_merchants filters to expenses
        merchants = result['Merchant'].tolist()
        assert 'EMPLOYER' not in merchants

    def test_min_transactions_filter(self):
        df = _make_merchant_df()
        # STARBUCKS only has 1 transaction; min_transactions=2 should exclude it
        result = analyze_merchants(df, extraction_method='first_word', min_transactions=2)

        merchants = result['Merchant'].tolist()
        assert 'STARBUCKS' not in merchants
        # KROGER has 3, CHIPOTLE has 2 - both should be present
        assert 'KROGER' in merchants
        assert 'CHIPOTLE' in merchants

    def test_amounts_are_positive(self):
        df = _make_merchant_df()
        result = analyze_merchants(df, extraction_method='first_word', min_transactions=1)

        assert (result['Total_Spent'] > 0).all()
        assert (result['Avg_Transaction'] > 0).all()
