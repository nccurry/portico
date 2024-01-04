from datetime import datetime
from typing import Dict
import pandas as pd
from src.sidebar import configure_sidebar
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet
import streamlit as st


def configure_page(
        transaction_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    time_period_radio = st.session_state["time_period_radio"]
    start_date_input = st.session_state["start_date_input"]
    end_date_input = st.session_state["end_date_input"]
    start_date = st.session_state["start_date"]
    end_date = st.session_state["end_date"]
    filtered_account_groups_multiselect = st.session_state["filtered_account_groups_multiselect"]

    if time_period_radio == "Custom":
        start_date = datetime(start_date_input.year, start_date_input.month, start_date_input.day)
        end_date = datetime(end_date_input.year, end_date_input.month, end_date_input.day)

    amount_by_expense_group_df = transaction_spreadsheet.get_amount_by_group(
        start_date=start_date,
        end_date=end_date,
        ignore_groups=["Transfer"]
    )
    amount_by_income_categories_df = transaction_spreadsheet.get_group_amount_by_category(
        group="Income",
        start_date=start_date,
        end_date=end_date
    )

    st.header(f"Financial Summary")
    st.subheader(
        body=f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}",
        divider="blue")
    col1, col2 = st.columns(2)
    col1.subheader(f"Expenses: -${-amount_by_expense_group_df['Amount'].sum():,.2f}")
    col1.bar_chart(
        data=amount_by_expense_group_df,
        color="#d47468"
    )
    col2.subheader(f"Income: ${amount_by_income_categories_df['Amount'].sum():,.2f}")
    col2.bar_chart(
        data=amount_by_income_categories_df,
        color="#7dc781"
    )

    groups = []
    for group in balance_history_spreadsheet.get_groups():
        if group not in filtered_account_groups_multiselect:
             groups.append(group)  # TODO: This will fail if there is a nan

    data: Dict[str, Dict[str, pd.DataFrame]] = {}
    for group in groups:
        latest_balance_df, latest_balance_total = balance_history_spreadsheet.get_latest_balance_by_group(
            group=group,
            end_date=end_date
        )
        balance_history_df = balance_history_spreadsheet.get_balance_history_by_group(
            group=group,
            start_date=start_date,
            end_date=end_date
        )
        data[group] = dict(
            latest_balance_df=latest_balance_df,
            latest_balance_total=latest_balance_total,
            balance_history_df=balance_history_df
        )

    st.header("Account Balances")
    for group in groups:
        st.subheader(group)
        delta = data[group]["balance_history_df"].reset_index()["Balance"].iloc[-1] - data[group]["balance_history_df"].reset_index()["Balance"].iloc[0]
        st.metric(
            label="Total",
            value="${:,.2f}".format(data[group]["latest_balance_total"]),
            delta="{:,.2f}".format(delta),
            delta_color="inverse" if group in ["Credit Card"] else "normal"
        )
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


    st.subheader("Transactions")

    transactions_df = transaction_spreadsheet.scrubbed_df
    transactions_df = transactions_df.sort_values(by='Date', ascending=False)
    transactions_df = transactions_df[transactions_df["Date"].between(start_date, end_date)]
    transactions_df = transactions_df.filter(["Date", "Full Description", "Amount", "Account", "Category", "Group"])
    st.dataframe(
        data=transactions_df,
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn(
                disabled=True,
            )
        },
        use_container_width=True
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
