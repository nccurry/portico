"""Tests for ``Spreadsheet.scrub()`` across all four sheet subclasses.

Covers:
    - ``TransactionsSpreadsheet.scrub`` and its category-join edge cases.
    - ``BalanceHistorySpreadsheet.scrub`` and its account-join edge cases.
    - ``CategoriesSpreadsheet.scrub`` and ``AccountsSpreadsheet.scrub``.
    - ``Spreadsheet.load`` error handling.
"""
from unittest.mock import patch

import pandas as pd
import pytest

from src.spreadsheet import (
    AccountsSpreadsheet,
    BalanceHistorySpreadsheet,
    CategoriesSpreadsheet,
    Spreadsheet,
    TransactionsSpreadsheet,
)


# ===================================================================
# TransactionsSpreadsheet.scrub()
# ===================================================================

class TestTransactionsScrub:

    def _make(self, raw_df: pd.DataFrame, categories_for_scrub: CategoriesSpreadsheet) -> TransactionsSpreadsheet:
        with (
            patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)),
            patch("src.spreadsheet.load_categories_data", return_value=categories_for_scrub),
        ):
            return TransactionsSpreadsheet()

    def test_scrub_drops_unnamed_column(self, scrub_input_transactions_df, categories_for_scrub):
        ts = self._make(scrub_input_transactions_df, categories_for_scrub)
        assert "Unnamed: 0" not in ts.scrubbed_df.columns

    def test_scrub_amount_parsed_as_float(
        self,
        scrub_input_transactions_df,
        categories_for_scrub,
    ):
        ts = self._make(scrub_input_transactions_df, categories_for_scrub)
        assert ts.scrubbed_df["Amount"].dtype == float
        assert ts.scrubbed_df["Amount"].iloc[0] == pytest.approx(1234.56)

    def test_scrub_date_is_datetime(self, scrub_input_transactions_df, categories_for_scrub):
        ts = self._make(scrub_input_transactions_df, categories_for_scrub)
        assert pd.api.types.is_datetime64_any_dtype(ts.scrubbed_df["Date"])

    def test_scrub_month_format(self, scrub_input_transactions_df, categories_for_scrub):
        ts = self._make(scrub_input_transactions_df, categories_for_scrub)
        assert ts.scrubbed_df["Month"].iloc[0] == "2024-01"

    def test_scrub_output_columns(self, scrub_input_transactions_df, categories_for_scrub):
        ts = self._make(scrub_input_transactions_df, categories_for_scrub)
        expected = {"Date", "Category", "Amount", "Account", "Month",
                    "Full Description", "Group", "Type", "Institution", "Account #"}
        assert set(ts.scrubbed_df.columns) == expected

    def test_scrub_joins_group_from_categories(
        self,
        scrub_input_transactions_df,
        categories_for_scrub,
    ):
        ts = self._make(scrub_input_transactions_df, categories_for_scrub)
        assert ts.scrubbed_df.iloc[0]["Group"] == "Food"
        assert ts.scrubbed_df.iloc[1]["Group"] == "Housing"

    def test_scrub_joins_type_from_categories(
        self,
        scrub_input_transactions_df,
        categories_for_scrub,
    ):
        ts = self._make(scrub_input_transactions_df, categories_for_scrub)
        assert ts.scrubbed_df.iloc[0]["Type"] == "Expense"

    def test_scrub_uncategorized_fallback(self, categories_for_scrub):
        """Categories not in the lookup get Group='Uncategorized'."""
        raw = pd.DataFrame({
            "Unnamed: 0": [None],
            "Date": ["2024-01-15"],
            "Category": ["UnknownCategory"],
            "Amount": ["$100.00"],
            "Account": ["Checking"],
            "Month": ["2024-01-01"],
            "Week": ["2024-01-15"],
            "Full Description": ["TEST"],
            "Institution": ["Bank"],
            "Account #": ["1234"],
            "Date Added": ["2024-01-15"],
            "Categorized Date": ["2024-01-15"],
        })
        ts = self._make(raw, categories_for_scrub)
        assert ts.scrubbed_df.iloc[0]["Group"] == "Uncategorized"

    def test_scrub_missing_unnamed_column(
        self,
        scrub_input_transactions_df,
        categories_for_scrub,
    ):
        """scrub() should not crash when 'Unnamed: 0' column is absent."""
        df_no_unnamed = scrub_input_transactions_df.drop("Unnamed: 0", axis=1)
        ts = self._make(df_no_unnamed, categories_for_scrub)
        assert "Unnamed: 0" not in ts.scrubbed_df.columns


