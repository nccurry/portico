"""Tests for duplicate-transaction detection."""
import pandas as pd

from src.analysis.duplicates import find_duplicates_efficient, normalize_description
from tests._helpers import _make_df


class TestNormalizeDescription:
    """Unit tests for normalize_description."""

    def test_basic_lowercase_and_strip(self) -> None:
        assert normalize_description("  KROGER Store  ") == "kroger store"

    def test_already_normalized(self) -> None:
        assert normalize_description("kroger store") == "kroger store"

    def test_none_returns_empty(self) -> None:
        assert normalize_description(None) == ""

    def test_nan_returns_empty(self) -> None:
        import math
        assert normalize_description(math.nan) == ""

    def test_int_returns_empty(self) -> None:
        assert normalize_description(42) == ""

    def test_float_returns_empty(self) -> None:
        assert normalize_description(3.14) == ""

    def test_empty_string(self) -> None:
        assert normalize_description("") == ""

    def test_whitespace_only(self) -> None:
        assert normalize_description("   ") == ""

    def test_mixed_case(self) -> None:
        assert normalize_description("TST* Two Hands - FRANKLIN TN") == "tst* two hands - franklin tn"

    def test_internal_whitespace_preserved(self) -> None:
        assert normalize_description("UBER   *TRIP") == "uber   *trip"


