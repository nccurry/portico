import altair as alt
import streamlit as st
from typing import List

from transactions import get_category_stats_by_group
from page import MonthlyExpensesPage

# Initialize page
mep = MonthlyExpensesPage()

# Configure UI

st.header("Amount by Group", divider="blue")

col1, col2 = st.columns([0.6, 0.4])

lookback_months: int = col2.slider(
    label="Lookback (Months)",
    min_value=1,
    max_value=st.session_state[f'{mep.state_prefix}_total_months'],
    value=st.session_state[f'{mep.state_prefix}_lookback_months'],
    key="slider_lookback_months",
    on_change=mep.ui_widget_callback
)

group: str = col2.selectbox(
    label="Group",
    options=st.session_state[f'{mep.state_prefix}_total_groups'],
    key="selectbox_group",
    on_change=mep.ui_widget_callback
)

included_categories: List[str] = col2.multiselect(
    label="Included Categories",
    options=st.session_state[f'{mep.state_prefix}_group_categories'],
    default=st.session_state[f'{mep.state_prefix}_included_categories'],
    key="multiselect_included_categories",
    on_change=mep.ui_widget_callback
)

ignored_categories: List[str] = col2.multiselect(
    label="Ignored Categories",
    options=st.session_state[f'{mep.state_prefix}_group_categories'],
    default=st.session_state[f'{mep.state_prefix}_ignored_categories'],
    key="multiselect_ignored_categories",
    on_change=mep.ui_widget_callback
)

reset = col2.button(
    label="Clear",
    type="primary",
    on_click=mep.clear_filtered_data
)

chart = alt.Chart(st.session_state.filtered_data).mark_bar().encode(
   x=alt.X('Month'),
   xOffset='Category',
   y=alt.Y('Amount'),
   color='Category'
).configure_view(
    stroke=None,
)
col1.altair_chart(
    altair_chart=chart,
    use_container_width=True
)

st.subheader("Transactions", divider="blue")
transactions_stats = get_category_stats_by_group(
    data_frame=st.session_state.filtered_data,
    group=st.session_state.selectbox_group
)
st.text("Stats")
st.dataframe(
    data=transactions_stats
)
st.text("All Transactions")
st.dataframe(
    data=st.session_state.filtered_data,
    hide_index=True
)
