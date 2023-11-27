import os
from datetime import datetime
from typing import Dict
import pandas as pd
from balance_history import get_latest_balance_by_group, get_balance_history_by_group
from spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet
from transactions import get_amounts_by_group, get_amounts_by_group_category
import streamlit as st
from utils import first_day_of_the_month

st.set_page_config(layout="wide")

transaction_spreadsheet = TransactionsSpreadsheet()
balance_history_spreadsheet = BalanceHistorySpreadsheet()

time_period_radio_value = st.sidebar.radio(
    label="Time Period",
    options=[
        "This Month",
        "Last 3 Months",
        "Last 12 Months",
        "Custom"
    ]
)

if time_period_radio_value == "This Month":
    custom_input_disabled = True
    start_date = first_day_of_the_month(relative_months=0)
elif time_period_radio_value == "Last 3 Months":
    custom_input_disabled = True
    start_date = first_day_of_the_month(relative_months=-3)
elif time_period_radio_value == "Last 12 Months":
    custom_input_disabled = True
    start_date = first_day_of_the_month(relative_months=-12)
else:
    custom_input_disabled = False
    start_date = first_day_of_the_month(relative_months=0)

end_date = datetime.today()

start_date_input_value = st.sidebar.date_input(
    label="Start Date",
    value=start_date,
    disabled=custom_input_disabled
)
end_date_input_value = st.sidebar.date_input(
    label="End Date",
    value=end_date,
    disabled=custom_input_disabled
)

filtered_account_groups_multiselect = st.sidebar.multiselect(
    label="Filtered Account Groups",
    options=balance_history_spreadsheet.scrubbed_df["Group"].unique(),
    default=["House", "Loan"]
)

if time_period_radio_value == "Custom":
    start_date = datetime(start_date_input_value.year, start_date_input_value.month, start_date_input_value.day)
    end_date = datetime(end_date_input_value.year, end_date_input_value.month, end_date_input_value.day)

amount_by_expense_group_df = get_amounts_by_group(
    data_frame=transaction_spreadsheet.scrubbed_df,
    start_date=start_date,
    end_date=end_date,
    ignore_groups=["Transfer"]
)
amount_by_income_categories_df = get_amounts_by_group_category(
    data_frame=transaction_spreadsheet.scrubbed_df,
    group="Income",
    start_date=start_date,
    end_date=end_date
)

st.header(f"Financial Summary")
st.subheader(
    body=f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}",
    divider="blue")
col1, col2 = st.columns(2)
col1.subheader("Expenses")
col1.bar_chart(
    data=amount_by_expense_group_df,
    color="#d47468"
)
col2.subheader("Income")
col2.bar_chart(
    data=amount_by_income_categories_df,
    color="#7dc781"
)

groups = []
for group in balance_history_spreadsheet.scrubbed_df.sort_values("Group")["Group"].unique():
    if group not in filtered_account_groups_multiselect:
        groups.append(group)

data: Dict[str, Dict[str, pd.DataFrame]] = {}
for group in groups:
    latest_balance_df, latest_balance_total = get_latest_balance_by_group(
        scrubbed_data_frame=balance_history_spreadsheet.scrubbed_df,
        group=group,
        end_date=end_date
    )
    balance_history_df = get_balance_history_by_group(
        scrubbed_data_frame=balance_history_spreadsheet.scrubbed_df,
        group=group,
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
    st.metric(label="Total", value="${:,.2f}".format(data[group]["latest_balance_total"]))
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