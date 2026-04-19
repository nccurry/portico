"""Classes for interacting with Google Sheets spreadsheets."""
import datetime
from typing import ClassVar, override

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from abc import ABCMeta, abstractmethod


class Spreadsheet(metaclass=ABCMeta):
    """Class used to interact with Spreadsheet data in Google Sheets"""
    # Friendly name for this spreadsheet (must match the connection name in secrets.toml)
    name: ClassVar[str]

    # The raw, unscrubbed, data from the spreadsheet
    raw_df: pd.DataFrame

    # The scrubbed data from the spreadsheet
    scrubbed_df: pd.DataFrame

    def __init__(self) -> None:
        """Load the spreadsheet from Google Sheets and scrub it."""
        self.load()
        self.scrub()

    def load(self) -> None:
        """Load data from the external spreadsheet"""
        try:
            conn = st.connection(name=self.name, type=GSheetsConnection)
            self.raw_df = conn.read()
        except Exception as e:
            st.error(f"Failed to load data from Google Sheets ({self.name}): {e}")
            st.info("Check your .streamlit/secrets.toml configuration and network connection.")
            st.stop()

    @abstractmethod
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        ...


class CategoriesSpreadsheet(Spreadsheet):
    """Category-to-group mapping and monthly budget data from the Categories sheet."""

    name: ClassVar[str] = "categories"

    # Budget data: long-format DataFrame with per-category monthly budgets
    budget_df: pd.DataFrame

    @override
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()

        # Metadata columns (first 4)
        meta = df.filter(["Category", "Group", "Type", "Hide From Reports"]).copy()
        meta = meta.dropna(subset=["Category"])
        self.scrubbed_df = meta

        # Budget columns (columns 5+) have date headers from Google Sheets
        budget_cols = df.iloc[:, 4:]
        month_map = {}
        for col in budget_cols.columns:
            try:
                dt = pd.to_datetime(col)
                month_map[col] = dt.month
            except (ValueError, TypeError):
                continue

        if not month_map:
            self.budget_df = pd.DataFrame(
                columns=["Category", "Month_Num", "Budget", "Group", "Type"]
            )
            return

        # Build wide DataFrame: Category + one column per month number
        budget_wide = df[["Category"]].copy()
        for orig_col, month_num in month_map.items():
            cleaned = df[orig_col].astype(str).str.replace(r'[$,]', '', regex=True)
            budget_wide[month_num] = pd.to_numeric(cleaned, errors="coerce").fillna(0)
        budget_wide = budget_wide.dropna(subset=["Category"])

        # Melt to long format
        month_nums = sorted(month_map.values())
        budget_long = budget_wide.melt(
            id_vars=["Category"],
            value_vars=month_nums,
            var_name="Month_Num",
            value_name="Budget",
        )

        # Join with metadata for Group/Type
        budget_long = budget_long.merge(
            meta[["Category", "Group", "Type"]], on="Category", how="left"
        )

        self.budget_df = budget_long


class AccountsSpreadsheet(Spreadsheet):
    """Account metadata (group, visibility) from the Accounts sheet."""

    name: ClassVar[str] = "accounts"

    @override
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()
        # Columns A-D are user-managed: Account (composite key), Class Override, Group, Hide
        df = df.iloc[:, :4]
        df.columns = ["Account", "Class Override", "Group", "Hide"]
        df = df.dropna(subset=["Account"])
        df = df.filter(["Account", "Group", "Hide"])
        self.scrubbed_df = df



