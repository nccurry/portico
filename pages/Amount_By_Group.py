from datetime import date
import altair as alt
import dateutil
import streamlit as st
from typing import List
from spreadsheet import TransactionsSpreadsheet
from transactions import get_category_stats_by_group

st.set_page_config(layout="wide")

transaction_spreadsheet = TransactionsSpreadsheet()

# Configure UI

st.header("Amount by Group", divider="blue")

col1, col2 = st.columns([0.6, 0.4])

lookback_months_slider: int = col2.slider(
    label="Lookback (Months)",
    min_value=1,
    max_value=transaction_spreadsheet.get_total_months(),
    value=3,
)

group_selectbox: str = col2.selectbox(
    label="Group",
    options=transaction_spreadsheet.get_groups(),
)

included_categories: List[str] = col2.multiselect(
    label="Included Categories",
    options=transaction_spreadsheet.get_group_categories(group_selectbox),
    default=[]
)

ignored_categories: List[str] = col2.multiselect(
    label="Ignored Categories",
    options=transaction_spreadsheet.get_group_categories(group_selectbox),
    default=[]
)

# reset = col2.button(
#     label="Clear",
#     type="primary",
#     on_click=mep.clear_filtered_data
# )

filtered_df = transaction_spreadsheet.scrubbed_df.copy()

# Filter by selected group
filtered_df = filtered_df.loc[filtered_df["Group"] == group_selectbox]
categories = transaction_spreadsheet.get_group_categories(group_selectbox)

# Filter by included / ignored categories
if included_categories:
    filtered_df = filtered_df[filtered_df["Category"].isin(included_categories)]
if ignored_categories:
    filtered_df = filtered_df[-filtered_df["Category"].isin(ignored_categories)]

# Filter by Month lookback
first_of_the_month = date.today().replace(day=1)
month_cutoff = first_of_the_month + dateutil.relativedelta.relativedelta(months=-(lookback_months_slider + 1))
filtered_df = filtered_df[filtered_df["Date"].dt.date > month_cutoff]

chart = alt.Chart(filtered_df).mark_bar().encode(
   x=alt.X('Month'),
   xOffset='Category',
   y=alt.Y('Amount'),
   color='Category'
).configure_view(
    stroke=None,
)
col1.altair_chart(
    altair_chart=chart,
    use_container_width=True
)

st.subheader("Transactions", divider="blue")
transactions_stats = get_category_stats_by_group(
    data_frame=filtered_df,
    group=group_selectbox
)
st.text("Stats")
st.dataframe(
    data=transactions_stats,
    use_container_width=True
)
st.text("All Transactions")
st.dataframe(
    data=filtered_df,
    hide_index=True,
    use_container_width=True
)
