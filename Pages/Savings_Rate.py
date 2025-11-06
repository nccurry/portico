import streamlit as st
import pandas as pd
import altair as alt

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet


def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    st.header("Savings Rate")
    
    # Get all transactions
    df = transactions_spreadsheet.scrubbed_df.copy()
    
    # Group by month and type
    df_monthly = df.groupby(['Month', 'Type'])['Amount'].sum().reset_index()
    
    # Pivot so Income and Expense are separate columns
    df_pivot = df_monthly.pivot(index='Month', columns='Type', values='Amount').fillna(0).reset_index()
    
    # Ensure we have both columns
    if 'Income' not in df_pivot.columns:
        df_pivot['Income'] = 0
    if 'Expense' not in df_pivot.columns:
        df_pivot['Expense'] = 0
    
    # Calculate savings (Income + Expense, since Expense is negative)
    df_pivot['Savings'] = df_pivot['Income'] + df_pivot['Expense']
    
    # Calculate savings rate percentage
    # Avoid division by zero
    df_pivot['Savings_Rate'] = df_pivot.apply(
        lambda row: (row['Savings'] / row['Income'] * 100) if row['Income'] > 0 else 0,
        axis=1
    )
    
    # Sort by month
    df_pivot = df_pivot.sort_values('Month')
    
    # Show current month metrics
    if not df_pivot.empty:
        latest = df_pivot.iloc[-1]
        prev = df_pivot.iloc[-2] if len(df_pivot) > 1 else None
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label=f"Current Month ({latest['Month']})",
                value=f"{latest['Savings_Rate']:.1f}%"
            )
        
        with col2:
            avg_rate = df_pivot['Savings_Rate'].mean()
            st.metric(
                label="Average Savings Rate",
                value=f"{avg_rate:.1f}%"
            )
        
        with col3:
            st.metric(
                label="Saved This Month",
                value=f"${abs(latest['Savings']):,.2f}"
            )
        
        with col4:
            # Calculate trend (vs previous month)
            if prev is not None:
                delta = latest['Savings_Rate'] - prev['Savings_Rate']
                st.metric(
                    label="vs Last Month",
                    value=f"{latest['Savings_Rate']:.1f}%",
                    delta=f"{delta:+.1f}%"
                )
    
    st.divider()
    
    # Create visualization
    # Line chart for savings rate
    line = alt.Chart(df_pivot).mark_line(
        color='lightgreen',
        strokeWidth=3,
        point=True
    ).encode(
        x=alt.X('Month:O', axis=alt.Axis(labelAngle=-45), title='Month'),
        y=alt.Y('Savings_Rate:Q', 
                axis=alt.Axis(title='Savings Rate (%)'),
                scale=alt.Scale(zero=True)),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Savings_Rate:Q', title='Savings Rate', format='.1f'),
            alt.Tooltip('Savings:Q', title='Amount Saved', format='$,.2f'),
            alt.Tooltip('Income:Q', title='Income', format='$,.2f'),
            alt.Tooltip('Expense:Q', title='Expenses', format='$,.2f')
        ]
    ).properties(
        height=400,
        title='Savings Rate Over Time'
    )
    
    # Add target line (optional - can set your goal)
    target_rate = 20  # 20% savings rate target
    target_line = alt.Chart(pd.DataFrame({'y': [target_rate]})).mark_rule(
        color='gold',
        strokeDash=[5, 5],
        strokeWidth=2
    ).encode(y='y:Q')
    
    combined = (line + target_line)
    
    st.altair_chart(combined, width='stretch')
    
    # Show data table
    with st.expander("📊 View Monthly Savings Data"):
        display_df = df_pivot.copy()
        display_df['Income'] = display_df['Income'].abs()
        display_df['Expense'] = display_df['Expense'].abs()
        display_df['Savings'] = display_df['Savings'].abs()
        
        st.dataframe(
            display_df,
            width='stretch',
            hide_index=True,
            column_config={
                'Month': st.column_config.TextColumn('Month'),
                'Income': st.column_config.NumberColumn('Income', format='$%.2f'),
                'Expense': st.column_config.NumberColumn('Expenses', format='$%.2f'),
                'Savings': st.column_config.NumberColumn('Saved', format='$%.2f'),
                'Savings_Rate': st.column_config.NumberColumn('Savings Rate', format='%.1f%%')
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

