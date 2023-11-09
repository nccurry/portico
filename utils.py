from typing import List
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
import math


def load_data() -> pd.DataFrame:
    """Load data from Google Sheets and set it in the session state"""
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()

    st.session_state.raw_data = df
    st.session_state.scrubbed_data = scrub_data(df)

    return df


def scrub_data(
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


def initialize_session_state(force: bool = False) -> None:
    """Initialize streamlit session state with default values"""
    if st.session_state.raw_data is None \
            or st.session_state.scrubbed_data is None:
        raise ValueError("Could not initialize session state. Please load data first...")

    if 'total_months' not in st.session_state or force:
        st.session_state.total_months = get_total_months(st.session_state.scrubbed_data)

    if 'selected_group' not in st.session_state or force:
        st.session_state.selected_group = st.session_state.scrubbed_data["Group"].unique()[0]

    if 'total_groups' not in st.session_state or force:
        st.session_state.total_groups = st.session_state.scrubbed_data["Group"].unique()

    if 'group_categories' not in st.session_state or force:
        st.session_state.group_categories = get_group_categories(
            group=st.session_state.scrubbed_data["Group"].unique()[0],
            data_frame=st.session_state.scrubbed_data
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


def on_widget_change() -> pd.DataFrame:
    """Callback function to execute when a UI widget is updated"""
    update = False

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
    """Filter data in session_state based on widget settions"""
    df = st.session_state.scrubbed_data.copy()

    df = df.loc[df["Group"] == st.session_state.selected_group]
    st.session_state.group_categories = get_group_categories(
        group=st.session_state.selected_group,
        data_frame=df
    )

    if st.session_state.included_categories:
        df = df[df["Category"].isin(st.session_state.included_categories)]

    if st.session_state.ignored_categories:
        df = df[-df["Category"].isin(st.session_state.ignored_categories)]

    st.session_state.filtered_data = df
