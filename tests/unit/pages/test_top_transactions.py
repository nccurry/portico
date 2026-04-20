"""Tests for Pages/10_Top_Transactions.py - top transaction analysis."""
import pytest
import pandas as pd

from tests._pages import top_transactions as _mod

get_top_transactions = _mod.get_top_transactions
get_category_breakdown = _mod.get_category_breakdown
find_recurring_large_expenses = _mod.find_recurring_large_expenses


class TestGetTopTransactions:

    def test_returns_n_largest(self, varied_expenses: pd.DataFrame) -> None:
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        top_df, _stats = get_top_transactions(varied_expenses, 3, start, end)

        assert len(top_df) == 3
        amounts = top_df['Abs_Amount'].tolist()
        # Should be 1000, 750, 500
        assert amounts[0] == pytest.approx(1000)
        assert amounts[1] == pytest.approx(750)
        assert amounts[2] == pytest.approx(500)

    def test_stats_pct_of_total(self, varied_expenses: pd.DataFrame) -> None:
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        _, stats = get_top_transactions(varied_expenses, 3, start, end)

        total = 50 + 500 + 100 + 1000 + 200 + 300 + 750 + 25
        top3_total = 1000 + 750 + 500
        expected_pct = top3_total / total * 100
        assert stats['pct_of_total'] == pytest.approx(expected_pct)

    def test_date_range_filtering(self, varied_expenses: pd.DataFrame) -> None:
        """Only transactions within date range are considered."""
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-01-31', tz='UTC')

        _top_df, stats = get_top_transactions(varied_expenses, 10, start, end)

        # Only January transactions (5)
        assert stats['num_transactions'] == 5

    def test_empty_result(self, varied_expenses: pd.DataFrame) -> None:
        start = pd.Timestamp('2025-01-01', tz='UTC')
        end = pd.Timestamp('2025-12-31', tz='UTC')

        top_df, stats = get_top_transactions(varied_expenses, 5, start, end)

        assert top_df.empty
        assert stats['total_top_n'] == 0
        assert stats['pct_of_total'] == 0

    def test_n_larger_than_available(self, varied_expenses: pd.DataFrame) -> None:
        """If N > total expenses, return all of them."""
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        top_df, stats = get_top_transactions(varied_expenses, 100, start, end)

        assert len(top_df) == 8
        assert stats['total_top_n'] == pytest.approx(stats['total_spending'])

    def test_all_income_returns_empty(self) -> None:
        """A DataFrame with only income transactions returns empty stats."""
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
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        top_df, stats = get_top_transactions(df, 10, start, end)
        assert top_df.empty
        assert stats['total_top_n'] == 0
        assert stats['pct_of_total'] == 0

    def test_ties_at_boundary_returns_n(self, varied_expenses: pd.DataFrame) -> None:
        """When multiple transactions tie at the N-th position, nlargest returns exactly N."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01'] * 5, utc=True),
            'Amount': [-100, -100, -100, -100, -100],
            'Type': ['Expense'] * 5,
            'Category': ['Cat'] * 5,
            'Group': ['Grp'] * 5,
            'Account': ['Checking'] * 5,
            'Month': ['2024-01'] * 5,
            'Full Description': ['A', 'B', 'C', 'D', 'E'],
            'Institution': ['Bank'] * 5,
            'Account #': ['1234'] * 5,
        })
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        top_df, stats = get_top_transactions(df, 3, start, end)
        assert len(top_df) == 3
        assert stats['total_top_n'] == pytest.approx(300)
        assert stats['pct_of_total'] == pytest.approx(60)

    def test_ties_break_by_date_ascending(self) -> None:
        """Tied amounts sort by Date ascending for deterministic display order."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-03-01', '2024-01-01', '2024-02-01'], utc=True),
            'Amount': [-200, -200, -200],
            'Type': ['Expense'] * 3,
            'Category': ['Cat'] * 3,
            'Group': ['Grp'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-03', '2024-01', '2024-02'],
            'Full Description': ['March', 'January', 'February'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        top_df, _stats = get_top_transactions(df, 3, start, end)
        descs = top_df['Full Description'].tolist()
        assert descs == ['January', 'February', 'March']

    def test_mixed_amounts_tie_at_boundary_selects_by_date(self) -> None:
        """Distinct large amounts fill slots, then tied amounts at the cutoff
        compete — earliest dates win the remaining slots."""
        df = pd.DataFrame({
            'Date': pd.to_datetime([
                '2024-01-01',  # -500 (clear winner)
                '2024-04-01',  # -100 tied, late date (should lose)
                '2024-02-01',  # -100 tied, early date (should win)
                '2024-03-01',  # -100 tied, middle date (should win)
            ], utc=True),
            'Amount': [-500, -100, -100, -100],
            'Type': ['Expense'] * 4,
            'Category': ['Cat'] * 4,
            'Group': ['Grp'] * 4,
            'Account': ['Checking'] * 4,
            'Month': ['2024-01', '2024-04', '2024-02', '2024-03'],
            'Full Description': ['Big', 'April', 'February', 'March'],
            'Institution': ['Bank'] * 4,
            'Account #': ['1234'] * 4,
        })
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        top_df, _stats = get_top_transactions(df, 3, start, end)
        assert len(top_df) == 3
        descs = top_df['Full Description'].tolist()
        assert descs == ['Big', 'February', 'March']

    def test_overflow_ties_select_earliest_dates(self) -> None:
        """When more rows tie at the cutoff amount than fit in N, earlier dates win."""
        df = pd.DataFrame({
            'Date': pd.to_datetime([
                '2024-01-01', '2024-02-01', '2024-03-01',
                '2024-04-01', '2024-05-01',
            ], utc=True),
            'Amount': [-100, -100, -100, -100, -100],
            'Type': ['Expense'] * 5,
            'Category': ['Cat'] * 5,
            'Group': ['Grp'] * 5,
            'Account': ['Checking'] * 5,
            'Month': ['2024-01', '2024-02', '2024-03', '2024-04', '2024-05'],
            'Full Description': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            'Institution': ['Bank'] * 5,
            'Account #': ['1234'] * 5,
        })
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        top_df, _stats = get_top_transactions(df, 3, start, end)
        assert len(top_df) == 3
        descs = top_df['Full Description'].tolist()
        assert descs == ['Jan', 'Feb', 'Mar']


class TestGetCategoryBreakdown:

    def test_groups_by_category(self, varied_expenses: pd.DataFrame) -> None:
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        top_df, _ = get_top_transactions(varied_expenses, 10, start, end)
        breakdown = get_category_breakdown(top_df)

        # Rent should be largest (1000 + 750 + 500 = 2250)
        assert breakdown.iloc[0]['Category'] == 'Rent'
        assert breakdown.iloc[0]['Total'] == pytest.approx(2250)
        assert breakdown.iloc[0]['Count'] == 3

    def test_empty_input(self) -> None:
        breakdown = get_category_breakdown(pd.DataFrame())
        assert breakdown.empty


class TestFindRecurringLargeExpenses:

    def test_finds_recurring_merchants(self, varied_expenses: pd.DataFrame) -> None:
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        top_df, _ = get_top_transactions(varied_expenses, 10, start, end)
        recurring = find_recurring_large_expenses(top_df)

        merchants = recurring['Merchant'].tolist()
        # LANDLORD LLC appears 3 times, STARBUCKS appears 2 times
        assert 'LANDLORD LLC' in merchants
        assert 'STARBUCKS' in merchants

    def test_single_occurrence_excluded(self, varied_expenses: pd.DataFrame) -> None:
        """Merchants appearing only once should not be listed."""
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        top_df, _ = get_top_transactions(varied_expenses, 10, start, end)
        recurring = find_recurring_large_expenses(top_df)

        merchants = recurring['Merchant'].tolist()
        assert 'KROGER STORE' not in merchants

    def test_empty_input(self) -> None:
        recurring = find_recurring_large_expenses(pd.DataFrame())
        assert recurring.empty
