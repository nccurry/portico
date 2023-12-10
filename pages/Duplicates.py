import streamlit as st
from spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet

st.set_page_config(layout="wide")

transaction_spreadsheet = TransactionsSpreadsheet()
balance_history_spreadsheet = BalanceHistorySpreadsheet()

transactions_df = transaction_spreadsheet.scrubbed_df

duplicate_transactions_df = transactions_df[transactions_df.duplicated(
    subset=["Amount", "Date", "Account", "Institution"],
    keep=False
)]

st.dataframe(duplicate_transactions_df)

accounts_df = balance_history_spreadsheet.scrubbed_df

duplicate_accounts = accounts_df[accounts_df.duplicated(
    subset=["Account", "Account #", "Institution"],
    keep=False
)]

st.dataframe(duplicate_accounts)