import streamlit as st

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet
from src.page_helpers import render_group_page


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    groups = [
        "Shopping",
        "Travel",
        "Entertainment"
    ]
    
    render_group_page(groups, transactions_spreadsheet)


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet)


if __name__ == "__main__":
    main()

