"""Classes for interacting with Google Sheets spreadsheets."""
import datetime
from typing import Optional, List, Tuple
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from abc import ABCMeta, abstractmethod
import math
import numpy as np


class Spreadsheet(metaclass=ABCMeta):
    """Class used to interact with Spreadsheet data in Google Sheets"""
    # Friendly name for this spreadsheet (must match the connection name in secrets.toml)
    name: str

    # The raw, unscrubbed, data from the spreadsheet
    raw_df: pd.DataFrame

    # The scrubbed data from the spreadsheet
    scrubbed_df: pd.DataFrame

    def __init__(self) -> None:
        self.load()
        self.scrub()

    def load(self) -> None:
        """Load data from the external spreadsheet"""
        conn = st.connection(name=self.name, type=GSheetsConnection)
        self.raw_df = conn.read()

    @abstractmethod
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        ...


class TransactionsSpreadsheet(Spreadsheet):
    name = "transactions_spreadsheet"

    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()

        # Drop empty column
        df = df.drop("Unnamed: 0", axis=1)

        # Recast Amount column as float
        df["Amount"] = df["Amount"].replace('[\$,]', '', regex=True).astype(float)

        # Recast dates as datetime (utc=True handles mixed timezones)
        df["Date"] = pd.to_datetime(df["Date"], format='mixed', utc=True)
        df["Month"] = pd.to_datetime(df["Month"], format='mixed', utc=True)
        df["Week"] = pd.to_datetime(df["Week"], format='mixed', utc=True)
        df["Date Added"] = pd.to_datetime(df["Date Added"], format='mixed', utc=True)
        df["Categorized Date"] = pd.to_datetime(df["Categorized Date"], format='mixed', utc=True)

        # Use better strings for Month and Week columns
        df["Month"] = df["Month"].dt.strftime('%Y-%m')
        df["Week"] = df["Week"].dt.strftime('%U')

        df = df.filter(["Date", "Category", "Amount", "Account", "Month", "Full Description", "Group", "Type", "Institution", "Account #"])

        self.scrubbed_df = df

    def get_total_months(
            self
    ) -> int:
        """Return the total amount of months in the data set as an int"""
        oldest_date = self.scrubbed_df["Date"].min()
        latest_date = self.scrubbed_df["Date"].max()
        total_months = math.ceil((latest_date - oldest_date)/np.timedelta64(1, 'M'))

        return total_months

    def get_groups(
            self
    ) -> List[str]:
        """Return the unique list of account group names"""
        return self.scrubbed_df.sort_values("Group")["Group"].unique()

    def get_group_categories(
        self,
        group: str
    ) -> List[str]:
        """Return all unique category names from a given group"""
        df = self.scrubbed_df.copy()
        df = df[df["Group"] == group]

        return df["Category"].unique()

    def get_group_category_stats(
            self,
            group: str
    ) -> pd.DataFrame:
        """Return a data frame summarizing the transaction amounts per group"""
        df = self.scrubbed_df.copy()
        df = df[df["Group"] == group]
        # TODO: There is a bug here when the dataframe has no rows
        df = df.groupby('Category').describe().unstack(1).reset_index().pivot(index='Category', values=0, columns='level_1')

        return df

    def filter_transactions(
            self,
            include_categories: List[str] = [],
            ignore_categories: List[str] = [],
            include_groups: List[str] = [],
            ignore_groups: List[str] = [],
            include_types: List[str] = [],
            ignore_types: List[str] = [],
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None,
            filtered_columns: List[str] = [],
            group_by_column: Optional[str] = None,
    ) -> pd.DataFrame:
        """Filter transactions based on various attributes. Optionally group by a given column"""
        df = self.scrubbed_df.copy()
        df = df.sort_values("Date")

        if include_categories:
            df = df[df["Category"].isin(include_categories)]
        df = df[-df["Category"].isin(ignore_categories)]

        if include_groups:
            df = df[df["Group"].isin(include_groups)]
        df = df[-df["Group"].isin(ignore_groups)]

        if include_types:
            df = df[df["Type"].isin(include_types)]
        df = df[-df["Group"].isin(ignore_types)]

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
            include_categories: List[str] = [],
            ignore_categories: List[str] = [],
            include_groups: List[str] = [],
            ignore_groups: List[str] = [],
            include_types: List[str] = [],
            ignore_types: List[str] = [],
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None,
            invert_amount: bool = False
    ) -> pd.DataFrame:
        """Get the total spending per group over a specified period"""
        df = self.scrubbed_df.copy()
        df = df.filter(["Date", "Category", "Group", "Amount", "Type"])
        df = df.sort_values("Date")

        if include_categories:
            df = df[df["Category"].isin(include_categories)]
        df = df[-df["Category"].isin(ignore_categories)]

        if include_groups:
            df = df[df["Group"].isin(include_groups)]
        df = df[-df["Group"].isin(ignore_groups)]

        if include_types:
            df = df[df["Type"].isin(include_types)]
        df = df[-df["Group"].isin(ignore_types)]

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()
        df = df[df["Date"].between(start_date, end_date)]

        if invert_amount:
            df["Amount"] = df["Amount"] * -1

        df = df.groupby("Group").sum(numeric_only=True)

        return df

    def get_amount_by_group_category(
            self,
            group: str,
            include_categories: List[str] = [],
            ignore_categories: List[str] = [],
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None,
            invert_amount: bool = False,
    ) -> pd.DataFrame:
        """Get the total group spending per categories over a specified period"""
        df = self.scrubbed_df.copy()
        df = df[df["Group"] == group]
        df = df.filter(["Date", "Group", "Category", "Amount", "Type"])
        df = df.sort_values("Date")

        # If include_categories is empty, include all categories
        if include_categories:
            df = df[df["Category"].isin(include_categories)]
        df = df[-df["Category"].isin(ignore_categories)]

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()
        df = df[df["Date"].between(start_date, end_date)]

        if invert_amount:
            df["Amount"] = df["Amount"] * -1

        df = df.groupby("Category").sum(numeric_only=True)

        return df

    def get_monthly_amounts_by_category(
            self,
            category: str,
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None,
            invert_amount: bool = False
    ) -> pd.DataFrame:
        """Get the total monthly transaction amount by a specified category"""
        df = self.scrubbed_df.copy()
        df = df.sort_values(["Date"])
        df = df[df["Category"] == category]
        df = df.filter(["Date", "Month", "Group", "Category", "Amount", "Type"])

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()

        df = df[df["Date"].between(start_date, end_date)]

        if invert_amount:
            df["Amount"] = df["Amount"] * -1

        df = df.groupby("Month").sum(numeric_only=True)

        return df

    def get_monthly_amounts_by_group(
            self,
            group: str,
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None,
            invert_amount: bool = False
    ) -> pd.DataFrame:
        """Get the total monthly transaction amount by a specified group"""
        df = self.scrubbed_df.copy()
        df = df.sort_values(["Date"])
        df = df[df["Group"] == group]
        df = df.filter(["Date", "Month", "Group", "Category", "Amount", "Type"])

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()

        df = df[df["Date"].between(start_date, end_date)]

        if invert_amount:
            df["Amount"] = df["Amount"] * -1

        df = df.groupby("Month").sum(numeric_only=True)

        return df

    def get_transactions_by_category(
            self,
            category: str,
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None
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
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None
    ) -> pd.DataFrame:
        """Get all transactions for a specific group"""
        return self.filter_transactions(
            include_groups=[group],
            start_date=start_date,
            end_date=end_date
        )

    def get_category_stats_by_group(
            self,
            group: str
    ) -> pd.DataFrame:
        """Return a data frame summarizing the transaction amounts per group"""
        df = self.scrubbed_df.copy()
        df = df[df["Group"] == group]
        # TODO: There is a bug here when the dataframe has no rows
        df = df.groupby('Category').describe().unstack(1).reset_index().pivot(index='Category', values=0, columns='level_1')

        return df


