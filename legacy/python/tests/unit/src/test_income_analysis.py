"""Behavior tests for the Income & Savings analysis model."""

import pandas as pd
import pytest

from src.analysis.income import (
    build_income_expense_ledger,
    calculate_savings_summary,
    process_income_expense_data,
    summarize_income_expense_ledger,
)
from src.custom_types import IncomeExpenseFilters, TransactionFilterOptions
from tests.custom_types import TransactionsSpreadsheetFactory


def _transactions(rows: list[dict[str, object]]) -> pd.DataFrame:
    columns = ["Month", "Amount", "Type", "Category", "Group", "Description"]
    transactions = pd.DataFrame(rows, columns=columns)
    transactions["Full Description"] = [str(row.get("Full Description", row["Description"])) for row in rows]
    return transactions


class TestBuildIncomeExpenseLedger:
    def test_annotates_group_and_category_exclusions(
        self,
        basic_filters: IncomeExpenseFilters,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": -500,
                    "Type": "Expense",
                    "Category": "Flight",
                    "Group": "Travel",
                    "Description": "AIRLINE",
                },
                {
                    "Month": "2024-01",
                    "Amount": 2_000,
                    "Type": "Income",
                    "Category": "Bonus",
                    "Group": "Income",
                    "Description": "BONUS",
                },
                {
                    "Month": "2024-01",
                    "Amount": -100,
                    "Type": "Expense",
                    "Category": "Groceries",
                    "Group": "Food",
                    "Description": "STORE",
                },
            ]
        )
        filters = basic_filters | {
            "exclude_groups": ["Travel"],
            "exclude_income_categories": ["Bonus"],
            "exclude_expense_categories": [],
        }

        ledger = build_income_expense_ledger(transactions, filters)

        reasons = dict(zip(ledger["Description"], ledger["Exclusion_Reason"], strict=True))
        included = dict(zip(ledger["Description"], ledger["Included"], strict=True))
        assert included == {"AIRLINE": False, "BONUS": False, "STORE": True}
        assert reasons["AIRLINE"] == "Excluded group: Travel"
        assert reasons["BONUS"] == "Excluded income category: Bonus"
        assert reasons["STORE"] == ""

    def test_reports_every_matching_exclusion_reason(
        self,
        basic_filters: IncomeExpenseFilters,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": -2_000,
                    "Type": "Expense",
                    "Category": "Flight",
                    "Group": "Travel",
                    "Description": "AIRLINE",
                },
            ]
        )
        filters = basic_filters | {
            "exclude_groups": ["Travel"],
            "exclude_expense_categories": ["Flight"],
            "filter_large_expenses": True,
            "expense_threshold": 1_000,
        }

        ledger = build_income_expense_ledger(transactions, filters)

        assert not bool(ledger.iloc[0]["Included"])
        assert ledger.iloc[0]["Exclusion_Reason"].split("; ") == [
            "Excluded group: Travel",
            "Excluded expense category: Flight",
            "Expense over $1,000",
        ]

    def test_amount_equal_to_threshold_remains_included(
        self,
        basic_filters: IncomeExpenseFilters,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": -1_000,
                    "Type": "Expense",
                    "Category": "Repair",
                    "Group": "Home",
                    "Description": "AT LIMIT",
                },
                {
                    "Month": "2024-01",
                    "Amount": -1_000.01,
                    "Type": "Expense",
                    "Category": "Repair",
                    "Group": "Home",
                    "Description": "OVER LIMIT",
                },
                {
                    "Month": "2024-01",
                    "Amount": 5_000,
                    "Type": "Income",
                    "Category": "Bonus",
                    "Group": "Income",
                    "Description": "INCOME AT LIMIT",
                },
                {
                    "Month": "2024-01",
                    "Amount": 5_000.01,
                    "Type": "Income",
                    "Category": "Bonus",
                    "Group": "Income",
                    "Description": "INCOME OVER LIMIT",
                },
            ]
        )
        filters = basic_filters | {
            "filter_large_expenses": True,
            "expense_threshold": 1_000,
            "filter_large_income": True,
            "income_threshold": 5_000,
        }

        ledger = build_income_expense_ledger(transactions, filters)

        included = dict(zip(ledger["Description"], ledger["Included"], strict=True))
        assert included == {
            "AT LIMIT": True,
            "OVER LIMIT": False,
            "INCOME AT LIMIT": True,
            "INCOME OVER LIMIT": False,
        }

    def test_exclusions_override_the_union_of_include_rules(self) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": -100,
                    "Type": "Expense",
                    "Category": "Flight",
                    "Group": "Travel",
                    "Description": "GROUP MATCH",
                },
                {
                    "Month": "2024-01",
                    "Amount": -100,
                    "Type": "Expense",
                    "Category": "Groceries",
                    "Group": "Food",
                    "Description": "CATEGORY MATCH",
                },
                {
                    "Month": "2024-01",
                    "Amount": -100,
                    "Type": "Expense",
                    "Category": "Dining",
                    "Group": "Food",
                    "Description": "NO MATCH",
                },
            ]
        )
        filters: TransactionFilterOptions = {
            "include_groups": ["Travel"],
            "include_categories": ["Groceries"],
            "exclude_groups": ["Travel"],
            "exclude_categories": ["Groceries"],
        }

        ledger = build_income_expense_ledger(transactions, filters)

        included = dict(zip(ledger["Description"], ledger["Included"], strict=True))
        assert included == {
            "GROUP MATCH": False,
            "CATEGORY MATCH": False,
            "NO MATCH": False,
        }
        assert ledger.loc[ledger["Description"] == "NO MATCH", "Exclusion_Reason"].item() == (
            "Outside included groups/categories/transactions"
        )

    def test_transaction_description_rules_apply_to_income_and_expenses(self) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": 1_000,
                    "Type": "Income",
                    "Category": "Salary",
                    "Group": "Income",
                    "Description": "PAYROLL",
                    "Full Description": "EMPLOYER PAYROLL",
                },
                {
                    "Month": "2024-01",
                    "Amount": -20,
                    "Type": "Expense",
                    "Category": "Coffee",
                    "Group": "Food",
                    "Description": "COFFEE",
                    "Full Description": "COFFEE CORNER",
                },
                {
                    "Month": "2024-01",
                    "Amount": -500,
                    "Type": "Expense",
                    "Category": "Tax",
                    "Group": "Bills",
                    "Description": "IRS",
                    "Full Description": "ACH IRS PAYMENT",
                },
            ]
        )
        filters: TransactionFilterOptions = {
            "include_transactions_like": ["coffee", "payroll"],
            "exclude_transactions_like": ["IRS"],
        }

        ledger = build_income_expense_ledger(transactions, filters)

        assert dict(zip(ledger["Description"], ledger["Included"], strict=True)) == {
            "PAYROLL": True,
            "COFFEE": True,
            "IRS": False,
        }
        assert ledger.loc[ledger["Description"] == "IRS", "Exclusion_Reason"].item() == (
            "Outside included groups/categories/transactions; Excluded transaction like: IRS"
        )

    def test_same_named_income_exclusion_does_not_exclude_expense(
        self,
        basic_filters: IncomeExpenseFilters,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": 1_000,
                    "Type": "Income",
                    "Category": "Shared Name",
                    "Group": "Income",
                    "Description": "INCOME",
                },
                {
                    "Month": "2024-01",
                    "Amount": -100,
                    "Type": "Expense",
                    "Category": "Shared Name",
                    "Group": "Food",
                    "Description": "EXPENSE",
                },
            ]
        )
        filters = basic_filters | {
            "exclude_income_categories": ["Shared Name"],
            "exclude_expense_categories": [],
        }

        ledger = build_income_expense_ledger(transactions, filters)

        included = dict(zip(ledger["Description"], ledger["Included"], strict=True))
        assert included == {"INCOME": False, "EXPENSE": True}
        assert ledger.loc[ledger["Description"] == "INCOME", "Exclusion_Reason"].item() == (
            "Excluded income category: Shared Name"
        )

    def test_retains_only_income_and_expense_rows_in_requested_period(
        self,
        basic_filters: IncomeExpenseFilters,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2023-12",
                    "Amount": 1_000,
                    "Type": "Income",
                    "Category": "Salary",
                    "Group": "Income",
                    "Description": "OLD",
                },
                {
                    "Month": "2024-01",
                    "Amount": 1_000,
                    "Type": "Income",
                    "Category": "Salary",
                    "Group": "Income",
                    "Description": "IN PERIOD",
                },
                {
                    "Month": "2024-01",
                    "Amount": -500,
                    "Type": "Transfer",
                    "Category": "Transfer",
                    "Group": "Transfer",
                    "Description": "TRANSFER",
                },
            ]
        )

        ledger = build_income_expense_ledger(
            transactions,
            basic_filters,
            start_month="2024-01",
            end_month="2024-02",
        )

        assert ledger["Description"].tolist() == ["IN PERIOD"]


