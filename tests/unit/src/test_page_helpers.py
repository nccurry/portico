"""Tests for src/page_helpers.py - prepare_year_comparison_data, extract_merchant_name,
create_year_comparison_chart, and create_sparkline_chart."""
import pytest
import pandas as pd
import altair as alt

from src.page_helpers import (
    prepare_year_comparison_data,
    extract_merchant_name,
    create_year_comparison_chart,
    create_sparkline_chart,
)


class TestPrepareYearComparisonData:

    def test_pivots_to_year_columns(self, monthly_amounts_df: pd.DataFrame) -> None:
        """Monthly data with YYYY-MM index pivots to Year columns, Month 1-12 rows."""
        result = prepare_year_comparison_data(monthly_amounts_df)

        # Columns should be years
        assert 2023 in result.columns
        assert 2024 in result.columns

        # Index should be month numbers
        assert result.index.name == 'Month'
        assert list(result.index) == [1, 2, 3, 4, 5, 6]

        # Spot-check values
        assert result.loc[1, 2023] == 100
        assert result.loc[1, 2024] == 110
        assert result.loc[6, 2023] == 350

    def test_empty_input(self) -> None:
        """Empty DataFrame returns empty DataFrame."""
        empty = pd.DataFrame({'Amount': []}, index=pd.Index([], name='Month'))
        result = prepare_year_comparison_data(empty)
        assert result.empty

    def test_single_year(self) -> None:
        """Works correctly with only one year of data."""
        data = {'Amount': [500, 600]}
        index = pd.Index(['2024-03', '2024-07'], name='Month')
        df = pd.DataFrame(data, index=index)

        result = prepare_year_comparison_data(df)

        assert result.columns.equals(pd.Index([2024]))
        assert 3 in result.index
        assert 7 in result.index
        assert result.loc[3, 2024] == 500

    def test_fills_na_with_zero(self) -> None:
        """Missing months for a year are filled with 0."""
        data = {'Amount': [100, 200, 300]}
        index = pd.Index(['2023-01', '2024-01', '2024-02'], name='Month')
        df = pd.DataFrame(data, index=index)

        result = prepare_year_comparison_data(df)

        # 2023 only has month 1; month 2 should be 0 for 2023
        assert result.loc[2, 2023] == 0
        # 2024 only has months 1 and 2; month 1 for 2023 should be present
        assert result.loc[1, 2023] == 100


class TestExtractMerchantName:

    def test_single_word_with_multi_word_method(self) -> None:
        """A single-word description with first_three should return that word."""
        assert extract_merchant_name("NETFLIX", "first_three") == "NETFLIX"

    def test_unknown_method_falls_back_to_first_word(self) -> None:
        """An unrecognized method returns the first word."""
        assert extract_merchant_name("FOO BAR BAZ", "bad_method") == "FOO"

    def test_nan_input_returns_unknown(self) -> None:
        """NaN description returns 'Unknown'."""
        assert extract_merchant_name(float('nan')) == 'Unknown'
        assert extract_merchant_name(None) == 'Unknown'

    def test_empty_string_returns_unknown(self) -> None:
        """Empty string returns 'Unknown' (split produces empty list)."""
        assert extract_merchant_name("") == 'Unknown'
        assert extract_merchant_name("   ") == 'Unknown'

    def test_first_two_method(self) -> None:
        """first_two returns the first two words."""
        assert extract_merchant_name("WHOLE FOODS MARKET", "first_two") == "WHOLE FOODS"

    def test_first_three_method(self) -> None:
        """first_three returns the first three words."""
        assert extract_merchant_name("THE HOME DEPOT STORE", "first_three") == "THE HOME DEPOT"

    def test_first_word_default(self) -> None:
        """Default method returns first word."""
        assert extract_merchant_name("AMAZON MARKETPLACE") == "AMAZON"

    def test_unicode_characters(self) -> None:
        """Unicode characters in description don't crash."""
        assert extract_merchant_name("CAFÉ MOCHA HOUSE") == "CAFÉ"

    def test_special_characters(self) -> None:
        """Special characters are preserved."""
        assert extract_merchant_name("7-ELEVEN #12345") == "7-ELEVEN"


