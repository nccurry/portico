"""Tests for Pages/5_Subscriptions.py - detect_recurring_transactions."""
import pytest
import pandas as pd

from importlib import import_module

from tests._helpers import _make_recurring_df

_mod = import_module('Pages.5_Subscriptions')
detect_recurring_transactions = _mod.detect_recurring_transactions


class TestDetectRecurringTransactions:

    def test_detects_monthly_subscription(self):
        df = _make_recurring_df(months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1
        assert 'NETFLIX' in result.iloc[0]['Merchant']

    def test_excludes_mortgage_categories(self):
        df = _make_recurring_df(category='Mortgage Payment', months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) == 0

    def test_cadence_filtering_20_40_days(self):
        """Charges spaced 60 days apart should not pass the 20-40 day cadence filter."""
        dates = pd.date_range(start='2024-01-15', periods=6, freq='60D', tz='UTC')
        df = pd.DataFrame({
            'Date': dates,
            'Amount': [-20.00] * 6,
            'Type': ['Expense'] * 6,
            'Category': ['Entertainment'] * 6,
            'Group': ['Entertainment'] * 6,
            'Account': ['Checking'] * 6,
            'Month': [d.strftime('%Y-%m') for d in dates],
            'Full Description': ['BIMONTHLY SVC'] * 6,
            'Institution': ['Bank'] * 6,
            'Account #': ['1234'] * 6,
        })
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) == 0

    def test_min_occurrences_filter(self):
        """Fewer than min_occurrences should be excluded."""
        df = _make_recurring_df(months=2)  # only 2 occurrences
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=2)
        assert len(result) == 0

    def test_division_by_zero_count_one(self):
        """A single occurrence should not crash on the days-between calculation."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [-9.99],
            'Type': ['Expense'],
            'Category': ['Entertainment'],
            'Group': ['Entertainment'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['SINGLE CHARGE'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        # With min_occurrences=1, a single row should not produce nan or inf in Days_Between.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            detect_recurring_transactions(df, min_occurrences=1, min_months=1)

    def test_annual_cost_calculation(self):
        df = _make_recurring_df(amount=-25.00, months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1
        row = result.iloc[0]
        assert row['Annual_Cost'] == pytest.approx(abs(row['Avg_Amount']) * 12)

    def test_mode_empty_fallback(self):
        """When all categories are unique, mode() returns all of them but should not crash."""
        dates = pd.date_range(start='2024-01-15', periods=4, freq='MS', tz='UTC') + pd.Timedelta(days=14)
        df = pd.DataFrame({
            'Date': dates,
            'Amount': [-9.99] * 4,
            'Type': ['Expense'] * 4,
            'Category': ['Cat_A', 'Cat_B', 'Cat_C', 'Cat_D'],
            'Group': ['Entertainment'] * 4,
            'Account': ['Checking'] * 4,
            'Month': [d.strftime('%Y-%m') for d in dates],
            'Full Description': ['STREAMING SVC'] * 4,
            'Institution': ['Bank'] * 4,
            'Account #': ['1234'] * 4,
        })
        # Should not raise; mode() with all-unique values returns all values
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1
        # Category should be a string, not crash
        assert isinstance(result.iloc[0]['Category'], str)

    def test_multiple_subscriptions(self):
        """Multiple distinct merchants are all detected."""
        df1 = _make_recurring_df(merchant='NETFLIX MONTHLY', amount=-15.99, months=6)
        df2 = _make_recurring_df(merchant='SPOTIFY PREMIUM', amount=-9.99, months=6)
        df = pd.concat([df1, df2], ignore_index=True)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        merchants = result['Merchant'].tolist()
        assert len(result) >= 2
        assert any('NETFLIX' in m for m in merchants)
        assert any('SPOTIFY' in m for m in merchants)

    def test_excludes_category_via_regex(self):
        """Categories matching the regex pattern are excluded even if not in the explicit list."""
        df = _make_recurring_df(category='Home Mortgage Insurance', months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) == 0
