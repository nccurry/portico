import os
from abc import ABCMeta, abstractmethod
from typing import Optional, Dict

import streamlit as st
from streamlit.commands.page_config import Layout, PageIcon, InitialSideBarState, MenuItems
from dataclasses import dataclass, asdict

from src.utils.spreadsheet import Spreadsheet, TransactionSpreadsheet, BalanceHistorySpreadsheet


@dataclass
class PageConfig:
    """Configuration for a Streamlit Page. Expected to get passed to the set_page_config function"""
    page_title: Optional[str] = None
    page_icon: Optional[PageIcon] = None
    layout: Layout = "wide"
    initial_sidebar_state: InitialSideBarState = "collapsed"
    menu_items: Optional[MenuItems] = None

    def __dict__(self):
        """Return the dict representation of this dataclass"""
        d = {}
        for k, v in asdict(self).items():
            if v is not None:
                d[k] = v
        return d


class Page(metaclass=ABCMeta):
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
    def load_spreadsheets(self) -> None:
        transaction_spreadsheet_url = os.environ.get("TRANSACTIONS_SPREADSHEET_URL")
        self.spreadsheets["transactions"] = TransactionSpreadsheet(
            name="transactions",
            url=transaction_spreadsheet_url
        )

        balance_history_spreadsheet_url = os.environ.get("BALANCE_HISTORY_SPREADSHEET_URL")
        self.spreadsheets["balance_history"] = BalanceHistorySpreadsheet(
            name="balance_history",
            url=balance_history_spreadsheet_url
        )

    def initialize_session_state(
            self,
            force: bool = False
    ) -> None:
        for v in self.spreadsheets.values():
            v.cache(
                force=force
            )

    def ui_widget_callback(self) -> None:
        ...