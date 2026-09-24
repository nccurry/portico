import re
from collections.abc import Sequence
from math import isfinite
from typing import Literal, overload

import pandas as pd
import streamlit as st

from src.analysis.merchants import configured_merchant_aliases, extract_merchant_name
from src.config import get_settings
from src.custom_types import ColumnConfig
from src.reporting_periods import current_timestamp
from src.value_visibility import mask_value, value_safe_dataframe

__all__ = [
    "configured_merchant_aliases",
    "currency_input",
    "display_transactions_expander",
    "extract_merchant_name",
    "get_transaction_column_config",
    "render_data_refresh_controls",
    "render_demo_banner",
    "render_time_frame_control",
]


_CURRENCY_INPUT_PATTERN = re.compile(r"^-?\$?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?$")


def _format_currency_input(value: float | None) -> str:
    """Format one numeric value for a dollar input."""
    if value is None:
        return ""
    sign = "-" if value < 0 else ""
    amount = abs(value)
    if amount.is_integer():
        return f"{sign}${amount:,.0f}"
    return f"{sign}${amount:,.2f}"


def _parse_currency_input(value: str) -> float | None:
    """Parse a plain or dollar-formatted amount with up to two decimal places."""
    text = value.strip()
    if not text or not _CURRENCY_INPUT_PATTERN.fullmatch(text):
        return None
    amount = float(text.replace("$", "").replace(",", ""))
    return round(amount, 2) if isfinite(amount) else None


def _set_currency_input_value(
    value_key: str,
    display_key: str,
    synced_key: str,
    min_value: float,
    max_value: float | None,
    allow_empty: bool,
) -> None:
    """Store a valid dollar-input value and restore invalid text."""
    text = str(st.session_state[display_key])
    amount = _parse_currency_input(text)
    current_amount = _numeric_currency_value(st.session_state.get(value_key))
    if amount is None:
        if not text.strip() and allow_empty:
            st.session_state[value_key] = None
            st.session_state[synced_key] = None
            return
    elif amount >= min_value and (max_value is None or amount <= max_value):
        st.session_state[value_key] = amount
        st.session_state[display_key] = _format_currency_input(amount)
        st.session_state[synced_key] = amount
        return

    st.session_state[display_key] = _format_currency_input(current_amount)
    st.session_state[synced_key] = current_amount


def _numeric_currency_value(value: object) -> float | None:
    """Return a finite numeric value suitable for a dollar input."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    amount = float(value)
    return amount if isfinite(amount) else None


@overload
def currency_input(
    label: str,
    *,
    min_value: float,
    max_value: float | None,
    key: str,
    value: float | None = None,
    allow_empty: Literal[False] = False,
    placeholder: str | None = None,
    help: str | None = None,
    persist_state: Literal["page", "session"] | None = None,
) -> float: ...


@overload
def currency_input(
    label: str,
    *,
    min_value: float,
    max_value: float | None,
    key: str,
    value: float | None = None,
    allow_empty: Literal[True],
    placeholder: str | None = None,
    help: str | None = None,
    persist_state: Literal["page", "session"] | None = None,
) -> float | None: ...


def currency_input(
    label: str,
    *,
    min_value: float,
    max_value: float | None,
    key: str,
    value: float | None = None,
    allow_empty: bool = False,
    placeholder: str | None = None,
    help: str | None = None,
    persist_state: Literal["page", "session"] | None = None,
) -> float | None:
    """Render a dollar input while keeping its numeric value in session state."""
    display_key = f"{key}_currency"
    synced_key = f"{key}_currency_synced"
    if key not in st.session_state:
        st.session_state[key] = value if value is not None or allow_empty else min_value

    current_amount = _numeric_currency_value(st.session_state[key])
    if current_amount is None and not allow_empty:
        current_amount = min_value
        st.session_state[key] = current_amount

    if display_key not in st.session_state or st.session_state.get(synced_key) != current_amount:
        st.session_state[display_key] = _format_currency_input(current_amount)
        st.session_state[synced_key] = current_amount

    st.text_input(
        label,
        key=display_key,
        placeholder=placeholder,
        help=help,
        on_change=_set_currency_input_value,
        args=(key, display_key, synced_key, min_value, max_value, allow_empty),
        persist_state=persist_state,
    )
    return _numeric_currency_value(st.session_state[key])


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
    if get_settings().is_demo:
        st.info(
            "Demo data is active. The dashboard uses committed synthetic records and does not contact a remote spreadsheet.",
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
