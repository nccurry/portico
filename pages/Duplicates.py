import streamlit as st

from src.sidebar import configure_sidebar
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet

def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    transactions_df = transactions_spreadsheet.scrubbed_df

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


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = TransactionsSpreadsheet()
    balance_history_spreadsheet = BalanceHistorySpreadsheet()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()
