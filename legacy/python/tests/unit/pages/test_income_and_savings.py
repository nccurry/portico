"""Regression tests for monthly income and expense processing."""

import pandas as pd
import pytest

from src.analysis.income import process_income_expense_data
from src.custom_types import IncomeExpenseFilters
from tests.custom_types import TransactionsSpreadsheetFactory


class TestProcessIncomeExpenseData:
    def test_returns_canonical_monthly_cash_flow(
        self,
        income_expense_sample_df: pd.DataFrame,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        result = process_income_expense_data(
            make_transactions_spreadsheet(income_expense_sample_df),
            basic_filters,
        )

        assert result.columns.tolist() == [
            "Month",
            "Income",
            "Expense",
            "Net_Expenses",
            "Cash_Flow_Surplus",
            "Savings_Rate",
        ]
        assert result["Month"].tolist() == ["2024-01", "2024-02", "2024-03"]
        assert result["Income"].tolist() == pytest.approx([3_000, 4_000, 5_000])
        assert result["Expense"].tolist() == pytest.approx([-1_000, -2_000, -1_500])
        assert result["Net_Expenses"].tolist() == pytest.approx([1_000, 2_000, 1_500])
        assert result["Cash_Flow_Surplus"].tolist() == pytest.approx([2_000, 2_000, 3_500])
        assert result["Savings_Rate"].tolist() == pytest.approx([2_000 / 3_000 * 100, 50, 70])

    @pytest.mark.parametrize(
        ("amounts", "types", "expected_income", "expected_surplus", "expected_rate"),
        [
            ([5_000], ["Income"], 5_000, 5_000, 100.0),
            ([-500], ["Expense"], 0, -500, None),
            ([-200, -100], ["Income", "Expense"], -200, -300, None),
        ],
    )
    def test_savings_rate_requires_positive_income(
        self,
        amounts: list[float],
        types: list[str],
        expected_income: float,
        expected_surplus: float,
        expected_rate: float | None,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transaction_count = len(amounts)
        transactions = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-15"] * transaction_count, utc=True),
                "Amount": amounts,
                "Type": types,
                "Category": ["Test"] * transaction_count,
                "Group": ["Income" if transaction_type == "Income" else "Food" for transaction_type in types],
                "Account": ["Checking"] * transaction_count,
                "Month": ["2024-01"] * transaction_count,
                "Full Description": ["TEST"] * transaction_count,
                "Institution": ["Bank"] * transaction_count,
                "Account #": ["1234"] * transaction_count,
            }
        )

        result = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
        ).iloc[0]

        assert result["Income"] == pytest.approx(expected_income)
        assert result["Cash_Flow_Surplus"] == pytest.approx(expected_surplus)
        if expected_rate is None:
            assert pd.isna(result["Savings_Rate"])
        else:
            assert result["Savings_Rate"] == pytest.approx(expected_rate)

    def test_empty_transactions_return_empty_canonical_frame(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
        empty_transactions_df: pd.DataFrame,
    ) -> None:
        result = process_income_expense_data(
            make_transactions_spreadsheet(empty_transactions_df),
            basic_filters,
        )

        assert result.empty
        assert result.columns.tolist() == [
            "Month",
            "Income",
            "Expense",
            "Net_Expenses",
            "Cash_Flow_Surplus",
            "Savings_Rate",
        ]

    def test_accumulates_multiple_transactions_in_each_flow(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = pd.DataFrame(
            {
                "Date": pd.to_datetime(
                    ["2024-01-05", "2024-01-10", "2024-01-15", "2024-01-20"],
                    utc=True,
                ),
                "Amount": [3_000, 1_500, -100, -250],
                "Type": ["Income", "Income", "Expense", "Expense"],
                "Category": ["Salary", "Bonus", "Groceries", "Dining"],
                "Group": ["Income", "Income", "Food", "Food"],
                "Account": ["Checking"] * 4,
                "Month": ["2024-01"] * 4,
                "Full Description": ["PAYROLL", "BONUS", "STORE", "RESTAURANT"],
                "Institution": ["Bank"] * 4,
                "Account #": ["1234"] * 4,
            }
        )

        result = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
        ).iloc[0]

        assert result["Income"] == pytest.approx(4_500)
        assert result["Expense"] == pytest.approx(-350)
        assert result["Cash_Flow_Surplus"] == pytest.approx(4_150)

    def test_type_controls_flow_and_transfer_rows_are_excluded(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = pd.DataFrame(
            {
                "Date": pd.to_datetime(
                    ["2024-01-05", "2024-01-10", "2024-01-15"],
                    utc=True,
                ),
                "Amount": [50, 25, 5_000],
                "Type": ["Income", "Expense", "Transfer"],
                "Category": ["Refund", "Shopping", "Transfer"],
                "Group": ["Income", "Shopping", "Transfer"],
                "Account": ["Checking"] * 3,
                "Month": ["2024-01"] * 3,
                "Full Description": ["INCOME REFUND", "EXPENSE REFUND", "TRANSFER"],
                "Institution": ["Bank"] * 3,
                "Account #": ["1234"] * 3,
            }
        )

        result = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
        ).iloc[0]

        assert result["Income"] == pytest.approx(50)
        assert result["Expense"] == pytest.approx(25)
        assert result["Net_Expenses"] == pytest.approx(-25)
        assert result["Cash_Flow_Surplus"] == pytest.approx(75)
        assert result["Savings_Rate"] == pytest.approx(150)

    def test_months_sort_across_year_boundaries(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = pd.DataFrame(
            {
                "Date": pd.to_datetime(
                    ["2025-01-15", "2023-12-15", "2024-12-15", "2024-01-15"],
                    utc=True,
                ),
                "Amount": [1_300, 1_000, 1_200, 1_100],
                "Type": ["Income"] * 4,
                "Category": ["Salary"] * 4,
                "Group": ["Income"] * 4,
                "Account": ["Checking"] * 4,
                "Month": ["2025-01", "2023-12", "2024-12", "2024-01"],
                "Full Description": ["PAY"] * 4,
                "Institution": ["Bank"] * 4,
                "Account #": ["1234"] * 4,
            }
        )

        result = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
        )

        assert result["Month"].tolist() == ["2023-12", "2024-01", "2024-12", "2025-01"]

    def test_positive_penny_income_still_calculates_rate(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-15", "2024-01-16"], utc=True),
                "Amount": [0.50, -100],
                "Type": ["Income", "Expense"],
                "Category": ["Misc", "Groceries"],
                "Group": ["Income", "Food"],
                "Account": ["Checking"] * 2,
                "Month": ["2024-01"] * 2,
                "Full Description": ["MISC", "STORE"],
                "Institution": ["Bank"] * 2,
                "Account #": ["1234"] * 2,
            }
        )

        result = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
        ).iloc[0]

        assert result["Savings_Rate"] == pytest.approx((0.50 - 100) / 0.50 * 100)

    def test_excluded_group_is_removed(
        self,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        filters: IncomeExpenseFilters = {
            "exclude_groups": ["Food"],
            "exclude_income_categories": [],
            "exclude_expense_categories": [],
            "filter_large_income": False,
            "income_threshold": 50_000,
            "filter_large_expenses": False,
            "expense_threshold": 50_000,
            "target_rate": 20,
        }

        result = process_income_expense_data(
            make_transactions_spreadsheet(),
            filters,
        )

        assert abs(result["Expense"].sum()) == pytest.approx(95.0 + 200.0 + 79.99)
