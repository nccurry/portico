import streamlit as st
import pandas as pd

from src.spreadsheet import load_transactions_data, TransactionsSpreadsheet
from src.page_helpers import render_category_page, render_group_page


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    st.header("Year over Year Comparison")

    all_categories = sorted([str(c) for c in transactions_spreadsheet.scrubbed_df['Category'].unique()
                             if pd.notna(c) and str(c).strip()])
    all_groups = sorted([str(g) for g in transactions_spreadsheet.scrubbed_df['Group'].unique()
                         if pd.notna(g) and str(g).strip() and g != 'Transfer'])

    tab1, tab2 = st.tabs(["By Category", "By Group"])

    with tab1:
        default_cats = [c for c in ["Electric Bill", "Gas Bill", "Water Bill", "Phone Bill",
                                     "Internet Bill", "Automobile Fuel", "Groceries",
                                     "Restaurants / Bars"] if c in all_categories]
        selected = st.multiselect("Select Categories", options=all_categories, default=default_cats)
        if selected:
            render_category_page(selected, transactions_spreadsheet)

    with tab2:
        default_groups = [g for g in ["Shopping", "Travel", "Entertainment"] if g in all_groups]
        selected = st.multiselect("Select Groups", options=all_groups, default=default_groups)
        if selected:
            render_group_page(selected, transactions_spreadsheet)


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()

    configure_page(transactions_spreadsheet)


if __name__ == "__main__":
    main()

