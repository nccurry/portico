"""Tests for category spending and transaction-distribution calculations."""
import pytest
import pandas as pd

from src.custom_types import SpendingFilters
from src.analysis.spending import (
    calculate_distribution_stats,
    calculate_spending_summary,
    process_spending_data,
)
from tests.custom_types import TransactionsSpreadsheetFactory


class TestProcessSpendingData:

    def test_filters_to_expenses_only(
        self,
        spending_transactions_df: pd.DataFrame,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        df_period, _df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        # df_period should contain only expenses
        assert (df_period['Type'] == 'Expense').all()

    def test_category_grouping_with_abs_amounts(
        self,
        spending_transactions_df: pd.DataFrame,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        _, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        # All amounts should be positive (absolute values)
        assert (df_by_category['Amount'] >= 0).all()

        # Groceries should have 200 + 100 = 300
        groceries_row = df_by_category[df_by_category['Category'] == 'Groceries']
        assert groceries_row['Amount'].values[0] == pytest.approx(300)

    def test_percentages_sum_to_100(
        self,
        spending_transactions_df: pd.DataFrame,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        ts = make_transactions_spreadsheet(spending_transactions_df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        _, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        total_pct = df_by_category['Percentage'].sum()
        assert total_pct == pytest.approx(100.0, abs=0.5)


class TestCalculateDistributionStats:

    def test_percentiles_correct(self, expenses_only_df: pd.DataFrame) -> None:
        """Hand-computed percentiles for amounts [10, 50, 100, 300, 500].

        Median of 5 sorted values = middle value = 100.
        Mean = (10+50+100+300+500)/5 = 960/5 = 192.
        Pandas quantile uses linear interpolation:
          p25 of 5 values: position = 0.25 * 4 = 1.0 → exactly index 1 → 50
          p75 of 5 values: position = 0.75 * 4 = 3.0 → exactly index 3 → 300
        """
        stats = calculate_distribution_stats(expenses_only_df)
        assert stats['median'] == pytest.approx(100.0)
        assert stats['mean'] == pytest.approx(192.0)
        assert stats['p25'] == pytest.approx(50.0)
        assert stats['p75'] == pytest.approx(300.0)

    def test_size_bucket_counts(self, expenses_only_df: pd.DataFrame) -> None:
        stats = calculate_distribution_stats(expenses_only_df)

        # Amounts are 10, 50, 100, 300, 500
        # small (<25): 10 -> 1
        # medium (25-250): 50, 100 -> 2
        # large (>=250): 300, 500 -> 2
        assert stats['small_count'] == 1
        assert stats['medium_count'] == 2
        assert stats['large_count'] == 2

    def test_pareto_off_by_one(self, expenses_only_df: pd.DataFrame) -> None:
        """The count should include the transaction that pushes cumulative sum past 80%."""
        stats = calculate_distribution_stats(expenses_only_df)

        # Amounts sorted desc: 500, 300, 100, 50, 10 -> total = 960
        # 80% threshold = 768
        # cumsum: 500, 800, 900, 950, 960
        # Transaction at cumsum=800 pushes past 768, so 2 transactions account for 80%
        # Expected pareto_pct = 2/5 * 100 = 40%
        assert stats['pareto_pct'] == pytest.approx(40.0)

    def test_single_transaction(self) -> None:
        """Distribution stats for a single transaction."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-05'], utc=True),
            'Amount': [-100],
            'Type': ['Expense'],
            'Category': ['Groceries'],
            'Group': ['Food'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['STORE'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        stats = calculate_distribution_stats(df)

        assert stats['median'] == pytest.approx(100.0)
        assert stats['mean'] == pytest.approx(100.0)
        assert stats['p25'] == pytest.approx(100.0)
        assert stats['p75'] == pytest.approx(100.0)
        # Single transaction accounts for 100% of spending
        assert stats['pareto_pct'] == pytest.approx(100.0)

    def test_all_same_amount(self) -> None:
        """All transactions with same amount."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03'], utc=True),
            'Amount': [-50, -50, -50],
            'Type': ['Expense'] * 3,
            'Category': ['Coffee'] * 3,
            'Group': ['Food'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01'] * 3,
            'Full Description': ['CAFE'] * 3,
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        stats = calculate_distribution_stats(df)

        assert stats['median'] == pytest.approx(50.0)
        assert stats['mean'] == pytest.approx(50.0)
        assert stats['small_count'] == 0
        assert stats['medium_count'] == 3
        assert stats['large_count'] == 0

    def test_date_range_filters_transactions(
        self,
        spending_transactions_df: pd.DataFrame,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Only transactions within the date range are included."""
        ts = make_transactions_spreadsheet(spending_transactions_df)
        # Only January
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-01-31', tz='UTC')

        df_period, _df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        # February transaction should be excluded
        assert all(d.month == 1 for d in df_period['Date'])

    def test_zero_spending_returns_zero_percentages(
        self,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """No expenses in range produces zero percentages."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15'], utc=True),
            'Amount': [5000],
            'Type': ['Income'],
            'Category': ['Salary'],
            'Group': ['Income'],
            'Account': ['Checking'],
            'Month': ['2024-01'],
            'Full Description': ['PAY'],
            'Institution': ['Bank'],
            'Account #': ['1234'],
        })
        ts = make_transactions_spreadsheet(df)
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        df_period, df_by_category = process_spending_data(ts, basic_spending_filters, start, end)

        assert len(df_period) == 0
        assert len(df_by_category) == 0


class TestCalculateSpendingSummary:
    """Test ``calculate_spending_summary`` — pure metrics from category breakdown."""

    def test_empty_df(self) -> None:
        """Empty input returns zeroed summary with empty top_category."""
        result = calculate_spending_summary(pd.DataFrame(columns=["Amount", "Category", "Percentage"]))
        assert result["total_spending"] == 0.0
        assert result["top_category"] == ""
        assert result["top_category_amount"] == 0.0
        assert result["num_categories"] == 0

    def test_single_category(self) -> None:
        df = pd.DataFrame({"Category": ["Groceries"], "Amount": [450.0], "Percentage": [100.0]})
        result = calculate_spending_summary(df)
        assert result["total_spending"] == pytest.approx(450.0)
        assert result["top_category"] == "Groceries"
        assert result["top_category_amount"] == pytest.approx(450.0)
        assert result["num_categories"] == 1

    def test_multiple_categories_top_is_first(self) -> None:
        """Top category is the first row (assumes descending sort from process_spending_data)."""
        df = pd.DataFrame({
            "Category": ["Rent", "Groceries", "Coffee"],
            "Amount": [1200.0, 300.0, 50.0],
            "Percentage": [77.4, 19.4, 3.2],
        })
        result = calculate_spending_summary(df)
        assert result["total_spending"] == pytest.approx(1550.0)
        assert result["top_category"] == "Rent"
        assert result["top_category_amount"] == pytest.approx(1200.0)
        assert result["num_categories"] == 3


# ---------------------------------------------------------------------------
# Deep corner cases: distribution bucket boundaries, Pareto edge cases
# ---------------------------------------------------------------------------


class TestDistributionBucketBoundaries:
    """The size buckets are: small < 25, medium [25, 250), large >= 250.
    Verify the exact boundary semantics — off-by-one errors here would misclassify
    transactions that land exactly on the threshold."""

    def _expense_df(self, amounts: list[float]) -> pd.DataFrame:
        n = len(amounts)
        return pd.DataFrame({
            'Date': pd.to_datetime([f'2024-01-{i+1:02d}' for i in range(n)], utc=True),
            'Amount': [-a for a in amounts],
            'Type': ['Expense'] * n,
            'Category': ['X'] * n,
            'Group': ['Y'] * n,
            'Account': ['Checking'] * n,
            'Month': ['2024-01'] * n,
            'Full Description': [f'txn-{i}' for i in range(n)],
            'Institution': ['Bank'] * n,
            'Account #': ['1234'] * n,
        })

    def test_boundary_24_99_is_small(self) -> None:
        """24.99 < 25 → small bucket."""
        df = self._expense_df([24.99])
        stats = calculate_distribution_stats(df)
        assert stats['small_count'] == 1
        assert stats['medium_count'] == 0
        assert stats['large_count'] == 0

    def test_boundary_exactly_25_is_medium(self) -> None:
        """Exactly 25 crosses the <25 threshold → medium bucket."""
        df = self._expense_df([25.0])
        stats = calculate_distribution_stats(df)
        assert stats['small_count'] == 0
        assert stats['medium_count'] == 1
        assert stats['large_count'] == 0

    def test_boundary_249_99_is_medium(self) -> None:
        """249.99 < 250 → medium bucket."""
        df = self._expense_df([249.99])
        stats = calculate_distribution_stats(df)
        assert stats['medium_count'] == 1
        assert stats['large_count'] == 0

    def test_boundary_exactly_250_is_large(self) -> None:
        """Exactly 250 crosses the <250 threshold → large bucket."""
        df = self._expense_df([250.0])
        stats = calculate_distribution_stats(df)
        assert stats['medium_count'] == 0
        assert stats['large_count'] == 1

    def test_buckets_partition_all_rows(self) -> None:
        """Every row lands in exactly one bucket — no gaps, no overlaps."""
        amounts = [0.01, 1.0, 24.99, 25.0, 100.0, 249.99, 250.0, 1000.0]
        df = self._expense_df(amounts)
        stats = calculate_distribution_stats(df)
        assert (
            stats['small_count'] + stats['medium_count'] + stats['large_count']
            == len(amounts)
        )

    def test_bucket_percentages_sum_to_100(self) -> None:
        amounts = [5.0, 30.0, 100.0, 300.0, 1000.0]
        df = self._expense_df(amounts)
        stats = calculate_distribution_stats(df)
        total = stats['small_pct'] + stats['medium_pct'] + stats['large_pct']
        assert total == pytest.approx(100.0, abs=0.01)

    def test_zero_amount_is_small(self) -> None:
        """An exactly-zero expense (rare but possible) counts as small."""
        df = self._expense_df([0.0])
        stats = calculate_distribution_stats(df)
        assert stats['small_count'] == 1


class TestParetoAnalysis:
    """The Pareto calculation finds the smallest count of transactions whose
    cumulative sum exceeds 80% of total spending."""

    def _expense_df(self, amounts: list[float]) -> pd.DataFrame:
        n = len(amounts)
        return pd.DataFrame({
            'Date': pd.to_datetime([f'2024-01-{i+1:02d}' for i in range(n)], utc=True),
            'Amount': [-a for a in amounts],
            'Type': ['Expense'] * n,
            'Category': ['X'] * n,
            'Group': ['Y'] * n,
            'Account': ['Checking'] * n,
            'Month': ['2024-01'] * n,
            'Full Description': [f'txn-{i}' for i in range(n)],
            'Institution': ['Bank'] * n,
            'Account #': ['1234'] * n,
        })

    def test_extreme_pareto_one_dominates(self) -> None:
        """When a single transaction is >80% of spending, pareto_pct = 1/N.

        Algorithm: count rows whose cumsum is <= 80% threshold, then +1 to
        include the row that crosses the threshold (capped at N).
        """
        df = self._expense_df([1000, 50, 50, 50, 50])
        stats = calculate_distribution_stats(df)
        # Sorted desc cumsum: [1000, 1050, 1100, 1150, 1200]; 80% threshold = 960.
        # cumsum <= 960 → NONE (first value 1000 already exceeds).
        # count = 0 + 1 = 1 → pareto_pct = 1/5 * 100 = 20%
        assert stats['pareto_pct'] == pytest.approx(20.0)

    def test_uniform_distribution_needs_most_transactions(self) -> None:
        """With equal amounts, ~80% of transactions are needed for 80% of spending."""
        df = self._expense_df([100] * 10)
        stats = calculate_distribution_stats(df)
        # cumsum: [100, 200, ..., 1000]; 80% threshold = 800
        # The eighth transaction reaches the threshold exactly.
        assert stats['pareto_pct'] == pytest.approx(80.0)

    def test_empty_df_pareto_is_zero(self) -> None:
        """An empty DataFrame produces pareto_pct = 0 without division error."""
        df = pd.DataFrame({
            'Amount': pd.Series([], dtype=float),
        })
        stats = calculate_distribution_stats(df)
        assert stats['pareto_pct'] == 0.0

    def test_two_transactions(self) -> None:
        """Minimum meaningful sample: sorted desc [100, 10], total=110.
        80% threshold = 88. cumsum[0]=100 > 88 → count=0, +1=1 → 1/2 = 50%."""
        df = self._expense_df([100, 10])
        stats = calculate_distribution_stats(df)
        assert stats['pareto_pct'] == pytest.approx(50.0)

    def test_pareto_upper_bound_capped_at_n(self) -> None:
        """The +1 cushion is capped at len(amounts) so pareto_pct never exceeds 100%."""
        df = self._expense_df([10] * 5)
        stats = calculate_distribution_stats(df)
        assert stats['pareto_pct'] <= 100.0


class TestDistributionEdgeCases:
    """Other distribution stat edge cases."""

    def test_negative_and_positive_amounts_treated_as_abs(self) -> None:
        """calculate_distribution_stats uses abs(), so sign doesn't matter."""
        df = pd.DataFrame({
            'Amount': [-100, 100, -50, 50],
            'Date': pd.to_datetime(['2024-01-01'] * 4, utc=True),
        })
        stats = calculate_distribution_stats(df)
        assert stats['mean'] == pytest.approx(75.0)
        assert stats['median'] == pytest.approx(75.0)

    def test_all_zeros(self) -> None:
        """All-zero amounts produce 0 for percentiles/buckets without division errors.

        Note: ``pareto_pct`` is 100% in this case because the 80%-threshold is 0
        and every cumsum row satisfies ``cumsum <= 0``. The ``if total_spending > 0``
        guard only protects the dollar-percent buckets, not the Pareto calculation.
        This is documented behavior, not a test expectation.
        """
        df = pd.DataFrame({
            'Amount': [0.0, 0.0, 0.0],
            'Date': pd.to_datetime(['2024-01-01'] * 3, utc=True),
        })
        stats = calculate_distribution_stats(df)
        assert stats['median'] == 0.0
        assert stats['mean'] == 0.0
        assert stats['small_pct'] == 0.0
        assert stats['medium_pct'] == 0.0
        assert stats['large_pct'] == 0.0
        # pareto_pct intentionally not asserted — the guard only applies to dollar
        # percentages, so pareto_pct here is an implementation artifact.

    def test_percentiles_on_known_distribution(self) -> None:
        """Hand-verified percentiles for a 10-element dataset."""
        df = pd.DataFrame({
            'Amount': [-10.0, -20.0, -30.0, -40.0, -50.0, -60.0, -70.0, -80.0, -90.0, -100.0],
            'Date': pd.to_datetime([f'2024-01-{i:02d}' for i in range(1, 11)], utc=True),
        })
        stats = calculate_distribution_stats(df)
        # Pandas uses linear interpolation by default
        # p25 of 1..10 = 3.25 → scaled = 32.5; p50 = 55; p75 = 77.5
        assert stats['p25'] == pytest.approx(32.5)
        assert stats['median'] == pytest.approx(55.0)
        assert stats['p75'] == pytest.approx(77.5)
        assert stats['p80'] == pytest.approx(82.0)
        assert stats['p90'] == pytest.approx(91.0)


# ---------------------------------------------------------------------------
# Deep corner cases: process_spending_data
# ---------------------------------------------------------------------------


class TestProcessSpendingDataCorners:

    def test_same_category_in_multiple_months_aggregates(
        self,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Same category across different months sums into one row in df_by_category."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-15', '2024-02-15', '2024-03-15'], utc=True),
            'Amount': [-100, -150, -200],
            'Type': ['Expense'] * 3,
            'Category': ['Groceries'] * 3,
            'Group': ['Food'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01', '2024-02', '2024-03'],
            'Full Description': ['A', 'B', 'C'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        ts = make_transactions_spreadsheet(df)
        _, df_by_cat = process_spending_data(
            ts, basic_spending_filters,
            pd.Timestamp('2024-01-01', tz='UTC'),
            pd.Timestamp('2024-12-31', tz='UTC'),
        )
        assert len(df_by_cat) == 1
        assert df_by_cat.iloc[0]['Amount'] == pytest.approx(450.0)

    def test_output_sorted_descending_by_amount(
        self,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """df_by_category must be sorted descending so calculate_spending_summary
        can trust iloc[0] as the top category."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03'], utc=True),
            'Amount': [-50, -1000, -200],
            'Type': ['Expense'] * 3,
            'Category': ['Coffee', 'Rent', 'Groceries'],
            'Group': ['Food', 'Bills', 'Food'],
            'Account': ['Checking'] * 3,
            'Month': ['2024-01'] * 3,
            'Full Description': ['A', 'B', 'C'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        ts = make_transactions_spreadsheet(df)
        _, df_by_cat = process_spending_data(
            ts, basic_spending_filters,
            pd.Timestamp('2024-01-01', tz='UTC'),
            pd.Timestamp('2024-12-31', tz='UTC'),
        )
        amounts = df_by_cat['Amount'].tolist()
        assert amounts == sorted(amounts, reverse=True)
        assert df_by_cat.iloc[0]['Category'] == 'Rent'

    def test_date_range_inclusive_on_both_ends(
        self,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """start_date and end_date are both inclusive (>= and <=)."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01', '2024-01-31', '2024-02-01'], utc=True),
            'Amount': [-100, -200, -300],
            'Type': ['Expense'] * 3,
            'Category': ['X'] * 3,
            'Group': ['Y'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01', '2024-01', '2024-02'],
            'Full Description': ['A', 'B', 'C'],
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        ts = make_transactions_spreadsheet(df)
        df_period, _ = process_spending_data(
            ts, basic_spending_filters,
            pd.Timestamp('2024-01-01', tz='UTC'),
            pd.Timestamp('2024-01-31', tz='UTC'),
        )
        # Both Jan 1 and Jan 31 included, Feb 1 excluded
        assert len(df_period) == 2

    def test_excluded_groups_filter_removed_from_total(
        self,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Filter excluding a group drops its expenses from df_by_category."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01', '2024-01-02'], utc=True),
            'Amount': [-100, -200],
            'Type': ['Expense'] * 2,
            'Category': ['Rent', 'Groceries'],
            'Group': ['Bills', 'Food'],
            'Account': ['Checking'] * 2,
            'Month': ['2024-01'] * 2,
            'Full Description': ['A', 'B'],
            'Institution': ['Bank'] * 2,
            'Account #': ['1234'] * 2,
        })
        ts = make_transactions_spreadsheet(df)
        filters: SpendingFilters = {
            'include_groups': [],
            'include_categories': [],
            'exclude_groups': ['Bills'],
            'exclude_categories': [],
            'filter_large_expenses': False,
            'expense_threshold': 50000,
        }
        _, df_by_cat = process_spending_data(
            ts, filters,
            pd.Timestamp('2024-01-01', tz='UTC'),
            pd.Timestamp('2024-12-31', tz='UTC'),
        )
        assert 'Rent' not in df_by_cat['Category'].values
        assert df_by_cat['Amount'].sum() == pytest.approx(200.0)

    def test_income_always_excluded(
        self,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Even positive expense-shaped Income rows are excluded from spending."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01', '2024-01-02'], utc=True),
            'Amount': [5000, -100],
            'Type': ['Income', 'Expense'],
            'Category': ['Salary', 'Groceries'],
            'Group': ['Income', 'Food'],
            'Account': ['Checking'] * 2,
            'Month': ['2024-01'] * 2,
            'Full Description': ['PAY', 'STORE'],
            'Institution': ['Bank'] * 2,
            'Account #': ['1234'] * 2,
        })
        ts = make_transactions_spreadsheet(df)
        df_period, df_by_cat = process_spending_data(
            ts, basic_spending_filters,
            pd.Timestamp('2024-01-01', tz='UTC'),
            pd.Timestamp('2024-12-31', tz='UTC'),
        )
        assert len(df_period) == 1
        assert df_by_cat['Amount'].sum() == pytest.approx(100.0)
        assert 'Salary' not in df_by_cat['Category'].values

    def test_percentages_rounded_to_one_decimal(
        self,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Percentages are rounded to 1 decimal — verify they're not raw floats."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03'], utc=True),
            'Amount': [-100, -200, -33.33],
            'Type': ['Expense'] * 3,
            'Category': ['A', 'B', 'C'],
            'Group': ['G'] * 3,
            'Account': ['Checking'] * 3,
            'Month': ['2024-01'] * 3,
            'Full Description': ['X'] * 3,
            'Institution': ['Bank'] * 3,
            'Account #': ['1234'] * 3,
        })
        ts = make_transactions_spreadsheet(df)
        _, df_by_cat = process_spending_data(
            ts, basic_spending_filters,
            pd.Timestamp('2024-01-01', tz='UTC'),
            pd.Timestamp('2024-12-31', tz='UTC'),
        )
        for pct in df_by_cat['Percentage']:
            # Round to 1 decimal means the remainder after 1 decimal is 0
            assert pct == round(pct, 1)

    def test_refund_positive_expense_amount_absolute(
        self,
        basic_spending_filters: SpendingFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """A positive-amount row classified as Expense (rare partial refund)
        is absorbed via abs() — so a +50 expense shows as $50 in the category total."""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2024-01-01', '2024-01-02'], utc=True),
            'Amount': [-200, 50],  # -200 then +50 refund but classified Expense
            'Type': ['Expense', 'Expense'],
            'Category': ['Groceries'] * 2,
            'Group': ['Food'] * 2,
            'Account': ['Checking'] * 2,
            'Month': ['2024-01'] * 2,
            'Full Description': ['STORE', 'RETURN'],
            'Institution': ['Bank'] * 2,
            'Account #': ['1234'] * 2,
        })
        ts = make_transactions_spreadsheet(df)
        _, df_by_cat = process_spending_data(
            ts, basic_spending_filters,
            pd.Timestamp('2024-01-01', tz='UTC'),
            pd.Timestamp('2024-12-31', tz='UTC'),
        )
        # Sum is -200 + 50 = -150 → abs = 150
        assert df_by_cat.iloc[0]['Amount'] == pytest.approx(150.0)
