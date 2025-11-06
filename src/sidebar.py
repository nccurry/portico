from datetime import datetime
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet
import streamlit as st
from src.utils import first_day_of_month, last_day_of_month, relative_date


def configure_sidebar(
        transaction_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    """Configure Streamlit sidebar widgets"""

    st.session_state["sidebar_configured"] = True
