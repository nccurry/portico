import streamlit as st

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet
from src.page_helpers import render_category_page


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    categories = [
        "Electric Bill",
        "Gas Bill",
        "Water Bill",
        "Phone Bill",
        "Internet Bill",
        "Automobile Fuel"
    ]
    
    render_category_page(categories, transactions_spreadsheet)


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet)


if __name__ == "__main__":
    main()
