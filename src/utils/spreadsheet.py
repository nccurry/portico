import streamlit as st
from streamlit.runtime.state import SessionStateProxy
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from abc import ABCMeta, abstractmethod


class Spreadsheet(metaclass=ABCMeta):
    """Class used to interact with Spreadsheet data in Google Sheets"""
    name: str
    url: str
    raw_df: pd.DataFrame
    scrubbed_df: pd.DataFrame

    def __init__(self, name: str, url: str) -> None:
        self.name = name
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

    def cache(
            self,
            session_state: SessionStateProxy,
            state_prefix: str = "ss",
            force: bool = False
    ) -> None:
        """Cache the Spreadsheet data in the Streamlit session state"""
        if f"{self.name}_raw_df" not in session_state or force:
            session_state[f"{state_prefix}_{self.name}_raw_df"] = self.raw_df

        if f"{self.name}_scrubbed_df" not in session_state or force:
            session_state[f"{state_prefix}_{self.name}_scrubbed_df"] = self.scrubbed_df


class TransactionSpreadsheet(Spreadsheet):
    def scrub(self) -> None:
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

        self.scrubbed_df = df


class BalanceHistorySpreadsheet(Spreadsheet):
    def scrub(self) -> None:
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

        self.scrubbed_df = df