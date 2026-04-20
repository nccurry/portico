"""Tests for Pages/6_Merchant_Analysis.py - merchant enrichment and analysis."""
import numpy as np
import pandas as pd
import pytest

from src.page_helpers import extract_merchant_name
from tests._helpers import _make_merchant_df
from tests._pages import merchant_analysis as _mod

enrich_with_merchant = _mod.enrich_with_merchant
analyze_merchants = _mod.analyze_merchants


class TestExtractMerchantName:

    def test_first_word(self) -> None:
        assert extract_merchant_name('KROGER #1234 STORE', 'first_word') == 'KROGER'

    def test_first_two(self) -> None:
        assert extract_merchant_name('KROGER #1234 STORE', 'first_two') == 'KROGER #1234'

    def test_first_three(self) -> None:
        assert extract_merchant_name('KROGER #1234 STORE', 'first_three') == 'KROGER #1234 STORE'

    def test_nan_returns_unknown(self) -> None:
        assert extract_merchant_name(np.nan, 'first_word') == 'Unknown'

    def test_empty_returns_unknown(self) -> None:
        assert extract_merchant_name('', 'first_word') == 'Unknown'

    def test_whitespace_only_returns_unknown(self) -> None:
        assert extract_merchant_name('   ', 'first_word') == 'Unknown'

    def test_unknown_method_falls_back_to_first_word(self) -> None:
        """Invalid method argument falls through to first_word extraction."""
        assert extract_merchant_name('ACME STORE', 'gibberish_method') == 'ACME'

    def test_single_word_first_two_returns_single(self) -> None:
        """first_two on a single-word description returns that single word."""
        assert extract_merchant_name('AMAZON', 'first_two') == 'AMAZON'

    def test_single_word_first_three_returns_single(self) -> None:
        """first_three on a single-word description returns that single word."""
        assert extract_merchant_name('AMAZON', 'first_three') == 'AMAZON'

    def test_none_returns_unknown(self) -> None:
        """None (not just NaN) is handled by the pd.isna check."""
        assert extract_merchant_name(None, 'first_word') == 'Unknown'

    def test_integer_input_coerced_to_string(self) -> None:
        """Non-string, non-NaN input (like an int) is coerced to string and split."""
        # str(12345) = "12345" → single "word" → returns "12345"
        assert extract_merchant_name(12345, 'first_word') == '12345'

    def test_leading_trailing_whitespace_ignored(self) -> None:
        """split() ignores leading/trailing whitespace."""
        assert extract_merchant_name('   AMAZON   ORDER   ', 'first_two') == 'AMAZON ORDER'

    def test_multiple_internal_spaces_collapsed_by_split(self) -> None:
        """str.split() collapses runs of whitespace."""
        assert extract_merchant_name('UBER    *TRIP    NYC', 'first_three') == 'UBER *TRIP NYC'


class TestEnrichWithMerchant:

    def test_adds_merchant_column(self) -> None:
        df = _make_merchant_df()
        enriched = enrich_with_merchant(df, 'first_word')
        assert 'Merchant' in enriched.columns
        assert 'KROGER' in enriched['Merchant'].values

    def test_does_not_mutate_input(self) -> None:
        df = _make_merchant_df()
        _ = enrich_with_merchant(df, 'first_word')
        assert 'Merchant' not in df.columns

    def test_first_two_method(self) -> None:
        df = _make_merchant_df()
        enriched = enrich_with_merchant(df, 'first_two')
        assert 'KROGER #1234' in enriched['Merchant'].values