# ===================================================================
# BalanceHistorySpreadsheet.scrub()
# ===================================================================

class TestBalanceScrub:

    def _make(self, raw_df: pd.DataFrame, accounts_for_scrub: AccountsSpreadsheet) -> BalanceHistorySpreadsheet:
        with (
            patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)),
            patch("src.spreadsheet.load_accounts_data", return_value=accounts_for_scrub),
        ):
            return BalanceHistorySpreadsheet()

    def test_scrub_missing_unnamed_column(self, scrub_input_balance_df, accounts_for_scrub):
        """scrub() should not crash when 'Unnamed: 0' column is absent."""
        df_no_unnamed = scrub_input_balance_df.drop("Unnamed: 0", axis=1)
        bs = self._make(df_no_unnamed, accounts_for_scrub)
        assert "Unnamed: 0" not in bs.scrubbed_df.columns

    def test_scrub_joins_group_from_accounts(self, scrub_input_balance_df, accounts_for_scrub):
        bs = self._make(scrub_input_balance_df, accounts_for_scrub)
        checking_rows = bs.scrubbed_df[bs.scrubbed_df["Account"] == "Checking"]
        assert all(checking_rows["Group"] == "Assets")

    def test_scrub_filters_hidden(self, scrub_input_balance_df, accounts_for_scrub):
        bs = self._make(scrub_input_balance_df, accounts_for_scrub)
        assert "Hidden" not in bs.scrubbed_df["Account"].values

    def test_scrub_balance_float(self, scrub_input_balance_df, accounts_for_scrub):
        bs = self._make(scrub_input_balance_df, accounts_for_scrub)
        assert bs.scrubbed_df["Balance"].dtype == float


# ===================================================================
# Spreadsheet.load() error handling
# ===================================================================

class TestLoadErrorHandling:

    def test_load_calls_st_stop_on_failure(self):
        """When st.connection raises, load() shows an error and calls st.stop()."""
        with (
            patch("src.spreadsheet.st.connection", side_effect=RuntimeError("no creds")),
            patch("src.spreadsheet.st.error") as mock_error,
            patch("src.spreadsheet.st.info"),
            patch("src.spreadsheet.st.stop") as mock_stop,
            patch.object(TransactionsSpreadsheet, "scrub"),
        ):
            TransactionsSpreadsheet()
            mock_error.assert_called_once()
            assert "no creds" in mock_error.call_args[0][0]
            mock_stop.assert_called_once()


# ===================================================================
# CategoriesSpreadsheet.scrub()
# ===================================================================

class TestCategoriesScrub:

    def _make(self, raw_df: pd.DataFrame) -> CategoriesSpreadsheet:
        with patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)):
            return CategoriesSpreadsheet()

    def test_scrub_keeps_expected_columns(self):
        raw = pd.DataFrame({
            "Category": ["Groceries", "Rent"],
            "Group": ["Food", "Housing"],
            "Type": ["Expense", "Expense"],
            "Hide From Reports": ["", "Hide"],
            "Jan 2024": [100, 200],
            "Feb 2024": [100, 200],
        })
        cs = self._make(raw)
        assert set(cs.scrubbed_df.columns) == {"Category", "Group", "Type", "Hide From Reports"}

    def test_scrub_drops_rows_with_null_category(self):
        raw = pd.DataFrame({
            "Category": ["Groceries", None, "Rent"],
            "Group": ["Food", "Bills", "Housing"],
            "Type": ["Expense", "Expense", "Expense"],
            "Hide From Reports": ["", "", ""],
        })
        cs = self._make(raw)
        assert len(cs.scrubbed_df) == 2
        assert "Groceries" in cs.scrubbed_df["Category"].values
        assert "Rent" in cs.scrubbed_df["Category"].values


