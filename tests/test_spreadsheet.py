"""Tests for src/spreadsheet.py."""
import pytest
import pandas as pd
from unittest.mock import patch
from src.spreadsheet import (
    Spreadsheet,
    TransactionsSpreadsheet,
    BalanceHistorySpreadsheet,
    calculate_group_sparkline,
    calculate_net_worth_sparkline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(year, month, day):
    """Return a timezone-aware UTC datetime."""
    return pd.Timestamp(year, month, day, tz="UTC")


def _transactions_df(rows):
    """Build a minimal scrubbed transactions DataFrame from a list of dicts.

    Each dict should contain Date, Category, Amount, Account, Month, Group,
    Type (and optionally Full Description, Institution, Account #).
    """
    defaults = {
        "Full Description": "",
        "Institution": "",
        "Account #": "",
    }
    records = [{**defaults, **r} for r in rows]
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    df["Amount"] = df["Amount"].astype(float)
    return df


def _balance_df(rows):
    """Build a minimal scrubbed balance-history DataFrame from a list of dicts."""
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    if "Time" in df.columns:
        df["Time"] = pd.to_datetime(df["Time"], utc=True)
    df["Balance"] = df["Balance"].astype(float)
    return df


# ---------------------------------------------------------------------------
# Raw DataFrames for scrub() tests
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_transactions_df():
    """A raw DataFrame that TransactionsSpreadsheet.scrub() should clean."""
    return pd.DataFrame({
        "Unnamed: 0": [None, None],
        "Date": ["2024-01-15", "2024-02-20"],
        "Category": ["Groceries", "Rent"],
        "Amount": ["$1,234.56", "$2,000.00"],
        "Account": ["Checking", "Checking"],
        "Month": ["2024-01-01", "2024-02-01"],
        "Week": ["2024-01-15", "2024-02-19"],
        "Full Description": ["STORE", "LANDLORD"],
        "Institution": ["Bank", "Bank"],
        "Account #": ["1234", "5678"],
        "Date Added": ["2024-01-15", "2024-02-20"],
        "Categorized Date": ["2024-01-15", "2024-02-20"],
    })


@pytest.fixture
def raw_balance_df():
    """A raw DataFrame that BalanceHistorySpreadsheet.scrub() should clean."""
    return pd.DataFrame({
        "Unnamed: 0": [None, None, None],
        "Date": ["2024-01-15", "2024-02-20", "2024-03-01"],
        "Time": ["2024-01-15 10:00", "2024-02-20 11:00", "2024-03-01 09:00"],
        "Balance": ["$1,000.00", "$2,000.00", "$500.00"],
        "Account": ["Checking", "Savings", "Hidden"],
        "Account #": ["xxxx1234", "xxxx5678", "xxxx9999"],
        "Account ID": ["65440a84a14656002f35ab01", "65440a84a14656002f35cd02", "65440a84a14656002f35ef03"],
        "Institution": ["Bank", "Bank", "Bank"],
        "Class": ["Asset", "Asset", "Asset"],
        "Month": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "Week": ["2024-01-15", "2024-02-19", "2024-02-26"],
        "Date Added": ["2024-01-15", "2024-02-20", "2024-03-01"],
    })


@pytest.fixture
def categories_for_scrub():
    """Categories lookup for scrub tests."""
    from src.spreadsheet import CategoriesSpreadsheet
    cat = CategoriesSpreadsheet.__new__(CategoriesSpreadsheet)
    cat.scrubbed_df = pd.DataFrame({
        "Category": ["Groceries", "Rent"],
        "Group": ["Food", "Housing"],
        "Type": ["Expense", "Expense"],
        "Hide From Reports": ["", ""],
    })
    return cat


@pytest.fixture
def accounts_for_scrub():
    """Accounts lookup for scrub tests. Keys match the composite key format."""
    from src.spreadsheet import AccountsSpreadsheet
    acct = AccountsSpreadsheet.__new__(AccountsSpreadsheet)
    # Column A from Accounts sheet (composite key format, mixed case like real data)
    acct.scrubbed_df = pd.DataFrame({
        "Account": [
            "Checking - xxxx1234 (AB01)",
            "SAVINGS - xxxx5678 (CD02)",
            "Hidden - xxxx9999 (EF03)",
        ],
        "Group": ["Assets", "Assets", "Secret"],
        "Hide": ["", "", "Hide"],
    })
    return acct



# ---------------------------------------------------------------------------
# Sample scrubbed data used by most tests
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_transactions_df():
    return _transactions_df([
        {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,  "Account": "Checking", "Month": "2024-01", "Group": "Food",      "Type": "Expense"},
        {"Date": "2024-01-20", "Category": "Rent",      "Amount": -1200,"Account": "Checking", "Month": "2024-01", "Group": "Housing",   "Type": "Expense"},
        {"Date": "2024-02-05", "Category": "Groceries", "Amount": -60,  "Account": "Checking", "Month": "2024-02", "Group": "Food",      "Type": "Expense"},
        {"Date": "2024-02-15", "Category": "Salary",    "Amount": 3000, "Account": "Checking", "Month": "2024-02", "Group": "Income",    "Type": "Income"},
        {"Date": "2024-03-01", "Category": "Dining",    "Amount": -30,  "Account": "Credit",   "Month": "2024-03", "Group": "Food",      "Type": "Expense"},
        {"Date": "2024-03-10", "Category": "Transfer",  "Amount": 500,  "Account": "Savings",  "Month": "2024-03", "Group": "Transfers", "Type": "Transfer"},
    ])


@pytest.fixture
def sample_balance_df():
    return _balance_df([
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1", "Institution": "Bank", "Group": "Assets",      "Class": "Asset",     "Balance": 5000, "Hide": ""},
        {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "Checking", "Account ID": "a1", "Institution": "Bank", "Group": "Assets",      "Class": "Asset",     "Balance": 4500, "Hide": ""},
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Savings",  "Account ID": "a2", "Institution": "Bank", "Group": "Assets",      "Class": "Asset",     "Balance": 10000,"Hide": ""},
        {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "Savings",  "Account ID": "a2", "Institution": "Bank", "Group": "Assets",      "Class": "Asset",     "Balance": 10500,"Hide": ""},
        {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Mortgage",  "Account ID": "a3", "Institution": "Lender","Group": "Liabilities","Class": "Liability", "Balance": 200000,"Hide": ""},
        {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "Mortgage",  "Account ID": "a3", "Institution": "Lender","Group": "Liabilities","Class": "Liability", "Balance": 199500,"Hide": ""},
    ])


# ===================================================================
# TransactionsSpreadsheet.scrub()
# ===================================================================

class TestTransactionsScrub:

    def _make(self, raw_df, categories_for_scrub):
        with (
            patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)),
            patch("src.spreadsheet.load_categories_data", return_value=categories_for_scrub),
        ):
            return TransactionsSpreadsheet()

    def test_scrub_drops_unnamed_column(self, raw_transactions_df, categories_for_scrub):
        ts = self._make(raw_transactions_df, categories_for_scrub)
        assert "Unnamed: 0" not in ts.scrubbed_df.columns

    def test_scrub_amount_parsed_as_float(self, raw_transactions_df, categories_for_scrub):
        ts = self._make(raw_transactions_df, categories_for_scrub)
        assert ts.scrubbed_df["Amount"].dtype == float
        assert ts.scrubbed_df["Amount"].iloc[0] == pytest.approx(1234.56)

    def test_scrub_date_is_datetime(self, raw_transactions_df, categories_for_scrub):
        ts = self._make(raw_transactions_df, categories_for_scrub)
        assert pd.api.types.is_datetime64_any_dtype(ts.scrubbed_df["Date"])

    def test_scrub_month_format(self, raw_transactions_df, categories_for_scrub):
        ts = self._make(raw_transactions_df, categories_for_scrub)
        assert ts.scrubbed_df["Month"].iloc[0] == "2024-01"

    def test_scrub_output_columns(self, raw_transactions_df, categories_for_scrub):
        ts = self._make(raw_transactions_df, categories_for_scrub)
        expected = {"Date", "Category", "Amount", "Account", "Month",
                    "Full Description", "Group", "Type", "Institution", "Account #"}
        assert set(ts.scrubbed_df.columns) == expected

    def test_scrub_joins_group_from_categories(self, raw_transactions_df, categories_for_scrub):
        ts = self._make(raw_transactions_df, categories_for_scrub)
        assert ts.scrubbed_df.iloc[0]["Group"] == "Food"       # Groceries -> Food
        assert ts.scrubbed_df.iloc[1]["Group"] == "Housing"    # Rent -> Housing

    def test_scrub_joins_type_from_categories(self, raw_transactions_df, categories_for_scrub):
        ts = self._make(raw_transactions_df, categories_for_scrub)
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

    def test_scrub_missing_unnamed_column(self, raw_transactions_df, categories_for_scrub):
        """scrub() should not crash when 'Unnamed: 0' column is absent."""
        df_no_unnamed = raw_transactions_df.drop("Unnamed: 0", axis=1)
        ts = self._make(df_no_unnamed, categories_for_scrub)
        assert "Unnamed: 0" not in ts.scrubbed_df.columns


