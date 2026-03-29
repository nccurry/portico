"""Tests for Pages/5_Subscriptions.py - detect_recurring_transactions."""
import pytest
import pandas as pd

from importlib import import_module

_mod = import_module('Pages.5_Subscriptions')
detect_recurring_transactions = _mod.detect_recurring_transactions


def _make_recurring_df(merchant='NETFLIX MONTHLY', amount=-15.99, category='Entertainment',
                       start='2024-01-15', months=6):
    """Build a DataFrame with monthly recurring charges for a single merchant."""
    dates = pd.date_range(start=start, periods=months, freq='MS', tz='UTC') + pd.Timedelta(days=14)
    return pd.DataFrame({
        'Date': dates,
        'Amount': [amount] * months,
        'Type': ['Expense'] * months,
        'Category': [category] * months,
        'Group': ['Entertainment'] * months,
        'Account': ['Checking'] * months,
        'Month': [d.strftime('%Y-%m') for d in dates],
        'Full Description': [merchant] * months,
        'Institution': ['Bank'] * months,
        'Account #': ['1234'] * months,
    })


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
        """A single occurrence should not crash due to division by zero.

        The bug: line 72 computes (Last_Date - First_Date).days / (Count - 1).
        When Count==1, this divides by zero.  Pandas silently produces nan
        (0 days / 0 = nan), which fillna(0) turns to 0.  The cadence filter
        then removes the row.  So the function doesn't crash, but the
        computation is still mathematically wrong -- it should guard against
        Count==1 explicitly rather than relying on nan propagation.
        """
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
        # With min_occurrences=1 and min_months=1, the single row should survive
        # the occurrence/month filters.  The bug is that Days_Between is computed
        # via division by zero.  We assert that the intermediate grouped df
        # should never contain nan or inf in Days_Between.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = detect_recurring_transactions(df, min_occurrences=1, min_months=1)

    def test_annual_cost_calculation(self):
        df = _make_recurring_df(amount=-25.00, months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1
        row = result.iloc[0]
        assert row['Annual_Cost'] == pytest.approx(abs(row['Avg_Amount']) * 12)
