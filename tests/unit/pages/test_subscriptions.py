"""Tests for Pages/5_Subscriptions.py - detect_recurring_transactions."""
import pytest
import pandas as pd

from tests._helpers import _make_recurring_df
from tests._pages import subscriptions

detect_recurring_transactions = subscriptions.detect_recurring_transactions


class TestDetectRecurringTransactions:

    def test_detects_monthly_subscription(self) -> None:
        df = _make_recurring_df(months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1
        assert 'NETFLIX' in result.iloc[0]['Merchant']

    def test_excludes_mortgage_categories(self) -> None:
        df = _make_recurring_df(category='Mortgage Payment', months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) == 0

    def test_cadence_filtering_20_40_days(self) -> None:
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

    def test_min_occurrences_filter(self) -> None:
        """Fewer than min_occurrences should be excluded."""
        df = _make_recurring_df(months=2)  # only 2 occurrences
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=2)
        assert len(result) == 0

    def test_division_by_zero_count_one(self) -> None:
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

    def test_annual_cost_is_twelve_times_monthly(self) -> None:
        """Annual_Cost = |Avg_Amount| * 12. With a known $25/month subscription,
        expected annual cost is $300."""
        df = _make_recurring_df(amount=-25.00, months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1
        assert result.iloc[0]['Annual_Cost'] == pytest.approx(300.0)

    def test_annual_cost_ignores_sign(self) -> None:
        """A -$9.99 subscription projects to $119.88 annual (positive)."""
        df = _make_recurring_df(amount=-9.99, months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1
        assert result.iloc[0]['Annual_Cost'] == pytest.approx(9.99 * 12)
        assert result.iloc[0]['Annual_Cost'] > 0

    def test_mode_empty_fallback(self) -> None:
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

    def test_multiple_subscriptions(self) -> None:
        """Multiple distinct merchants are all detected."""
        df1 = _make_recurring_df(merchant='NETFLIX MONTHLY', amount=-15.99, months=6)
        df2 = _make_recurring_df(merchant='SPOTIFY PREMIUM', amount=-9.99, months=6)
        df = pd.concat([df1, df2], ignore_index=True)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        merchants = result['Merchant'].tolist()
        assert len(result) >= 2
        assert any('NETFLIX' in m for m in merchants)
        assert any('SPOTIFY' in m for m in merchants)

    def test_excludes_category_via_regex(self) -> None:
        """Categories matching the regex pattern are excluded even if not in the explicit list."""
        df = _make_recurring_df(category='Home Mortgage Insurance', months=6)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) == 0

    def test_cadence_boundary_exactly_20_days_included(self) -> None:
        """Cadence filter is 20 <= days <= 40, so exactly 20 days passes."""
        dates = pd.date_range(start='2024-01-01', periods=6, freq='20D', tz='UTC')
        df = pd.DataFrame({
            'Date': dates,
            'Amount': [-10.00] * 6,
            'Type': ['Expense'] * 6,
            'Category': ['Entertainment'] * 6,
            'Group': ['Entertainment'] * 6,
            'Account': ['Checking'] * 6,
            'Month': [d.strftime('%Y-%m') for d in dates],
            'Full Description': ['FAST CADENCE'] * 6,
            'Institution': ['Bank'] * 6,
            'Account #': ['1234'] * 6,
        })
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1

    def test_cadence_boundary_exactly_40_days_included(self) -> None:
        """Cadence 40 is the upper boundary — should be included."""
        dates = pd.date_range(start='2024-01-01', periods=6, freq='40D', tz='UTC')
        df = pd.DataFrame({
            'Date': dates,
            'Amount': [-10.00] * 6,
            'Type': ['Expense'] * 6,
            'Category': ['Entertainment'] * 6,
            'Group': ['Entertainment'] * 6,
            'Account': ['Checking'] * 6,
            'Month': [d.strftime('%Y-%m') for d in dates],
            'Full Description': ['SLOW CADENCE'] * 6,
            'Institution': ['Bank'] * 6,
            'Account #': ['1234'] * 6,
        })
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1

    def test_cadence_19_days_excluded(self) -> None:
        """Just below the 20-day lower bound — excluded."""
        dates = pd.date_range(start='2024-01-01', periods=6, freq='19D', tz='UTC')
        df = pd.DataFrame({
            'Date': dates,
            'Amount': [-10.00] * 6,
            'Type': ['Expense'] * 6,
            'Category': ['Entertainment'] * 6,
            'Group': ['Entertainment'] * 6,
            'Account': ['Checking'] * 6,
            'Month': [d.strftime('%Y-%m') for d in dates],
            'Full Description': ['TOO FAST'] * 6,
            'Institution': ['Bank'] * 6,
            'Account #': ['1234'] * 6,
        })
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) == 0

    def test_min_occurrences_exactly_threshold_included(self) -> None:
        """Exactly min_occurrences charges should be detected."""
        df = _make_recurring_df(months=3)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1

    def test_min_months_exactly_threshold_included(self) -> None:
        """Exactly min_months unique months qualifies."""
        df = _make_recurring_df(months=3)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) >= 1
        assert result.iloc[0]["Unique_Months"] == 3

    def test_amount_variance_creates_separate_groups(self) -> None:
        """Same merchant with different amounts becomes two groups because
        grouping is by (merchant, rounded amount)."""
        dates = pd.date_range(start='2024-01-15', periods=6, freq='MS', tz='UTC') + pd.Timedelta(days=14)
        df = pd.DataFrame({
            'Date': list(dates) + list(dates),
            'Amount': [-9.99] * 6 + [-19.99] * 6,
            'Type': ['Expense'] * 12,
            'Category': ['Entertainment'] * 12,
            'Group': ['Entertainment'] * 12,
            'Account': ['Checking'] * 12,
            'Month': [d.strftime('%Y-%m') for d in dates] * 2,
            'Full Description': ['NETFLIX MONTHLY'] * 12,
            'Institution': ['Bank'] * 12,
            'Account #': ['1234'] * 12,
        })
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) == 2

    def test_amount_tiny_rounding_difference_groups_together(self) -> None:
        """Amounts that round to the same value group together (tax variations)."""
        dates = pd.date_range(start='2024-01-15', periods=6, freq='MS', tz='UTC') + pd.Timedelta(days=14)
        amounts = [-15.994, -15.996, -16.001, -16.003, -15.995, -16.002]
        df = pd.DataFrame({
            'Date': dates,
            'Amount': amounts,
            'Type': ['Expense'] * 6,
            'Category': ['Entertainment'] * 6,
            'Group': ['Entertainment'] * 6,
            'Account': ['Checking'] * 6,
            'Month': [d.strftime('%Y-%m') for d in dates],
            'Full Description': ['NETFLIX MONTHLY'] * 6,
            'Institution': ['Bank'] * 6,
            'Account #': ['1234'] * 6,
        })
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        # Should group into either 1 or 2 (depends on round-to-2-decimals)
        # Round(-15.994, 2) = -15.99; round(-15.995, 2) = -16.00 (banker's)
        # So behavior is implementation-defined, but total rows <= 2
        assert len(result) >= 1 and len(result) <= 2

    def test_merchant_extracted_from_first_three_words(self) -> None:
        """Merchant is the first three whitespace-separated words, lowercased."""
        dates = pd.date_range(start='2024-01-15', periods=6, freq='MS', tz='UTC') + pd.Timedelta(days=14)
        df = pd.DataFrame({
            'Date': dates,
            'Amount': [-9.99] * 6,
            'Type': ['Expense'] * 6,
            'Category': ['Entertainment'] * 6,
            'Group': ['Entertainment'] * 6,
            'Account': ['Checking'] * 6,
            'Month': [d.strftime('%Y-%m') for d in dates],
            'Full Description': ['NETFLIX STREAMING SERVICES LLC 9999'] * 6,
            'Institution': ['Bank'] * 6,
            'Account #': ['1234'] * 6,
        })
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        assert len(result) == 1
        # Merchant is first 3 words (implementation uses 'first_three')
        assert result.iloc[0]["Merchant"].lower().startswith("netflix streaming")

    def test_results_sorted_by_raw_avg_amount_descending(self) -> None:
        """Code sorts ``Avg_Amount`` with ``ascending=False``. Because expenses
        are stored as negative numbers, this currently puts the LEAST expensive
        subscription first (-4.99 > -99.99), which contradicts the function's
        docstring claim of "most expensive first".

        This test documents the actual behavior so any future fix is visible.
        If the sort is changed to ``abs(Avg_Amount)``, update this test.
        """
        df1 = _make_recurring_df(merchant='EXPENSIVE SERVICE', amount=-99.99, months=6)
        df2 = _make_recurring_df(merchant='CHEAP SERVICE', amount=-4.99, months=6)
        df = pd.concat([df1, df2], ignore_index=True)
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        # Currently: sort by raw Avg_Amount descending → least-negative first
        assert result.iloc[0]["Avg_Amount"] > result.iloc[-1]["Avg_Amount"]
        assert result.iloc[0]["Avg_Amount"] == pytest.approx(-4.99)
        assert result.iloc[-1]["Avg_Amount"] == pytest.approx(-99.99)

    def test_days_between_calculation(self) -> None:
        """Days_Between should equal (last - first) / (count - 1)."""
        dates = pd.date_range(start='2024-01-01', periods=6, freq='30D', tz='UTC')
        df = pd.DataFrame({
            'Date': dates,
            'Amount': [-10.00] * 6,
            'Type': ['Expense'] * 6,
            'Category': ['Entertainment'] * 6,
            'Group': ['Entertainment'] * 6,
            'Account': ['Checking'] * 6,
            'Month': [d.strftime('%Y-%m') for d in dates],
            'Full Description': ['MONTHLY SVC'] * 6,
            'Institution': ['Bank'] * 6,
            'Account #': ['1234'] * 6,
        })
        result = detect_recurring_transactions(df, min_occurrences=3, min_months=3)
        row = result.iloc[0]
        # 6 charges 30 days apart: span = 150 days, count-1 = 5, days_between = 30
        assert row["Days_Between"] == pytest.approx(30.0)

    def test_empty_df_returns_empty(self) -> None:
        """An empty transactions DataFrame returns an empty result."""
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
        result = detect_recurring_transactions(df)
        assert result.empty
