"""Aggregation integrity tests.

Feed larger datasets through the filter + aggregate pipeline and verify
that the numbers at each stage are arithmetically consistent.
"""
import pandas as pd
import pytest

from src.config import get_settings
from src.custom_types import IncomeExpenseFilters, SpendingFilters, TransactionFilterOptions
from src.analysis.financial_independence import calculate_avg_monthly_spending
from src.analysis.income import process_income_expense_data
from src.analysis.spending import build_spending_ledger, build_spending_overview
from src.filters import apply_transaction_filters
from src.spreadsheet import get_all_accounts, get_portfolio_value
from tests.custom_types import FullDatasetFactory, TransactionsSpreadsheetFactory

# ---------------------------------------------------------------------------
# Filter pipeline integrity
# ---------------------------------------------------------------------------

class TestFilterPipelineIntegrity:
    """Verify that filtering preserves arithmetic identities."""

    def test_total_amount_preserved_without_filters(self, extended_transactions_df: pd.DataFrame) -> None:
        """With no filters (except Transfer exclusion), total amount is preserved."""
        df = extended_transactions_df.copy()
        # Ensure no Transfer rows in extended fixture
        original_total = df[df['Group'] != 'Transfer']['Amount'].sum()

        filtered = apply_transaction_filters(df, {})
        assert filtered['Amount'].sum() == pytest.approx(original_total)

    def test_exclude_group_removes_correct_amount(self, extended_transactions_df: pd.DataFrame) -> None:
        """Excluding a group removes exactly that group's total."""
        df = extended_transactions_df.copy()
        df = df[df['Group'] != 'Transfer']

        food_total = df[df['Group'] == 'Food']['Amount'].sum()
        non_food_total = df[df['Group'] != 'Food']['Amount'].sum()

        filtered = apply_transaction_filters(df, {'exclude_groups': ['Food']})
        assert filtered['Amount'].sum() == pytest.approx(non_food_total)
        assert filtered['Amount'].sum() == pytest.approx(
            df['Amount'].sum() - food_total
        )

    def test_include_group_keeps_only_that_group(self, extended_transactions_df: pd.DataFrame) -> None:
        """Include filter keeps only the specified group."""
        df = extended_transactions_df.copy()

        food_total = df[df['Group'] == 'Food']['Amount'].sum()

        filtered = apply_transaction_filters(df, {'include_groups': ['Food']})
        assert filtered['Amount'].sum() == pytest.approx(food_total)

    def test_large_expense_filter_removes_correct_rows(self, extended_transactions_df: pd.DataFrame) -> None:
        """Large expense filter removes exactly the over-threshold expenses."""
        df = extended_transactions_df.copy()
        df = df[df['Group'] != 'Transfer']
        threshold = 200

        # Manually compute what should remain
        expenses_over = df[(df['Type'] == 'Expense') & (df['Amount'].abs() > threshold)]
        expected_removed_amount = expenses_over['Amount'].sum()

        filters: TransactionFilterOptions = {
            'filter_large_expenses': True,
            'expense_threshold': threshold,
        }
        filtered = apply_transaction_filters(df, filters)

        assert filtered['Amount'].sum() == pytest.approx(
            df['Amount'].sum() - expected_removed_amount
        )


# ---------------------------------------------------------------------------
# Income/Expense aggregation integrity
# ---------------------------------------------------------------------------

