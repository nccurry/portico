import streamlit as st
import pandas as pd
from datetime import timedelta

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet
from src.constants import MIN_DUPLICATE_AMOUNT, DEFAULT_DUPLICATE_DAYS_THRESHOLD


def find_duplicates_efficient(
    df: pd.DataFrame,
    days_threshold: int,
    min_amount: float,
    check_same_account: bool,
    check_same_category: bool
) -> pd.DataFrame:
    """Efficiently find potential duplicate transactions using vectorized operations.
    
    This replaces the O(n²) nested loop with pandas merge operations for much better performance.
    
    Args:
        df: Transaction dataframe
        days_threshold: Maximum days apart to consider duplicates
        min_amount: Minimum transaction amount to check
        check_same_account: Only flag if same account
        check_same_category: Only flag if same category
        
    Returns:
        DataFrame of potential duplicate pairs
    """
    # Filter to reasonable amounts
    df_filtered = df[df['Amount'].abs() >= min_amount].copy()
    
    if df_filtered.empty:
        return pd.DataFrame()
    
    df_filtered = df_filtered.sort_values(['Amount', 'Date']).reset_index(drop=True)
    
    # Self-join on amount to find matching transaction amounts
    duplicates = df_filtered.merge(
        df_filtered,
        on='Amount',
        suffixes=('_1', '_2')
    )
    
    # Filter to only pairs where first transaction comes before second
    # Use the original index to ensure we don't match a transaction with itself
    duplicates = duplicates[duplicates.index_1 < duplicates.index_2]
    
    # Calculate date difference in days
    duplicates['Days_Apart'] = (
        duplicates['Date_2'] - duplicates['Date_1']
    ).dt.days.abs()
    
    # Apply date threshold filter
    duplicates = duplicates[duplicates['Days_Apart'] <= days_threshold]
    
    # Apply account filter if requested
    if check_same_account:
        duplicates = duplicates[duplicates['Account_1'] == duplicates['Account_2']]
    
    # Apply category filter if requested
    if check_same_category:
        duplicates = duplicates[duplicates['Category_1'] == duplicates['Category_2']]
    
    # Format output dataframe
    result = pd.DataFrame({
        'Date1': duplicates['Date_1'],
        'Date2': duplicates['Date_2'],
        'Days_Apart': duplicates['Days_Apart'],
        'Amount': duplicates['Amount'],
        'Category': duplicates['Category_1'],
        'Account1': duplicates['Account_1'],
        'Account2': duplicates['Account_2'],
        'Description1': duplicates['Full Description_1'],
        'Description2': duplicates['Full Description_2'],
        'Month': duplicates['Month_1']
    })
    
    return result


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
                value=DEFAULT_DUPLICATE_DAYS_THRESHOLD,
                help="Consider transactions duplicates if within this many days"
            )
            
            min_amount = st.number_input(
                "Minimum Amount ($)",
                min_value=0.0,
                max_value=1000.0,
                value=MIN_DUPLICATE_AMOUNT,
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
    
    # Find potential duplicates using efficient vectorized method
    df_duplicates = find_duplicates_efficient(
        df=df,
        days_threshold=days_threshold,
        min_amount=min_amount,
        check_same_account=check_same_account,
        check_same_category=check_same_category
    )
    
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

