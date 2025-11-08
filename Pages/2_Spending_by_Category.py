import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet


def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    st.header("Spending by Category")
    
    # Add filter controls
    with st.expander("⚙️ Filter Settings", expanded=False):
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            include_groups = st.multiselect(
                "Include Only These Groups",
                options=['Travel', 'Investment', 'Entertainment', 'Shopping', 'Donations', 'Bills', 'Food', 'Income', 'Maintenance', 'Work'],
                default=[],
                help="If set, ONLY show these groups (ignores all exclude filters)"
            )
            
            # Get all categories for the include dropdown
            all_categories = transactions_spreadsheet.scrubbed_df['Category'].unique()
            all_categories = [str(c) for c in all_categories if pd.notna(c) and str(c).strip() != '']
            all_categories = sorted(all_categories)
            
            include_categories = st.multiselect(
                "Include Only These Categories",
                options=all_categories,
                default=[],
                help="If set, ONLY show these categories (ignores all filters)"
            )
            
            st.divider()
            
            exclude_groups = st.multiselect(
                "Exclude Groups",
                options=['Travel', 'Investment', 'Entertainment', 'Shopping', 'Donations', 'Bills', 'Food', 'Income', 'Maintenance', 'Work'],
                default=["Bills", "Income", "Work", "Donations", "Investment"],
                help="Exclude entire transaction groups (Transfer always excluded)"
            )
            
            exclude_categories = st.multiselect(
                "Exclude Categories",
                options=[
                    'Christmas',
                    'Investment',
                    'Home Improvements',
                ],
                default=[
                    'Christmas',
                    'Investment',
                    'Home Improvements',
                ],
                help="Exclude specific one-time or non-recurring transaction categories"
            )
        
        with col_filter2:
            # Filter large expenses
            filter_large_expenses = st.checkbox(
                "Filter Large Expenses",
                value=True,
                help="Exclude individual large expense transactions above a threshold"
            )
            
            expense_threshold = 3000  # Default
            
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Expense Threshold ($)",
                    min_value=1000,
                    max_value=100000,
                    value=3000,
                    step=500,
                    help="Exclude individual expense transactions larger than this amount"
                )
    
    # Time period selector
    period = st.selectbox(
        "Time Period",
        ["This Month", "Last Month", "Last 3 Months", "Last 6 Months", "Last 12 Months", "Year to Date", "All Time"],
        index=2  # Default to Last 3 Months
    )
    
    # Calculate date range based on selection
    now = pd.Timestamp.now(tz='UTC')
    
    if period == "This Month":
        start_date = now.replace(day=1)
        end_date = now
    elif period == "Last Month":
        start_date = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        end_date = now.replace(day=1) - timedelta(days=1)
    elif period == "Last 3 Months":
        start_date = now - timedelta(days=90)
        end_date = now
    elif period == "Last 6 Months":
        start_date = now - timedelta(days=180)
        end_date = now
    elif period == "Last 12 Months":
        start_date = now - timedelta(days=365)
        end_date = now
    elif period == "Year to Date":
        start_date = now.replace(month=1, day=1)
        end_date = now
    else:  # All Time
        df = transactions_spreadsheet.scrubbed_df.copy()
        start_date = df['Date'].min()
        end_date = now
    
    # Get all transactions for the period
    df = transactions_spreadsheet.scrubbed_df.copy()
    
    # Always exclude Transfer group (silently)
    df = df[df['Group'] != 'Transfer']
    
    # Apply INCLUDE filters first (they override excludes)
    if include_groups:
        # If include groups specified, ONLY show those groups
        df = df[df['Group'].isin(include_groups)]
    elif include_categories:
        # If include categories specified, ONLY show those categories
        df = df[df['Category'].isin(include_categories)]
    else:
        # No include filters - apply exclude filters
        if exclude_groups:
            df = df[~df['Group'].isin(exclude_groups)]
        
        if exclude_categories:
            df = df[~df['Category'].isin(exclude_categories)]
    
    # Filter out large expenses if enabled
    if filter_large_expenses:
        df = df[(df['Type'] != 'Expense') | (df['Amount'].abs() <= expense_threshold)]
    
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
    
    # Calculate totals
    total_spending = df_by_category['Amount'].sum()
    df_by_category['Percentage'] = (df_by_category['Amount'] / total_spending * 100).round(1)
    
    # Show summary metrics
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
    
    st.divider()
    
    # Create shared color scale for consistent colors across both charts
    if not df_by_category.empty:
        # Get top 10 categories for color mapping
        top_10_categories = df_by_category.head(10)['Category'].tolist()
        
        # Define color palette (using Tableau10 colors for distinctiveness)
        color_palette = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', 
                        '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac']
        
        # Create color scale
        color_scale = alt.Scale(
            domain=top_10_categories,
            range=color_palette[:len(top_10_categories)]
        )
    
    # Create two columns for visualizations
    viz_col1, viz_col2 = st.columns(2)
    
    with viz_col1:
        st.subheader("Spending Over Time")
        
        # Line chart showing monthly spending for top categories
        if not df_by_category.empty:
            # Get top 5 categories
            top_5_categories = df_by_category.head(5)['Category'].tolist()
            
            # Get monthly spending for these categories
            df_monthly = df_period[df_period['Category'].isin(top_5_categories)].copy()
            df_monthly['Amount'] = df_monthly['Amount'].abs()
            df_monthly_grouped = df_monthly.groupby(['Month', 'Category'])['Amount'].sum().reset_index()
            
            # Create line chart with shared color scale
            lines = alt.Chart(df_monthly_grouped).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Month:O', axis=alt.Axis(labelAngle=-45), title='Month'),
                y=alt.Y('Amount:Q', title='Amount ($)'),
                color=alt.Color('Category:N', 
                               scale=color_scale,
                               legend=None),  # No legend - bar chart serves as legend
                tooltip=[
                    alt.Tooltip('Month:O', title='Month'),
                    alt.Tooltip('Category:N', title='Category'),
                    alt.Tooltip('Amount:Q', title='Amount', format='$,.2f')
                ]
            ).properties(
                height=400,
                title='Top 5 Categories - Monthly Trend'
            )
            
            st.altair_chart(lines, width='stretch')
    
    with viz_col2:
        st.subheader("Top 10 Categories")
        
        # Horizontal bar chart with shared color scale
        if not df_by_category.empty:
            df_top10 = df_by_category.head(10)
            
            bars = alt.Chart(df_top10).mark_bar().encode(
                x=alt.X('Amount:Q', title='Amount ($)'),
                y=alt.Y('Category:N', 
                       sort=df_top10['Category'].tolist(),
                       title='Category'),
                color=alt.Color('Category:N',
                               scale=color_scale,
                               legend=None),  # No legend - shown on left chart
                tooltip=[
                    alt.Tooltip('Category:N', title='Category'),
                    alt.Tooltip('Amount:Q', title='Amount', format='$,.2f'),
                    alt.Tooltip('Percentage:Q', title='% of Total', format='.1f')
                ]
            ).properties(
                height=400,
                title='Top 10 Categories by Amount'
            )
            
            st.altair_chart(bars, width='stretch')
    
    st.divider()
    
    # Show detailed category table
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
    
    # Show large transactions
    with st.expander("💰 View Large Transactions"):
        large_transaction_threshold = st.slider(
            "Minimum Amount to Show ($)",
            min_value=100,
            max_value=5000,
            value=500,
            step=100,
            help="Show transactions larger than this amount"
        )
        
        df_large = df_period[df_period['Amount'].abs() > large_transaction_threshold].copy()
        st.caption(f"Showing {len(df_large)} transactions >${large_transaction_threshold:,}")
        
        # Sort by date descending
        df_large_display = df_large.sort_values('Date', ascending=False)
        
        st.dataframe(
            df_large_display,
            width='stretch',
            height=600,
            hide_index=True,
            column_config={
                'Date': st.column_config.DateColumn('Date', format='YYYY-MM-DD'),
                'Month': st.column_config.TextColumn('Month'),
                'Amount': st.column_config.NumberColumn('Amount', format='$%.2f'),
                'Category': st.column_config.TextColumn('Category'),
                'Group': st.column_config.TextColumn('Group'),
                'Type': st.column_config.TextColumn('Type'),
                'Account': st.column_config.TextColumn('Account'),
                'Full Description': st.column_config.TextColumn('Description')
            }
        )
    
    # Show all transactions
    with st.expander("📋 View All Transactions"):
        st.caption(f"Showing {len(df_period)} expense transactions")
        
        # Sort by date descending
        df_all_display = df_period.sort_values('Date', ascending=False)
        
        st.dataframe(
            df_all_display,
            width='stretch',
            height=600,
            hide_index=True,
            column_config={
                'Date': st.column_config.DateColumn('Date', format='YYYY-MM-DD'),
                'Amount': st.column_config.NumberColumn('Amount', format='$%.2f'),
                'Category': st.column_config.TextColumn('Category'),
                'Group': st.column_config.TextColumn('Group'),
                'Type': st.column_config.TextColumn('Type'),
                'Account': st.column_config.TextColumn('Account'),
                'Full Description': st.column_config.TextColumn('Description')
            }
        )


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()

