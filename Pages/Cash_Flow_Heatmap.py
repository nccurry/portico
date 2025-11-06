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
    st.header("Cash Flow Heatmap")
    
    # Time period selector
    col1, col2 = st.columns([1, 3])
    
    with col1:
        period = st.selectbox(
            "Time Period",
            ["Last 3 Months", "Last 6 Months", "Last 12 Months", "Year to Date"],
            index=1  # Default to Last 6 Months
        )
    
    # Calculate date range
    now = pd.Timestamp.now(tz='UTC')
    
    if period == "Last 3 Months":
        start_date = now - timedelta(days=90)
    elif period == "Last 6 Months":
        start_date = now - timedelta(days=180)
    elif period == "Last 12 Months":
        start_date = now - timedelta(days=365)
    else:  # Year to Date
        start_date = now.replace(month=1, day=1)
    
    end_date = now
    
    # Get transactions
    df = transactions_spreadsheet.scrubbed_df.copy()
    df_period = df[
        (df['Date'] >= start_date) & 
        (df['Date'] <= end_date)
    ].copy()
    
    # Extract day of week and week number
    df_period['DayOfWeek'] = df_period['Date'].dt.day_name()
    df_period['WeekNum'] = df_period['Date'].dt.isocalendar().week
    df_period['MonthName'] = df_period['Date'].dt.strftime('%Y-%m')
    df_period['DayOfMonth'] = df_period['Date'].dt.day
    
    # Show summary metrics
    total_income = df_period[df_period['Type'] == 'Income']['Amount'].sum()
    total_expense = df_period[df_period['Type'] == 'Expense']['Amount'].sum()
    net_flow = total_income + total_expense
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Total Income",
            value=f"${abs(total_income):,.2f}"
        )
    
    with col2:
        st.metric(
            label="Total Expenses",
            value=f"${abs(total_expense):,.2f}"
        )
    
    with col3:
        st.metric(
            label="Net Cash Flow",
            value=f"${net_flow:,.2f}",
            delta="Positive" if net_flow > 0 else "Negative"
        )
    
    st.divider()
    
    # Create two tabs for different heatmap views
    tab1, tab2 = st.tabs(["By Day of Week", "By Day of Month"])
    
    with tab1:
        st.subheader("Spending by Day of Week")
        
        # Aggregate expenses by day of week
        df_dow = df_period[df_period['Type'] == 'Expense'].copy()
        df_dow['Amount'] = df_dow['Amount'].abs()
        df_dow_agg = df_dow.groupby('DayOfWeek')['Amount'].sum().reset_index()
        
        # Order days properly
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        df_dow_agg['DayOfWeek'] = pd.Categorical(df_dow_agg['DayOfWeek'], categories=day_order, ordered=True)
        df_dow_agg = df_dow_agg.sort_values('DayOfWeek')
        
        # Bar chart
        chart = alt.Chart(df_dow_agg).mark_bar(color='lightcoral').encode(
            x=alt.X('DayOfWeek:N', 
                   sort=day_order,
                   title='Day of Week',
                   axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('Amount:Q', title='Total Spending ($)'),
            tooltip=[
                alt.Tooltip('DayOfWeek:N', title='Day'),
                alt.Tooltip('Amount:Q', title='Total Spent', format='$,.2f')
            ]
        ).properties(
            height=400,
            title='Total Spending by Day of Week'
        )
        
        st.altair_chart(chart, width='stretch')
        
        # Show average per day
        avg_by_dow = df_dow.groupby('DayOfWeek')['Amount'].mean().reset_index()
        avg_by_dow['DayOfWeek'] = pd.Categorical(avg_by_dow['DayOfWeek'], categories=day_order, ordered=True)
        avg_by_dow = avg_by_dow.sort_values('DayOfWeek')
        
        st.caption("Average Spending Per Day")
        cols = st.columns(7)
        for idx, row in avg_by_dow.iterrows():
            with cols[idx % 7]:
                st.metric(
                    label=row['DayOfWeek'][:3],
                    value=f"${row['Amount']:,.0f}"
                )
    
    with tab2:
        st.subheader("Spending Heatmap by Day of Month")
        
        # Create heatmap data: Month (rows) x Day of Month (columns)
        df_expenses = df_period[df_period['Type'] == 'Expense'].copy()
        df_expenses['Amount'] = df_expenses['Amount'].abs()
        
        # Aggregate by month and day of month
        df_heatmap = df_expenses.groupby(['MonthName', 'DayOfMonth'])['Amount'].sum().reset_index()
        
        # Create heatmap
        if not df_heatmap.empty:
            heatmap = alt.Chart(df_heatmap).mark_rect().encode(
                x=alt.X('DayOfMonth:O', 
                       title='Day of Month',
                       scale=alt.Scale(domain=list(range(1, 32)))),
                y=alt.Y('MonthName:O', 
                       title='Month',
                       sort=None),
                color=alt.Color('Amount:Q',
                               scale=alt.Scale(scheme='reds'),
                               legend=alt.Legend(title='Spending ($)')),
                tooltip=[
                    alt.Tooltip('MonthName:O', title='Month'),
                    alt.Tooltip('DayOfMonth:O', title='Day'),
                    alt.Tooltip('Amount:Q', title='Spent', format='$,.2f')
                ]
            ).properties(
                height=400,
                title='Daily Spending Heatmap (Darker = More Spending)'
            )
            
            st.altair_chart(heatmap, width='stretch')
            
            st.info("💡 **Tip:** Look for dark vertical stripes (days you consistently spend) or dark horizontal stripes (expensive months)")
        else:
            st.info("No expense data available for this period")
    
    # Transaction count heatmap
    st.divider()
    st.subheader("Transaction Frequency")
    
    # Count transactions by day of week
    df_count = df_period.groupby('DayOfWeek').size().reset_index(name='Count')
    df_count['DayOfWeek'] = pd.Categorical(df_count['DayOfWeek'], categories=day_order, ordered=True)
    df_count = df_count.sort_values('DayOfWeek')
    
    count_chart = alt.Chart(df_count).mark_bar(color='steelblue').encode(
        x=alt.X('DayOfWeek:N', 
               sort=day_order,
               title='Day of Week',
               axis=alt.Axis(labelAngle=-45)),
        y=alt.Y('Count:Q', title='Number of Transactions'),
        tooltip=[
            alt.Tooltip('DayOfWeek:N', title='Day'),
            alt.Tooltip('Count:Q', title='Transactions')
        ]
    ).properties(
        height=300,
        title='Transaction Count by Day of Week'
    )
    
    st.altair_chart(count_chart, width='stretch')


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()

