"""Tests for top-transaction analysis."""
import pytest
import pandas as pd

from src.analysis.top_transactions import (
    build_transaction_breakdown,
    build_transaction_inventory,
    filter_transaction_focus,
    find_recurring_large_expenses,
    get_category_breakdown,
    get_top_transactions,
    summarize_transaction_inventory,
)


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
        """If N > total expenses, return all of them.

        The fixture has 8 expenses totaling
        $50 + $500 + $100 + $1000 + $200 + $300 + $750 + $25 = $2925.
        When n=100 > 8, all 8 are returned and total_top_n == $2925.
        """
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')

        top_df, stats = get_top_transactions(varied_expenses, 100, start, end)

        assert len(top_df) == 8
        assert stats['total_top_n'] == pytest.approx(2925.0)
        assert stats['total_spending'] == pytest.approx(2925.0)
        assert stats['pct_of_total'] == pytest.approx(100.0)

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

    def test_empty_input_returns_expected_columns(self) -> None:
        """Empty input produces DataFrame with Merchant/Count/Total columns for UI stability."""
        recurring = find_recurring_large_expenses(pd.DataFrame())
        assert list(recurring.columns) == ['Merchant', 'Count', 'Total']

    def test_sorted_by_total_descending(self) -> None:
        """Result should be sorted by Total descending (worst spender first)."""
        df = pd.DataFrame({
            'Abs_Amount': [100, 100, 50, 50, 50],
            'Full Description': [
                'CHEAP STORE', 'CHEAP STORE',
                'EXPENSIVE ONE', 'EXPENSIVE ONE', 'EXPENSIVE ONE',
            ],
        })
        recurring = find_recurring_large_expenses(df)
        totals = recurring['Total'].tolist()
        assert totals == sorted(totals, reverse=True)


class TestGetCategoryBreakdownCorners:

    def test_single_category(self) -> None:
        """One category → one row in breakdown."""
        df = pd.DataFrame({
            'Category': ['Food'] * 3,
            'Abs_Amount': [100, 200, 300],
        })
        breakdown = get_category_breakdown(df)
        assert len(breakdown) == 1
        assert breakdown.iloc[0]['Total'] == pytest.approx(600)
        assert breakdown.iloc[0]['Count'] == 3

    def test_sorted_descending_by_total(self) -> None:
        df = pd.DataFrame({
            'Category': ['Food', 'Rent', 'Food', 'Utilities'],
            'Abs_Amount': [100, 1000, 50, 200],
        })
        breakdown = get_category_breakdown(df)
        # Food: 150, Rent: 1000, Utilities: 200
        assert breakdown.iloc[0]['Category'] == 'Rent'
        assert breakdown.iloc[1]['Category'] == 'Utilities'
        assert breakdown.iloc[2]['Category'] == 'Food'


