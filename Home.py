from datetime import datetime

import pandas as pd

from utils import load_data, initialize_session_state
import streamlit as st

st.set_page_config(layout="wide")

# Initialize
load_data()
initialize_session_state()


def get_account_balances(account_id: str, data_frame: pd.DataFrame) -> pd.Series:
    df = data_frame.copy()

    print(account_id, list(df.columns.values))
    df = df[df["Account ID"] == account_id]
    df = df[df["Date"] > datetime.now() - pd.to_timedelta("30day")]

    return df["Balance"]


# Data
cash_df = st.session_state.balances_scrubbed_data
cash_df = cash_df.sort_values(by='Date')
cash_df = cash_df.drop_duplicates('Account ID', keep='last')
cash_df = cash_df[cash_df["Group"] == "Cash"]
cash_df = cash_df.filter(["Account", "Balance"])

credit_df = st.session_state.balances_scrubbed_data
credit_df = credit_df.sort_values(by='Date')
credit_df = credit_df.drop_duplicates('Account ID', keep='last')
credit_df = credit_df[credit_df["Group"] == "Credit Card"]
credit_df = credit_df.filter(["Account", "Balance"])

investment_df = st.session_state.balances_scrubbed_data
investment_df = investment_df.sort_values(by='Date')
investment_df = investment_df.drop_duplicates('Account ID', keep='last')
investment_df = investment_df[investment_df["Group"] == "Investment"]
investment_df = investment_df.filter(["Account", "Balance"])

# UI

st.title("Financial Summary")

col1, col2, col3 = st.columns(3)

total = float(cash_df["Balance"].sum())
col1.header(f'Cash: ${"{:,.2f}".format(total)}')
col1.dataframe(
    data=cash_df,
    hide_index=True,
    width=300,
    column_config={
        "Account": st.column_config.Column(
            width="small"
        )
    }
)

total = credit_df["Balance"].sum()
col2.header(f'Credit: -${"{:,.2f}".format(total)}')
col2.dataframe(
    data=credit_df,
    hide_index=True,
    width=300,
    column_config={
        "Account": st.column_config.Column(
            width="small"
        )
    }
)

total = investment_df["Balance"].sum()
col3.header(f'Investments: ${"{:,.2f}".format(total)}')
col3.dataframe(
    data=investment_df,
    hide_index=True,
    width=300,
    column_config={
        "Account": st.column_config.Column(
            width="small"
        )
    }
)

st.write(st.session_state.balance_history_raw_data)