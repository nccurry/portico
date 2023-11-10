from utils import load_data, initialize_session_state
import streamlit as st

st.set_page_config(layout="wide")

# Initialize
load_data()
initialize_session_state()

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

col1.header("Cash")
col1.dataframe(cash_df, hide_index=True)

col2.header("Credit")
col2.dataframe(credit_df, hide_index=True)

col3.header("Investments")
col3.dataframe(investment_df, hide_index=True)

st.write(st.session_state.balance_history_raw_data)