class TestGetTopTransactionsMathCorners:

    def _df(self, dates: list[str], amounts: list[float],
            descs: list[str] | None = None) -> pd.DataFrame:
        n = len(dates)
        return pd.DataFrame({
            'Date': pd.to_datetime(dates, utc=True),
            'Amount': amounts,
            'Type': ['Expense'] * n,
            'Category': ['X'] * n,
            'Group': ['Y'] * n,
            'Account': ['Checking'] * n,
            'Month': [d[:7] for d in dates],
            'Full Description': descs if descs else [f'txn-{i}' for i in range(n)],
            'Institution': ['Bank'] * n,
            'Account #': ['1234'] * n,
        })

    def test_pct_of_total_100_when_all_fit(self) -> None:
        """When n >= num_transactions, pct_of_total is 100%."""
        df = self._df(['2024-01-01', '2024-01-02'], [-100, -200])
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        _, stats = get_top_transactions(df, 10, start, end)
        assert stats['pct_of_total'] == pytest.approx(100.0)

    def test_pct_of_total_rounds_correctly(self) -> None:
        """Pct math should be exact (no rounding errors for simple ratios)."""
        df = self._df(['2024-01-01', '2024-01-02'], [-75, -25])
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        _, stats = get_top_transactions(df, 1, start, end)
        assert stats['pct_of_total'] == pytest.approx(75.0)

    def test_start_date_equals_end_date_single_day(self) -> None:
        """Start==End selects exactly that day."""
        df = self._df(
            ['2024-01-05', '2024-01-15', '2024-01-25'],
            [-50, -100, -200],
        )
        start = pd.Timestamp('2024-01-15', tz='UTC')
        end = pd.Timestamp('2024-01-15', tz='UTC')
        top_df, stats = get_top_transactions(df, 10, start, end)
        assert stats['num_transactions'] == 1
        assert top_df.iloc[0]['Abs_Amount'] == pytest.approx(100.0)

    def test_date_range_inclusive_on_both_bounds(self) -> None:
        """Both start and end are inclusive (>= and <=)."""
        df = self._df(
            ['2024-01-01', '2024-01-31', '2024-02-01'],
            [-100, -200, -300],
        )
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-01-31', tz='UTC')
        _, stats = get_top_transactions(df, 10, start, end)
        assert stats['num_transactions'] == 2

    def test_all_positive_amounts_filtered_out(self) -> None:
        """Rows with Type=Expense but positive amounts still count as expenses
        (since type is the filter, not sign). Verify aggregate is the abs sum."""
        df = self._df(['2024-01-01', '2024-01-02'], [50, -100])
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        _top_df, stats = get_top_transactions(df, 10, start, end)
        # abs values: 50 + 100 = 150
        assert stats['total_spending'] == pytest.approx(150.0)
        assert stats['num_transactions'] == 2

    def test_single_row_boundary(self) -> None:
        """Single expense with n=1."""
        df = self._df(['2024-01-01'], [-42.50])
        start = pd.Timestamp('2024-01-01', tz='UTC')
        end = pd.Timestamp('2024-12-31', tz='UTC')
        top_df, stats = get_top_transactions(df, 1, start, end)
        assert len(top_df) == 1
        assert stats['total_top_n'] == pytest.approx(42.50)
        assert stats['pct_of_total'] == pytest.approx(100.0)


