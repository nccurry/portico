"""Tests for Pages/4_Duplicate_Detection.py - find_duplicates_efficient."""
import pytest
import pandas as pd

from importlib import import_module

_mod = import_module('Pages.4_Duplicate_Detection')
find_duplicates_efficient = _mod.find_duplicates_efficient

# The bug on line 48 (duplicates.index_1 doesn't exist after reset_index(drop=True))
# crashes any call where the merge produces at least one row, which is any call
# with at least one amount whose absolute value >= min_amount.

def _make_df(rows):
    """Build a transaction DataFrame from a list of dicts with sensible defaults."""
    defaults = {
        'Type': 'Expense',
        'Category': 'Groceries',
        'Group': 'Food',
        'Account': 'Checking',
        'Month': '2024-01',
        'Full Description': 'STORE PURCHASE',
        'Institution': 'Bank',
        'Account #': '1234',
    }
    for row in rows:
        for k, v in defaults.items():
            row.setdefault(k, v)
        row['Date'] = pd.Timestamp(row['Date'], tz='UTC')
    return pd.DataFrame(rows)


class TestFindDuplicatesEfficient:

    def test_finds_exact_duplicates_same_day(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False)
        assert len(result) == 1
        assert result.iloc[0]['Amount'] == -50.00

    def test_finds_near_duplicates_within_threshold(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -75.00},
            {'Date': '2024-01-17', 'Amount': -75.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False)
        assert len(result) == 1
        assert result.iloc[0]['Days_Apart'] <= 3

    def test_no_duplicates_different_amounts(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -75.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False)
        assert len(result) == 0

    def test_min_amount_filter(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -5.00},
            {'Date': '2024-01-15', 'Amount': -5.00},
        ])
        # min_amount=10 should exclude these $5 transactions (filtered before the bug)
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False)
        assert len(result) == 0

    def test_same_account_filter(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Checking'},
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Savings'},
        ])
        # With check_same_account=True, different accounts should not match
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=False)
        assert len(result) == 0

    def test_same_category_filter(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Category': 'Groceries'},
            {'Date': '2024-01-15', 'Amount': -100.00, 'Category': 'Dining'},
        ])
        # With check_same_category=True, different categories should not match
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=True)
        assert len(result) == 0

    def test_index_columns_after_merge(self):
        """After merge, the code references duplicates.index_1 which doesn't exist."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        # This should work without AttributeError
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False)
        # Verify the function produced valid output
        assert 'Date1' in result.columns
        assert 'Date2' in result.columns

    def test_empty_input(self):
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
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False)
        assert result.empty