class TestAnalyzeMerchants:

    def _enrich_and_analyze(
        self, df: pd.DataFrame, method: str = 'first_word', min_transactions: int = 1
    ) -> pd.DataFrame:
        return analyze_merchants(enrich_with_merchant(df, method), min_transactions=min_transactions)  # type: ignore[no-any-return]

    def test_groups_by_merchant(self) -> None:
        result = self._enrich_and_analyze(_make_merchant_df())

        merchants = result['Merchant'].tolist()
        assert 'KROGER' in merchants
        assert 'CHIPOTLE' in merchants

    def test_expenses_only(self) -> None:
        result = self._enrich_and_analyze(_make_merchant_df())

        merchants = result['Merchant'].tolist()
        assert 'EMPLOYER' not in merchants

    def test_min_transactions_filter(self) -> None:
        result = self._enrich_and_analyze(_make_merchant_df(), min_transactions=2)

        merchants = result['Merchant'].tolist()
        assert 'STARBUCKS' not in merchants
        assert 'KROGER' in merchants
        assert 'CHIPOTLE' in merchants

    def test_amounts_are_positive(self) -> None:
        result = self._enrich_and_analyze(_make_merchant_df())

        assert (result['Total_Spent'] > 0).all()
        assert (result['Avg_Transaction'] > 0).all()

    def test_empty_input(self) -> None:
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
        result = self._enrich_and_analyze(df)
        assert result.empty

    def test_all_income_returns_empty(self) -> None:
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
        result = self._enrich_and_analyze(df)
        assert result.empty

    def test_days_active_calculated(self) -> None:
        """Days_Active column reflects the span between first and last transaction."""
        result = self._enrich_and_analyze(_make_merchant_df())
        kroger = result[result['Merchant'] == 'KROGER'].iloc[0]
        # KROGER transactions: Jan 10, Jan 15, Feb 1 -> 22 days
        assert kroger['Days_Active'] == 22

    def test_mode_empty_fallback(self) -> None:
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
        result = self._enrich_and_analyze(df)
        store_row = result[result['Merchant'] == 'STORE'].iloc[0]
        assert isinstance(store_row['Primary_Category'], str)

    def test_total_spent_matches_hand_computed_sum(self) -> None:
        """Aggregation math: Total_Spent == sum of abs(Amount) for that merchant."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-05', '2024-01-10', '2024-02-05'], utc=True),
            'Amount': [-100.50, -200.25, -50.75],
            'Type': ['Expense'] * 3,
            'Category': ['Food'] * 3,
            'Group': ['Food'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01', '2024-01', '2024-02'],
            'Full Description': ['KROGER #1234', 'KROGER #5678', 'KROGER #1234'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        result = self._enrich_and_analyze(df, 'first_word')
        kroger = result[result['Merchant'] == 'KROGER'].iloc[0]
        # 100.50 + 200.25 + 50.75 = 351.50
        assert kroger['Total_Spent'] == pytest.approx(351.50)
        assert kroger['Num_Transactions'] == 3
        # 351.50 / 3 ≈ 117.1667
        assert kroger['Avg_Transaction'] == pytest.approx(117.16666, abs=1e-4)

    def test_sorted_descending_by_total_spent(self) -> None:
        """Top merchant by dollar amount is first in the result."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01'] * 3, utc=True),
            'Amount': [-10, -100, -50],
            'Type': ['Expense'] * 3,
            'Category': ['X'] * 3,
            'Group': ['Y'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01'] * 3,
            'Full Description': ['CHEAP STORE', 'EXPENSIVE STORE', 'MID STORE'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        result = self._enrich_and_analyze(df, 'first_two')
        totals = result['Total_Spent'].tolist()
        assert totals == sorted(totals, reverse=True)
        assert result.iloc[0]['Merchant'] == 'EXPENSIVE STORE'

    def test_single_transaction_days_active_zero(self) -> None:
        """A merchant with a single transaction has Days_Active = 0."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-03-15'], utc=True),
            'Amount': [-50.0],
            'Type': ['Expense'],
            'Category': ['Food'],
            'Group': ['Food'],
            'Account': ['Checking'],
            'Month': ['2024-03'],
            'Full Description': ['ONE SHOT'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        result = self._enrich_and_analyze(df, 'first_word')
        assert result.iloc[0]['Days_Active'] == 0
