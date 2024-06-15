import streamlit as st

from src.sidebar import configure_sidebar
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet


def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    categories = [
        "Electric Bill",
        "Gas Bill",
        "Water Bill",
        "Phone Bill",
        "Internet Bill",
        "Automobile Fuel"
    ]

    for category in categories:
        monthly_amounts_df = transactions_spreadsheet.get_monthly_amounts_by_category(
            category=category,
            invert_amount=True
        )
        st.subheader(category)
        col1, col2 = st.columns([1, 4])
        col1.dataframe(monthly_amounts_df)
        col2.line_chart(
            data=monthly_amounts_df
        )


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = TransactionsSpreadsheet()
    balance_history_spreadsheet = BalanceHistorySpreadsheet()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()