class TestFindDuplicatesEfficient:

    def test_finds_exact_duplicates_same_day(self) -> None:
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 1
        assert result.iloc[0]['Amount'] == -50.00

    def test_finds_near_duplicates_within_threshold(self) -> None:
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -75.00},
            {'Date': '2024-01-17', 'Amount': -75.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 1
        assert result.iloc[0]['Days_Apart'] <= 3

    def test_no_duplicates_different_amounts(self) -> None:
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -75.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 0

    def test_min_amount_filter(self) -> None:
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -5.00},
            {'Date': '2024-01-15', 'Amount': -5.00},
        ])
        # min_amount=10 should exclude these $5 transactions
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 0

    def test_same_account_filter(self) -> None:
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Checking'},
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Savings'},
        ])
        # With check_same_account=True, different accounts should not match
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=False, require_same_description=True)
        assert len(result) == 0

    def test_same_category_filter(self) -> None:
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Category': 'Groceries'},
            {'Date': '2024-01-15', 'Amount': -100.00, 'Category': 'Dining'},
        ])
        # With check_same_category=True, different categories should not match
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=True, require_same_description=True)
        assert len(result) == 0

    def test_index_columns_after_merge(self) -> None:
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

    def test_beyond_days_threshold(self) -> None:
        """Identical amounts beyond the days threshold are not flagged."""
        df = _make_df([
            {'Date': '2024-01-01', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False, require_same_description=True)
        assert len(result) == 0

    def test_three_way_duplicates(self) -> None:
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

    def test_same_account_and_category_combined(self) -> None:
        """Both account and category checks applied simultaneously."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Checking', 'Category': 'Groceries'},
            {'Date': '2024-01-15', 'Amount': -100.00, 'Account': 'Checking', 'Category': 'Dining'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=True, require_same_description=True)
        # Same account but different category — should not match
        assert len(result) == 0

    def test_different_descriptions_not_flagged(self) -> None:
        """Same amount, same day, same account, but different descriptions are not duplicates."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -20.95, 'Full Description': 'WB Studio Enterprises Inc'},
            {'Date': '2024-01-15', 'Amount': -20.95, 'Full Description': 'UBER   *TRIP'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=True, check_same_category=True,
                                           require_same_description=True)
        assert len(result) == 0

    def test_different_descriptions_flagged_when_disabled(self) -> None:
        """When description matching is off, same amount + same day matches regardless."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -20.95, 'Full Description': 'WB Studio Enterprises Inc'},
            {'Date': '2024-01-15', 'Amount': -20.95, 'Full Description': 'UBER   *TRIP'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=False)
        assert len(result) == 1

    def test_description_matching_case_insensitive(self) -> None:
        """Description comparison should be case-insensitive."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00, 'Full Description': 'STORE PURCHASE'},
            {'Date': '2024-01-15', 'Amount': -50.00, 'Full Description': 'store purchase'},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 1

    def test_investment_transfers_same_amount_different_descriptions(self) -> None:
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

    def test_real_duplicate_same_description(self) -> None:
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

    def test_require_same_description_filters_different_descs(self) -> None:
        """Same amount, same day, same account — but different descriptions.
        With require_same_description=True (page default), no duplicates.
        With require_same_description=False, one pair found."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00, 'Account': 'Checking',
             'Full Description': 'KROGER STORE #1234'},
            {'Date': '2024-01-15', 'Amount': -50.00, 'Account': 'Checking',
             'Full Description': 'TARGET STORE #5678'},
        ])
        with_desc = find_duplicates_efficient(
            df, days_threshold=1, min_amount=10,
            check_same_account=True, check_same_category=False,
            require_same_description=True,
        )
        without_desc = find_duplicates_efficient(
            df, days_threshold=1, min_amount=10,
            check_same_account=True, check_same_category=False,
            require_same_description=False,
        )
        assert len(with_desc) == 0
        assert len(without_desc) == 1

    def test_min_amount_boundary_exactly_equal_included(self) -> None:
        """Amount exactly equal to min_amount uses >= so it is included."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -10.00},
            {'Date': '2024-01-15', 'Amount': -10.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=1, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 1

    def test_min_amount_boundary_below_excluded(self) -> None:
        """Amount just below min_amount is excluded (9.99 < 10.00)."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -9.99},
            {'Date': '2024-01-15', 'Amount': -9.99},
        ])
        result = find_duplicates_efficient(df, days_threshold=1, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 0

    def test_days_threshold_zero_only_same_day(self) -> None:
        """days_threshold=0 matches only same-day transactions."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-16', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=0, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 0

    def test_days_threshold_exactly_matches(self) -> None:
        """days_apart == days_threshold is included (<=, not <)."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-18', 'Amount': -50.00},  # 3 days apart
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 1

    def test_positive_and_negative_same_abs_value_not_duplicates(self) -> None:
        """A -100 expense and a +100 refund should NOT match (different signs)."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -100.00, 'Full Description': 'STORE'},
            {'Date': '2024-01-15', 'Amount': 100.00, 'Full Description': 'STORE'},
        ])
        result = find_duplicates_efficient(df, days_threshold=1, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        # Merge is on exact Amount match, and -100 != 100, so no pair
        assert len(result) == 0

    def test_large_value_precision(self) -> None:
        """Large matching amounts still merge correctly (no float drift)."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -12345.67},
            {'Date': '2024-01-15', 'Amount': -12345.67},
        ])
        result = find_duplicates_efficient(df, days_threshold=1, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 1

    def test_n_identical_transactions_produce_n_choose_2_pairs(self) -> None:
        """4 identical transactions produce C(4,2) = 6 unordered pairs."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=1, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 6

    def test_self_pair_not_counted(self) -> None:
        """A single transaction cannot be a duplicate of itself.
        (Row 0 is never paired with row 0 due to _row_id_1 < _row_id_2 filter.)"""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=1, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 0

    def test_description_whitespace_and_case_normalized(self) -> None:
        """normalize_description handles whitespace and case on both sides of pair."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00, 'Full Description': '  STORE PURCHASE  '},
            {'Date': '2024-01-15', 'Amount': -50.00, 'Full Description': 'store purchase'},
        ])
        result = find_duplicates_efficient(df, days_threshold=1, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert len(result) == 1

    def test_days_apart_populated_correctly(self) -> None:
        """Days_Apart column should contain the actual date difference."""
        df = _make_df([
            {'Date': '2024-01-15', 'Amount': -50.00},
            {'Date': '2024-01-17', 'Amount': -50.00},
        ])
        result = find_duplicates_efficient(df, days_threshold=3, min_amount=10,
                                           check_same_account=False, check_same_category=False,
                                           require_same_description=True)
        assert result.iloc[0]['Days_Apart'] == 2

    def test_empty_input(self) -> None:
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
        assert list(result.columns) == [
            "Date1",
            "Date2",
            "Days_Apart",
            "Amount",
            "Category",
            "Account1",
            "Account2",
            "Description1",
            "Description2",
            "Month",
        ]
