"""Tests for merchant extraction and reusable page charts."""
import pandas as pd
import altair as alt

from src.page_helpers import (
    extract_merchant_name,
    create_sparkline_chart,
)


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
