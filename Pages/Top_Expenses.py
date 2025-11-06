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
    st.header("Top Expenses")
    
    # Get current and previous month dates
    now = pd.Timestamp.now(tz='UTC')
    current_month_start = now.replace(day=1)
    
    # Previous month
    if current_month_start.month == 1:
        prev_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
    else:
        prev_month_start = current_month_start.replace(month=current_month_start.month - 1)
    
    prev_month_end = current_month_start - timedelta(days=1)
    
    # Get transactions
    df = transactions_spreadsheet.scrubbed_df.copy()
    
    # Filter to expenses only (negative amounts)
    df_expenses = df[df['Type'] == 'Expense'].copy()
    
    # Current month expenses by category
    df_current = df_expenses[
        df_expenses['Date'] >= current_month_start
    ].groupby('Category')['Amount'].sum().reset_index()
    df_current['Amount'] = df_current['Amount'].abs()
    df_current = df_current.sort_values('Amount', ascending=False).head(10)
    df_current.columns = ['Category', 'Current_Month']
    
    # Previous month expenses by category
    df_previous = df_expenses[
        (df_expenses['Date'] >= prev_month_start) & 
        (df_expenses['Date'] <= prev_month_end)
    ].groupby('Category')['Amount'].sum().reset_index()
    df_previous['Amount'] = df_previous['Amount'].abs()
    df_previous.columns = ['Category', 'Previous_Month']
    
    # Merge current and previous
    df_comparison = pd.merge(df_current, df_previous, on='Category', how='outer').fillna(0)
    df_comparison['Change'] = df_comparison['Current_Month'] - df_comparison['Previous_Month']
    df_comparison['Change_Pct'] = df_comparison.apply(
        lambda row: ((row['Change'] / row['Previous_Month']) * 100) if row['Previous_Month'] > 0 else 0,
        axis=1
    )
    
    # Sort by current month spending
    df_comparison = df_comparison.sort_values('Current_Month', ascending=False)
    
    # Show top metrics
    col1, col2, col3 = st.columns(3)
    
    if not df_comparison.empty:
        top_category = df_comparison.iloc[0]
        
        with col1:
            st.metric(
                label="Highest Category",
                value=top_category['Category'],
                delta=f"${top_category['Current_Month']:,.2f}"
            )
        
        with col2:
            total_current = df_comparison['Current_Month'].sum()
            total_previous = df_comparison['Previous_Month'].sum()
            change = total_current - total_previous
            st.metric(
                label="Total Expenses",
                value=f"${total_current:,.2f}",
                delta=f"${change:+,.2f} vs last month",
                delta_color="inverse"
            )
        
        with col3:
            # Biggest increase
            biggest_increase = df_comparison.loc[df_comparison['Change'].idxmax()]
            st.metric(
                label="Biggest Increase",
                value=biggest_increase['Category'],
                delta=f"${biggest_increase['Change']:+,.2f}"
            )
    
    st.divider()
    
    # Create comparison chart
    df_chart = df_comparison.head(10).melt(
        id_vars='Category',
        value_vars=['Current_Month', 'Previous_Month'],
        var_name='Period',
        value_name='Amount'
    )
    
    chart = alt.Chart(df_chart).mark_bar().encode(
        x=alt.X('Amount:Q', title='Amount ($)'),
        y=alt.Y('Category:N', 
                sort=df_comparison.head(10)['Category'].tolist(),
                title='Category'),
        color=alt.Color('Period:N',
                       scale=alt.Scale(
                           domain=['Current_Month', 'Previous_Month'],
                           range=['lightgreen', 'lightgray']
                       ),
                       legend=alt.Legend(
                           title='Period',
                           labelExpr="datum.label == 'Current_Month' ? 'This Month' : 'Last Month'"
                       )),
        tooltip=[
            alt.Tooltip('Category:N', title='Category'),
            alt.Tooltip('Period:N', title='Period'),
            alt.Tooltip('Amount:Q', title='Amount', format='$,.2f')
        ]
    ).properties(
        height=500,
        title='Top 10 Expense Categories: This Month vs Last Month'
    )
    
    st.altair_chart(chart, width='stretch')
    
    # Show detailed data table
    with st.expander("📊 View All Categories"):
        st.dataframe(
            df_comparison,
            width='stretch',
            hide_index=True,
            column_config={
                'Category': st.column_config.TextColumn('Category'),
                'Current_Month': st.column_config.NumberColumn('This Month', format='$%.2f'),
                'Previous_Month': st.column_config.NumberColumn('Last Month', format='$%.2f'),
                'Change': st.column_config.NumberColumn('Change ($)', format='$+.2f'),
                'Change_Pct': st.column_config.NumberColumn('Change (%)', format='%.1f%%')
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

