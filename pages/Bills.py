
from page import BillsPage
import streamlit as st

from transactions import get_monthly_amounts_by_category

bills_page = BillsPage()

categories = [
    "Electric Bill",
    "Gas Bill",
    "Water Bill",
    "Phone Bill",
    "Internet Bill",
    "Automobile Fuel"
]


for category in categories:
    monthly_amounts_df = get_monthly_amounts_by_category(
        data_frame=bills_page.spreadsheets["ts"].scrubbed_df,
        category=category
    )
    st.subheader(category)
    col1, col2 = st.columns([1, 4])
    col1.dataframe(monthly_amounts_df)
    col2.line_chart(
        data=monthly_amounts_df
    )
