import datetime
import os
from typing import Optional, List, Tuple
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from abc import ABCMeta, abstractmethod
import math
import numpy as np


class Spreadsheet(metaclass=ABCMeta):
    """Class used to interact with Spreadsheet data in Google Sheets"""
    # Friendly name for this spreadsheet
    name: str

    # The environment variable string to use when looking up the spreadsheet url
    url_env_var_str: str

    # The spreadsheet url
    url: str

    # The raw, unscrubbed, data from the spreadsheet
    raw_df: pd.DataFrame

    # THe scrubbed data from the spreadsheet
    scrubbed_df: pd.DataFrame

    def __init__(
            self,
            url: Optional[str] = None
    ) -> None:
        if url:
            self.url = url
        else:
            url = os.environ.get(self.url_env_var_str)
            if not url:
                raise ValueError(f"You must supply a value for environment variable {self.url_env_var_str}")
            self.url = url
        self.load()
        self.scrub()

    def load(self) -> None:
        """Load data from the external spreadsheet"""
        conn = st.connection(name=self.name, type=GSheetsConnection)
        self.raw_df = conn.read(spreadsheet=self.url)

    @abstractmethod
    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        ...


class TransactionsSpreadsheet(Spreadsheet):
    name = "transactions_spreadsheet"
    url_env_var_str: str = "TRANSACTIONS_SPREADSHEET_URL"

    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()

        # Drop empty column
        df = df.drop("Unnamed: 0", axis=1)

        # Recast Amount column as float
        df["Amount"] = df["Amount"].replace('[\$,]', '', regex=True).astype(float)

        # Recast dates as datetime
        df["Date"] = pd.to_datetime(df["Date"])
        df["Month"] = pd.to_datetime(df["Month"])
        df["Week"] = pd.to_datetime(df["Week"])
        df["Date Added"] = pd.to_datetime(df["Date Added"])
        df["Categorized Date"] = pd.to_datetime(df["Categorized Date"])

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

    def get_amount_by_group(
            self,
            transaction_type: str = "Expense",
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None,
            ignore_groups: List[str] = []
    ) -> pd.DataFrame:
        """Get the total spending per group over a specified period"""
        df = self.scrubbed_df.copy()
        df = df[df["Type"] == transaction_type]
        df = df.filter(["Date", "Group", "Amount", "Type"])
        df = df.sort_values("Date")

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()

        df = df[df["Date"].between(start_date, end_date)]
        df = df[-df["Group"].isin(ignore_groups)]
        df = df.groupby("Group").sum()

        return df

    def get_group_amount_by_category(
            self,
            group: str,
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None,
            ignore_categories: List[str] = []
    ) -> pd.DataFrame:
        """Get the total group spending per categories over a specified period"""
        df = self.scrubbed_df.copy()
        df = df[df["Group"] == group]
        df = df.filter(["Date", "Group", "Category", "Amount", "Type"])
        df = df.sort_values("Date")

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()

        df = df[df["Date"].between(start_date, end_date)]
        df = df[-df["Category"].isin(ignore_categories)]
        df = df.groupby("Category").sum()

        return df

    def get_monthly_amounts_by_category(
            self,
            category: str,
            start_date: Optional[datetime.datetime] = None,
            end_date: Optional[datetime.datetime] = None
    ) -> pd.DataFrame:
        """Get the total monthly transaction amount by a specified category"""
        df = self.scrubbed_df.copy()
        df = df.sort_values("Date")
        df = df[df["Category"] == category]
        df = df.filter(["Month", "Group", "Category", "Amount", "Type"])

        if start_date is None:
            start_date = df["Date"].min()
        if end_date is None:
            end_date = df["Date"].max()

        df = df[df["Date"].between(start_date, end_date)]
        df = df.groupby("Month").sum()

        return df


class BalanceHistorySpreadsheet(Spreadsheet):
    name = "balance_history_spreadsheet"
    url_env_var_str: str = "BALANCE_HISTORY_SPREADSHEET_URL"

    def scrub(self) -> None:
        """Clean up the data stored in self.raw_df"""
        df = self.raw_df.copy()

        # Drop empty column
        df = df.drop("Unnamed: 0", axis=1)

        # Recast Amount column as float
        df["Balance"] = df["Balance"].replace('[\$,]', '', regex=True).astype(float)

        # Recast dates as datetime
        df["Date"] = pd.to_datetime(df["Date"])
        df["Time"] = pd.to_datetime(df["Time"])
        df["Month"] = pd.to_datetime(df["Month"])
        df["Week"] = pd.to_datetime(df["Week"])
        df["Date Added"] = pd.to_datetime(df["Date Added"])

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
            end_date: Optional[datetime] = None
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
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
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
        df = df.bfill().fillna(method="ffill") # bfill fills empty start dates, ffill fills empty middle dates

        return df

    def get_balance_delta(
            self,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> float:
        """Get the difference in account balance at the beginning and ending of a period"""
