import altair as alt
import streamlit as st
from typing import List

from utils import on_widget_change, initialize_session_state, load_data, clear_filtered_data

# Initialize
load_data()
initialize_session_state()


# Configure UI Widgets

lookback_months: int = st.sidebar.slider(
    label="Lookback (Months)",
    min_value=1,
    max_value=st.session_state.total_months,
    value=st.session_state.lookback_months,
    key="slider_lookback_months",
    on_change=on_widget_change
)

group: str = st.sidebar.selectbox(
    label="Group",
    options=st.session_state.total_groups,
    key="selectbox_group",
    on_change=on_widget_change
)

included_categories: List[str] = st.sidebar.multiselect(
    label="Included Categories",
    options=st.session_state.group_categories,
    default=st.session_state.included_categories,
    key="multiselect_included_categories",
    on_change=on_widget_change
)

ignored_categories: List[str] = st.sidebar.multiselect(
    label="Ignored Categories",
    options=st.session_state.group_categories,
    default=st.session_state.ignored_categories,
    key="multiselect_ignored_categories",
    on_change=on_widget_change
)

reset = st.sidebar.button(
    label="Clear",
    type="primary",
    on_click=clear_filtered_data
)

# Create chart

test_chart = alt.Chart(st.session_state.filtered_data).mark_bar().encode(
   x=alt.X('Month'),
   xOffset='Category',
   y=alt.Y('Amount'),
   color='Category'
).configure_view(
    stroke=None,
)

test_chart
