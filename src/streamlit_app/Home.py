import os
from datetime import datetime
import pandas as pd

from src.utils.balance_history import summarize_balance_by_group
from src.utils.page import HomePage, PageConfig
from src.utils.spreadsheet import TransactionSpreadsheet, BalanceHistorySpreadsheet
from src.utils.utils import initialize_session_state
import streamlit as st
import os

# Initialize Page configuration

home_page = HomePage()

# Data
checking_df, checking_total = summarize_balance_by_group(
    data_frame=st.session_state.ss_balance_history_scrubbed_df,
    group="Checking"
)
saving_df, saving_total = summarize_balance_by_group(
    data_frame=st.session_state.ss_balance_history_scrubbed_df,
    group="Saving"
)
credit_df, credit_total = summarize_balance_by_group(
    data_frame=st.session_state.ss_balance_history_scrubbed_df,
    group="Credit Card"
)
investment_df, investment_total = summarize_balance_by_group(
    data_frame=st.session_state.ss_balance_history_scrubbed_df,
    group="Investment"
)

# UI

col1, col2 = st.columns(2)

col1.header("Checking")
col1.subheader(f'${"{:,.2f}".format(checking_total)}')
col1.dataframe(
    data=checking_df,
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

col1.header("Saving")
col1.subheader(f'${"{:,.2f}".format(saving_total)}')
col1.dataframe(
    data=saving_df,
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


col2.header("Credit")
col2.subheader(f'-${"{:,.2f}".format(credit_total)}')
col2.dataframe(
    data=credit_df,
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


col2.header("Investments")
col2.subheader(f'${"{:,.2f}".format(investment_total)}')
col2.dataframe(
    data=investment_df,
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

st.title("Recent Transactions")

transactions_df = st.session_state.ss_transactions_scrubbed_df
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