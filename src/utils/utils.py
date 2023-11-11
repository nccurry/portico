import os
from datetime import date
from typing import List

import dateutil
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
import math
from dateutil.relativedelta import relativedelta






def load_data(force: bool = False):
    """Load data from Google Sheets and set it in the session state"""

    if 'transactions_raw_data' not in st.session_state or 'transactions_scrubbed_data' not in st.session_state or force:
        conn = st.connection(name="transactions", type=GSheetsConnection)
        transactions_spreadsheet_url = os.environ.get("TRANSACTIONS_SPREADSHEET_URL")
        if transactions_spreadsheet_url:
            df = conn.read(spreadsheet=transactions_spreadsheet_url)
        else:
            df = conn.read()

        st.session_state.transactions_raw_data = df
        st.session_state.transactions_scrubbed_data = scrub_transaction_data(df)

    if 'balance_history_raw_data' not in st.session_state or 'balance_history_scrubbed_data' not in st.session_state or force:
        conn = st.connection(name="balance_history", type=GSheetsConnection)
        balance_history_spreadsheet_url = os.environ.get("BALANCE_HISTORY_SPREADSHEET_URL")
        if balance_history_spreadsheet_url:
            df = conn.read(spreadsheet=balance_history_spreadsheet_url)
        else:
            df = conn.read()

        st.session_state.balance_history_raw_data = df
        st.session_state.balance_history_scrubbed_data = scrub_balance_history_data(df)


def scrub_transaction_data(
    data_frame: pd.DataFrame
) -> pd.DataFrame:
    """Clean up the data retrieved from the Tiller spreadsheet"""
    df = data_frame.copy()

    # Drop empty column
    df = df.drop("Unnamed: 0", axis=1)

    # Recast Amount column as float
    df["Amount"] = df["Amount"].replace('[\$,]', '', regex=True).astype(float)

    # Recast dates as datetime
    df["Date"] = pd.to_datetime(df["Date"])
    df["Month"] = pd.to_datetime(df["Month"])
    df["Week"] = pd.to_datetime(df["Week"])
    df["Date Added"] = pd.to_datetime(df["Date Added"])
    df["Categorized Date"] = pd.to_datetime(df["Categorized Date"])

    # Use better strings for Month and Week columns
    df["Month"] = df["Month"].dt.strftime('%Y-%m')
    df["Week"] = df["Week"].dt.strftime('%U')

    # Only show expenses
    df = df.loc[df["Type"] == "Expense"]

    # Use positive values for amounts, since we are only focused on expenses
    df.loc[:, 'Amount'] = df['Amount'] * -1
    return df


def scrub_balance_history_data(
    data_frame: pd.DataFrame
) -> pd.DataFrame:
    """Clean up the data retrieved from the Tiller spreadsheet"""
    df = data_frame.copy()

    # Drop empty column
    df = df.drop("Unnamed: 0", axis=1)

    # Recast Amount column as float
    df["Balance"] = df["Balance"].replace('[\$,]', '', regex=True).astype(float)

    # Recast dates as datetime
    df["Date"] = pd.to_datetime(df["Date"])
    df["Time"] = pd.to_datetime(df["Time"])
    df["Month"] = pd.to_datetime(df["Month"])
    df["Week"] = pd.to_datetime(df["Week"])
    df["Date Added"] = pd.to_datetime(df["Date Added"])

    # Use better strings for Month and Week columns
    df["Month"] = df["Month"].dt.strftime('%Y-%m')
    df["Week"] = df["Week"].dt.strftime('%U')

    return df


def initialize_session_state(force: bool = False) -> None:
    """Initialize streamlit session state with default values"""
    if st.session_state.transactions_raw_data is None \
            or st.session_state.transactions_scrubbed_data is None:
        raise ValueError("Could not initialize session state. Please load data first...")

    if 'lookback_months' not in st.session_state or force:
        st.session_state.lookback_months = 3

    if 'total_months' not in st.session_state or force:
        st.session_state.total_months = get_total_months(st.session_state.transactions_scrubbed_data)

    if 'selected_group' not in st.session_state or force:
        st.session_state.selected_group = st.session_state.transactions_scrubbed_data["Group"].unique()[0]

    if 'total_groups' not in st.session_state or force:
        st.session_state.total_groups = st.session_state.transactions_scrubbed_data["Group"].unique()

    if 'group_categories' not in st.session_state or force:
        st.session_state.group_categories = get_group_categories(
            group=st.session_state.transactions_scrubbed_data["Group"].unique()[0],
            data_frame=st.session_state.transactions_scrubbed_data
        )

    if 'included_categories' not in st.session_state or force:
        st.session_state.included_categories = []

    if 'ignored_categories' not in st.session_state or force:
        st.session_state.ignored_categories = []

    update_filtered_data()


@st.cache_data
def get_total_months(
    data_frame: pd.DataFrame
) -> int:
    """Given Tiller data, return the total amount of months in the data set"""
    oldest_date = data_frame["Date"].min()
    latest_date = data_frame["Date"].max()
    total_months = math.ceil((latest_date - oldest_date)/np.timedelta64(1, 'M'))

    return total_months


@st.cache_data
def get_group_categories(
    group: str,
    data_frame: pd.DataFrame
) -> List[str]:
    """Return all categories from a given group"""
    df = data_frame.copy()
    df = df[df["Group"] == group]

    return df["Category"].unique()


def on_widget_change():
    """Callback function to execute when a UI widget is updated"""
    update = False

    if st.session_state.lookback_months != st.session_state.slider_lookback_months:
        st.session_state.lookback_months = st.session_state.slider_lookback_months
        update = True

    if st.session_state.selected_group != st.session_state.selectbox_group:
        st.session_state.selected_group = st.session_state.selectbox_group
        update = True

    if st.session_state.included_categories != st.session_state.multiselect_included_categories:
        st.session_state.included_categories = st.session_state.multiselect_included_categories
        update = True

    if st.session_state.ignored_categories != st.session_state.multiselect_ignored_categories:
        st.session_state.ignored_categories = st.session_state.multiselect_ignored_categories
        update = True

    if update:
        update_filtered_data()


def update_filtered_data() -> None:
    """Filter data in session_state based on widget settings"""
    df = st.session_state.transactions_scrubbed_data.copy()

    # Filter by selected group
    df = df.loc[df["Group"] == st.session_state.selected_group]

    # Set new group categories
    st.session_state.group_categories = get_group_categories(
        group=st.session_state.selected_group,
        data_frame=df
    )

    # Filter by included / ignored categories
    if st.session_state.included_categories:
        df = df[df["Category"].isin(st.session_state.included_categories)]
    if st.session_state.ignored_categories:
        df = df[-df["Category"].isin(st.session_state.ignored_categories)]

    # Filter by Month lookback
    first_of_the_month = date.today().replace(day=1)
    month_cutoff = first_of_the_month + dateutil.relativedelta.relativedelta(months=-st.session_state.lookback_months + 1)
    df = df[df["Date"].dt.date > month_cutoff]

    st.session_state.filtered_data = df


def clear_filtered_data():
    """Reset session state"""
    initialize_session_state(force=True)
    update_filtered_data()

