"""Classes for interacting with Google Sheets spreadsheets."""

import datetime
from abc import ABCMeta, abstractmethod
from typing import ClassVar, TypedDict, override

import pandas as pd
import streamlit as st

from src.config import get_settings
from src.scrubbing import (
    BALANCE_HISTORY_REQUIRED_COLUMNS,
    scrub_categories,
    scrub_transactions,
)
from src.scrubbing import (
    SpreadsheetSchemaError as SpreadsheetSchemaError,
)
from src.scrubbing import (
    validate_required_columns as validate_required_columns,
)


def validate_min_columns(
    df: pd.DataFrame,
    min_columns: int,
    sheet_name: str,
) -> None:
    """Raise when ``df`` has fewer than ``min_columns`` columns."""
    if len(df.columns) < min_columns:
        raise SpreadsheetSchemaError(
            f"{sheet_name} sheet must have at least {min_columns} columns; found {len(df.columns)}"
        )


class NetWorthSummary(TypedDict):
    """Aggregated net worth view for the Home page.

    All four fields are derived from a single ``BalanceHistorySpreadsheet`` so
    that callers (Home.py and unit tests) share one calculation surface.
    """

    total_net_worth: float
    group_balances: dict[str, float]
    group_classes: dict[str, str]
    group_accounts: dict[str, pd.DataFrame]


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
        try:
            self.scrub()
        except SpreadsheetSchemaError as e:
            st.error(str(e))
            st.info("Check that the configured Google Sheet tab matches the expected Tiller sheet.")
            st.stop()
            raise

    def load(self) -> None:
        """Load raw data from the configured source."""
        settings = get_settings()
        if settings.data.is_demo:
            path = settings.data.demo_directory / f"{self.name}.csv"
            try:
                self.raw_df = pd.read_csv(path)
            except Exception:
                st.error(f"Failed to load demo data ({self.name}).")
                st.info("Restore the committed files under demo/data, then restart the app.")
                st.stop()
            return

        try:
            from streamlit_gsheets import GSheetsConnection

            conn = st.connection(name=self.name, type=GSheetsConnection)
            self.raw_df = conn.read()
        except Exception:
            st.error(f"Failed to load data from Google Sheets ({self.name}).")
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
        self.scrubbed_df, self.budget_df = scrub_categories(self.raw_df)


class AccountsSpreadsheet(Spreadsheet):
    """Account metadata (group, visibility) from the Accounts sheet."""

    name: ClassVar[str] = "accounts"

    @override
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()
        validate_min_columns(df, 4, "Accounts")
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
        categories = load_categories_data()
        self.scrubbed_df = scrub_transactions(self.raw_df, categories.scrubbed_df)

    def get_total_months(self) -> int:
        """Return the total amount of months in the data set as an int"""
        oldest_date = self.scrubbed_df["Date"].min()
        latest_date = self.scrubbed_df["Date"].max()
        total_months: int = (latest_date.year - oldest_date.year) * 12 + (latest_date.month - oldest_date.month)

        return total_months

    def get_groups(self) -> list[str]:
        """Return the unique list of account group names"""
        return list(self.scrubbed_df.sort_values("Group")["Group"].unique())

    def get_all_categories(self) -> list[str]:
        """Return sorted unique categories, excluding NaN and blank strings."""
        return sorted(str(c) for c in self.scrubbed_df["Category"].unique() if pd.notna(c) and str(c).strip())

    def get_all_groups(self) -> list[str]:
        """Return sorted unique groups, excluding NaN, blanks, and Transfer."""
        return sorted(
            str(g) for g in self.scrubbed_df["Group"].unique() if pd.notna(g) and str(g).strip() and g != "Transfer"
        )

    def get_group_categories(self, group: str) -> list[str]:
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
        invert_amount: bool = False,
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
        invert_amount: bool = False,
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
        invert_amount: bool = False,
    ) -> pd.DataFrame:
        """Get the total monthly transaction amount by a specified category"""
        return self._get_monthly_amounts("Category", category, start_date, end_date, invert_amount)

    def get_monthly_amounts_by_group(
        self,
        group: str,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        invert_amount: bool = False,
    ) -> pd.DataFrame:
        """Get the total monthly transaction amount by a specified group"""
        return self._get_monthly_amounts("Group", group, start_date, end_date, invert_amount)

    def get_transactions_by_category(
        self, category: str, start_date: datetime.datetime | None = None, end_date: datetime.datetime | None = None
    ) -> pd.DataFrame:
        """Get all transactions for a specific category"""
        return self.filter_transactions(include_categories=[category], start_date=start_date, end_date=end_date)

    def get_transactions_by_group(
        self, group: str, start_date: datetime.datetime | None = None, end_date: datetime.datetime | None = None
    ) -> pd.DataFrame:
        """Get all transactions for a specific group"""
        return self.filter_transactions(include_groups=[group], start_date=start_date, end_date=end_date)