# ===================================================================
# AccountsSpreadsheet.scrub()
# ===================================================================

class TestAccountsScrub:

    def _make(self, raw_df: pd.DataFrame) -> AccountsSpreadsheet:
        with patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)):
            return AccountsSpreadsheet()

    def test_scrub_uses_first_four_columns(self):
        raw = pd.DataFrame({
            "col_a": ["Checking - xxxx1234 (AB01)", "Savings - xxxx5678 (CD02)"],
            "col_b": [None, "Asset"],
            "col_c": ["Checking", "Savings"],
            "col_d": ["", "Hide"],
            "col_e": ["extra1", "extra2"],
            "col_f": ["extra3", "extra4"],
        })
        accts = self._make(raw)
        assert set(accts.scrubbed_df.columns) == {"Account", "Group", "Hide"}
        assert len(accts.scrubbed_df) == 2

    def test_scrub_drops_rows_with_null_account(self):
        raw = pd.DataFrame({
            "col_a": ["Checking - xxxx1234 (AB01)", None, "Savings - xxxx5678 (CD02)"],
            "col_b": [None, None, "Asset"],
            "col_c": ["Checking", "", "Savings"],
            "col_d": ["", "", ""],
        })
        accts = self._make(raw)
        assert len(accts.scrubbed_df) == 2


# ===================================================================
# Balance History scrub - join edge cases
# ===================================================================

