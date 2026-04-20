"""Tests for Pages/6_Merchant_Analysis.py - merchant enrichment and analysis."""
import pandas as pd
import numpy as np

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
