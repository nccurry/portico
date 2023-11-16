from datetime import datetime
from typing import Dict

import pandas as pd
from src.data.balance_history import get_latest_balance_by_group, get_balance_history_by_group
from src.page.page import HomePage
import streamlit as st

# Initialize page

home_page = HomePage()

# Get data

group_filter = ["House", "Loan"]
groups = []
for group in home_page.spreadsheets["bhs"].scrubbed_df.sort_values("Group")["Group"].unique():
    if group not in group_filter:
        groups.append(group)
data: Dict[str, Dict[str, pd.DataFrame]] = {}
for group in groups:
    latest_balance_df, latest_balance_total = get_latest_balance_by_group(
        scrubbed_data_frame=home_page.spreadsheets["bhs"].scrubbed_df,
        group=group
    )
    balance_history_df = get_balance_history_by_group(
        scrubbed_data_frame=home_page.spreadsheets["bhs"].scrubbed_df,
        group=group
    )
    data[group] = dict(
        latest_balance_df=latest_balance_df,
        latest_balance_total=latest_balance_total,
        balance_history_df=balance_history_df
    )

# Configure UI

for group in groups:
    with st.expander(f'# **{group}**: ${"{:,.2f}".format(data[group]["latest_balance_total"])}', expanded=True):
        col1, col2 = st.columns(2)
        col1.dataframe(
            data=data[group]["latest_balance_df"].sort_values("Balance", ascending=False),
            hide_index=True,
            width=300,
            column_config={
                "Account": st.column_config.Column(
                    width="small"
                ),
                "Balance": st.column_config.NumberColumn(
                    format="$ %.2f"
                )
            }
        )
        col2.line_chart(
            data=data[group]["balance_history_df"],
            use_container_width=True,
            height=200
        )


st.markdown("**Recent Transactions**")

transactions_df = home_page.spreadsheets["ts"].scrubbed_df
transactions_df = transactions_df[transactions_df["Date"] > datetime.now() - pd.to_timedelta("10day")]
transactions_df = transactions_df.sort_values(by='Date', ascending=False)
transactions_df = transactions_df.filter(["Date", "Full Description", "Amount", "Account", "Category", "Group"])
st.dataframe(
    data=transactions_df,
    hide_index=True,
    column_config={
        "Date": st.column_config.DateColumn(
            disabled=True,
        )
    }
)