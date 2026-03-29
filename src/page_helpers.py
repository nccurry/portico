import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from typing import List, Dict, Optional

from src.spreadsheet import TransactionsSpreadsheet
from src.constants import COLOR_PLACEHOLDER


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
        return alt.Chart(pd.DataFrame()).mark_text().encode(text=alt.value("No data available"))
    
    current_year = datetime.now().year
    
    # Reshape data for Altair (need long format)
    df_long = pivoted_df.reset_index()
    df_long = df_long.melt(id_vars='Month', var_name='Year', value_name='Amount')
    df_long['Year'] = df_long['Year'].astype(str)
    
    # Create color mapping: current year = green, others = gray shades
    years = sorted(df_long['Year'].unique(), reverse=True)
    color_domain = years
    
    # Current year gets green, previous years get progressively lighter gray
    color_range = []
    for year in years:
        if int(year) == current_year:
            color_range.append('lightgreen')
        else:
            # Older years get progressively lighter gray
            years_ago = current_year - int(year)
            if years_ago == 1:
                color_range.append('darkgray')
            elif years_ago == 2:
                color_range.append('gray')
            else:
                color_range.append('lightgray')
    
    # For each year, trim leading and trailing zeros but keep middle zeros
    filtered_rows = []
    for year in df_long['Year'].unique():
        year_data = df_long[df_long['Year'] == year].copy()
        
        # Find first and last non-zero month for this year
        non_zero = year_data[year_data['Amount'] > 0]
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
    
    return chart


def display_transaction_table(transactions_df: pd.DataFrame, label: str) -> None:
    """Display an interactive dataframe table in an expander"""
    with st.expander(f"📊 View {label} Transactions ({len(transactions_df)} rows)"):
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


def render_category_page(
        categories: List[str],
        transactions_spreadsheet: TransactionsSpreadsheet
) -> None:
    """Render a page showing year-over-year comparisons for a list of categories."""
    for category in categories:
        monthly_amounts_df = transactions_spreadsheet.get_monthly_amounts_by_category(
            category=category,
            invert_amount=True
        )
        
        # Transform data for year-over-year comparison
        pivoted_df = prepare_year_comparison_data(monthly_amounts_df)
        
        st.subheader(category)
        col1, col2 = st.columns([1, 4])
        
        # Show pivoted data table (years as columns)
        col1.dataframe(pivoted_df)
        
        # Show year-over-year comparison chart
        chart = create_year_comparison_chart(pivoted_df, category)
        col2.altair_chart(chart, width='stretch')
        
        # Show expandable transaction table
        transactions_df = transactions_spreadsheet.get_transactions_by_category(category)
        display_transaction_table(transactions_df, category)


def render_group_page(
        groups: List[str],
        transactions_spreadsheet: TransactionsSpreadsheet
) -> None:
    """Render a page showing year-over-year comparisons for a list of groups."""
    for group in groups:
        monthly_amounts_df = transactions_spreadsheet.get_monthly_amounts_by_group(
            group=group,
            invert_amount=True
        )
        
        # Transform data for year-over-year comparison
        pivoted_df = prepare_year_comparison_data(monthly_amounts_df)
        
        st.subheader(group)
        col1, col2 = st.columns([1, 4])
        
        # Show pivoted data table (years as columns)
        col1.dataframe(pivoted_df)
        
        # Show year-over-year comparison chart
        chart = create_year_comparison_chart(pivoted_df, group)
        col2.altair_chart(chart, width='stretch')
        
        # Show expandable transaction table
        transactions_df = transactions_spreadsheet.get_transactions_by_group(group)
        display_transaction_table(transactions_df, group)


def create_sparkline_chart(
    df: pd.DataFrame,
    value_column: str,
    date_column: str,
    color: str,
    height: int = 50,
    current_value: Optional[float] = None,
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
        scale_params = {'zero': False}
        if use_min_scale:
            min_value = df[value_column].min() * 0.95
            scale_params['domainMin'] = min_value
        
        chart = alt.Chart(df).mark_line(
            color=color,
            strokeWidth=2 if height <= 50 else 3,
            interpolate='monotone'
        ).encode(
            x=alt.X(f'{date_column}:T', axis=None),
            y=alt.Y(f'{value_column}:Q', axis=None, scale=alt.Scale(**scale_params))
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
    
    return chart


def extract_merchant_name(description: str, method: str = 'first_word') -> str:
    """Extract merchant name from transaction description.

    Args:
        description: Full transaction description
        method: Extraction method ('first_word', 'first_two', 'first_three')

    Returns:
        Extracted merchant name
    """
    if pd.isna(description):
        return 'Unknown'

    words = str(description).split()
    if not words:
        return 'Unknown'

    if method == 'first_word':
        return words[0]
    elif method == 'first_two':
        return ' '.join(words[:2])
    elif method == 'first_three':
        return ' '.join(words[:3])
    else:
        return words[0]


def get_transaction_column_config() -> Dict:
    """Standard column configuration for transaction dataframes.
    
    Returns:
        Dictionary of column configurations for st.dataframe
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
    with st.expander(f"📋 {title} ({len(df)} transactions)"):
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

