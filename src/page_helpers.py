from collections.abc import Sequence

import pandas as pd
import streamlit as st

from src.analysis.merchants import configured_merchant_aliases, extract_merchant_name
from src.config import get_settings
from src.custom_types import ColumnConfig
from src.reporting_periods import current_timestamp
from src.value_visibility import mask_value, value_safe_dataframe

__all__ = [
    "configured_merchant_aliases",
    "display_transactions_expander",
    "extract_merchant_name",
    "get_transaction_column_config",
    "render_data_refresh_controls",
    "render_demo_banner",
    "render_time_frame_control",
]


def get_transaction_column_config() -> ColumnConfig:
    """Standard column configuration for transaction dataframes.

    Returns:
        dictionary of column configurations for st.dataframe
    """
    return {
        "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
        "Category": st.column_config.TextColumn("Category"),
        "Group": st.column_config.TextColumn("Group"),
        "Type": st.column_config.TextColumn("Type"),
        "Account": st.column_config.TextColumn("Account"),
        "Month": st.column_config.TextColumn("Month"),
        "Full Description": st.column_config.TextColumn("Description"),
        "Institution": st.column_config.TextColumn("Institution"),
    }


def render_demo_banner() -> None:
    """Show a shared banner when the app uses synthetic demo data."""
    if get_settings().data.show_demo_banner:
        st.info(
            "Demo data is active. The dashboard uses committed synthetic records and does not contact Google Sheets.",
            icon=":material/science:",
        )


def render_time_frame_control(
    options: Sequence[str],
    *,
    default: str,
    key: str,
) -> str:
    """Render the shared page-level reporting-period control."""
    selected = st.segmented_control(
        "Time frame",
        options=list(options),
        default=default,
        required=True,
        key=key,
        help="Controls the time period shown on this page.",
        persist_state="page",
        width="content",
    )
    return selected if isinstance(selected, str) and selected in options else default


def display_transactions_expander(
    df: pd.DataFrame,
    title: str,
    height: int = 600,
    default_sort_column: str = "Date",
    default_sort_ascending: bool = False,
) -> None:
    """Display transactions in an expandable section.

    Args:
        df: Transaction dataframe to display
        title: Title for the expander
        height: Height of the dataframe in pixels
        default_sort_column: Column to sort by before display
        default_sort_ascending: Sort order
    """
    with st.expander(f"{title} ({mask_value(f'{len(df):,}')} transactions)"):
        if df.empty:
            st.info("No transactions found")
            return

        # Sort by specified column
        df_display = df.sort_values(default_sort_column, ascending=default_sort_ascending)

        value_safe_dataframe(
            df_display, width="stretch", height=height, hide_index=True, column_config=get_transaction_column_config()
        )


def render_data_refresh_controls() -> None:
    """Render shared cache refresh controls in the sidebar."""
    if "data_last_refreshed" not in st.session_state:
        st.session_state["data_last_refreshed"] = current_timestamp()

    with st.sidebar:
        loaded_at = pd.Timestamp(st.session_state["data_last_refreshed"])
        st.caption(f"Loaded {loaded_at.strftime('%Y-%m-%d %H:%M UTC')}")
        if st.button(
            "Refresh data",
            key="refresh_data",
            icon=":material/refresh:",
            width="stretch",
        ):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.session_state["data_last_refreshed"] = current_timestamp()
            st.rerun()
