import os
from abc import ABCMeta, abstractmethod
from datetime import date
from typing import Optional, Dict

import dateutil
import streamlit as st
from streamlit.commands.page_config import Layout, PageIcon, InitialSideBarState, MenuItems
from dataclasses import dataclass, asdict

from transactions import get_total_months, get_group_categories
from spreadsheet import Spreadsheet, TransactionsSpreadsheet, BalanceHistorySpreadsheet


@dataclass
class PageConfig:
    """Configuration for a Streamlit Page. Expected to get passed to the set_page_config function"""
    page_title: Optional[str] = None
    page_icon: Optional[PageIcon] = None
    layout: Layout = "wide"
    initial_sidebar_state: InitialSideBarState = "auto"
    menu_items: Optional[MenuItems] = None

    def __dict__(self):
        """Return the dict representation of this dataclass"""
        d = {}
        for k, v in asdict(self).items():
            if v is not None:
                d[k] = v
        return d


class Page(metaclass=ABCMeta):
    state_prefix: str = "p"
    config: Optional[PageConfig] = PageConfig()
    spreadsheets: Dict[str, Spreadsheet] = {}

    def __init__(
            self,
            config: Optional[PageConfig] = None
    ) -> None:
        if config:
            self.config = config
        self.set_page_config()
        self.load_spreadsheets()
        self.initialize_session_state()

    def set_page_config(self) -> None:
        """Apply the Streamlit page configuration"""
        if self.config:
            # Convert dataclass to key / value function args
            st.set_page_config(**self.config.__dict__())

    @abstractmethod
    def load_spreadsheets(self) -> None:
        """Load the data from the Google Sheets spreadsheets"""

    @abstractmethod
    def initialize_session_state(self) -> None:
        """Initialize Streamlit session state for this page"""

    @abstractmethod
    def ui_widget_callback(self) -> None:
        """Callback function for Streamlit UI widgets"""


class HomePage(Page):
    state_prefix = "hp"

    def load_spreadsheets(self) -> None:
        ts_url = os.environ.get("TRANSACTIONS_SPREADSHEET_URL")
        if not ts_url:
            raise ValueError("You must set a value for the environment variable TRANSACTIONS_SPREADSHEET_URL")
        ts = TransactionsSpreadsheet(url=ts_url)
        self.spreadsheets[ts.name] = ts

        bhs_url = os.environ.get("BALANCE_HISTORY_SPREADSHEET_URL")
        if not bhs_url:
            raise ValueError("You must set a value for the environment variable BALANCE_HISTORY_SPREADSHEET_URL")
        bhs = BalanceHistorySpreadsheet(url=bhs_url)
        self.spreadsheets[bhs.name] = bhs

    def initialize_session_state(
            self,
            force: bool = False
    ) -> None:
        ...

    def ui_widget_callback(self) -> None:
        ...


class MonthlyExpensesPage(Page):
    state_prefix = "mep"

    def load_spreadsheets(self) -> None:
        ts_url = os.environ.get("TRANSACTIONS_SPREADSHEET_URL")
        ts = TransactionsSpreadsheet(url=ts_url)
        self.spreadsheets[ts.name] = ts

    def initialize_session_state(
            self,
            force: bool = False
    ) -> None:
        ts_scrubbed_df = self.spreadsheets["transactions_spreadsheet"].scrubbed_df
        ts_groups = self.spreadsheets["transactions_spreadsheet"].scrubbed_df["Group"].unique()

        if f'{self.state_prefix}_lookback_months' not in st.session_state or force:
            st.session_state[f'{self.state_prefix}_lookback_months'] = 3

        if f'{self.state_prefix}_total_months' not in st.session_state or force:
            st.session_state[f'{self.state_prefix}_total_months'] = get_total_months(ts_scrubbed_df)

        if f'{self.state_prefix}_selected_group' not in st.session_state or force:
            st.session_state[f'{self.state_prefix}_selected_group'] = ts_groups[0]

        if f'{self.state_prefix}_total_groups' not in st.session_state or force:
            st.session_state[f'{self.state_prefix}_total_groups'] = ts_groups

        if f'{self.state_prefix}_group_categories' not in st.session_state or force:
            st.session_state[f'{self.state_prefix}_group_categories'] = get_group_categories(
                data_frame=ts_scrubbed_df,
                group=ts_groups[0]
            )

        if f'{self.state_prefix}_included_categories' not in st.session_state or force:
            st.session_state[f'{self.state_prefix}_included_categories'] = []

        if f'{self.state_prefix}_ignored_categories' not in st.session_state or force:
            st.session_state[f'{self.state_prefix}_ignored_categories'] = []

        self.update_filtered_data()

    def update_filtered_data(self) -> None:
        """Filter data in session_state based on widget settings"""
        df = self.spreadsheets["transactions_spreadsheet"].scrubbed_df.copy()

        # Filter by selected group
        df = df.loc[df["Group"] == st.session_state[f'{self.state_prefix}_selected_group']]

        # Set new group categories
        st.session_state[f'{self.state_prefix}_group_categories'] = get_group_categories(
            data_frame=df,
            group=st.session_state[f'{self.state_prefix}_selected_group']
        )

        # Filter by included / ignored categories
        if st.session_state[f'{self.state_prefix}_included_categories']:
            df = df[df["Category"].isin(st.session_state[f'{self.state_prefix}_included_categories'])]
        if st.session_state[f'{self.state_prefix}_ignored_categories']:
            df = df[-df["Category"].isin(st.session_state[f'{self.state_prefix}_ignored_categories'])]

        # Filter by Month lookback
        first_of_the_month = date.today().replace(day=1)
        month_cutoff = first_of_the_month + dateutil.relativedelta.relativedelta(
            months=-st.session_state[f'{self.state_prefix}_lookback_months'] + 1)
        df = df[df["Date"].dt.date > month_cutoff]

        # TODO: Figure out where to store data inside / outside session state
        st.session_state.filtered_data = df

    def clear_filtered_data(self):
        """Reset session state"""
        self.initialize_session_state(force=True)
        self.update_filtered_data()

    def ui_widget_callback(self) -> None:
        update = False

        if st.session_state[f'{self.state_prefix}_lookback_months'] != st.session_state.slider_lookback_months:
            st.session_state[f'{self.state_prefix}_lookback_months'] = st.session_state.slider_lookback_months
            update = True

        if st.session_state[f'{self.state_prefix}_selected_group'] != st.session_state.selectbox_group:
            st.session_state[f'{self.state_prefix}_selected_group'] = st.session_state.selectbox_group
            st.session_state.multiselect_included_categories = []
            st.session_state.multiselect_ignored_categories = []
            update = True

        if st.session_state[f'{self.state_prefix}_included_categories'] != st.session_state.multiselect_included_categories:
            st.session_state[f'{self.state_prefix}_included_categories'] = st.session_state.multiselect_included_categories
            update = True

        if st.session_state[f'{self.state_prefix}_ignored_categories'] != st.session_state.multiselect_ignored_categories:
            st.session_state[f'{self.state_prefix}_ignored_categories'] = st.session_state.multiselect_ignored_categories
            update = True

        if update:
            self.update_filtered_data()


class BillsPage(Page):
    state_prefix = "bp"

    def load_spreadsheets(self) -> None:
        ts_url = os.environ.get("TRANSACTIONS_SPREADSHEET_URL")
        ts = TransactionsSpreadsheet(url=ts_url)
        self.spreadsheets[ts.name] = ts

    def initialize_session_state(
            self,
            force: bool = False
    ) -> None:
        ...

    def ui_widget_callback(self) -> None:
        ...