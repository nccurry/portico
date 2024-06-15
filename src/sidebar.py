from datetime import datetime
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet
import streamlit as st
from src.utils import first_day_of_month, last_day_of_month, relative_date


def configure_sidebar(
        transaction_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    """Configure Streamlit sidebar widgets"""
    time_period_radio = st.sidebar.radio(
        label="Time Period",
        options=[
            "Last 7 Days",
            "Last 14 Days",
            "Last 28 Days",
            "This Month",
            "Last Month",
            "Last 3 Months",
            "Last 12 Months",
            "Custom"
        ],
        index=3,
        key="time_period_radio"
    )

    custom_input_disabled = True
    if time_period_radio == "Last 7 Days":
        start_date = relative_date(relative_days=-7)
        end_date = relative_date(relative_days=-1)
    elif time_period_radio == "Last 14 Days":
        start_date = relative_date(relative_days=-14)
        end_date = relative_date(relative_days=-1)
    elif time_period_radio == "Last 28 Days":
        start_date = relative_date(relative_days=-28)
        end_date = relative_date(relative_days=-1)
    elif time_period_radio == "This Month":
        start_date = first_day_of_month(relative_months=0)
        end_date = relative_date(relative_days=-1)
    elif time_period_radio == "Last Month":
        start_date = first_day_of_month(relative_months=-1)
        end_date = last_day_of_month(relative_months=-1)
    elif time_period_radio == "Last 3 Months":
        start_date = first_day_of_month(relative_months=-3)
        end_date = last_day_of_month(relative_months=-1)
    elif time_period_radio == "Last 12 Months":
        start_date = first_day_of_month(relative_months=-12)
        end_date = last_day_of_month(relative_months=-1)
    else:
        custom_input_disabled = False
        start_date = first_day_of_month(relative_months=0)
        end_date = relative_date(relative_days=-1)

    st.session_state["start_date"] = start_date
    st.session_state["end_date"] = end_date

    start_date_input = st.sidebar.date_input(
        label="Start Date",
        value=start_date,
        disabled=custom_input_disabled,
        key="start_date_input"
    )
    end_date_input = st.sidebar.date_input(
        label="End Date",
        value=end_date,
        disabled=custom_input_disabled,
        key="end_date_input"
    )

    filtered_account_groups_multiselect = st.sidebar.multiselect(
        label="Filtered Account Groups",
        options=balance_history_spreadsheet.scrubbed_df["Group"].unique(),
        default=["House", "Loan"],
        key="filtered_account_groups_multiselect"
    )

    filtered_account_categories_multiselect = st.sidebar.multiselect(
        label="Filtered Account Categories",
        options=transaction_spreadsheet.scrubbed_df["Category"].unique(),
        default=["Transfer", "Returned Purchase", "Returned Purchase Income", "Tax Return Payment"],
        key="filtered_account_categories_multiselect"
    )

    st.session_state["sidebar_configured"] = True
