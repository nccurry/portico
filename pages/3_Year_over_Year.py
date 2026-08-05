import streamlit as st

from src.spreadsheet import load_transactions_data, TransactionsSpreadsheet
from src.page_helpers import render_year_over_year_page, render_data_refresh_controls


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    """Render category/group selectors and year-over-year comparison charts."""
    st.header("Year over Year Comparison")

    all_categories = transactions_spreadsheet.get_all_categories()
    all_groups = transactions_spreadsheet.get_all_groups()

    tab1, tab2 = st.tabs(["By Category", "By Group"])

    with tab1:
        default_cats = [c for c in ["Electric Bill", "Gas Bill", "Water Bill", "Phone Bill",
                                     "Internet Bill", "Automobile Fuel", "Groceries",
                                     "Restaurants / Bars"] if c in all_categories]
        selected = st.multiselect("Select Categories", options=all_categories, default=default_cats)
        if selected:
            render_year_over_year_page(selected, transactions_spreadsheet, by="category")

    with tab2:
        default_groups = [g for g in ["Shopping", "Travel", "Entertainment"] if g in all_groups]
        selected = st.multiselect("Select Groups", options=all_groups, default=default_groups)
        if selected:
            render_year_over_year_page(selected, transactions_spreadsheet, by="group")


def main() -> None:
    """Streamlit entry point for the Year over Year page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()

    transactions_spreadsheet = load_transactions_data()

    configure_page(transactions_spreadsheet)


if __name__ == "__main__":
    main()

