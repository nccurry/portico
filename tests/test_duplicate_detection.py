"""Tests for Pages/4_Duplicate_Detection.py - find_duplicates_efficient."""
import pandas as pd

from importlib import import_module

from tests._helpers import _make_df

_mod = import_module('Pages.4_Duplicate_Detection')
find_duplicates_efficient = _mod.find_duplicates_efficient


class TestFindDuplicatesEfficient:

    def test_finds_exact_duplicates_same_day(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 1
        assert result.iloc[0]['Amount'] == -50.00

    def test_finds_near_duplicates_within_threshold(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -75.00},
            {'Date': '2024-01-17', 'Amount': -75.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 1
        assert result.iloc[0]['Days_Apart'] <= 3

    def test_no_duplicates_different_amounts(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -75.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 0

    def test_min_amount_filter(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -5.00},
            {'Date': '2024-01-15', 'Amount': -5.00},
        ])
        # min_amount=10 should exclude these $5 transactions
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 0

    def test_same_account_filter(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Checking'},
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Savings'},
        ])
        # With check_same_account=True, different accounts should not match
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=False, require_same_description=True)
        assert len(result) == 0

    def test_same_category_filter(self):
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Category': 'Groceries'},
            {'Date': '2024-01-15', 'Amount': -100.00, 'Category': 'Dining'},
        ])
        # With check_same_category=True, different categories should not match
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=True, require_same_description=True)
        assert len(result) == 0

    def test_index_columns_after_merge(self):
        """Result contains expected output columns."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        # This should work without AttributeError
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        # Verify the function produced valid output
        assert 'Date1' in result.columns
        assert 'Date2' in result.columns

    def test_beyond_days_threshold(self):
        """Identical amounts beyond the days threshold are not flagged."""
        df = _make_df([
            {'Date': '2024-01-01', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 0

    def test_three_way_duplicates(self):
        """Three matching transactions produce multiple pairs."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-16', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        # 3 transactions produce 3 pairs: (0,1), (0,2), (1,2)
        assert len(result) == 3

    def test_same_account_and_category_combined(self):
        """Both account and category checks applied simultaneously."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Checking', 'Category': 'Groceries'},
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Checking', 'Category': 'Dining'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=True, require_same_description=True)
        # Same account but different category — should not match
        assert len(result) == 0

    def test_different_descriptions_not_flagged(self):
        """Same amount, same day, same account, but different descriptions are not duplicates."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -20.95, 'Full Description': 'WB Studio Enterprises Inc'},
            {'Date': '2024-01-15', 'Amount': -20.95, 'Full Description': 'UBER   *TRIP'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=True,
                                           require_same_description=True)
        assert len(result) == 0

    def test_different_descriptions_flagged_when_disabled(self):
        """When description matching is off, same amount + same day matches regardless."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -20.95, 'Full Description': 'WB Studio Enterprises Inc'},
            {'Date': '2024-01-15', 'Amount': -20.95, 'Full Description': 'UBER   *TRIP'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=False)
        assert len(result) == 1

    def test_description_matching_case_insensitive(self):
        """Description comparison should be case-insensitive."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00, 'Full Description': 'STORE PURCHASE'},
            {'Date': '2024-01-15', 'Amount': -50.00, 'Full Description': 'store purchase'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 1

    def test_investment_transfers_same_amount_different_descriptions(self):
        """Recurring investment transactions with same amount but different descriptions."""
        df = _make_df([
            {'Date': '2024-01-17', 'Amount': -500, 'Account': 'Individual - TOD',
             'Category': 'Stock Purchase', 'Group': 'Investment',
             'Full Description': 'CALVERT U.S. LRG CAP - YOU BOUGHT PERIODIC INVESTMENT'},
            {'Date': '2024-01-17', 'Amount': -500, 'Account': 'Individual - TOD',
             'Category': 'Transfer', 'Group': 'Transfer',
             'Full Description': 'FIDELITY GOVERNMENT MONEY MARKET - PURCHASE INTO CORE ACCOUNT'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 0

    def test_real_duplicate_same_description(self):
        """Actual duplicate: same amount, account, description within days threshold."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.39, 'Account': 'Hilton Card',
             'Category': 'Restaurants', 'Full Description': 'TST* TWO HANDS - FRANKLIN TN'},
            {'Date': '2024-01-15', 'Amount': -100.39, 'Account': 'Hilton Card',
             'Category': 'Restaurants', 'Full Description': 'TST* TWO HANDS - FRANKLIN TN'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=True,
                                           require_same_description=True)
        assert len(result) == 1

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
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert result.empty
