from datetime import datetime
from typing import Dict
import pandas as pd
from src.sidebar import configure_sidebar
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet
import streamlit as st

from src.utils import relative_date, format_dollar_amount, first_day_of_month, last_day_of_month


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

    st.header("At a Glance")
    st.subheader("Discretionary Spending")
    periods = [
        {
            "label": "Last 7 Days",
            "relative_start_date": -7,
            "relative_end_date": -1,
            "relative_start_date_previous": -14,
            "relative_end_date_previous": -8,
            "start_date": relative_date(-7),
            "end_date": relative_date(-1),
            "start_date_previous": relative_date(-14),
            "end_date_previous": relative_date(-8),
        },
        {
            "label": "Last 14 Days",
            "start_date": relative_date(-14),
            "end_date": relative_date(-1),
            "start_date_previous": relative_date(-28),
            "end_date_previous": relative_date(-15),
        },
        {
            "label": "Last 28 Days",
            "start_date": relative_date(-28),
            "end_date": relative_date(-1),
            "start_date_previous": relative_date(-56),
            "end_date_previous": relative_date(-29),
        },
        {
            "label": "Last Month",
            "start_date": first_day_of_month(relative_months=-1),
            "end_date": last_day_of_month(relative_months=-1),
            "start_date_previous": first_day_of_month(relative_months=-2),
            "end_date_previous": last_day_of_month(relative_months=-2),
        },
        {
            "label": "Last Quarter",
            "start_date": first_day_of_month(relative_months=-3),
            "end_date": last_day_of_month(relative_months=-1),
            "start_date_previous": first_day_of_month(relative_months=-6),
            "end_date_previous": last_day_of_month(relative_months=-4),
        },
    ]
    for period in periods:
        columns = st.columns(3)
        period_amount_by_group_df = transaction_spreadsheet.get_amount_by_group(
            ignore_groups=["Transfer", "Bills"],
            ignore_types=["Income"],
            start_date=period["start_date"],
            end_date=period["end_date"]
        )
        period_amount_by_group_total = period_amount_by_group_df["Amount"].sum()
        period_amount_by_group_last_df = transaction_spreadsheet.get_amount_by_group(
            ignore_groups=["Transfer", "Bills"],
            ignore_types=["Income"],
            start_date=period["start_date_previous"],
            end_date=period["end_date_previous"]
        )
        period_amount_by_group_last_total = period_amount_by_group_last_df["Amount"].sum()
        period_total_delta = period_amount_by_group_last_total - period_amount_by_group_total
        columns[0].metric(
            label=period["label"],
            value=format_dollar_amount(-period_amount_by_group_total),
            delta=format_dollar_amount(period_total_delta),
            delta_color="inverse"
        )

        period_transactions_df = transaction_spreadsheet.filter_transactions(
            ignore_groups=["Transfer", "Bills"],
            ignore_types=["Income"],
            start_date=period["start_date"],
            end_date=period["end_date"],
            filtered_columns=["Date", "Amount"]
        )

        summed_amount_by_day = period_transactions_df.groupby('Date').sum(numeric_only=True)
        idx = pd.date_range(period["start_date"], period["end_date"])
        summed_amount_by_day = summed_amount_by_day.reindex(index=idx, fill_value=0)
        summed_amount_by_day = summed_amount_by_day.bfill().fillna(method="ffill")
        cumulative_amount_by_day = summed_amount_by_day.cumsum()
        cumulative_amount_by_day.index = range(0, len(cumulative_amount_by_day))

        period_transactions_previous_df = transaction_spreadsheet.filter_transactions(
            ignore_groups=["Transfer", "Bills"],
            ignore_types=["Income"],
            start_date=period["start_date_previous"],
            end_date=period["end_date_previous"],
        )
        summed_amount_by_day_previous = period_transactions_previous_df.groupby('Date').sum(numeric_only=True)
        idx = pd.date_range(period["start_date_previous"], period["end_date_previous"])
        summed_amount_by_day_previous = summed_amount_by_day_previous.reindex(index=idx, fill_value=0)
        summed_amount_by_day_previous = summed_amount_by_day_previous.bfill().fillna(method="ffill")
        cumulative_amount_by_day_previous = summed_amount_by_day_previous.cumsum()
        cumulative_amount_by_day_previous.index = range(0, len(cumulative_amount_by_day_previous))

        agg_df = pd.DataFrame()
        agg_df.index = range(len(cumulative_amount_by_day))
        agg_df["Amount"] = cumulative_amount_by_day["Amount"]
        agg_df["Amount Previous"] = cumulative_amount_by_day_previous["Amount"]

        columns[1].line_chart(
            data=agg_df,
            color=["#33cc33", "#cccccc"]
        )

    # Category
    amount_by_expense_groups_df = transaction_spreadsheet.get_amount_by_group(
        ignore_groups=["Transfer"],
        include_types=["Expense"],
        start_date=start_date,
        end_date=end_date,
    )
    amount_by_income_groups_df = transaction_spreadsheet.get_amount_by_group_category(
        group="Income",
        start_date=start_date,
        end_date=end_date,
    )

    st.header(f"By Category")
    st.subheader(
        body=f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}",
        divider="blue")
    col1, col2 = st.columns(2)
    col1.subheader(f"Expenses: -${-amount_by_expense_groups_df['Amount'].sum():,.2f}")
    col1.bar_chart(
        data=amount_by_expense_groups_df,
        color="#d47468"
    )
    col2.subheader(f"Income: ${amount_by_income_groups_df['Amount'].sum():,.2f}")
    col2.bar_chart(
        data=amount_by_income_groups_df,
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

    st.header("Balances Over Time")
    for group in groups:
        st.subheader(group)
        period_total_delta = data[group]["balance_history_df"].reset_index()["Balance"].iloc[-1] - data[group]["balance_history_df"].reset_index()["Balance"].iloc[0]
        st.metric(
            label="Total",
            value="${:,.2f}".format(data[group]["latest_balance_total"]),
            delta="{:,.2f}".format(period_total_delta),
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
