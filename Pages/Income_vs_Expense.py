import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet


def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    st.header("Income vs Expense")
    
    # Get all transactions
    df = transactions_spreadsheet.scrubbed_df.copy()
    
    # Group by month and type (Income vs Expense)
    df_monthly = df.groupby(['Month', 'Type'])['Amount'].sum().reset_index()
    
    # Pivot so Income and Expense are separate columns
    df_pivot = df_monthly.pivot(index='Month', columns='Type', values='Amount').fillna(0).reset_index()
    
    # Ensure we have both Income and Expense columns
    if 'Income' not in df_pivot.columns:
        df_pivot['Income'] = 0
    if 'Expense' not in df_pivot.columns:
        df_pivot['Expense'] = 0
    
    # Calculate net (Income - Expense, inverted because expenses are negative)
    df_pivot['Net'] = df_pivot['Income'] + df_pivot['Expense']  # Expense is already negative
    
    # Sort by month
    df_pivot = df_pivot.sort_values('Month')
    
    # Show key metrics for current month
    if not df_pivot.empty:
        latest_month = df_pivot.iloc[-1]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label=f"Income ({latest_month['Month']})",
                value=f"${abs(latest_month['Income']):,.2f}"
            )
        
        with col2:
            st.metric(
                label=f"Expenses ({latest_month['Month']})",
                value=f"${abs(latest_month['Expense']):,.2f}"
            )
        
        with col3:
            net_value = latest_month['Net']
            st.metric(
                label=f"Net ({latest_month['Month']})",
                value=f"${net_value:,.2f}",
                delta=f"{'Surplus' if net_value > 0 else 'Deficit'}"
            )
    
    st.divider()
    
    # Create visualization - reshape for Altair
    df_long = df_pivot.melt(
        id_vars=['Month'], 
        value_vars=['Income', 'Expense', 'Net'],
        var_name='Category',
        value_name='Amount'
    )
    
    # Income should be positive, Expense should be negative for visualization
    df_long_bars = df_long[df_long['Category'].isin(['Income', 'Expense'])].copy()
    df_long_bars.loc[df_long_bars['Category'] == 'Expense', 'Amount'] = df_long_bars.loc[df_long_bars['Category'] == 'Expense', 'Amount'] * -1
    
    # Create bar chart for Income and Expense
    bars = alt.Chart(df_long_bars).mark_bar().encode(
        x=alt.X('Month:O', axis=alt.Axis(labelAngle=-45), title='Month'),
        y=alt.Y('Amount:Q', title='Amount ($)'),
        color=alt.Color('Category:N', 
                       scale=alt.Scale(
                           domain=['Income', 'Expense'],
                           range=['lightgreen', 'lightcoral']
                       ),
                       legend=alt.Legend(title='Type')),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Category:N', title='Type'),
            alt.Tooltip('Amount:Q', title='Amount', format='$,.2f')
        ]
    ).properties(
        height=400,
        title='Monthly Income vs Expenses'
    )
    
    # Create line chart for Net
    df_net = df_long[df_long['Category'] == 'Net'].copy()
    line = alt.Chart(df_net).mark_line(
        color='gold',
        strokeWidth=3,
        point=True
    ).encode(
        x=alt.X('Month:O'),
        y=alt.Y('Amount:Q'),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Amount:Q', title='Net', format='$,.2f')
        ]
    )
    
    # Combine charts
    combined = (bars + line).resolve_scale(color='independent')
    
    st.altair_chart(combined, width='stretch')
    
    # Show data table
    with st.expander("📊 View Monthly Data"):
        display_df = df_pivot.copy()
        display_df['Income'] = display_df['Income'].abs()
        display_df['Expense'] = display_df['Expense'].abs()
        
        st.dataframe(
            display_df,
            width='stretch',
            hide_index=True,
            column_config={
                'Month': st.column_config.TextColumn('Month'),
                'Income': st.column_config.NumberColumn('Income', format='$%.2f'),
                'Expense': st.column_config.NumberColumn('Expenses', format='$%.2f'),
                'Net': st.column_config.NumberColumn('Net', format='$%.2f')
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