class BalanceHistorySpreadsheet(Spreadsheet):
    """Daily account balance snapshots from the Balance History sheet."""

    name: ClassVar[str] = "balance_history"

    @override
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()
        validate_required_columns(df, BALANCE_HISTORY_REQUIRED_COLUMNS, "Balance History")

        # Drop empty column
        df = df.drop("Unnamed: 0", axis=1, errors="ignore")

        # Recast Amount column as float
        df["Balance"] = df["Balance"].replace(r"[\$,]", "", regex=True).astype(float)

        # Recast dates as datetime (utc=True handles mixed timezones)
        df["Date"] = pd.to_datetime(df["Date"], format="mixed", utc=True)
        df["Time"] = pd.to_datetime(df["Time"], format="mixed", utc=True)
        df["Month"] = pd.to_datetime(df["Month"], format="mixed", utc=True)
        df["Week"] = pd.to_datetime(df["Week"], format="mixed", utc=True)
        df["Date Added"] = pd.to_datetime(df["Date Added"], format="mixed", utc=True)

        # Use better strings for Month and Week columns
        df["Month"] = df["Month"].dt.strftime("%Y-%m")
        df["Week"] = df["Week"].dt.strftime("%U")

        # Join with Accounts to populate Group and Hide.
        # The Accounts sheet uses a composite key: "Account - Account # (XXXX)"
        # where XXXX is the uppercased last 4 characters of Account ID.
        # Google Sheets VLOOKUP is case-insensitive, so we lowercase both sides.
        df = df.drop(columns=["Group", "Hide"], errors="ignore")
        acct_num = df["Account #"].fillna("").astype(str)
        acct_id_suffix = df["Account ID"].astype(str).str[-4:].str.upper()
        df["_account_key"] = (df["Account"].astype(str) + " - " + acct_num + " (" + acct_id_suffix + ")").str.lower()
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

    def get_groups(self) -> list[str]:
        """Return the unique list of account group names"""
        return list(self.scrubbed_df.sort_values("Group")["Group"].unique())

    def get_latest_balance_by_group(
        self, group: str, end_date: datetime.datetime | None = None
    ) -> tuple[pd.DataFrame, float]:
        """Summarize balance information by balance_history group"""
        return get_latest_balance_by_group(self.scrubbed_df, group, end_date)

    def get_balance_history_by_group(
        self, group: str, start_date: datetime.datetime | None = None, end_date: datetime.datetime | None = None
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

    def get_portfolio_value(
        self,
        account_names: list[str],
        as_of: datetime.datetime | None = None,
    ) -> tuple[pd.DataFrame, float]:
        """Return per-account latest balances and signed total for *account_names*."""
        return get_portfolio_value(self.scrubbed_df, account_names, as_of)

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


def get_latest_balance_by_group(
    balance_history_df: pd.DataFrame,
    group: str,
    end_date: datetime.datetime | None = None,
) -> tuple[pd.DataFrame, float]:
    """Summarize the latest balance for each account in *group*.

    Pure function over a scrubbed BalanceHistory DataFrame; lifted out of
    ``BalanceHistorySpreadsheet.get_latest_balance_by_group`` so it can be
    called and tested without instantiating the full spreadsheet object.

    Parameters
    ----------
    balance_history_df:
        Scrubbed BalanceHistory data with columns ``Date``, ``Time``,
        ``Account``, ``Account ID``, ``Group``, ``Balance``.
    group:
        The account group to summarize (e.g. ``"Checking"``).
    end_date:
        Upper bound on observations. Defaults to ``balance_history_df["Date"].max()``
        when ``None``.

    Returns
    -------
    tuple[pd.DataFrame, float]
        A two-column ``[Account, Balance]`` frame with one row per account
        (using each account's most recent observation), and the total of
        those balances.
    """
    df = balance_history_df.copy()

    start_date = df["Date"].min()
    if end_date is None:
        end_date = df["Date"].max()
    df = df[df["Date"].between(start_date, end_date)]

    df = df.sort_values(by=["Date", "Time"])
    df = df.drop_duplicates("Account ID", keep="last")
    df = df[df["Group"] == group]
    df = df.filter(["Account", "Balance"])

    total = float(df["Balance"].sum())
    return df, total


def get_all_accounts(balance_history_df: pd.DataFrame) -> list[str]:
    """Return sorted unique Account names, dropping rows marked Hide="Hide"."""
    df = balance_history_df
    if "Hide" in df.columns:
        df = df[df["Hide"] != "Hide"]
    accounts = df["Account"].dropna().unique()
    return sorted(str(a) for a in accounts if str(a).strip())


def get_portfolio_value(
    balance_history_df: pd.DataFrame,
    account_names: list[str],
    as_of: datetime.datetime | None = None,
) -> tuple[pd.DataFrame, float]:
    """Sum the latest signed balance for each account in *account_names*.

    Liabilities count negatively (matching :func:`calculate_net_worth_summary`),
    so mixing an asset and a margin loan yields the correct net contribution.

    Parameters
    ----------
    balance_history_df:
        Scrubbed BalanceHistory frame.
    account_names:
        Accounts to include in the portfolio total.
    as_of:
        Upper bound on observations; defaults to the data's max date.

    Returns
    -------
    tuple[pd.DataFrame, float]
        ``(per_account_df, signed_total)`` where ``per_account_df`` has
        ``[Account, Balance]`` with one row per selected account (balance is
        signed by Class). Empty selection returns an empty frame and 0.0.
    """
    empty = pd.DataFrame(columns=["Account", "Balance"])
    if not account_names:
        return empty, 0.0

    df = balance_history_df.copy()
    if "Hide" in df.columns:
        df = df[df["Hide"] != "Hide"]

    if as_of is None:
        as_of = df["Date"].max()
    df = df[df["Date"] <= as_of]
    df = df[df["Account"].isin(account_names)]

    if df.empty:
        return empty, 0.0

    df = df.sort_values(by=["Date", "Time"])
    df = df.drop_duplicates("Account ID", keep="last")

    multiplier = df["Class"].map({"Liability": -1, "Asset": 1}).fillna(1)
    df = df.assign(Balance=df["Balance"] * multiplier)

    per_account = df.filter(["Account", "Balance"]).reset_index(drop=True)
    total = float(per_account["Balance"].sum())
    return per_account, total


def calculate_net_worth_summary(
    balance_history: BalanceHistorySpreadsheet,
) -> NetWorthSummary:
    """Compute the per-group net worth summary used by the Home page.

    For each non-empty group:
        * pull each account's most recent balance via
          :func:`get_latest_balance_by_group`
        * sign each account individually (``-1`` for Liability, ``+1`` for
          Asset) so groups that mix classes compute correct net worth
        * determine the dominant class for display (majority wins)

    Parameters
    ----------
    balance_history:
        Loaded ``BalanceHistorySpreadsheet``.

    Returns
    -------
    NetWorthSummary
        Dict with ``total_net_worth``, ``group_balances``, ``group_classes``,
        and ``group_accounts``.
    """
    raw_groups = balance_history.get_groups()
    groups = [str(g) for g in raw_groups if pd.notna(g) and g != ""]

    total_net_worth = 0.0
    group_balances: dict[str, float] = {}
    group_classes: dict[str, str] = {}
    group_accounts: dict[str, pd.DataFrame] = {}

    scrubbed = balance_history.scrubbed_df
    for group in groups:
        accounts_df, total = balance_history.get_latest_balance_by_group(group)
        group_accounts[group] = accounts_df
        group_balances[group] = total

        # Determine each account's class from the latest observation and
        # compute a correctly-signed contribution to net worth.  This handles
        # groups that mix asset and liability accounts (e.g. a brokerage with
        # a margin loan).
        df_latest = scrubbed.copy()
        df_latest = df_latest.sort_values(by=["Date", "Time"])
        df_latest = df_latest.drop_duplicates("Account ID", keep="last")
        df_latest = df_latest[df_latest["Group"] == group]

        signed_total = 0.0
        dominant_class = "Asset"
        if not df_latest.empty:
            multiplier = df_latest["Class"].map({"Liability": -1, "Asset": 1}).fillna(1)
            signed_total = float((df_latest["Balance"] * multiplier).sum())
            liability_count = (df_latest["Class"] == "Liability").sum()
            dominant_class = "Liability" if liability_count > len(df_latest) / 2 else "Asset"

        group_classes[group] = dominant_class
        total_net_worth += signed_total

    return NetWorthSummary(
        total_net_worth=total_net_worth,
        group_balances=group_balances,
        group_classes=group_classes,
        group_accounts=group_accounts,
    )


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
    df_group = df_group.sort_values(["Account ID", "Date"])

    # For each account, get the last balance for each week
    # Set Date as index for resampling
    df_group_indexed = df_group.set_index("Date")

    # Group by Account ID and resample to weekly, taking last balance.
    # Unstack into account columns, then forward-fill so weeks where an account
    # has no data carry the last known balance. This prevents partial sums when
    # only some accounts report in a given week.
    weekly = df_group_indexed.groupby("Account ID")["Balance"].resample("W").last().unstack("Account ID").ffill()
    balances_by_date = weekly.sum(axis=1).reset_index().rename(columns={"index": "Date", 0: "Balance"})

    # Filter to date range
    balances_by_date = balances_by_date[
        (balances_by_date["Date"] >= start_date) & (balances_by_date["Date"] <= end_date)
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
    df_all_copy["Multiplier"] = df_all_copy["Class"].map({"Liability": -1, "Asset": 1}).fillna(1)
    df_all_copy["SignedBalance"] = df_all_copy["Balance"] * df_all_copy["Multiplier"]

    # Sort by account and date
    df_all_copy = df_all_copy.sort_values(["Account ID", "Date"])

    # Set Date as index for resampling
    df_indexed = df_all_copy.set_index("Date")

    # For each account, get the last balance for each week, then sum across accounts.
    # Unstack and forward-fill so weeks without data carry the last known balance.
    weekly = df_indexed.groupby("Account ID")["SignedBalance"].resample("W").last().unstack("Account ID").ffill()
    net_worth_by_date = weekly.sum(axis=1).reset_index().rename(columns={"index": "Date", 0: "NetWorth"})

    # Filter to date range
    net_worth_by_date = net_worth_by_date[
        (net_worth_by_date["Date"] >= start_date) & (net_worth_by_date["Date"] <= end_date)
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
