from abc import ABCMeta, abstractmethod
from typing import Optional

import streamlit as st
from streamlit.commands.page_config import Layout, PageIcon, InitialSideBarState, MenuItems
from streamlit.runtime.state import SessionStateProxy
from dataclasses import dataclass


@dataclass
class PageConfig:
    """Configuration for a Streamlit Page. Expected to get passed to the set_page_config function"""
    page_title: Optional[str] = None,
    page_icon: Optional[PageIcon] = None,
    layout: Layout = "centered",
    initial_sidebar_state: InitialSideBarState = "auto",
    menu_items: Optional[MenuItems] = None


class Page(metaclass=ABCMeta):
    config: Optional[PageConfig]

    def __init__(
            self,
            page_config: Optional[PageConfig] = None
    ) -> None:
        self.config = page_config

    def set_page_config(self) -> None:
        """Apply the Streamlit page configuration"""
        if self.config:
            st.set_page_config(**self.config)

    @abstractmethod
    def initialize_session_state(
            self,
            session_state: SessionStateProxy,
    ) -> None:
        """Initialize Streamlit session state for this page"""
        ...