class TestMonthlyCashFlow:
    def test_process_delegates_to_the_annotated_ledger(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": 1_000,
                    "Type": "Income",
                    "Category": "Salary",
                    "Group": "Income",
                    "Description": "PAY",
                },
                {
                    "Month": "2024-01",
                    "Amount": -500,
                    "Type": "Expense",
                    "Category": "Flight",
                    "Group": "Travel",
                    "Description": "AIRLINE",
                },
            ]
        )
        filters = basic_filters | {"exclude_groups": ["Travel"]}
        ledger = build_income_expense_ledger(
            transactions,
            filters,
            start_month="2024-01",
            end_month="2024-03",
        )

        from_ledger = summarize_income_expense_ledger(
            ledger,
            start_month="2024-01",
            end_month="2024-03",
        )
        from_spreadsheet = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            filters,
            start_month="2024-01",
            end_month="2024-03",
        )

        pd.testing.assert_frame_equal(from_ledger, from_spreadsheet)
        assert from_ledger["Cash_Flow_Surplus"].tolist() == [1_000, 0]

    def test_requested_period_includes_zero_activity_months(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": 1_000,
                    "Type": "Income",
                    "Category": "Salary",
                    "Group": "Income",
                    "Description": "PAY",
                },
                {
                    "Month": "2024-03",
                    "Amount": -400,
                    "Type": "Expense",
                    "Category": "Groceries",
                    "Group": "Food",
                    "Description": "STORE",
                },
            ]
        )

        monthly = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
            start_month="2024-01",
            end_month="2024-04",
        )

        assert monthly["Month"].tolist() == ["2024-01", "2024-02", "2024-03"]
        assert monthly.columns.tolist() == [
            "Month",
            "Income",
            "Expense",
            "Net_Expenses",
            "Cash_Flow_Surplus",
            "Savings_Rate",
        ]
        february = monthly.loc[monthly["Month"] == "2024-02"].iloc[0]
        assert february["Income"] == 0
        assert february["Net_Expenses"] == 0
        assert february["Cash_Flow_Surplus"] == 0
        assert pd.isna(february["Savings_Rate"])

    def test_empty_data_still_returns_every_requested_month(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        monthly = process_income_expense_data(
            make_transactions_spreadsheet(_transactions([])),
            basic_filters,
            start_month="2024-01",
            end_month="2024-04",
        )

        assert monthly["Month"].tolist() == ["2024-01", "2024-02", "2024-03"]
        assert (monthly[["Income", "Net_Expenses", "Cash_Flow_Surplus"]] == 0).all().all()
        assert monthly["Savings_Rate"].isna().all()

    def test_expense_refunds_reduce_net_expenses(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": 1_000,
                    "Type": "Income",
                    "Category": "Salary",
                    "Group": "Income",
                    "Description": "PAY",
                },
                {
                    "Month": "2024-01",
                    "Amount": -500,
                    "Type": "Expense",
                    "Category": "Shopping",
                    "Group": "Shopping",
                    "Description": "PURCHASE",
                },
                {
                    "Month": "2024-01",
                    "Amount": 200,
                    "Type": "Expense",
                    "Category": "Shopping",
                    "Group": "Shopping",
                    "Description": "REFUND",
                },
            ]
        )

        monthly = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
        )

        assert monthly.iloc[0]["Expense"] == pytest.approx(-300)
        assert monthly.iloc[0]["Net_Expenses"] == pytest.approx(300)
        assert monthly.iloc[0]["Cash_Flow_Surplus"] == pytest.approx(700)
        assert monthly.iloc[0]["Savings_Rate"] == pytest.approx(70)

    def test_net_refund_can_make_expenses_negative(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": 250,
                    "Type": "Expense",
                    "Category": "Shopping",
                    "Group": "Shopping",
                    "Description": "REFUND",
                },
            ]
        )

        monthly = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
        )

        assert monthly.iloc[0]["Net_Expenses"] == pytest.approx(-250)
        assert monthly.iloc[0]["Cash_Flow_Surplus"] == pytest.approx(250)
        assert pd.isna(monthly.iloc[0]["Savings_Rate"])

    def test_negative_income_has_no_savings_rate(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        transactions = _transactions(
            [
                {
                    "Month": "2024-01",
                    "Amount": -200,
                    "Type": "Income",
                    "Category": "Payroll correction",
                    "Group": "Income",
                    "Description": "CLAWBACK",
                },
                {
                    "Month": "2024-01",
                    "Amount": -100,
                    "Type": "Expense",
                    "Category": "Groceries",
                    "Group": "Food",
                    "Description": "STORE",
                },
            ]
        )

        monthly = process_income_expense_data(
            make_transactions_spreadsheet(transactions),
            basic_filters,
        )

        assert monthly.iloc[0]["Income"] == pytest.approx(-200)
        assert monthly.iloc[0]["Cash_Flow_Surplus"] == pytest.approx(-300)
        assert pd.isna(monthly.iloc[0]["Savings_Rate"])

    def test_requires_both_period_boundaries(
        self,
        basic_filters: IncomeExpenseFilters,
        make_transactions_spreadsheet: TransactionsSpreadsheetFactory,
    ) -> None:
        with pytest.raises(ValueError, match="provided together"):
            process_income_expense_data(
                make_transactions_spreadsheet(_transactions([])),
                basic_filters,
                start_month="2024-01",
            )


class TestSavingsSummary:
    def test_empty_period_returns_zero_totals_and_no_rate(self) -> None:
        assert calculate_savings_summary(pd.DataFrame()) == {
            "total_income": 0.0,
            "total_net_expenses": 0.0,
            "total_cash_flow_surplus": 0.0,
            "weighted_savings_rate": None,
            "average_monthly_surplus": 0.0,
            "positive_surplus_months": 0,
            "num_months": 0,
        }

    def test_calculates_authoritative_period_metrics(self) -> None:
        monthly = pd.DataFrame(
            [
                {
                    "Income": 4_000,
                    "Net_Expenses": 3_000,
                    "Cash_Flow_Surplus": 1_000,
                    "Savings_Rate": 25.0,
                },
                {
                    "Income": 6_000,
                    "Net_Expenses": 4_000,
                    "Cash_Flow_Surplus": 2_000,
                    "Savings_Rate": 100 / 3,
                },
                {
                    "Income": 0,
                    "Net_Expenses": 500,
                    "Cash_Flow_Surplus": -500,
                    "Savings_Rate": None,
                },
            ]
        )

        summary = calculate_savings_summary(monthly)

        assert summary["total_income"] == pytest.approx(10_000)
        assert summary["total_net_expenses"] == pytest.approx(7_500)
        assert summary["total_cash_flow_surplus"] == pytest.approx(2_500)
        assert summary["weighted_savings_rate"] == pytest.approx(25)
        assert summary["average_monthly_surplus"] == pytest.approx(2_500 / 3)
        assert summary["positive_surplus_months"] == 2
        assert summary["num_months"] == 3

    @pytest.mark.parametrize("income", [0, -500])
    def test_nonpositive_total_income_has_no_weighted_rate(self, income: float) -> None:
        monthly = pd.DataFrame(
            [
                {
                    "Income": income,
                    "Net_Expenses": 500,
                    "Cash_Flow_Surplus": income - 500,
                    "Savings_Rate": None,
                }
            ]
        )

        summary = calculate_savings_summary(monthly)

        assert summary["weighted_savings_rate"] is None

    def test_weighted_rate_uses_total_income_not_month_count(self) -> None:
        monthly = pd.DataFrame(
            [
                {
                    "Income": 100_000,
                    "Net_Expenses": 50_000,
                    "Cash_Flow_Surplus": 50_000,
                },
                *[
                    {
                        "Income": 1_000,
                        "Net_Expenses": 1_000,
                        "Cash_Flow_Surplus": 0,
                    }
                    for _ in range(11)
                ],
            ]
        )

        summary = calculate_savings_summary(monthly)

        assert summary["weighted_savings_rate"] == pytest.approx(50_000 / 111_000 * 100)
        assert summary["average_monthly_surplus"] == pytest.approx(50_000 / 12)
        assert summary["positive_surplus_months"] == 1
        assert summary["num_months"] == 12