class TransactionsSpreadsheet(Spreadsheet):
    """Individual transactions from the Transactions sheet, with filtering and aggregation helpers."""

    name: ClassVar[str] = "transactions"

    @override
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()

        # Drop empty column
        df = df.drop("Unnamed: 0", axis=1, errors='ignore')

        # Recast Amount column as float
        df["Amount"] = df["Amount"].replace(r'[\$,]', '', regex=True).astype(float)

        # Recast dates as datetime (utc=True handles mixed timezones)
        df["Date"] = pd.to_datetime(df["Date"], format='mixed', utc=True)
        df["Month"] = pd.to_datetime(df["Month"], format='mixed', utc=True)
        df["Week"] = pd.to_datetime(df["Week"], format='mixed', utc=True)
        df["Date Added"] = pd.to_datetime(df["Date Added"], format='mixed', utc=True)
        df["Categorized Date"] = pd.to_datetime(df["Categorized Date"], format='mixed', utc=True)

        # Use better strings for Month and Week columns
        df["Month"] = df["Month"].dt.strftime('%Y-%m')
        df["Week"] = df["Week"].dt.strftime('%U')

        # Join with Categories to populate Group, Type, and Hide From Reports
        df = df.drop(columns=["Group", "Type", "Hide From Reports"], errors="ignore")
        categories = load_categories_data()
        df = df.merge(categories.scrubbed_df, on="Category", how="left")
        df["Group"] = df["Group"].fillna("Uncategorized")
        df["Type"] = df["Type"].fillna("")
        df["Hide From Reports"] = df["Hide From Reports"].fillna("")

        df = df.filter(["Date", "Category", "Amount", "Account", "Month", "Full Description", "Group", "Type", "Institution", "Account #"])

        self.scrubbed_df = df

    def get_total_months(
            self
    ) -> int:
        """Return the total amount of months in the data set as an int"""
        oldest_date = self.scrubbed_df["Date"].min()
        latest_date = self.scrubbed_df["Date"].max()
        total_months: int = (latest_date.year - oldest_date.year) * 12 + (latest_date.month - oldest_date.month)

        return total_months

    def get_groups(
            self
    ) -> list[str]:
        """Return the unique list of account group names"""
        return list(self.scrubbed_df.sort_values("Group")["Group"].unique())

    def get_group_categories(
        self,
        group: str
    ) -> list[str]:
        """Return all unique category names from a given group"""
        df = self.scrubbed_df.copy()
        df = df[df["Group"] == group]

        return list(df["Category"].unique())

    def filter_transactions(
            self,
            include_categories: list[str] | None = None,
            ignore_categories: list[str] | None = None,
            include_groups: list[str] | None = None,
            ignore_groups: list[str] | None = None,
            include_types: list[str] | None = None,
            ignore_types: list[str] | None = None,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None,
            filtered_columns: list[str] | None = None,
            group_by_column: str | None = None,
    ) -> pd.DataFrame:
        """Filter transactions based on various attributes. Optionally group by a given column"""
        if include_categories is None:
            include_categories = []
        if ignore_categories is None:
            ignore_categories = []
        if include_groups is None:
            include_groups = []
        if ignore_groups is None:
            ignore_groups = []
        if include_types is None:
            include_types = []
        if ignore_types is None:
            ignore_types = []

        df = self.scrubbed_df.copy()
        df = df.sort_values("Date")

        if include_categories:
            df = df[df["Category"].isin(include_categories)]
        df = df[~df["Category"].isin(ignore_categories)]

        if include_groups:
            df = df[df["Group"].isin(include_groups)]
        df = df[~df["Group"].isin(ignore_groups)]

        if include_types:
            df = df[df["Type"].isin(include_types)]
        df = df[~df["Type"].isin(ignore_types)]

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()
        df = df[df["Date"].between(start_date, end_date)]

        if filtered_columns:
            df = df.filter(filtered_columns)

        if group_by_column:
            df = df.groupby(group_by_column).sum(numeric_only=True)

        return df

    def get_amount_by_group(
            self,
            include_categories: list[str] | None = None,
            ignore_categories: list[str] | None = None,
            include_groups: list[str] | None = None,
            ignore_groups: list[str] | None = None,
            include_types: list[str] | None = None,
            ignore_types: list[str] | None = None,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None,
            invert_amount: bool = False
    ) -> pd.DataFrame:
        """Get the total spending per group over a specified period"""
        df = self.filter_transactions(
            include_categories=include_categories,
            ignore_categories=ignore_categories,
            include_groups=include_groups,
            ignore_groups=ignore_groups,
            include_types=include_types,
            ignore_types=ignore_types,
            start_date=start_date,
            end_date=end_date,
            filtered_columns=["Date", "Category", "Group", "Amount", "Type"],
        )

        if invert_amount:
            df["Amount"] = df["Amount"] * -1

        return df.groupby("Group").sum(numeric_only=True)

    def get_amount_by_group_category(
            self,
            group: str,
            include_categories: list[str] | None = None,
            ignore_categories: list[str] | None = None,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None,
            invert_amount: bool = False,
    ) -> pd.DataFrame:
        """Get the total group spending per categories over a specified period"""
        df = self.filter_transactions(
            include_groups=[group],
            include_categories=include_categories,
            ignore_categories=ignore_categories,
            start_date=start_date,
            end_date=end_date,
            filtered_columns=["Date", "Group", "Category", "Amount", "Type"],
        )

        if invert_amount:
            df["Amount"] = df["Amount"] * -1

        return df.groupby("Category").sum(numeric_only=True)

    def _get_monthly_amounts(
            self,
            column: str,
            value: str,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None,
            invert_amount: bool = False
    ) -> pd.DataFrame:
        """Get the total monthly transaction amount filtered by a column value"""
        df = self.scrubbed_df.copy()
        df = df.sort_values(["Date"])
        df = df[df[column] == value]
        df = df.filter(["Date", "Month", "Group", "Category", "Amount", "Type"])

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()

        df = df[df["Date"].between(start_date, end_date)]

        if invert_amount:
            df["Amount"] = df["Amount"] * -1

        return df.groupby("Month").sum(numeric_only=True)

    def get_monthly_amounts_by_category(
            self,
            category: str,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None,
            invert_amount: bool = False
    ) -> pd.DataFrame:
        """Get the total monthly transaction amount by a specified category"""
        return self._get_monthly_amounts("Category", category, start_date, end_date, invert_amount)

    def get_monthly_amounts_by_group(
            self,
            group: str,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None,
            invert_amount: bool = False
    ) -> pd.DataFrame:
        """Get the total monthly transaction amount by a specified group"""
        return self._get_monthly_amounts("Group", group, start_date, end_date, invert_amount)

    def get_transactions_by_category(
            self,
            category: str,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None
    ) -> pd.DataFrame:
        """Get all transactions for a specific category"""
        return self.filter_transactions(
            include_categories=[category],
            start_date=start_date,
            end_date=end_date
        )

    def get_transactions_by_group(
            self,
            group: str,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None
    ) -> pd.DataFrame:
        """Get all transactions for a specific group"""
        return self.filter_transactions(
            include_groups=[group],
            start_date=start_date,
            end_date=end_date
        )



