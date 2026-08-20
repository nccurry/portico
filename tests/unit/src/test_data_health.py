"""Tests for data-health analysis helpers."""

import pandas as pd

from src.analysis.data_health import (
    build_data_health_report,
    find_cash_flow_reversals,
    find_incomplete_transactions,
    find_missing_account_mappings,
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

    def test_cash_flow_reversals_label_refunds_and_income_reversals(self) -> None:
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Refund", "Amount": 10,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-02", "Category": "Clawback", "Amount": -20,
             "Account": "Checking", "Month": "2024-01", "Group": "Income", "Type": "Income"},
            {"Date": "2024-01-03", "Category": "Groceries", "Amount": -30,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        result = find_cash_flow_reversals(df)
        assert set(result["Category"]) == {"Refund", "Clawback"}
        assert result.set_index("Category")["Review_Reason"].to_dict() == {
            "Refund": "Expense refund",
            "Clawback": "Income reversal",
        }

    def test_incomplete_transactions_lists_missing_identifying_fields(self) -> None:
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "Groceries", "Amount": -10,
             "Account": "", "Month": "2024-01", "Group": "Food", "Type": "Expense",
             "Full Description": ""},
            {"Date": "2024-01-02", "Category": "Groceries", "Amount": -20,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense",
             "Full Description": "STORE"},
        ])
        result = find_incomplete_transactions(df)
        assert len(result) == 1
        assert result.iloc[0]["Missing_Fields"] == "Account, Full Description"

    def test_missing_account_mappings_uses_latest_rows(self) -> None:
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00", "Account": "Checking",
             "Account ID": "1", "Group": "", "Class": "Asset", "Balance": 100},
            {"Date": "2024-01-02", "Time": "2024-01-02 08:00", "Account": "Savings",
             "Account ID": "2", "Group": "Savings", "Class": "Asset", "Balance": 200},
        ])
        result = find_missing_account_mappings(df)
        assert len(result) == 1
        assert result.iloc[0]["Account"] == "Checking"
        assert result.iloc[0]["Missing_Fields"] == "Group"

    def test_missing_account_mappings_checks_identity_and_class(self) -> None:
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00", "Account": "Mystery",
             "Account ID": "", "Group": "Assets", "Class": "", "Balance": 100},
        ])
        result = find_missing_account_mappings(df)
        assert result.iloc[0]["Missing_Fields"] == "Account ID, Class"

    def test_missing_account_ids_do_not_collapse_distinct_accounts(self) -> None:
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00", "Account": "Checking",
             "Account ID": "", "Group": "Assets", "Class": "Asset", "Balance": 100},
            {"Date": "2024-01-02", "Time": "2024-01-02 08:00", "Account": "Savings",
             "Account ID": "", "Group": "Assets", "Class": "Asset", "Balance": 200},
        ])
        result = find_missing_account_mappings(df)
        assert set(result["Account"]) == {"Checking", "Savings"}

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
            as_of=pd.Timestamp("2024-01-12", tz="UTC"),
        )
        assert set(report) == {
            "uncategorized_transactions",
            "incomplete_transactions",
            "cash_flow_reversals",
            "missing_account_mappings",
            "stale_accounts",
        }
