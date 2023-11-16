import os
from datetime import date
from typing import List

import dateutil
import streamlit as st
import pandas as pd
import numpy as np
import math
from dateutil.relativedelta import relativedelta


def initialize_session_state(force: bool = False) -> None:
    """Initialize streamlit session state with default values"""
    if 'lookback_months' not in st.session_state or force:
        st.session_state.lookback_months = 3

    if 'total_months' not in st.session_state or force:
        st.session_state.total_months = get_total_months(st.session_state.ss_transactions_scrubbed_df)

    if 'selected_group' not in st.session_state or force:
        st.session_state.selected_group = st.session_state.ss_transactions_scrubbed_df["Group"].unique()[0]

    if 'total_groups' not in st.session_state or force:
        st.session_state.total_groups = st.session_state.ss_transactions_scrubbed_df["Group"].unique()

    if 'group_categories' not in st.session_state or force:
        st.session_state.group_categories = get_group_categories(
            group=st.session_state.ss_transactions_scrubbed_df["Group"].unique()[0],
            data_frame=st.session_state.ss_transactions_scrubbed_df
        )

    if 'included_categories' not in st.session_state or force:
        st.session_state.included_categories = []

    if 'ignored_categories' not in st.session_state or force:
        st.session_state.ignored_categories = []

    update_filtered_data()


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
    df = st.session_state.ss_transactions_scrubbed_df.copy()

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

