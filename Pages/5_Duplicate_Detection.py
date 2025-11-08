import streamlit as st
import pandas as pd
from datetime import timedelta

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet


def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    st.header("Potential Duplicate Transactions")
    
    # Configuration options
    with st.expander("⚙️ Detection Settings", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            days_threshold = st.number_input(
                "Days Apart (Max)",
                min_value=0,
                max_value=7,
                value=1,
                help="Consider transactions duplicates if within this many days"
            )
            
            min_amount = st.number_input(
                "Minimum Amount ($)",
                min_value=0.0,
                max_value=1000.0,
                value=10.0,
                step=10.0,
                help="Only check for duplicates above this amount"
            )
        
        with col2:
            check_same_account = st.checkbox(
                "Require Same Account",
                value=True,
                help="Only flag as duplicate if on the same account"
            )
            
            check_same_category = st.checkbox(
                "Require Same Category",
                value=False,
                help="Only flag as duplicate if same category"
            )
    
    # Get transactions
    df = transactions_spreadsheet.scrubbed_df.copy()
    
    # Filter to reasonable amount
    df = df[df['Amount'].abs() >= min_amount]
    
    # Sort by date and amount for comparison
    df = df.sort_values(['Date', 'Amount']).reset_index(drop=True)
    
    # Find potential duplicates
    duplicates = []
    
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            row1 = df.iloc[i]
            row2 = df.iloc[j]
            
            # Check if amounts match (exactly)
            if row1['Amount'] != row2['Amount']:
                continue
            
            # Check if dates are close
            date_diff = abs((row2['Date'] - row1['Date']).days)
            if date_diff > days_threshold:
                break  # Sorted by date, so no more matches possible
            
            # Check account if required
            if check_same_account and row1['Account'] != row2['Account']:
                continue
            
            # Check category if required
            if check_same_category and row1['Category'] != row2['Category']:
                continue
            
            # Found a potential duplicate
            duplicates.append({
                'Date1': row1['Date'],
                'Date2': row2['Date'],
                'Days_Apart': date_diff,
                'Amount': row1['Amount'],
                'Category': row1['Category'],
                'Account1': row1['Account'],
                'Account2': row2['Account'],
                'Description1': row1['Full Description'],
                'Description2': row2['Full Description'],
                'Month': row1['Month']
            })
    
    df_duplicates = pd.DataFrame(duplicates)
    
    # Show summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Potential Duplicates",
            value=len(df_duplicates)
        )
    
    with col2:
        if len(df_duplicates) > 0:
            total_amount = df_duplicates['Amount'].abs().sum()
            st.metric(
                label="Total Amount",
                value=f"${total_amount:,.2f}"
            )
    
    with col3:
        if len(df_duplicates) > 0:
            unique_months = df_duplicates['Month'].nunique()
            st.metric(
                label="Affected Months",
                value=unique_months
            )
    
    st.divider()
    
    # Display duplicates
    if len(df_duplicates) > 0:
        st.subheader("Potential Duplicate Pairs")
        
        # Sort by most recent first
        df_duplicates_display = df_duplicates.sort_values('Date1', ascending=False)
        
        st.dataframe(
            df_duplicates_display,
            width='stretch',
            height=600,
            hide_index=True,
            column_config={
                'Date1': st.column_config.DateColumn('Date 1', format='YYYY-MM-DD'),
                'Date2': st.column_config.DateColumn('Date 2', format='YYYY-MM-DD'),
                'Days_Apart': st.column_config.NumberColumn('Days Apart'),
                'Amount': st.column_config.NumberColumn('Amount', format='$%.2f'),
                'Category': st.column_config.TextColumn('Category'),
                'Month': st.column_config.TextColumn('Month'),
                'Account1': st.column_config.TextColumn('Account 1'),
                'Account2': st.column_config.TextColumn('Account 2'),
                'Description1': st.column_config.TextColumn('Description 1'),
                'Description2': st.column_config.TextColumn('Description 2')
            }
        )
        
        # Summary by month
        with st.expander("📊 Duplicates by Month"):
            monthly_summary = df_duplicates.groupby('Month').agg({
                'Amount': ['count', lambda x: x.abs().sum()]
            }).reset_index()
            monthly_summary.columns = ['Month', 'Count', 'Total_Amount']
            monthly_summary = monthly_summary.sort_values('Month', ascending=False)
            
            st.dataframe(
                monthly_summary,
                width='stretch',
                hide_index=True,
                column_config={
                    'Month': st.column_config.TextColumn('Month'),
                    'Count': st.column_config.NumberColumn('Duplicate Pairs'),
                    'Total_Amount': st.column_config.NumberColumn('Total Amount', format='$%.2f')
                }
            )
    else:
        st.success("✓ No potential duplicates found with current settings!")
        st.info("Try adjusting the detection settings if you think there might be duplicates.")


def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()