class TestBalanceScrubJoinEdgeCases:

    def _make(self, raw_df: pd.DataFrame, accounts: AccountsSpreadsheet) -> BalanceHistorySpreadsheet:
        with (
            patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)),
            patch("src.spreadsheet.load_accounts_data", return_value=accounts),
        ):
            return BalanceHistorySpreadsheet()

    def test_case_insensitive_join(self):
        """Account names with different casing should still match."""
        raw = pd.DataFrame({
            "Date": ["2024-01-01"],
            "Time": ["2024-01-01 08:00"],
            "Balance": ["$1,000.00"],
            "Account": ["CREDIT CARD (-6403)"],
            "Account #": ["xxxx6403"],
            "Account ID": ["65440a84a14656002f355cba"],
            "Institution": ["Chase"],
            "Class": ["Liability"],
            "Month": ["2024-01-01"],
            "Week": ["2024-01-01"],
            "Date Added": ["2024-01-01"],
        })
        acct = AccountsSpreadsheet.__new__(AccountsSpreadsheet)
        acct.scrubbed_df = pd.DataFrame({
            "Account": ["Credit Card (-6403) - xxxx6403 (5CBA)"],
            "Group": ["Credit Card"],
            "Hide": [""],
        })
        bs = self._make(raw, acct)
        assert bs.scrubbed_df.iloc[0]["Group"] == "Credit Card"

    def test_null_account_number_builds_key(self):
        """Accounts with empty Account # (like Equity Awards) should still match."""
        raw = pd.DataFrame({
            "Date": ["2024-01-01"],
            "Time": ["2024-01-01 08:00"],
            "Balance": ["$180,000.00"],
            "Account": ["Equity Awards"],
            "Account #": [None],
            "Account ID": ["65440ec86c2203002f1bcbe8"],
            "Institution": ["Schwab"],
            "Class": ["Asset"],
            "Month": ["2024-01-01"],
            "Week": ["2024-01-01"],
            "Date Added": ["2024-01-01"],
        })
        acct = AccountsSpreadsheet.__new__(AccountsSpreadsheet)
        acct.scrubbed_df = pd.DataFrame({
            "Account": ["Equity Awards -  (CBE8)"],
            "Group": ["Investment"],
            "Hide": [""],
        })
        bs = self._make(raw, acct)
        assert bs.scrubbed_df.iloc[0]["Group"] == "Investment"

    def test_unmatched_account_gets_empty_group(self):
        """Accounts not in the Accounts sheet get Group='' instead of NaN."""
        raw = pd.DataFrame({
            "Date": ["2024-01-01"],
            "Time": ["2024-01-01 08:00"],
            "Balance": ["$500.00"],
            "Account": ["Brand New Account"],
            "Account #": ["xxxx9999"],
            "Account ID": ["65440a84a14656002f35ffff"],
            "Institution": ["Bank"],
            "Class": ["Asset"],
            "Month": ["2024-01-01"],
            "Week": ["2024-01-01"],
            "Date Added": ["2024-01-01"],
        })
        acct = AccountsSpreadsheet.__new__(AccountsSpreadsheet)
        acct.scrubbed_df = pd.DataFrame({
            "Account": pd.Series([], dtype=str),
            "Group": pd.Series([], dtype=str),
            "Hide": pd.Series([], dtype=str),
        })
        bs = self._make(raw, acct)
        assert bs.scrubbed_df.iloc[0]["Group"] == ""
        assert bs.scrubbed_df.iloc[0]["Hide"] == ""

    def test_no_group_or_hide_columns_in_raw_data(self):
        """Balance History from API may not have Group/Hide columns at all."""
        raw = pd.DataFrame({
            "Date": ["2024-01-01"],
            "Time": ["2024-01-01 08:00"],
            "Balance": ["$1,000.00"],
            "Account": ["Checking"],
            "Account #": ["xxxx1234"],
            "Account ID": ["65440a84a14656002f35ab01"],
            "Institution": ["Bank"],
            "Class": ["Asset"],
            "Month": ["2024-01-01"],
            "Week": ["2024-01-01"],
            "Date Added": ["2024-01-01"],
        })
        acct = AccountsSpreadsheet.__new__(AccountsSpreadsheet)
        acct.scrubbed_df = pd.DataFrame({
            "Account": ["Checking - xxxx1234 (AB01)"],
            "Group": ["Checking"],
            "Hide": [""],
        })
        bs = self._make(raw, acct)
        assert bs.scrubbed_df.iloc[0]["Group"] == "Checking"

    def test_legacy_group_hide_columns_are_dropped_before_join(self):
        """If raw data has legacy Group/Hide columns, they should be replaced by the join."""
        raw = pd.DataFrame({
            "Date": ["2024-01-01"],
            "Time": ["2024-01-01 08:00"],
            "Balance": ["$1,000.00"],
            "Account": ["Checking"],
            "Account #": ["xxxx1234"],
            "Account ID": ["65440a84a14656002f35ab01"],
            "Institution": ["Bank"],
            "Class": ["Asset"],
            "Month": ["2024-01-01"],
            "Week": ["2024-01-01"],
            "Date Added": ["2024-01-01"],
            "Group": ["WRONG GROUP"],
            "Hide": ["WRONG"],
        })
        acct = AccountsSpreadsheet.__new__(AccountsSpreadsheet)
        acct.scrubbed_df = pd.DataFrame({
            "Account": ["Checking - xxxx1234 (AB01)"],
            "Group": ["Checking"],
            "Hide": [""],
        })
        bs = self._make(raw, acct)
        assert bs.scrubbed_df.iloc[0]["Group"] == "Checking"
        assert bs.scrubbed_df.iloc[0]["Hide"] == ""


# ===================================================================
# Transactions scrub - join edge cases
# ===================================================================