def _explorer_transactions(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults = {
        "Date": "2024-01-01",
        "Amount": -100.0,
        "Type": "Expense",
        "Category": "Shopping",
        "Group": "Shopping",
        "Account": "Checking",
        "Month": "2024-01",
        "Full Description": "Example merchant",
        "Institution": "Bank",
        "Account #": "1234",
    }
    frame = pd.DataFrame([{**defaults, **row} for row in rows])
    frame["Date"] = pd.to_datetime(frame["Date"], utc=True)
    return frame


class TestTransactionExplorer:

    def test_inventory_applies_dimensions_search_and_amount_range(self) -> None:
        transactions = _explorer_transactions([
            {
                "Date": "2024-02-01",
                "Amount": -125.0,
                "Category": "Groceries",
                "Group": "Food",
                "Full Description": "Market Basket groceries",
            },
            {
                "Date": "2024-02-02",
                "Amount": -75.0,
                "Category": "Restaurants",
                "Group": "Food",
                "Full Description": "Corner Cafe dinner",
            },
            {"Date": "2024-02-03", "Amount": 3_000.0, "Type": "Income"},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
            transaction_types=["Expense"],
            groups=["Food"],
            categories=["Groceries"],
            accounts=["Checking"],
            search="market basket",
            minimum_magnitude=100.0,
            maximum_magnitude=200.0,
        )

        assert result["Full Description"].tolist() == ["Market Basket groceries"]
        assert result["Magnitude"].tolist() == [125.0]

    def test_aliases_keep_description_variants_from_looking_like_one_offs(self) -> None:
        transactions = _explorer_transactions([
            {"Full Description": "AMZN MKTPLACE order 1234"},
            {"Full Description": "AMAZON.COM purchase 5678", "Amount": -50.0},
            {"Full Description": "Local bookstore", "Amount": -30.0},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
            aliases={"AMZN MKTPLACE": "AMAZON", "AMAZON COM": "AMAZON"},
        )

        amazon = result[result["Merchant"].eq("AMAZON")]
        assert amazon["Occurrences"].tolist() == [2, 2]
        assert not amazon["Is_One_Off"].any()
        assert result.loc[result["Merchant"].eq("LOCAL BOOKSTORE"), "Is_One_Off"].item()

    def test_unusual_amounts_are_detected_within_repeat_merchants(self) -> None:
        transactions = _explorer_transactions([
            {"Full Description": "Utility power", "Amount": -100.0},
            {"Full Description": "Utility power", "Amount": -100.0},
            {"Full Description": "Utility power", "Amount": -500.0},
            {"Full Description": "One off", "Amount": -10_000.0},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
        )

        unusual = result[result["Is_Unusual"]]
        assert unusual["Amount"].tolist() == [-500.0]
        assert not result.loc[result["Merchant"].eq("ONE OFF"), "Is_Unusual"].item()

    def test_refunds_and_reversals_follow_type_and_amount_sign(self) -> None:
        transactions = _explorer_transactions([
            {"Amount": 25.0, "Type": "Expense", "Full Description": "Refund"},
            {"Amount": -50.0, "Type": "Income", "Full Description": "Income reversal"},
            {"Amount": 100.0, "Type": "Transfer", "Full Description": "Transfer"},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
        )

        assert result.set_index("Full Description")["Is_Reversal"].to_dict() == {
            "Transfer": False,
            "Income reversal": True,
            "Refund": True,
        }

    def test_focus_modes_filter_the_same_annotated_inventory(self) -> None:
        transactions = _explorer_transactions([
            {"Full Description": "Repeat", "Amount": -100.0},
            {"Full Description": "Repeat", "Amount": -100.0},
            {"Full Description": "Repeat", "Amount": -500.0},
            {"Full Description": "One off", "Amount": -200.0},
            {"Full Description": "Refund", "Amount": 25.0},
        ])
        inventory = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
        )

        assert filter_transaction_focus(inventory, "Largest", largest_count=2)[
            "Amount"
        ].tolist() == [-500.0, -200.0]
        assert set(
            filter_transaction_focus(inventory, "One-off merchants")["Merchant"]
        ) == {
            "ONE OFF",
            "REFUND",
        }
        assert filter_transaction_focus(inventory, "Unusual amounts")[
            "Amount"
        ].tolist() == [-500.0]
        assert filter_transaction_focus(inventory, "Refunds / reversals")[
            "Amount"
        ].tolist() == [25.0]
        with pytest.raises(ValueError, match="Unsupported transaction focus"):
            filter_transaction_focus(inventory, "Mystery")

    def test_summary_reconciles_raw_cash_directions(self) -> None:
        transactions = _explorer_transactions([
            {"Amount": -100.0},
            {"Amount": 20.0, "Type": "Expense"},
            {"Amount": 500.0, "Type": "Income"},
            {"Amount": -50.0, "Type": "Income"},
            {"Amount": -200.0, "Type": "Transfer"},
            {"Amount": 200.0, "Type": "Transfer"},
        ])

        summary = summarize_transaction_inventory(transactions)

        assert summary == {
            "transaction_count": 6,
            "inflow": pytest.approx(720.0),
            "outflow": pytest.approx(350.0),
            "net_amount": pytest.approx(370.0),
            "median_magnitude": pytest.approx(150.0),
        }

    def test_breakdown_summarizes_current_results(self) -> None:
        transactions = _explorer_transactions([
            {"Group": "Food", "Amount": -100.0},
            {"Group": "Food", "Amount": 25.0},
            {"Group": "Income", "Amount": 500.0, "Type": "Income"},
        ])

        result = build_transaction_breakdown(transactions, "Group")

        food = result.set_index("Entity").loc["Food"]
        assert food["Transactions"] == 2
        assert food["Outflow"] == pytest.approx(100.0)
        assert food["Inflow"] == pytest.approx(25.0)
        assert food["Net_Amount"] == pytest.approx(-75.0)
        assert result["Share"].sum() == pytest.approx(100.0)
        with pytest.raises(ValueError, match="Unsupported transaction breakdown"):
            build_transaction_breakdown(transactions, "Institution")
