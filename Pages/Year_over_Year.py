import streamlit as st

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet
from src.page_helpers import render_category_page, render_group_page


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    st.header("Year over Year Comparison")
    
    # Create tabs for different spending categories
    tab1, tab2, tab3 = st.tabs(["💡 Bills", "🍔 Food", "🛍️ Discretionary"])
    
    with tab1:
        st.subheader("Bills")
        categories = [
            "Electric Bill",
            "Gas Bill",
            "Water Bill",
            "Phone Bill",
            "Internet Bill",
            "Automobile Fuel"
        ]
        render_category_page(categories, transactions_spreadsheet)
    
    with tab2:
        st.subheader("Food")
        categories = [
            "Groceries",
            "Restaurants / Bars"
        ]
        render_category_page(categories, transactions_spreadsheet)
    
    with tab3:
        st.subheader("Discretionary Spending")
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