class BalanceHistorySpreadsheet(Spreadsheet):
    """Daily account balance snapshots from the Balance History sheet."""

    name: ClassVar[str] = "balance_history"

    @override
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()

        # Drop empty column
        df = df.drop("Unnamed: 0", axis=1, errors='ignore')

        # Recast Amount column as float
        df["Balance"] = df["Balance"].replace(r'[\$,]', '', regex=True).astype(float)

        # Recast dates as datetime (utc=True handles mixed timezones)
        df["Date"] = pd.to_datetime(df["Date"], format='mixed', utc=True)
        df["Time"] = pd.to_datetime(df["Time"], format='mixed', utc=True)
        df["Month"] = pd.to_datetime(df["Month"], format='mixed', utc=True)
        df["Week"] = pd.to_datetime(df["Week"], format='mixed', utc=True)
        df["Date Added"] = pd.to_datetime(df["Date Added"], format='mixed', utc=True)

        # Use better strings for Month and Week columns
        df["Month"] = df["Month"].dt.strftime('%Y-%m')
        df["Week"] = df["Week"].dt.strftime('%U')

        # Join with Accounts to populate Group and Hide.
        # The Accounts sheet uses a composite key: "Account - Account # (XXXX)"
        # where XXXX is the uppercased last 4 characters of Account ID.
        # Google Sheets VLOOKUP is case-insensitive, so we lowercase both sides.
        df = df.drop(columns=["Group", "Hide"], errors="ignore")
        acct_num = df["Account #"].fillna("").astype(str)
        acct_id_suffix = df["Account ID"].astype(str).str[-4:].str.upper()
        df["_account_key"] = (
            df["Account"].astype(str) + " - " + acct_num +
            " (" + acct_id_suffix + ")"
        ).str.lower()
        accounts = load_accounts_data()
        accounts_df = accounts.scrubbed_df.copy()
        accounts_df["_account_key"] = accounts_df["Account"].str.lower()
        accounts_df = accounts_df.drop(columns=["Account"])
        df = df.merge(accounts_df, on="_account_key", how="left")
        df = df.drop(columns=["_account_key"])
        df["Group"] = df["Group"].fillna("")
        df["Hide"] = df["Hide"].fillna("")

        df = df[df["Hide"] != "Hide"]

        self.scrubbed_df = df

    def get_groups(
            self
    ) -> list[str]:
        """Return the unique list of account group names"""
        return list(self.scrubbed_df.sort_values("Group")["Group"].unique())

    def get_latest_balance_by_group(
            self,
            group: str,
            end_date: datetime.datetime | None = None
    ) -> tuple[pd.DataFrame, float]:
        """Summarize balance information by balance_history group"""
        df = self.scrubbed_df.copy()

        start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()
        df = df[df["Date"].between(start_date, end_date)]

        df = df.sort_values(by=['Date', 'Time'])
        df = df.drop_duplicates('Account ID', keep='last')
        df = df[df["Group"] == group]
        df = df.filter(["Account", "Balance"])

        total = float(df["Balance"].sum())

        return df, total

    def get_balance_history_by_group(
            self,
            group: str,
            start_date: datetime.datetime | None = None,
            end_date: datetime.datetime | None = None
    ) -> pd.Series:
        """Get the balance history for all accounts under a single group"""
        df = self.scrubbed_df.copy()
        df = df[df["Group"] == group]

        if df.empty:
            return pd.Series(dtype=float, name="Balance")

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()

        # Sort and keep the last balance entry per account per date
        df = df.sort_values(["Account ID", "Date"])
        df = df.drop_duplicates(subset=["Account ID", "Date"], keep="last")

        # Pivot so each account is a column, dates are rows
        pivot = df.pivot_table(index="Date", columns="Account ID", values="Balance", aggfunc="last")

        # Reindex to the full date range and fill missing values
        idx = pd.date_range(start_date, end_date)
        pivot = pivot.reindex(idx)
        pivot = pivot.bfill().ffill()

        # Sum across all accounts for each date
        return pivot.sum(axis=1).rename("Balance")

    def get_balance_history_by_account_id(
            self,
            account_id: str,
            start_date: datetime.datetime,
            end_date: datetime.datetime,
            columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Get the balance history for a specific account, filtered by date range."""
        if columns is None:
            columns = ["Date", "Account", "Account ID", "Institution", "Group", "Balance"]
        # Filter and sort
        df = self.scrubbed_df.copy()
        df = df[df["Account ID"] == account_id]
        df = df.filter(columns)
        df = df.sort_values("Date")

        # Fill in missing dates
        df = df.drop_duplicates(["Date"], keep="last")
        idx = pd.date_range(start_date, end_date)
        df.index = pd.DatetimeIndex(df["Date"])
        df = df.reindex(idx)
        df["Date"] = df.index
        df = df.bfill().ffill()  # bfill fills empty start dates, ffill fills empty middle dates

        return df


# Helper function for efficient sparkline calculation
@st.cache_data(ttl=300)
def calculate_group_sparkline(
    df_all: pd.DataFrame,
    group: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Calculate sparkline data for a specific group (cached for performance).

    Optimized to use pandas resampling instead of iteration.
    """
    df_group = df_all[df_all["Group"] == group].copy()

    if df_group.empty:
        return pd.DataFrame()

    # Sort by account and date
    df_group = df_group.sort_values(['Account ID', 'Date'])

    # For each account, get the last balance for each week
    # Set Date as index for resampling
    df_group_indexed = df_group.set_index('Date')

    # Group by Account ID and resample to weekly, taking last balance.
    # Unstack into account columns, then forward-fill so weeks where an account
    # has no data carry the last known balance. This prevents partial sums when
    # only some accounts report in a given week.
    weekly = (
        df_group_indexed
        .groupby('Account ID')['Balance']
        .resample('W')
        .last()
        .unstack('Account ID')
        .ffill()
    )
    balances_by_date = (
        weekly
        .sum(axis=1)
        .reset_index()
        .rename(columns={'index': 'Date', 0: 'Balance'})
    )

    # Filter to date range
    balances_by_date = balances_by_date[
        (balances_by_date['Date'] >= start_date) &
        (balances_by_date['Date'] <= end_date)
    ]

    return balances_by_date


@st.cache_data(ttl=300)
def calculate_net_worth_sparkline(
    df_all: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Calculate net worth sparkline (cached for performance).

    Optimized to use pandas resampling instead of iteration.
    """
    df_all_copy = df_all.copy()

    # Add signed balance (assets positive, liabilities negative)
    df_all_copy['Multiplier'] = df_all_copy['Class'].map({'Liability': -1, 'Asset': 1}).fillna(1)
    df_all_copy['SignedBalance'] = df_all_copy['Balance'] * df_all_copy['Multiplier']

    # Sort by account and date
    df_all_copy = df_all_copy.sort_values(['Account ID', 'Date'])

    # Set Date as index for resampling
    df_indexed = df_all_copy.set_index('Date')

    # For each account, get the last balance for each week, then sum across accounts.
    # Unstack and forward-fill so weeks without data carry the last known balance.
    weekly = (
        df_indexed
        .groupby('Account ID')['SignedBalance']
        .resample('W')
        .last()
        .unstack('Account ID')
        .ffill()
    )
    net_worth_by_date = (
        weekly
        .sum(axis=1)
        .reset_index()
        .rename(columns={'index': 'Date', 0: 'NetWorth'})
    )

    # Filter to date range
    net_worth_by_date = net_worth_by_date[
        (net_worth_by_date['Date'] >= start_date) &
        (net_worth_by_date['Date'] <= end_date)
    ]

    return net_worth_by_date


# Cached data loading functions
# Use cache_resource for objects that should be reused across sessions
@st.cache_resource(ttl=300)
def load_categories_data() -> CategoriesSpreadsheet:
    """Load and cache categories spreadsheet data"""
    return CategoriesSpreadsheet()


@st.cache_resource(ttl=300)
def load_accounts_data() -> AccountsSpreadsheet:
    """Load and cache accounts spreadsheet data"""
    return AccountsSpreadsheet()


@st.cache_resource(ttl=300)
def load_transactions_data() -> TransactionsSpreadsheet:
    """Load and cache transactions spreadsheet data"""
    return TransactionsSpreadsheet()


@st.cache_resource(ttl=300)
def load_balance_history_data() -> BalanceHistorySpreadsheet:
    """Load and cache balance history spreadsheet data"""
    return BalanceHistorySpreadsheet()
