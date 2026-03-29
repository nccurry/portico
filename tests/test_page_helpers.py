"""Tests for src/page_helpers.py - prepare_year_comparison_data."""
import pytest
import pandas as pd

from src.page_helpers import prepare_year_comparison_data


@pytest.fixture
def monthly_amounts_df():
    """Monthly amounts with YYYY-MM index and Amount column, spanning two years."""
    data = {
        'Amount': [100, 200, 300, 150, 250, 350,
                   110, 210, 310, 160, 260, 360]
    }
    index = pd.Index([
        '2023-01', '2023-02', '2023-03', '2023-04', '2023-05', '2023-06',
        '2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06',
    ], name='Month')
    return pd.DataFrame(data, index=index)


class TestPrepareYearComparisonData:

    def test_pivots_to_year_columns(self, monthly_amounts_df):
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

    def test_empty_input(self):
        """Empty DataFrame returns empty DataFrame."""
        empty = pd.DataFrame({'Amount': []}, index=pd.Index([], name='Month'))
        result = prepare_year_comparison_data(empty)
        assert result.empty

    def test_single_year(self):
        """Works correctly with only one year of data."""
        data = {'Amount': [500, 600]}
        index = pd.Index(['2024-03', '2024-07'], name='Month')
        df = pd.DataFrame(data, index=index)

        result = prepare_year_comparison_data(df)

        assert list(result.columns) == [2024]
        assert 3 in result.index
        assert 7 in result.index
        assert result.loc[3, 2024] == 500

    def test_fills_na_with_zero(self):
        """Missing months for a year are filled with 0."""
        data = {'Amount': [100, 200, 300]}
        index = pd.Index(['2023-01', '2024-01', '2024-02'], name='Month')
        df = pd.DataFrame(data, index=index)

        result = prepare_year_comparison_data(df)

        # 2023 only has month 1; month 2 should be 0 for 2023
        assert result.loc[2, 2023] == 0
        # 2024 only has months 1 and 2; month 1 for 2023 should be present
        assert result.loc[1, 2023] == 100
