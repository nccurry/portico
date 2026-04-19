"""Tests for Pages/6_Merchant_Analysis.py - extract_merchant_name and analyze_merchants."""
import pandas as pd
import numpy as np

from src.page_helpers import extract_merchant_name
from tests._helpers import _make_merchant_df
from tests._pages import merchant_analysis as _mod

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

    def test_empty_input(self):
        """Empty DataFrame returns empty DataFrame."""
        df = pd.DataFrame({
            'Date': pd.Series([], dtype='datetime64[ns, UTC]'),
            'Amount': pd.Series([], dtype=float),
            'Type': pd.Series([], dtype=str),
            'Category': pd.Series([], dtype=str),
            'Group': pd.Series([], dtype=str),
            'Account': pd.Series([], dtype=str),
            'Month': pd.Series([], dtype=str),
            'Full Description': pd.Series([], dtype=str),
            'Institution': pd.Series([], dtype=str),
            'Account #': pd.Series([], dtype=str),
        })
        result = analyze_merchants(df, extraction_method='first_word', min_transactions=1)
        assert result.empty

    def test_all_income_returns_empty(self):
        """A DataFrame with only income transactions returns empty."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-05'], utc=True),
            'Amount': [3000],
            'Type': ['Income'],
            'Category': ['Salary'],
            'Group': ['Income'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['EMPLOYER PAYROLL'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        result = analyze_merchants(df, extraction_method='first_word', min_transactions=1)
        assert result.empty

    def test_days_active_calculated(self):
        """Days_Active column reflects the span between first and last transaction."""
        df = _make_merchant_df()
        result = analyze_merchants(df, extraction_method='first_word', min_transactions=1)
        kroger = result[result['Merchant'] == 'KROGER'].iloc[0]
        # KROGER transactions: Jan 10, Jan 15, Feb 1 -> 22 days
        assert kroger['Days_Active'] == 22

    def test_mode_empty_fallback(self):
        """When all categories are unique per merchant, mode() should not crash."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-05', '2024-01-10', '2024-01-15'], utc=True),
            'Amount': [-50, -60, -70],
            'Type': ['Expense'] * 3,
            'Category': ['CatA', 'CatB', 'CatC'],
            'Group': ['Food'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01'] * 3,
            'Full Description': ['STORE ABC', 'STORE DEF', 'STORE GHI'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        result = analyze_merchants(df, extraction_method='first_word', min_transactions=1)
        store_row = result[result['Merchant'] == 'STORE'].iloc[0]
        assert isinstance(store_row['Primary_Category'], str)