# ===================================================================
# BalanceHistorySpreadsheet.scrub() — missing column
# ===================================================================

class TestBalanceScrub:

    def _make(self, raw_df, accounts_for_scrub):
        with (
            patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)),
            patch("src.spreadsheet.load_accounts_data", return_value=accounts_for_scrub),
        ):
            return BalanceHistorySpreadsheet()

    def test_scrub_missing_unnamed_column(self, raw_balance_df, accounts_for_scrub):
        """scrub() should not crash when 'Unnamed: 0' column is absent."""
        df_no_unnamed = raw_balance_df.drop("Unnamed: 0", axis=1)
        bs = self._make(df_no_unnamed, accounts_for_scrub)
        assert "Unnamed: 0" not in bs.scrubbed_df.columns

    def test_scrub_joins_group_from_accounts(self, raw_balance_df, accounts_for_scrub):
        bs = self._make(raw_balance_df, accounts_for_scrub)
        checking_rows = bs.scrubbed_df[bs.scrubbed_df["Account"] == "Checking"]
        assert all(checking_rows["Group"] == "Assets")

    def test_scrub_filters_hidden(self, raw_balance_df, accounts_for_scrub):
        bs = self._make(raw_balance_df, accounts_for_scrub)
        assert "Hidden" not in bs.scrubbed_df["Account"].values

    def test_scrub_balance_float(self, raw_balance_df, accounts_for_scrub):
        bs = self._make(raw_balance_df, accounts_for_scrub)
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
# get_total_months / get_groups / get_group_categories
# ===================================================================

