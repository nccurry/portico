import streamlit as st

from src.sidebar import configure_sidebar
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet

def configure_page(
        transaction_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    st.header("Spending at a Glance")

def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = TransactionsSpreadsheet()
    balance_history_spreadsheet = BalanceHistorySpreadsheet()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)

if __name__ == "__main__":
    main()