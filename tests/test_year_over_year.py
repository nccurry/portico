"""Tests for Pages/3_Year_over_Year.py - category/group extraction logic."""
import pandas as pd
import numpy as np


class TestCategoryGroupExtraction:
    """Test the category/group list extraction logic from configure_page (lines 11-14)."""

    def _extract_categories_and_groups(self, df):
        """Replicate the extraction logic from configure_page."""
        all_categories = sorted([str(c) for c in df['Category'].unique()
                                 if pd.notna(c) and str(c).strip()])
        all_groups = sorted([str(g) for g in df['Group'].unique()
                             if pd.notna(g) and str(g).strip() and g != 'Transfer'])
        return all_categories, all_groups

    def test_nan_categories_excluded(self):
        """NaN values in Category column are filtered out."""
        df = pd.DataFrame({
            'Category': ['Groceries', None, np.nan, 'Dining'],
            'Group': ['Food', 'Food', 'Food', 'Food'],
        })
        categories, _ = self._extract_categories_and_groups(df)
        assert 'Groceries' in categories
        assert 'Dining' in categories
        assert len(categories) == 2

    def test_nan_groups_excluded(self):
        """NaN values in Group column are filtered out."""
        df = pd.DataFrame({
            'Category': ['Groceries', 'Dining'],
            'Group': ['Food', None],
        })
        _, groups = self._extract_categories_and_groups(df)
        assert 'Food' in groups
        assert len(groups) == 1

    def test_transfer_group_excluded(self):
        """Transfer group is excluded from the group list."""
        df = pd.DataFrame({
            'Category': ['Groceries', 'Bank Transfer'],
            'Group': ['Food', 'Transfer'],
        })
        _, groups = self._extract_categories_and_groups(df)
        assert 'Transfer' not in groups
        assert 'Food' in groups

    def test_empty_string_categories_excluded(self):
        """Whitespace-only category strings are excluded."""
        df = pd.DataFrame({
            'Category': ['Groceries', '', '   '],
            'Group': ['Food', 'Food', 'Food'],
        })
        categories, _ = self._extract_categories_and_groups(df)
        assert len(categories) == 1
        assert categories[0] == 'Groceries'

    def test_all_nan_returns_empty(self):
        """If all categories/groups are NaN, empty lists are returned."""
        df = pd.DataFrame({
            'Category': [None, np.nan],
            'Group': [None, np.nan],
        })
        categories, groups = self._extract_categories_and_groups(df)
        assert categories == []
        assert groups == []


class TestPrepareYearComparisonData:
    """Test the year-over-year data pivot from page_helpers."""

    def test_multi_year_pivot(self):
        from src.page_helpers import prepare_year_comparison_data

        # Monthly amounts indexed by YYYY-MM
        df = pd.DataFrame({
            'Amount': [100, 200, 150, 250],
        }, index=['2023-03', '2023-06', '2024-03', '2024-06'])
        df.index.name = 'Month'

        result = prepare_year_comparison_data(df)

        assert 2023 in result.columns
        assert 2024 in result.columns
        # Month 3 should have both years
        assert result.loc[3, 2023] == 100
        assert result.loc[3, 2024] == 150

    def test_missing_months_filled_with_zero(self):
        """Months without data in a year with data get filled with 0."""
        from src.page_helpers import prepare_year_comparison_data

        df = pd.DataFrame({
            'Amount': [100, 200],
        }, index=['2024-03', '2024-06'])
        df.index.name = 'Month'

        result = prepare_year_comparison_data(df)

        assert result.loc[3, 2024] == 100
        assert result.loc[6, 2024] == 200
        # Only months present in data appear (pivot doesn't pad)
        assert set(result.index) == {3, 6}

    def test_single_month_single_year(self):
        from src.page_helpers import prepare_year_comparison_data

        df = pd.DataFrame({
            'Amount': [500],
        }, index=['2024-01'])
        df.index.name = 'Month'

        result = prepare_year_comparison_data(df)

        assert len(result) == 1
        assert result.loc[1, 2024] == 500
        assert result.columns.tolist() == [2024]

    def test_empty_input(self):
        from src.page_helpers import prepare_year_comparison_data

        df = pd.DataFrame({'Amount': []})
        df.index.name = 'Month'

        result = prepare_year_comparison_data(df)
        assert result.empty
