import pandas as pd
import streamlit as st

from src.analysis.merchants import build_merchant_aliases, extract_merchant_name
from src.config import get_settings
from src.custom_types import ColumnConfig
from src.value_visibility import mask_value, value_safe_dataframe

__all__ = [
    "configured_merchant_aliases",
    "display_transactions_expander",
    "extract_merchant_name",
    "get_transaction_column_config",
    "render_data_refresh_controls",
    "render_demo_banner",
]


def configured_merchant_aliases() -> dict[str, str]:
    """Return validated merchant aliases from application settings."""
    configured = dict(get_settings().merchants.aliases)
    return build_merchant_aliases(configured)


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
    if get_settings().data.is_demo:
        st.info(
            "Demo data is active. The dashboard uses committed synthetic records and does not contact Google Sheets.",
            icon=":material/science:",
        )


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
        st.session_state["data_last_refreshed"] = pd.Timestamp.now(tz="UTC")

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
            st.session_state["data_last_refreshed"] = pd.Timestamp.now(tz="UTC")
            st.rerun()