class BalanceHistorySpreadsheet(Spreadsheet):
    name = "balance_history_spreadsheet"

    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()

        # Drop empty column
        df = df.drop("Unnamed: 0", axis=1)

        # Recast Amount column as float
        df["Balance"] = df["Balance"].replace('[\$,]', '', regex=True).astype(float)

        # Recast dates as datetime (utc=True handles mixed timezones)
        df["Date"] = pd.to_datetime(df["Date"], format='mixed', utc=True)
        df["Time"] = pd.to_datetime(df["Time"], format='mixed', utc=True)
        df["Month"] = pd.to_datetime(df["Month"], format='mixed', utc=True)
        df["Week"] = pd.to_datetime(df["Week"], format='mixed', utc=True)
        df["Date Added"] = pd.to_datetime(df["Date Added"], format='mixed', utc=True)

        # Use better strings for Month and Week columns
        df["Month"] = df["Month"].dt.strftime('%Y-%m')
        df["Week"] = df["Week"].dt.strftime('%U')

        df = df[df["Hide"] != "Hide"]

        self.scrubbed_df = df

    def get_groups(
            self
    ) -> List[str]:
        """Return the unique list of account group names"""
        return self.scrubbed_df.sort_values("Group")["Group"].unique()

    def get_latest_balance_by_group(
            self,
            group: str,
            end_date: Optional[datetime.datetime] = None
    ) -> Tuple[pd.DataFrame, float]:
        """Summarize balance information by balance_history group"""
        df = self.scrubbed_df.copy()

        start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()
        df = df[df["Date"].between(start_date, end_date)]

        df = df.sort_values(by='Date')
        df = df.drop_duplicates('Account ID', keep='last')
        df = df[df["Group"] == group]
        df = df.filter(["Account", "Balance"])

        total = float(df["Balance"].sum())

        return df, total

    def get_balance_history_by_group(
            self,
            group: str,
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None
    ) -> pd.DataFrame:
        """Get the balance history for all accounts under a single group"""
        df = self.scrubbed_df.copy()
        df = df[df["Group"] == group]
        account_ids = df["Account ID"].unique()

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()

        columns = ["Date", "Account", "Account ID", "Institution", "Group", "Balance"]
        agg_df = pd.DataFrame(columns=columns)
        for account_id in account_ids:
            account_df = self.get_balance_history_by_account_id(
                account_id=account_id,
                start_date=start_date,
                end_date=end_date,
                columns=columns
            )
            agg_df = pd.concat([agg_df, account_df])

        return agg_df.groupby(agg_df["Date"])["Balance"].sum()

    def get_balance_history_by_account_id(
            self,
            account_id: str,
            start_date: datetime,
            end_date: datetime,
            columns: List[str] = ["Date", "Account", "Account ID", "Institution", "Group", "Balance"]
    ) -> pd.DataFrame:
        """Get the balance history for a balance_history group"""
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
        df = df.bfill().fillna(method="ffill")  # bfill fills empty start dates, ffill fills empty middle dates

        return df

    def get_balance_delta(
            self,
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None
    ) -> float:
        """Get the difference in account balance at the beginning and ending of a period"""