class TestTransactionsMetadata:

    def test_get_total_months(self, make_transactions_spreadsheet):
        """get_total_months divides timedelta by np.timedelta64(1,'M')."""
        rows = [
            {"Date": "2024-01-10", "Category": "A", "Amount": -10, "Account": "C",
             "Month": "2024-01", "Group": "G", "Type": "Expense"},
            {"Date": "2024-03-10", "Category": "B", "Amount": -20, "Account": "C",
             "Month": "2024-03", "Group": "G", "Type": "Expense"},
        ]
        defaults = {"Full Description": "", "Institution": "", "Account #": ""}
        records = [{**defaults, **r} for r in rows]
        df = pd.DataFrame(records)
        df["Date"] = pd.to_datetime(df["Date"])
        df["Amount"] = df["Amount"].astype(float)
        ts = make_transactions_spreadsheet(df)
        months = ts.get_total_months()
        assert months == 2

    def test_get_groups(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        groups = list(ts.get_groups())
        assert "Food" in groups
        assert "Housing" in groups
        assert "Income" in groups

    def test_get_group_categories(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        cats = list(ts.get_group_categories("Food"))
        assert "Groceries" in cats
        assert "Dining" in cats
        assert "Rent" not in cats


# ===================================================================
# filter_transactions
# ===================================================================

class TestFilterTransactions:

    def test_no_filters(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions()
        assert len(result) == len(sample_transactions_df)

    def test_include_categories(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(include_categories=["Groceries"])
        assert all(result["Category"] == "Groceries")
        assert len(result) == 2

    def test_ignore_categories(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(ignore_categories=["Groceries"])
        assert "Groceries" not in result["Category"].values

    def test_include_groups(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(include_groups=["Food"])
        assert all(result["Group"] == "Food")

    def test_ignore_groups(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(ignore_groups=["Food"])
        assert "Food" not in result["Group"].values

    def test_include_types(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(include_types=["Income"])
        assert all(result["Type"] == "Income")

    def test_ignore_types_filters_type_column(self, sample_transactions_df, make_transactions_spreadsheet):
        """ignore_types should exclude rows by Type, not Group."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(ignore_types=["Transfer"])
        # After ignoring Transfer type, no Transfer rows should remain
        assert "Transfer" not in result["Type"].values

    def test_include_and_ignore_same_axis(self, sample_transactions_df, make_transactions_spreadsheet):
        """ignore_categories is applied after include_categories, so ignore wins."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(
            include_categories=["Groceries", "Rent"],
            ignore_categories=["Rent"],
        )
        assert "Groceries" in result["Category"].values
        assert "Rent" not in result["Category"].values

    def test_date_range(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        start = _utc(2024, 2, 1)
        end = _utc(2024, 2, 28)
        result = ts.filter_transactions(start_date=start, end_date=end)
        assert all((result["Date"] >= start) & (result["Date"] <= end))

    def test_filtered_columns(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(filtered_columns=["Date", "Amount"])
        assert list(result.columns) == ["Date", "Amount"]

    def test_group_by_column(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.filter_transactions(group_by_column="Group")
        assert "Amount" in result.columns
        assert "Food" in result.index

    def test_empty_df(self, make_transactions_spreadsheet):
        empty = pd.DataFrame({
            "Date": pd.Series([], dtype="datetime64[ns, UTC]"),
            "Category": pd.Series([], dtype=str),
            "Amount": pd.Series([], dtype=float),
            "Account": pd.Series([], dtype=str),
            "Month": pd.Series([], dtype=str),
            "Full Description": pd.Series([], dtype=str),
            "Group": pd.Series([], dtype=str),
            "Type": pd.Series([], dtype=str),
            "Institution": pd.Series([], dtype=str),
            "Account #": pd.Series([], dtype=str),
        })
        ts = make_transactions_spreadsheet(empty)
        result = ts.filter_transactions()
        assert len(result) == 0


# ===================================================================
# get_amount_by_group
# ===================================================================

class TestGetAmountByGroup:

    def test_basic(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group()
        assert "Amount" in result.columns
        # Food group: -50 + -60 + -30 = -140
        assert result.loc["Food", "Amount"] == pytest.approx(-140)

    def test_invert_amount(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group(invert_amount=True)
        assert result.loc["Food", "Amount"] == pytest.approx(140)

    def test_ignore_types_filters_type_column(self, make_transactions_spreadsheet):
        """ignore_types=['Transfer'] removes Transfer-typed rows regardless of group name."""
        df = _transactions_df([
            {"Date": "2024-01-01", "Category": "A", "Amount": 100, "Account": "C",
             "Month": "2024-01", "Group": "Savings", "Type": "Transfer"},
            {"Date": "2024-01-02", "Category": "B", "Amount": 200, "Account": "C",
             "Month": "2024-01", "Group": "Savings", "Type": "Income"},
        ])
        ts = make_transactions_spreadsheet(df)
        result = ts.get_amount_by_group(ignore_types=["Transfer"])
        # After ignoring Transfer type, only the Income row (200) should remain
        assert result.loc["Savings", "Amount"] == pytest.approx(200)


# ===================================================================
# get_amount_by_group_category
# ===================================================================

class TestGetAmountByGroupCategory:

    def test_basic(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("Food")
        assert "Groceries" in result.index
        assert "Dining" in result.index
        assert result.loc["Groceries", "Amount"] == pytest.approx(-110)

    def test_invert(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("Food", invert_amount=True)
        assert result.loc["Groceries", "Amount"] == pytest.approx(110)

    def test_empty_group(self, sample_transactions_df, make_transactions_spreadsheet):
        """A group that doesn't exist returns an empty DataFrame."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("NonExistent")
        assert result.empty

    def test_include_categories_narrows_within_group(self, sample_transactions_df, make_transactions_spreadsheet):
        """include_categories combined with group filter returns only matching categories."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("Food", include_categories=["Groceries"])
        assert "Groceries" in result.index
        assert "Dining" not in result.index

    def test_include_categories_outside_group_returns_empty(self, sample_transactions_df, make_transactions_spreadsheet):
        """A category not in the requested group returns nothing."""
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_amount_by_group_category("Food", include_categories=["Rent"])
        assert result.empty


# ===================================================================
# get_monthly_amounts_by_category / group
# ===================================================================

class TestMonthlyAmounts:

    def test_monthly_by_category(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_monthly_amounts_by_category("Groceries")
        assert "2024-01" in result.index
        assert "2024-02" in result.index
        assert result.loc["2024-01", "Amount"] == pytest.approx(-50)

    def test_monthly_by_category_invert(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_monthly_amounts_by_category("Groceries", invert_amount=True)
        assert result.loc["2024-01", "Amount"] == pytest.approx(50)

    def test_monthly_by_group(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_monthly_amounts_by_group("Food")
        assert "2024-01" in result.index
        # Jan: Groceries -50
        assert result.loc["2024-01", "Amount"] == pytest.approx(-50)
        # Mar: Dining -30
        assert result.loc["2024-03", "Amount"] == pytest.approx(-30)

    def test_monthly_by_group_invert(self, sample_transactions_df, make_transactions_spreadsheet):
        ts = make_transactions_spreadsheet(sample_transactions_df)
        result = ts.get_monthly_amounts_by_group("Food", invert_amount=True)
        assert result.loc["2024-01", "Amount"] == pytest.approx(50)



# ===================================================================
# Balance history methods
# ===================================================================

class TestBalanceHistory:

    def test_latest_balance_tuple_and_total(self, sample_balance_df, make_balance_spreadsheet):
        bs = make_balance_spreadsheet(sample_balance_df)
        df_result, total = bs.get_latest_balance_by_group("Assets")
        # Latest balances: Checking 4500, Savings 10500
        assert total == pytest.approx(15000)
        assert isinstance(df_result, pd.DataFrame)
        assert set(df_result.columns) == {"Account", "Balance"}

    def test_latest_balance_with_end_date(self, sample_balance_df, make_balance_spreadsheet):
        bs = make_balance_spreadsheet(sample_balance_df)
        # Only data up to Jan 1 — only the Jan 1 entries are the latest per account
        df_result, total = bs.get_latest_balance_by_group("Assets", end_date=_utc(2024, 1, 1))
        assert total == pytest.approx(15000)

    def test_get_groups(self, sample_balance_df, make_balance_spreadsheet):
        bs = make_balance_spreadsheet(sample_balance_df)
        groups = list(bs.get_groups())
        assert "Assets" in groups
        assert "Liabilities" in groups

    def test_balance_history_by_account_reindexes(self, sample_balance_df, make_balance_spreadsheet):
        bs = make_balance_spreadsheet(sample_balance_df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 15)
        result = bs.get_balance_history_by_account_id("a1", start, end)
        # Should have entries for every day from Jan 1 to Jan 15
        assert len(result) == 15  # 15 days inclusive

    def test_balance_history_by_account_missing_dates_filled(self, sample_balance_df, make_balance_spreadsheet):
        bs = make_balance_spreadsheet(sample_balance_df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 15)
        result = bs.get_balance_history_by_account_id("a1", start, end)
        # No NaN balances after bfill/ffill
        assert result["Balance"].isna().sum() == 0

    def test_balance_history_by_group_sums_across_accounts(self, sample_balance_df, make_balance_spreadsheet):
        bs = make_balance_spreadsheet(sample_balance_df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 15)
        result = bs.get_balance_history_by_group("Assets", start, end)
        # On Jan 15 both accounts have data: 4500 + 10500 = 15000
        last_val = result.iloc[-1]
        assert last_val == pytest.approx(15000)

    def test_balance_history_single_account_group(self, make_balance_spreadsheet):
        """A group with a single account should still work correctly."""
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "Mortgage", "Account ID": "a3",
             "Institution": "Lender", "Group": "Liabilities", "Class": "Liability",
             "Balance": 200000, "Hide": ""},
            {"Date": "2024-01-15", "Account": "Mortgage", "Account ID": "a3",
             "Institution": "Lender", "Group": "Liabilities", "Class": "Liability",
             "Balance": 199500, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 15)
        result = bs.get_balance_history_by_group("Liabilities", start, end)
        assert result.iloc[-1] == pytest.approx(199500)

    def test_balance_history_different_date_range(self, sample_balance_df, make_balance_spreadsheet):
        """Requesting a range that includes actual data points fills gaps via bfill/ffill."""
        bs = make_balance_spreadsheet(sample_balance_df)
        # Use a range that covers actual data points (Jan 1 and Jan 15)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 10)
        result = bs.get_balance_history_by_account_id("a1", start, end)
        assert len(result) == 10  # Jan 1-10 inclusive
        # Jan 1 has balance 5000; days 2-10 forward-filled to 5000
        assert result["Balance"].iloc[0] == pytest.approx(5000)
        assert result["Balance"].isna().sum() == 0

    def test_balance_history_by_group_empty_group(self, sample_balance_df, make_balance_spreadsheet):
        """A group with no matching data returns an empty series."""
        bs = make_balance_spreadsheet(sample_balance_df)
        result = bs.get_balance_history_by_group("NonExistent")
        assert result.empty

    def test_balance_history_by_group_overlapping_entries(self, make_balance_spreadsheet):
        """Multiple entries per account per date keeps the last one."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1000, "Hide": ""},
            {"Date": "2024-01-01", "Time": "2024-01-01 12:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1500, "Hide": ""},
            {"Date": "2024-01-02", "Time": "2024-01-02 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 2000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 2)
        result = bs.get_balance_history_by_group("Assets", start, end)
        # Jan 1 should use the last entry (1500), Jan 2 should be 2000
        assert result.iloc[0] == pytest.approx(1500)
        assert result.iloc[1] == pytest.approx(2000)

    def test_latest_balance_uses_latest_time(self, make_balance_spreadsheet):
        """When multiple entries share the same date, the latest time wins."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1000, "Hide": ""},
            {"Date": "2024-01-01", "Time": "2024-01-01 15:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 1500, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        _, total = bs.get_latest_balance_by_group("Assets")
        assert total == pytest.approx(1500)

    def test_latest_balance_empty_group(self, sample_balance_df, make_balance_spreadsheet):
        """A group with no accounts returns empty df and total 0."""
        bs = make_balance_spreadsheet(sample_balance_df)
        df_result, total = bs.get_latest_balance_by_group("NonExistent")
        assert df_result.empty
        assert total == pytest.approx(0.0)


# ===================================================================
# Sparkline functions
# ===================================================================

class TestSparklines:

    def test_group_sparkline_weekly_resample(self, sample_balance_df):
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 31)
        result = calculate_group_sparkline.__wrapped__(sample_balance_df, "Assets", start, end)
        assert "Balance" in result.columns
        assert "Date" in result.columns
        # Weekly resample means we should have a few rows
        assert len(result) >= 1

    def test_group_sparkline_empty_group(self, sample_balance_df):
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 31)
        result = calculate_group_sparkline.__wrapped__(sample_balance_df, "NonExistent", start, end)
        assert result.empty

    def test_net_worth_subtracts_liabilities(self, sample_balance_df):
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 31)
        result = calculate_net_worth_sparkline.__wrapped__(sample_balance_df, start, end)
        assert "NetWorth" in result.columns
        # Net worth should be negative overall since liabilities (200k) >> assets (15k)
        # Filter out any zero rows from edge-of-resample artifacts
        nonzero = result[result["NetWorth"] != 0]
        assert all(nonzero["NetWorth"] < 0)

    def test_group_sparkline_ffills_missing_weeks(self):
        """Accounts with data on different weeks should forward-fill so the sum
        doesn't drop when one account has no entry for a given week."""
        # Two accounts in the same group.  Account a1 reports on Jan 1 and Jan 15.
        # Account a2 reports only on Jan 1.  Without ffill, the Jan 15 week would
        # only sum a1's balance, dropping a2's contribution entirely.
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-15", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5500, "Hide": ""},
            {"Date": "2024-01-01", "Account": "Savings", "Account ID": "a2",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 10000, "Hide": ""},
        ])
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 21)
        result = calculate_group_sparkline.__wrapped__(df, "Assets", start, end)
        # Every week's balance should include both accounts (>= 15000)
        # Without ffill, later weeks would only show a1's balance (~5500)
        assert (result["Balance"] >= 10000).all()

    def test_net_worth_sparkline_ffills_missing_weeks(self):
        """Net worth sparkline should also forward-fill so accounts missing
        data in some weeks don't cause the net worth to spike."""
        df = _balance_df([
            {"Date": "2024-01-01", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-15", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset",
             "Balance": 5500, "Hide": ""},
            {"Date": "2024-01-01", "Account": "Credit Card", "Account ID": "a2",
             "Institution": "Chase", "Group": "Credit Card", "Class": "Liability",
             "Balance": 2000, "Hide": ""},
        ])
        start = _utc(2024, 1, 1)
        end = _utc(2024, 1, 21)
        result = calculate_net_worth_sparkline.__wrapped__(df, start, end)
        # Net worth should always reflect both accounts.
        # Without ffill, later weeks would omit the liability, inflating net worth.
        # Week 1: 5000 - 2000 = 3000.  Week 3: 5500 - 2000 = 3500.
        assert (result["NetWorth"] <= 3500).all()


# ===================================================================
# NaN / null handling
# ===================================================================

class TestNaNHandling:

    def test_filter_transactions_nan_amount(self, make_transactions_spreadsheet):
        """NaN in Amount column should not crash filter_transactions."""
        df = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-15", "Category": "Dining", "Amount": float('nan'),
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        result = ts.filter_transactions()
        # Both rows should be returned (NaN amount is not filtered out)
        assert len(result) == 2

    def test_get_amount_by_group_nan_amount(self, make_transactions_spreadsheet):
        """NaN amounts propagate through sum — group total includes NaN contribution."""
        df = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-15", "Category": "Dining", "Amount": float('nan'),
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        result = ts.get_amount_by_group()
        # pandas sum() with min_count default skips NaN: -50 + NaN = -50
        assert result.loc["Food", "Amount"] == pytest.approx(-50)

    def test_filter_transactions_nan_category(self, make_transactions_spreadsheet):
        """NaN in Category column: isin() excludes NaN, so include_categories filter drops NaN rows."""
        df = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-15", "Category": None, "Amount": -30,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        result = ts.filter_transactions(include_categories=["Groceries"])
        # NaN category is not in ["Groceries"], so it's excluded
        assert len(result) == 1
        assert result.iloc[0]["Category"] == "Groceries"

    def test_filter_transactions_nan_group(self, make_transactions_spreadsheet):
        """NaN in Group column: isin() excludes NaN, so include_groups filter drops NaN rows."""
        df = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-15", "Category": "Dining", "Amount": -30,
             "Account": "Checking", "Month": "2024-01", "Group": None, "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        result = ts.filter_transactions(include_groups=["Food"])
        assert len(result) == 1

    def test_filter_transactions_nan_date(self, make_transactions_spreadsheet):
        """NaN/NaT in Date column: between() returns False for NaT, so those rows are dropped."""
        df = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        # Append a row with NaT date
        nan_row = pd.DataFrame([{
            "Date": pd.NaT, "Category": "Dining", "Amount": -30,
            "Account": "Checking", "Month": "2024-01", "Group": "Food",
            "Type": "Expense", "Full Description": "", "Institution": "", "Account #": "",
        }])
        df = pd.concat([df, nan_row], ignore_index=True)
        ts = make_transactions_spreadsheet(df)
        result = ts.filter_transactions(
            start_date=_utc(2024, 1, 1),
            end_date=_utc(2024, 12, 31)
        )
        # NaT date is not between any range
        assert len(result) == 1

    def test_get_monthly_amounts_by_category_nan_amount(self, make_transactions_spreadsheet):
        """NaN in Amount is skipped by groupby sum, so monthly total only includes valid amounts."""
        df = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-20", "Category": "Groceries", "Amount": float('nan'),
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        result = ts.get_monthly_amounts_by_category("Groceries")
        assert result.loc["2024-01", "Amount"] == pytest.approx(-50)

    def test_get_total_months_single_row(self, make_transactions_spreadsheet):
        """A single transaction should return 0 total months (min == max)."""
        df = _transactions_df([
            {"Date": "2024-03-15", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-03", "Group": "Food", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        assert ts.get_total_months() == 0

    def test_get_monthly_amounts_nonexistent_category(self, make_transactions_spreadsheet):
        """Querying a category that doesn't exist returns an empty DataFrame."""
        df = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        result = ts.get_monthly_amounts_by_category("NonExistent")
        assert result.empty

    def test_groupby_nan_group_key(self, make_transactions_spreadsheet):
        """Rows with NaN Group are excluded from groupby results by default."""
        df = _transactions_df([
            {"Date": "2024-01-10", "Category": "Groceries", "Amount": -50,
             "Account": "Checking", "Month": "2024-01", "Group": "Food", "Type": "Expense"},
            {"Date": "2024-01-15", "Category": "Dining", "Amount": -30,
             "Account": "Checking", "Month": "2024-01", "Group": None, "Type": "Expense"},
        ])
        ts = make_transactions_spreadsheet(df)
        result = ts.get_amount_by_group()
        # NaN group key is dropped by groupby
        assert "Food" in result.index
        assert len(result) == 1


# ===================================================================
# CategoriesSpreadsheet.scrub()
# ===================================================================

class TestCategoriesScrub:

    def _make(self, raw_df):
        from src.spreadsheet import CategoriesSpreadsheet
        with patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)):
            return CategoriesSpreadsheet()

    def test_scrub_keeps_expected_columns(self):
        raw = pd.DataFrame({
            "Category": ["Groceries", "Rent"],
            "Group": ["Food", "Housing"],
            "Type": ["Expense", "Expense"],
            "Hide From Reports": ["", "Hide"],
            "Jan 2024": [100, 200],  # Budget columns should be dropped
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

    def _make(self, raw_df):
        from src.spreadsheet import AccountsSpreadsheet
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
# Balance History scrub — join edge cases
# ===================================================================

class TestBalanceScrubJoinEdgeCases:

    def _make(self, raw_df, accounts_for_scrub):
        with (
            patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)),
            patch("src.spreadsheet.load_accounts_data", return_value=accounts_for_scrub),
        ):
            return BalanceHistorySpreadsheet()

    def test_case_insensitive_join(self):
        """Account names with different casing should still match."""
        from src.spreadsheet import AccountsSpreadsheet
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
        from src.spreadsheet import AccountsSpreadsheet
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
        from src.spreadsheet import AccountsSpreadsheet
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
        from src.spreadsheet import AccountsSpreadsheet
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
        from src.spreadsheet import AccountsSpreadsheet
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
# Transactions scrub — join edge cases
# ===================================================================

class TestTransactionsScrubJoinEdgeCases:

    def _make(self, raw_df, categories):
        with (
            patch.object(Spreadsheet, 'load', lambda self: setattr(self, 'raw_df', raw_df)),
            patch("src.spreadsheet.load_categories_data", return_value=categories),
        ):
            return TransactionsSpreadsheet()

    def _raw(self, categories, amounts=None):
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
        from src.spreadsheet import CategoriesSpreadsheet
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
        from src.spreadsheet import CategoriesSpreadsheet
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
        from src.spreadsheet import CategoriesSpreadsheet
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
        from src.spreadsheet import CategoriesSpreadsheet
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


# ===================================================================
# Balance History — latest balance edge cases
# ===================================================================

class TestLatestBalanceEdgeCases:

    def test_multiple_accounts_same_group_different_dates(self, make_balance_spreadsheet):
        """Each account's latest entry is used, even if they're on different dates."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-15", "Time": "2024-01-15 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 4500, "Hide": ""},
            {"Date": "2024-01-10", "Time": "2024-01-10 08:00:00", "Account": "Savings", "Account ID": "a2",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 10000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        _, total = bs.get_latest_balance_by_group("Assets")
        # Checking latest = 4500 (Jan 15), Savings latest = 10000 (Jan 10)
        assert total == pytest.approx(14500)

    def test_end_date_excludes_future_entries(self, make_balance_spreadsheet):
        """Entries after end_date are excluded from latest balance."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 5000, "Hide": ""},
            {"Date": "2024-02-01", "Time": "2024-02-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 6000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        _, total = bs.get_latest_balance_by_group("Assets", end_date=_utc(2024, 1, 15))
        assert total == pytest.approx(5000)

    def test_single_entry_per_account(self, make_balance_spreadsheet):
        """Works correctly when each account has exactly one balance entry."""
        df = _balance_df([
            {"Date": "2024-01-01", "Time": "2024-01-01 08:00:00", "Account": "Checking", "Account ID": "a1",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 5000, "Hide": ""},
            {"Date": "2024-01-01", "Time": "2024-01-01 09:00:00", "Account": "Savings", "Account ID": "a2",
             "Institution": "Bank", "Group": "Assets", "Class": "Asset", "Balance": 10000, "Hide": ""},
        ])
        bs = make_balance_spreadsheet(df)
        df_result, total = bs.get_latest_balance_by_group("Assets")
        assert total == pytest.approx(15000)
        assert len(df_result) == 2
