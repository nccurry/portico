import streamlit as st
from src.spreadsheet import load_transactions_data, TransactionsSpreadsheet
from src.constants import MIN_DUPLICATE_AMOUNT, DEFAULT_DUPLICATE_DAYS_THRESHOLD
from src.page_helpers import render_data_refresh_controls
from src.analysis.duplicates import (
    find_duplicates_efficient,
    summarize_duplicates,
    summarize_duplicates_by_month,
)


def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
) -> None:
    """Render detection settings and display flagged duplicate transactions."""
    st.header("Potential Duplicate Transactions")

    # Configuration options
    with st.expander("Detection Settings", expanded=False):
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

            require_same_description = st.checkbox(
                "Require Same Description",
                value=True,
                help="Only flag as duplicate if descriptions match"
            )

    # Get transactions
    df = transactions_spreadsheet.scrubbed_df.copy()

    # Find potential duplicates using efficient vectorized method
    df_duplicates = find_duplicates_efficient(
        df=df,
        days_threshold=days_threshold,
        min_amount=min_amount,
        check_same_account=check_same_account,
        check_same_category=check_same_category,
        require_same_description=require_same_description,
    )
    summary = summarize_duplicates(df_duplicates)

    # Show summary
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Potential Duplicates",
            value=summary["pair_count"]
        )

    with col2:
        if summary["pair_count"]:
            st.metric(
                label="Total Amount",
                value=f"${summary['total_amount']:,.2f}"
            )

    with col3:
        if summary["pair_count"]:
            st.metric(
                label="Affected Months",
                value=summary["affected_months"]
            )

    st.divider()

    # Display duplicates
    if summary["pair_count"]:
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
        with st.expander("Duplicates by Month"):
            monthly_summary = summarize_duplicates_by_month(df_duplicates)

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
        st.success("No potential duplicates found with current settings.")
        st.info("Try adjusting the detection settings if you think there might be duplicates.")


def main() -> None:
    """Streamlit entry point for the Duplicate Detection page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()

    transactions_spreadsheet = load_transactions_data()

    configure_page(transactions_spreadsheet)


if __name__ == "__main__":
    main()
