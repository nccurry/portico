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
