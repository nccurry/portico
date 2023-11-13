import os
from datetime import datetime
import pandas as pd

from src.utils.page import HomePage, PageConfig
from src.utils.spreadsheet import TransactionSpreadsheet, BalanceHistorySpreadsheet
from src.utils.utils import initialize_session_state
import streamlit as st
import os

# Initialize Page configuration

home_page = HomePage()

# Data
checking_df = st.session_state.ss_balance_history_scrubbed_df
checking_df = checking_df.sort_values(by='Date')
checking_df = checking_df.drop_duplicates('Account ID', keep='last')
checking_df = checking_df[checking_df["Group"] == "Checking"]
checking_df = checking_df.filter(["Account", "Balance"])
checking_total = float(checking_df["Balance"].sum())

saving_df = st.session_state.ss_balance_history_scrubbed_df
saving_df = saving_df.sort_values(by='Date')
saving_df = saving_df.drop_duplicates('Account ID', keep='last')
saving_df = saving_df[saving_df["Group"] == "Saving"]
saving_df = saving_df.filter(["Account", "Balance"])
saving_total = float(saving_df["Balance"].sum())

credit_df = st.session_state.ss_balance_history_scrubbed_df
credit_df = credit_df.sort_values(by='Date')
credit_df = credit_df.drop_duplicates('Account ID', keep='last')
credit_df = credit_df[credit_df["Group"] == "Credit Card"]
credit_df = credit_df.filter(["Account", "Balance"])
credit_total = credit_df["Balance"].sum()

investment_df = st.session_state.ss_balance_history_scrubbed_df
investment_df = investment_df.sort_values(by='Date')
investment_df = investment_df.drop_duplicates('Account ID', keep='last')
investment_df = investment_df[investment_df["Group"] == "Investment"]
investment_df = investment_df.filter(["Account", "Balance"])
investment_total = investment_df["Balance"].sum()

# UI

col1, col2, col3 = st.columns(3)

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


col3.header("Investments")
col3.subheader(f'${"{:,.2f}".format(investment_total)}')
col3.dataframe(
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