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
    
    # Time period selector
    col1, col2 = st.columns([1, 3])
    
    with col1:
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
    
    # Get expenses for the period
    df = transactions_spreadsheet.scrubbed_df.copy()
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
    
    # Create two columns for visualizations
    viz_col1, viz_col2 = st.columns(2)
    
    with viz_col1:
        st.subheader("Spending Distribution")
        
        # Pie chart
        if not df_by_category.empty:
            # Limit to top 10 + "Other" for cleaner pie
            df_top = df_by_category.head(10).copy()
            
            if len(df_by_category) > 10:
                other_amount = df_by_category.iloc[10:]['Amount'].sum()
                other_pct = df_by_category.iloc[10:]['Percentage'].sum()
                df_other = pd.DataFrame([{
                    'Category': 'Other',
                    'Amount': other_amount,
                    'Percentage': other_pct
                }])
                df_top = pd.concat([df_top, df_other], ignore_index=True)
            
            pie = alt.Chart(df_top).mark_arc().encode(
                theta=alt.Theta('Amount:Q'),
                color=alt.Color('Category:N', legend=alt.Legend(title='Category')),
                tooltip=[
                    alt.Tooltip('Category:N', title='Category'),
                    alt.Tooltip('Amount:Q', title='Amount', format='$,.2f'),
                    alt.Tooltip('Percentage:Q', title='Percentage', format='.1f')
                ]
            ).properties(
                height=400,
                title='Spending by Category'
            )
            
            st.altair_chart(pie, width='stretch')
    
    with viz_col2:
        st.subheader("Top 10 Categories")
        
        # Horizontal bar chart
        if not df_by_category.empty:
            df_top10 = df_by_category.head(10)
            
            bars = alt.Chart(df_top10).mark_bar(color='lightcoral').encode(
                x=alt.X('Amount:Q', title='Amount ($)'),
                y=alt.Y('Category:N', 
                       sort=df_top10['Category'].tolist(),
                       title='Category'),
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
    
    # Show group breakdown
    st.divider()
    st.subheader("Spending by Group")
    
    df_by_group = df_period.groupby('Group')['Amount'].sum().reset_index()
    df_by_group['Amount'] = df_by_group['Amount'].abs()
    df_by_group = df_by_group.sort_values('Amount', ascending=False)
    
    # Create columns for group metrics
    num_groups = len(df_by_group)
    group_cols = st.columns(min(num_groups, 4))
    
    for idx, row in df_by_group.iterrows():
        with group_cols[idx % 4]:
            pct = (row['Amount'] / total_spending * 100) if total_spending > 0 else 0
            st.metric(
                label=row['Group'],
                value=f"${row['Amount']:,.2f}",
                delta=f"{pct:.1f}% of total"
            )
    
    # Detailed category table
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


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()