class TestIncomeExpenseAggregation:
    """Verify that monthly income/expense/savings aggregations are consistent."""

    def test_monthly_totals_sum_to_overall(
        self,
        extended_transactions_df: pd.DataFrame,
        passthrough_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Sum of monthly Income and Expense columns equals the raw totals."""
        ts = make_transactions_spreadsheet(extended_transactions_df)
        result = process_income_expense_data(ts, passthrough_filters)

        # Raw totals (Transfer excluded by filter)
        df = extended_transactions_df[extended_transactions_df['Group'] != 'Transfer']
        raw_income = df[df['Type'] == 'Income']['Amount'].sum()
        raw_expense = df[df['Type'] == 'Expense']['Amount'].sum()

        assert result['Income'].sum() == pytest.approx(raw_income)
        assert result['Expense'].sum() == pytest.approx(raw_expense)

    def test_cash_flow_surplus_is_income_plus_expense_every_month(
        self,
        extended_transactions_df: pd.DataFrame,
        passthrough_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Cash-flow surplus equals income plus signed expenses every month."""
        ts = make_transactions_spreadsheet(extended_transactions_df)
        result = process_income_expense_data(ts, passthrough_filters)

        for _, row in result.iterrows():
            assert row['Cash_Flow_Surplus'] == pytest.approx(
                row['Income'] + row['Expense']
            )

    def test_all_months_accounted_for(
        self,
        extended_transactions_df: pd.DataFrame,
        passthrough_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Every month with transactions appears in the result."""
        ts = make_transactions_spreadsheet(extended_transactions_df)
        result = process_income_expense_data(ts, passthrough_filters)

        df = extended_transactions_df[extended_transactions_df['Group'] != 'Transfer']
        expected_months = set(df['Month'].unique())
        result_months = set(result['Month'].unique())

        assert expected_months == result_months


# ---------------------------------------------------------------------------
# Spending aggregation integrity
# ---------------------------------------------------------------------------

class TestSpendingAggregation:
    """Verify that spending category aggregations are consistent."""

    def test_category_totals_sum_to_overall(
        self,
        extended_transactions_df: pd.DataFrame,
    ) -> None:
        filters: SpendingFilters = {
            'include_groups': [],
            'include_categories': [],
            'exclude_groups': [],
            'exclude_categories': [],
            'filter_large_expenses': False,
            'expense_threshold': 999999,
        }
        ledger = build_spending_ledger(
            extended_transactions_df,
            filters,
            start_month="2024-01",
            end_month="2025-01",
        )
        overview = build_spending_overview(
            ledger,
            ledger.iloc[0:0],
            dimension="Category",
            months=[f"2024-{month:02d}" for month in range(1, 13)],
        )

        # Sum of category amounts should equal total period spending
        assert overview["Spending"].sum() == pytest.approx(
            ledger.loc[ledger["Included"], "Net_Spend"].sum()
        )

    def test_percentages_sum_to_100(
        self,
        extended_transactions_df: pd.DataFrame,
    ) -> None:
        filters: SpendingFilters = {
            'include_groups': [],
            'include_categories': [],
            'exclude_groups': [],
            'exclude_categories': [],
            'filter_large_expenses': False,
            'expense_threshold': 999999,
        }
        ledger = build_spending_ledger(
            extended_transactions_df,
            filters,
            start_month="2024-01",
            end_month="2025-01",
        )
        overview = build_spending_overview(
            ledger,
            ledger.iloc[0:0],
            dimension="Category",
            months=[f"2024-{month:02d}" for month in range(1, 13)],
        )

        assert overview["Share"].sum() == pytest.approx(100.0)

    def test_no_income_in_spending(
        self,
        extended_transactions_df: pd.DataFrame,
    ) -> None:
        """Spending data should never include income transactions."""
        filters: SpendingFilters = {
            'include_groups': [],
            'include_categories': [],
            'exclude_groups': [],
            'exclude_categories': [],
            'filter_large_expenses': False,
            'expense_threshold': 999999,
        }
        ledger = build_spending_ledger(
            extended_transactions_df,
            filters,
            start_month="2024-01",
            end_month="2025-01",
        )

        assert (ledger["Type"] == "Expense").all()


# ---------------------------------------------------------------------------
# Monthly amounts aggregation (spreadsheet methods)
# ---------------------------------------------------------------------------

class TestMonthlyAmountsAggregation:
    """Verify that get_monthly_amounts_by_* methods sum correctly."""

    def test_monthly_category_sums_match_raw(
        self,
        extended_transactions_df: pd.DataFrame,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Monthly amounts by category should sum to the raw category total."""
        ts = make_transactions_spreadsheet(extended_transactions_df)

        for category in extended_transactions_df['Category'].unique():
            monthly = ts.get_monthly_amounts_by_category(category)
            raw_total = extended_transactions_df[
                extended_transactions_df['Category'] == category
            ]['Amount'].sum()

            assert monthly['Amount'].sum() == pytest.approx(raw_total)

    def test_monthly_group_sums_match_raw(
        self,
        extended_transactions_df: pd.DataFrame,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Monthly amounts by group should sum to the raw group total."""
        ts = make_transactions_spreadsheet(extended_transactions_df)

        for group in extended_transactions_df['Group'].unique():
            monthly = ts.get_monthly_amounts_by_group(group)
            raw_total = extended_transactions_df[
                extended_transactions_df['Group'] == group
            ]['Amount'].sum()

            assert monthly['Amount'].sum() == pytest.approx(raw_total)

    def test_inverted_amounts_negate(
        self,
        extended_transactions_df: pd.DataFrame,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        """Inverted amounts should be the negative of non-inverted."""
        ts = make_transactions_spreadsheet(extended_transactions_df)

        for category in ['Groceries', 'Salary']:
            normal = ts.get_monthly_amounts_by_category(category)
            inverted = ts.get_monthly_amounts_by_category(category, invert_amount=True)

            if not normal.empty:
                assert inverted['Amount'].sum() == pytest.approx(-normal['Amount'].sum())


# ---------------------------------------------------------------------------
# Financial Independence aggregation integrity (real-fixture round-trip)
# ---------------------------------------------------------------------------

@pytest.mark.uses_real_dates
class TestFinancialIndependenceIntegrity:
    """Cross-check FI helpers against independently-computed totals on the
    committed anonymized CSV fixtures."""

    def test_portfolio_value_matches_manual_latest_signed_sum(
        self, make_full_dataset: FullDatasetFactory,
    ) -> None:
        """get_portfolio_value agrees with a manual latest-observation aggregation."""
        _txns, bal, _cats, _accts = make_full_dataset()
        all_accounts = get_all_accounts(bal.scrubbed_df)
        assert all_accounts, "Real fixture should contain accounts"

        picked = all_accounts[:3]
        _, total = get_portfolio_value(bal.scrubbed_df, picked)

        # Independently reproduce the math: for each picked account, take the
        # row with the latest (Date, Time) per Account ID, sign by Class.
        df = bal.scrubbed_df.copy()
        if "Hide" in df.columns:
            df = df[df["Hide"] != "Hide"]
        df = df[df["Account"].isin(picked)]
        df = df.sort_values(["Date", "Time"]).drop_duplicates("Account ID", keep="last")
        multiplier = df["Class"].map({"Liability": -1, "Asset": 1}).fillna(1)
        expected = float((df["Balance"] * multiplier).sum())

        assert total == pytest.approx(expected)

    def test_avg_monthly_spending_matches_direct_groupby(
        self, make_full_dataset: FullDatasetFactory,
    ) -> None:
        """calculate_avg_monthly_spending agrees with a direct groupby on the
        same post-filter frame."""
        txns, _bal, _cats, _accts = make_full_dataset()
        filters: TransactionFilterOptions = {
            "exclude_groups": list(get_settings().income_savings.exclude_groups),
            "exclude_categories": [],
            "filter_large_expenses": False,
            "expense_threshold": 999_999,
        }
        df = apply_transaction_filters(txns.scrubbed_df, filters)

        end = (pd.Timestamp.now(tz="UTC") - pd.DateOffset(months=1)).strftime("%Y-%m")
        start = (pd.Timestamp.now(tz="UTC") - pd.DateOffset(months=12)).strftime("%Y-%m")

        avg, totals = calculate_avg_monthly_spending(df, start, end)

        # Independently compute net spending for every month in the requested
        # window, including zero-spend months.
        exp = df[df["Type"] == "Expense"]
        exp = exp[(exp["Month"] >= start) & (exp["Month"] <= end)]
        if exp.empty:
            pytest.skip("No expense rows in window for real fixture")
        expected_monthly = -exp.groupby("Month")["Amount"].sum()
        months = pd.period_range(start=start, end=end, freq="M").astype(str)
        expected_monthly = expected_monthly.reindex(months, fill_value=0.0)
        expected_avg = float(expected_monthly.mean())

        assert avg == pytest.approx(expected_avg)
        assert len(totals) == len(expected_monthly)
        assert totals["Spending"].sum() == pytest.approx(float(expected_monthly.sum()))

    def test_portfolio_value_empty_selection_is_zero(
        self, make_full_dataset: FullDatasetFactory,
    ) -> None:
        _txns, bal, _cats, _accts = make_full_dataset()
        _, total = get_portfolio_value(bal.scrubbed_df, [])
        assert total == 0.0
