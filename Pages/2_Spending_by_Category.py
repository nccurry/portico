import streamlit as st
import pandas as pd
import altair as alt

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet
from src.filters import render_spending_filters, apply_transaction_filters, calculate_date_range
from src.page_helpers import get_transaction_column_config, display_transactions_expander
from src.constants import (
    TIME_PERIODS,
    CHART_HEIGHT_STANDARD,
    COLOR_PALETTE,
    DEFAULT_LARGE_TRANSACTION_THRESHOLD
)


def process_spending_data(
    transactions_spreadsheet: TransactionsSpreadsheet,
    filters: dict,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply filters and calculate spending by category.
    
    Args:
        transactions_spreadsheet: Transactions data
        filters: Dictionary of filter settings
        start_date: Period start date
        end_date: Period end date
        
    Returns:
        Tuple of (filtered_df, category_summary_df)
    """
    # Get all transactions and apply filters
    df = transactions_spreadsheet.scrubbed_df.copy()
    df = apply_transaction_filters(df, filters)
    
    # Filter to date range and expenses only
    df_period = df[
        (df['Date'] >= start_date) & 
        (df['Date'] <= end_date) &
        (df['Type'] == 'Expense')
    ].copy()
    
    # Group by category
    df_by_category = df_period.groupby('Category')['Amount'].sum().reset_index()
    df_by_category['Amount'] = df_by_category['Amount'].abs()
    df_by_category = df_by_category.sort_values('Amount', ascending=False)
    
    # Calculate totals and percentages
    total_spending = df_by_category['Amount'].sum()
    if total_spending > 0:
        df_by_category['Percentage'] = (df_by_category['Amount'] / total_spending * 100).round(1)
    else:
        df_by_category['Percentage'] = 0
    
    return df_period, df_by_category


def display_summary_metrics(df_by_category: pd.DataFrame) -> None:
    """Display summary metrics for spending.
    
    Args:
        df_by_category: Category summary dataframe
    """
    total_spending = df_by_category['Amount'].sum()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Total Spending",
            value=f"${total_spending:,.2f}"
        )
    
    with col2:
        if not df_by_category.empty:
            st.metric(
                label="Top Category",
                value=df_by_category.iloc[0]['Category'],
                delta=f"${df_by_category.iloc[0]['Amount']:,.2f}"
            )
    
    with col3:
        num_categories = len(df_by_category)
        st.metric(
            label="Active Categories",
            value=num_categories
        )


def create_spending_trend_chart(
    df_period: pd.DataFrame,
    top_categories: list,
    color_scale: alt.Scale
) -> alt.Chart:
    """Create line chart showing monthly spending trend for top categories.
    
    Args:
        df_period: Filtered transaction data
        top_categories: List of top category names
        color_scale: Altair color scale for consistency
        
    Returns:
        Altair chart
    """
    # Get monthly spending for top categories
    df_monthly = df_period[df_period['Category'].isin(top_categories)].copy()
    df_monthly['Amount'] = df_monthly['Amount'].abs()
    df_monthly_grouped = df_monthly.groupby(['Month', 'Category'])['Amount'].sum().reset_index()
    
    # Create line chart with shared color scale
    chart = alt.Chart(df_monthly_grouped).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X('Month:O', axis=alt.Axis(labelAngle=-45), title='Month'),
        y=alt.Y('Amount:Q', title='Amount ($)'),
        color=alt.Color('Category:N', scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Category:N', title='Category'),
            alt.Tooltip('Amount:Q', title='Amount', format='$,.2f')
        ]
    ).properties(
        height=CHART_HEIGHT_STANDARD,
        title='Top 5 Categories - Monthly Trend'
    )
    
    return chart


def create_top_categories_chart(
    df_by_category: pd.DataFrame,
    color_scale: alt.Scale
) -> alt.Chart:
    """Create horizontal bar chart for top 10 categories.
    
    Args:
        df_by_category: Category summary data
        color_scale: Altair color scale for consistency
        
    Returns:
        Altair chart
    """
    df_top10 = df_by_category.head(10)
    
    chart = alt.Chart(df_top10).mark_bar().encode(
        x=alt.X('Amount:Q', title='Amount ($)'),
        y=alt.Y('Category:N', sort=df_top10['Category'].tolist(), title='Category'),
        color=alt.Color('Category:N', scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip('Category:N', title='Category'),
            alt.Tooltip('Amount:Q', title='Amount', format='$,.2f'),
            alt.Tooltip('Percentage:Q', title='% of Total', format='.1f')
        ]
    ).properties(
        height=CHART_HEIGHT_STANDARD,
        title='Top 10 Categories by Amount'
    )
    
    return chart


def display_data_tables(df_period: pd.DataFrame, df_by_category: pd.DataFrame) -> None:
    """Display expandable data tables for categories and transactions.
    
    Args:
        df_period: Filtered transaction data
        df_by_category: Category summary data
    """
    # Category summary table
    with st.expander("📊 View All Categories"):
        st.dataframe(
            df_by_category,
            width='stretch',
            hide_index=True,
            column_config={
                'Category': st.column_config.TextColumn('Category'),
                'Amount': st.column_config.NumberColumn('Amount', format='$%.2f'),
                'Percentage': st.column_config.NumberColumn('% of Total', format='%.1f%%')
            }
        )
    
    # Large transactions table
    with st.expander("💰 View Large Transactions"):
        large_transaction_threshold = st.slider(
            "Minimum Amount to Show ($)",
            min_value=100,
            max_value=5000,
            value=DEFAULT_LARGE_TRANSACTION_THRESHOLD,
            step=100,
            help="Show transactions larger than this amount"
        )
        
        df_large = df_period[df_period['Amount'].abs() > large_transaction_threshold].copy()
        st.caption(f"Showing {len(df_large)} transactions >${large_transaction_threshold:,}")
        
        df_large_display = df_large.sort_values('Date', ascending=False)
        
        st.dataframe(
            df_large_display,
            width='stretch',
            height=600,
            hide_index=True,
            column_config=get_transaction_column_config()
        )
    
    # All transactions table
    display_transactions_expander(df_period, "View All Transactions")


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    """Main page configuration - orchestrates all components."""
    st.header("Spending by Category")
    
    # Get all categories for filter options
    all_categories = transactions_spreadsheet.scrubbed_df['Category'].unique()
    all_categories = [str(c) for c in all_categories if pd.notna(c) and str(c).strip() != '']
    all_categories = sorted(all_categories)
    
    # Render filter controls
    filters = render_spending_filters(all_categories)
    
    # Time period selector
    period = st.selectbox(
        "Time Period",
        TIME_PERIODS,
        index=2  # Default to Last 3 Months
    )
    
    # Calculate date range based on selection
    start_date, end_date = calculate_date_range(period, transactions_spreadsheet.scrubbed_df)
    
    # Process data
    df_period, df_by_category = process_spending_data(
        transactions_spreadsheet,
        filters,
        start_date,
        end_date
    )
    
    # Display summary metrics
    display_summary_metrics(df_by_category)
    
    st.divider()
    
    # Create visualizations
    if not df_by_category.empty:
        # Create shared color scale for consistent colors across both charts
        top_10_categories = df_by_category.head(10)['Category'].tolist()
        color_scale = alt.Scale(
            domain=top_10_categories,
            range=COLOR_PALETTE[:len(top_10_categories)]
        )
        
        # Display charts side by side
        viz_col1, viz_col2 = st.columns(2)
        
        with viz_col1:
            st.subheader("Spending Over Time")
            top_5_categories = df_by_category.head(5)['Category'].tolist()
            trend_chart = create_spending_trend_chart(df_period, top_5_categories, color_scale)
            st.altair_chart(trend_chart, width='stretch')
        
        with viz_col2:
            st.subheader("Top 10 Categories")
            categories_chart = create_top_categories_chart(df_by_category, color_scale)
            st.altair_chart(categories_chart, width='stretch')
        
        st.divider()
        
        # Display data tables
        display_data_tables(df_period, df_by_category)
    else:
        st.info("No spending data found for the selected filters and time period")


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()
