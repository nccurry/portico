from datetime import datetime
from typing import Dict

import pandas as pd
from src.data.balance_history import get_latest_balance_by_group, get_balance_history_by_group
from src.data.transactions import get_amounts_by_group, get_amounts_by_group_category
from src.page.page import HomePage
import streamlit as st

from src.utils.utils import first_day_of_the_month, last_day_of_the_month

home_page = HomePage()

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

if time_period_radio_value == "Custom":
    start_date = datetime(start_date_input_value.year, start_date_input_value.month, start_date_input_value.day)
    end_date = datetime(end_date_input_value.year, end_date_input_value.month, end_date_input_value.day)

amount_by_expense_group_df = get_amounts_by_group(
    data_frame=home_page.spreadsheets["ts"].scrubbed_df,
    start_date=start_date,
    end_date=end_date,
    ignore_groups=["Transfer"]
)
amount_by_income_categories_df = get_amounts_by_group_category(
    data_frame=home_page.spreadsheets["ts"].scrubbed_df,
    group="Income",
    start_date=start_date,
    end_date=end_date
)

col1, col2 = st.columns(2)
col1.subheader("Expenses by Group")
col1.bar_chart(
    data=amount_by_expense_group_df,
    color="#d47468"
)
col2.subheader("Income by Category")
col2.bar_chart(
    data=amount_by_income_categories_df,
    color="#7dc781"
)

# TODO: Include this in the sidebar
group_filter = ["House", "Loan"]
groups = []
for group in home_page.spreadsheets["bhs"].scrubbed_df.sort_values("Group")["Group"].unique():
    if group not in group_filter:
        groups.append(group)

data: Dict[str, Dict[str, pd.DataFrame]] = {}
for group in groups:
    latest_balance_df, latest_balance_total = get_latest_balance_by_group(
        scrubbed_data_frame=home_page.spreadsheets["bhs"].scrubbed_df,
        group=group,
        end_date=end_date
    )
    balance_history_df = get_balance_history_by_group(
        scrubbed_data_frame=home_page.spreadsheets["bhs"].scrubbed_df,
        group=group,
        end_date=end_date
    )
    data[group] = dict(
        latest_balance_df=latest_balance_df,
        latest_balance_total=latest_balance_total,
        balance_history_df=balance_history_df
    )

st.subheader("Balance Histories")
for group in groups:
    with st.expander(f'# **{group}**: ${"{:,.2f}".format(data[group]["latest_balance_total"])}', expanded=True):
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


# TODO: Figure out how this interacts with the date selectors
st.subheader("Transactions")

transactions_df = home_page.spreadsheets["ts"].scrubbed_df
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
    }
)