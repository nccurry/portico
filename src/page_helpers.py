import streamlit as st
import pandas as pd
import altair as alt
from src.spreadsheet import TransactionsSpreadsheet
from src.constants import COLOR_PLACEHOLDER
from src.analysis.merchants import extract_merchant_name
from src.custom_types import ColumnConfig

__all__ = [
    "create_sparkline_chart",
    "create_year_comparison_chart",
    "display_transaction_table",
    "display_transactions_expander",
    "extract_merchant_name",
    "get_transaction_column_config",
    "prepare_year_comparison_data",
    "render_data_refresh_controls",
    "render_year_over_year_page",
]


def prepare_year_comparison_data(monthly_amounts_df: pd.DataFrame) -> pd.DataFrame:
    """Transform monthly data into year-over-year comparison format.

    Input: DataFrame with Month index (YYYY-MM format) and Amount column
    Output: DataFrame with Month (1-12) and separate columns per year
    """
    if monthly_amounts_df.empty:
        return pd.DataFrame()

    df = monthly_amounts_df.copy()
    df = df.reset_index()

    # Extract year and month number from Month column
    df['Year'] = pd.to_datetime(df['Month']).dt.year
    df['Month'] = pd.to_datetime(df['Month']).dt.month

    # Pivot: rows=month number (1-12), columns=year, values=amount
    pivoted = df.pivot(index='Month', columns='Year', values='Amount')
    pivoted = pivoted.fillna(0)

    return pivoted


def create_year_comparison_chart(pivoted_df: pd.DataFrame, label: str) -> alt.Chart:
    """Create an Altair chart showing year-over-year comparison.

    Current year is shown in green, previous years in shades of gray.
    """
    if pivoted_df.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(text=alt.value("No data available"))  # type: ignore[no-any-return]

    # Reshape data for Altair (need long format)
    df_long = pivoted_df.reset_index()
    df_long = df_long.melt(id_vars='Month', var_name='Year', value_name='Amount')
    df_long['Year'] = df_long['Year'].astype(str)
    current_year = max(int(year) for year in df_long['Year'].unique())

    # Current year is green, last year off-white, older years progressively darker
    years = sorted(df_long['Year'].unique(), reverse=True)
    color_domain = years

    # Brightness scale: 1 year ago = light grey, 5+ years ago = very dark (but visible)
    color_range = []
    for year in years:
        years_ago = current_year - int(year)
        if years_ago == 0:
            color_range.append('#57cc57')  # green for current year
        else:
            # Map 1 year ago -> light grey (180) down to 5+ years ago -> dark (50)
            brightness = max(50, 180 - (years_ago - 1) * 33)
            color_range.append(f'rgb({brightness},{brightness},{brightness})')

    # For each year, trim leading and trailing zeros but keep middle zeros
    filtered_rows = []
    for year in df_long['Year'].unique():
        year_data = df_long[df_long['Year'] == year].copy()

        # Find first and last non-zero month for this year
        non_zero = year_data[year_data['Amount'] != 0]
        if not non_zero.empty:
            min_month = non_zero['Month'].min()
            max_month = non_zero['Month'].max()

            # Keep only data between first and last non-zero months (inclusive)
            year_data = year_data[
                (year_data['Month'] >= min_month) &
                (year_data['Month'] <= max_month)
            ]
            filtered_rows.append(year_data)

    if filtered_rows:
        df_long = pd.concat(filtered_rows, ignore_index=True)
    else:
        df_long = pd.DataFrame()

    # Create the chart
    chart = alt.Chart(df_long).mark_line(point=True).encode(
        x=alt.X('Month:O',
                axis=alt.Axis(title='Month', labelAngle=0),
                scale=alt.Scale(domain=list(range(1, 13)))),
        y=alt.Y('Amount:Q',
                axis=alt.Axis(title='Amount ($)'),
                scale=alt.Scale(zero=True)),
        color=alt.Color('Year:N',
                       scale=alt.Scale(domain=color_domain, range=color_range),
                       legend=alt.Legend(title='Year')),
        tooltip=[
            alt.Tooltip('Year:N', title='Year'),
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Amount:Q', title='Amount', format='$.2f')
        ]
    ).properties(
        height=300,
        title=f'{label} - Year over Year Comparison'
    )

    return chart  # type: ignore[no-any-return]


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


def render_year_over_year_page(
        items: list[str],
        transactions_spreadsheet: TransactionsSpreadsheet,
        by: str = "category"
) -> None:
    """Render a page showing year-over-year comparisons for a list of categories or groups."""
    get_monthly = (transactions_spreadsheet.get_monthly_amounts_by_category
                   if by == "category"
                   else transactions_spreadsheet.get_monthly_amounts_by_group)
    get_transactions = (transactions_spreadsheet.get_transactions_by_category
                        if by == "category"
                        else transactions_spreadsheet.get_transactions_by_group)

    for item in items:
        monthly_amounts_df = get_monthly(item, invert_amount=True)

        # Transform data for year-over-year comparison
        pivoted_df = prepare_year_comparison_data(monthly_amounts_df)

        st.subheader(item)
        col1, col2 = st.columns([1, 4])

        # Show pivoted data table (years as columns)
        col1.dataframe(pivoted_df)

        # Show year-over-year comparison chart
        chart = create_year_comparison_chart(pivoted_df, item)
        col2.altair_chart(chart, width='stretch')

        # Show expandable transaction table
        transactions_df = get_transactions(item)
        display_transaction_table(transactions_df, item)


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
