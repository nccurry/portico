"""Tests for data-health analysis helpers."""

import pandas as pd

from src.analysis.data_health import (
    build_data_health_report,
    find_categories_without_budget,
    find_missing_account_mappings,
    find_sign_anomalies,
    find_stale_accounts,
    find_uncategorized_transactions,
)
from tests._helpers import _balance_df, _transactions_df


class TestDataHealth:

    def test_uncategorized_finds_missing_group_or_type(self) -> None:
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Mystery", "Amount": -10,
             "Account": "Checking", "Month": "2024-01", "Group": "Uncategorized", "Type": ""},
            {"Date": "2024-01-02", "Category": "Groceries", "Amount": -20,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = find_uncategorized_transactions(df)
        assert len(result) == 1
        assert result.iloc[0]["Category"] == "Mystery"

    def test_sign_anomalies_finds_positive_expense_and_negative_income(self) -> None:
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Refund", "Amount": 10,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "Clawback", "Amount": -20,
             "Account": "Checking", "Month": "2024-01", "Group": "Income", "Type": "Income"},
            {"Date": "2024-01-03", "Category": "Groceries", "Amount": -30,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = find_sign_anomalies(df)
        assert set(result["Category"]) == {"Refund", "Clawback"}

    def test_missing_account_mappings_uses_latest_rows(self) -> None:
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00", "Account": "Checking",
             "Account ID": "1", "Group": "", "Balance": 100},
            {"Date": "2024-01-02", "Time": "2024-01-02 08:00", "Account": "Savings",
             "Account ID": "2", "Group": "Savings", "Balance": 200},
        ])
        result = find_missing_account_mappings(df)
        assert len(result) == 1
        assert result.iloc[0]["Account"] == "Checking"

    def test_stale_accounts(self) -> None:
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00", "Account": "Old",
             "Account ID": "1", "Group": "Assets", "Balance": 100},
            {"Date": "2024-01-10", "Time": "2024-01-10 08:00", "Account": "Fresh",
             "Account ID": "2", "Group": "Assets", "Balance": 200},
        ])
        result = find_stale_accounts(df, as_of=pd.Timestamp("2024-01-12", tz="UTC"), stale_days=7)
        assert len(result) == 1
        assert result.iloc[0]["Account"] == "Old"
        assert result.iloc[0]["Days_Stale"] == 11

    def test_categories_without_budget(self) -> None:
        txns = _transactions_df([
            {"Date": "2024-01-01", "Category": "Groceries", "Amount": -100,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "Coffee", "Amount": -20,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        budget = pd.DataFrame({
            "Category": ["Groceries"],
            "Budget": [500],
        })
        result = find_categories_without_budget(txns, budget)
        assert len(result) == 1
        assert result.iloc[0]["Category"] == "Coffee"

    def test_report_contains_all_sections(self) -> None:
        txns = _transactions_df([
            {"Date": "2024-01-01", "Category": "Mystery", "Amount": 10,
             "Account": "Checking", "Month": "2024-01", "Group": "Uncategorized", "Type": "Expense"},
        ])
        balances = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00", "Account": "Checking",
             "Account ID": "1", "Group": "", "Balance": 100},
        ])
        report = build_data_health_report(
            txns,
            balances,
            pd.DataFrame(columns=["Category", "Budget"]),
            as_of=pd.Timestamp("2024-01-12", tz="UTC"),
        )
        assert set(report) == {
            "uncategorized_transactions",
            "sign_anomalies",
            "missing_account_mappings",
            "stale_accounts",
            "categories_without_budget",
        }