class TestTransactionsScrubJoinEdgeCases:

    def _make(self, raw_df: pd.DataFrame, categories: CategoriesSpreadsheet) -> TransactionsSpreadsheet:
        with (
            patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)),
            patch("src.spreadsheet.load_categories_data", return_value=categories),
        ):
            return TransactionsSpreadsheet()

    def _raw(self, categories: list[str], amounts: list[str] | None = None) -> pd.DataFrame:
        """Build a minimal raw transactions DataFrame."""
        n = len(categories)
        if amounts is None:
            amounts = ["$100.00"] * n
        return pd.DataFrame({
            "Date": ["2024-01-15"] * n,
            "Category": categories,
            "Amount": amounts,
            "Account": ["Checking"] * n,
            "Month": ["2024-01-01"] * n,
            "Week": ["2024-01-15"] * n,
            "Full Description": ["TEST"] * n,
            "Institution": ["Bank"] * n,
            "Account #": ["1234"] * n,
            "Date Added": ["2024-01-15"] * n,
            "Categorized Date": ["2024-01-15"] * n,
        })

    def test_multiple_uncategorized(self):
        """Multiple unknown categories all get Group='Uncategorized'."""
        cat = CategoriesSpreadsheet.__new__(CategoriesSpreadsheet)
        cat.scrubbed_df = pd.DataFrame({
            "Category": ["Groceries"],
            "Group": ["Food"],
            "Type": ["Expense"],
            "Hide From Reports": [""],
        })
        raw = self._raw(["Unknown1", "Unknown2", "Groceries"])
        ts = self._make(raw, cat)
        groups = ts.scrubbed_df["Group"].tolist()
        assert groups[0] == "Uncategorized"
        assert groups[1] == "Uncategorized"
        assert groups[2] == "Food"

    def test_type_defaults_to_empty_for_unknown(self):
        """Unknown categories get Type='' not NaN."""
        cat = CategoriesSpreadsheet.__new__(CategoriesSpreadsheet)
        cat.scrubbed_df = pd.DataFrame({
            "Category": pd.Series([], dtype=str),
            "Group": pd.Series([], dtype=str),
            "Type": pd.Series([], dtype=str),
            "Hide From Reports": pd.Series([], dtype=str),
        })
        raw = self._raw(["NewCategory"])
        ts = self._make(raw, cat)
        assert ts.scrubbed_df.iloc[0]["Type"] == ""

    def test_legacy_group_type_columns_are_replaced(self):
        """If raw data has legacy Group/Type columns from VLOOKUPs, they're replaced by the join."""
        cat = CategoriesSpreadsheet.__new__(CategoriesSpreadsheet)
        cat.scrubbed_df = pd.DataFrame({
            "Category": ["Groceries"],
            "Group": ["Food"],
            "Type": ["Expense"],
            "Hide From Reports": [""],
        })
        raw = self._raw(["Groceries"])
        raw["Group"] = ["WRONG"]
        raw["Type"] = ["WRONG"]
        raw["Hide From Reports"] = ["WRONG"]
        ts = self._make(raw, cat)
        assert ts.scrubbed_df.iloc[0]["Group"] == "Food"
        assert ts.scrubbed_df.iloc[0]["Type"] == "Expense"

    def test_negative_amounts_preserved(self):
        """Negative dollar amounts with special formatting are parsed correctly."""
        cat = CategoriesSpreadsheet.__new__(CategoriesSpreadsheet)
        cat.scrubbed_df = pd.DataFrame({
            "Category": ["Groceries"],
            "Group": ["Food"],
            "Type": ["Expense"],
            "Hide From Reports": [""],
        })
        raw = self._raw(["Groceries"], ["-$1,234.56"])
        ts = self._make(raw, cat)
        assert ts.scrubbed_df.iloc[0]["Amount"] == pytest.approx(-1234.56)
