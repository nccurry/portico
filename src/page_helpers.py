import altair as alt
import pandas as pd
import streamlit as st

from src.constants import COLOR_PLACEHOLDER
from src.analysis.merchants import extract_merchant_name
from src.custom_types import ColumnConfig

__all__ = [
    "create_sparkline_chart",
    "display_transaction_table",
    "display_transactions_expander",
    "extract_merchant_name",
    "get_transaction_column_config",
    "render_data_refresh_controls",
]


def display_transaction_table(transactions_df: pd.DataFrame, label: str) -> None:
    """Display an interactive dataframe table in an expander"""
    with st.expander(f"View {label} Transactions ({len(transactions_df)} rows)"):
        if transactions_df.empty:
            st.info("No transactions found")
            return

        # Display interactive dataframe with sorting, filtering, search
        st.dataframe(
            transactions_df,
            width='stretch',
            height=400,
            hide_index=True,
            column_config={
                "Amount": st.column_config.NumberColumn(
                    "Amount",
                    format="$%.2f"
                ),
                "Date": st.column_config.DateColumn(
                    "Date",
                    format="YYYY-MM-DD"
                )
            }
        )


def create_sparkline_chart(
    df: pd.DataFrame,
    value_column: str,
    date_column: str,
    color: str,
    height: int = 50,
    current_value: float | None = None,
    use_min_scale: bool = False
) -> alt.Chart:
    """Create a sparkline chart or flat line if insufficient data.

    Args:
        df: DataFrame containing the data
        value_column: Name of the column containing values
        date_column: Name of the column containing dates
        color: Color for the line
        height: Height of the chart in pixels
        current_value: Current value to use for flat line fallback
        use_min_scale: If True, set domain minimum to 95% of min value

    Returns:
        Altair chart object
    """
    if not df.empty and len(df) > 1:
        # Have historical data - show trend line
        scale = (
            alt.Scale(zero=False, domainMin=float(df[value_column].min() * 0.95))
            if use_min_scale
            else alt.Scale(zero=False)
        )

        chart = alt.Chart(df).mark_line(
            color=color,
            strokeWidth=2 if height <= 50 else 3,
            interpolate='monotone'
        ).encode(
            x=alt.X(f'{date_column}:T', axis=None),
            y=alt.Y(f'{value_column}:Q', axis=None, scale=scale)
        ).properties(
            height=height
        ).configure_view(
            strokeWidth=0
        )
    else:
        # Not enough history - show flat line at current value
        if current_value is None and not df.empty:
            current_value = df[value_column].iloc[0]
        elif current_value is None:
            current_value = 0

        flat_line_data = pd.DataFrame([
            {'x': 0, 'y': current_value},
            {'x': 1, 'y': current_value}
        ])
        chart = alt.Chart(flat_line_data).mark_line(
            color=COLOR_PLACEHOLDER,
            strokeWidth=2 if height <= 50 else 3,
            strokeDash=[5, 5]
        ).encode(
            x=alt.X('x:Q', axis=None),
            y=alt.Y('y:Q', axis=None, scale=alt.Scale(zero=False))
        ).properties(
            height=height
        ).configure_view(
            strokeWidth=0
        )

    return chart  # type: ignore[no-any-return]


def get_transaction_column_config() -> ColumnConfig:
    """Standard column configuration for transaction dataframes.

    Returns:
        dictionary of column configurations for st.dataframe
    """
    return {
        'Date': st.column_config.DateColumn('Date', format='YYYY-MM-DD'),
        'Amount': st.column_config.NumberColumn('Amount', format='$%.2f'),
        'Category': st.column_config.TextColumn('Category'),
        'Group': st.column_config.TextColumn('Group'),
        'Type': st.column_config.TextColumn('Type'),
        'Account': st.column_config.TextColumn('Account'),
        'Month': st.column_config.TextColumn('Month'),
        'Full Description': st.column_config.TextColumn('Description'),
        'Institution': st.column_config.TextColumn('Institution')
    }


def display_transactions_expander(
    df: pd.DataFrame,
    title: str,
    height: int = 600,
    default_sort_column: str = 'Date',
    default_sort_ascending: bool = False
) -> None:
    """Display transactions in an expandable section.

    Args:
        df: Transaction dataframe to display
        title: Title for the expander
        height: Height of the dataframe in pixels
        default_sort_column: Column to sort by before display
        default_sort_ascending: Sort order
    """
    with st.expander(f"{title} ({len(df)} transactions)"):
        if df.empty:
            st.info("No transactions found")
            return

        # Sort by specified column
        df_display = df.sort_values(default_sort_column, ascending=default_sort_ascending)

        st.dataframe(
            df_display,
            width='stretch',
            height=height,
            hide_index=True,
            column_config=get_transaction_column_config()
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