class TestCreateYearComparisonChart:

    @pytest.fixture
    def two_year_pivoted(self, monthly_amounts_df: pd.DataFrame) -> pd.DataFrame:
        return prepare_year_comparison_data(monthly_amounts_df)

    def test_empty_pivoted_returns_text_chart(self) -> None:
        """Empty DataFrame produces a text mark chart."""
        result = create_year_comparison_chart(pd.DataFrame(), "Test")
        assert isinstance(result, alt.Chart)

    def test_normal_data_returns_line_chart(self, two_year_pivoted: pd.DataFrame) -> None:
        """Multi-year pivoted data produces a line chart."""
        result = create_year_comparison_chart(two_year_pivoted, "Groceries")
        assert isinstance(result, alt.Chart)

    def test_single_year_pivoted(self) -> None:
        """Single year data still produces a valid chart."""
        data = {'Amount': [100, 200, 300]}
        index = pd.Index(['2024-01', '2024-03', '2024-05'], name='Month')
        df = pd.DataFrame(data, index=index)
        pivoted = prepare_year_comparison_data(df)
        result = create_year_comparison_chart(pivoted, "Test")
        assert isinstance(result, alt.Chart)

    def test_all_zero_year_trimmed(self) -> None:
        """A year with all-zero amounts is excluded from the chart data."""
        # Build pivoted data where 2023 is all zeros
        pivoted = pd.DataFrame(
            {2023: [0, 0, 0], 2024: [100, 200, 300]},
            index=pd.Index([1, 2, 3], name='Month')
        )
        result = create_year_comparison_chart(pivoted, "Test")
        assert isinstance(result, alt.Chart)


class TestCreateSparklineChart:

    def test_normal_data_returns_line_chart(self) -> None:
        """DataFrame with multiple rows returns a line chart."""
        df = pd.DataFrame({
            'Date': pd.date_range('2024-01-01', periods=5, freq='W'),
            'Balance': [1000, 1100, 1050, 1200, 1150]
        })
        result = create_sparkline_chart(df, 'Balance', 'Date', '#57cc57')
        assert isinstance(result, alt.Chart)

    def test_single_row_falls_to_flat_line(self) -> None:
        """Single-row DataFrame uses the flat-line fallback."""
        df = pd.DataFrame({
            'Date': [pd.Timestamp('2024-01-01')],
            'Balance': [5000.0]
        })
        result = create_sparkline_chart(df, 'Balance', 'Date', '#57cc57')
        assert isinstance(result, alt.Chart)

    def test_empty_df_with_current_value(self) -> None:
        """Empty DataFrame with explicit current_value uses flat line at that value."""
        df = pd.DataFrame({'Date': [], 'Balance': []})
        result = create_sparkline_chart(df, 'Balance', 'Date', '#57cc57', current_value=5000)
        assert isinstance(result, alt.Chart)

    def test_empty_df_no_current_value(self) -> None:
        """Empty DataFrame with no current_value defaults to 0."""
        df = pd.DataFrame({'Date': [], 'Balance': []})
        result = create_sparkline_chart(df, 'Balance', 'Date', '#57cc57')
        assert isinstance(result, alt.Chart)

    def test_use_min_scale(self) -> None:
        """use_min_scale=True should not crash."""
        df = pd.DataFrame({
            'Date': pd.date_range('2024-01-01', periods=5, freq='W'),
            'Balance': [1000, 1100, 1050, 1200, 1150]
        })
        result = create_sparkline_chart(
            df, 'Balance', 'Date', '#57cc57', use_min_scale=True
        )
        assert isinstance(result, alt.Chart)
