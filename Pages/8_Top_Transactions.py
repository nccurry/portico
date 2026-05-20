import streamlit as st
import pandas as pd
import altair as alt

from src.spreadsheet import load_transactions_data, TransactionsSpreadsheet
from src.filters import apply_transaction_filters, calculate_date_range
from src.analysis.merchants import normalize_merchant_name
from src.page_helpers import get_transaction_column_config, render_data_refresh_controls
from src.custom_types import TopTransactionsStats
from src.constants import (
    TIME_PERIODS,
    CHART_HEIGHT_STANDARD,
    TRANSACTION_TABLE_HEIGHT,
    COLOR_PALETTE,
)


# ---------------------------------------------------------------------------
# Pure helper functions (testable without Streamlit)
# ---------------------------------------------------------------------------

def get_top_transactions(
    df: pd.DataFrame,
    n: int,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, TopTransactionsStats]:
    """Get the N largest expense transactions in a date range.

    Args:
        df: Filtered transactions dataframe
        n: Number of top transactions to return
        start_date: Start of period
        end_date: End of period

    Returns:
        Tuple of (top_n_df, summary_stats dict)
    """
    expenses = df[
        (df['Type'] == 'Expense') &
        (df['Date'] >= start_date) &
        (df['Date'] <= end_date)
    ].copy()

    if expenses.empty:
        return pd.DataFrame(), {
            'total_top_n': 0,
            'total_spending': 0,
            'pct_of_total': 0,
            'num_transactions': 0,
        }

    expenses['Abs_Amount'] = expenses['Amount'].abs()
    total_spending = expenses['Abs_Amount'].sum()

    expenses = expenses.sort_values(
        ['Abs_Amount', 'Date'], ascending=[False, True],
    )
    top_n = expenses.head(n)
    total_top_n = top_n['Abs_Amount'].sum()

    pct_of_total = (total_top_n / total_spending * 100) if total_spending > 0 else 0

    return top_n, {
        'total_top_n': total_top_n,
        'total_spending': total_spending,
        'pct_of_total': pct_of_total,
        'num_transactions': len(expenses),
    }


def get_category_breakdown(top_n_df: pd.DataFrame) -> pd.DataFrame:
    """Get category breakdown of top transactions.

    Returns:
        DataFrame with Category, Total, Count columns sorted by Total descending
    """
    if top_n_df.empty:
        return pd.DataFrame(columns=['Category', 'Total', 'Count'])

    breakdown = top_n_df.groupby('Category').agg(
        Total=('Abs_Amount', 'sum'),
        Count=('Abs_Amount', 'count'),
    ).reset_index().sort_values('Total', ascending=False)

    return breakdown


def find_recurring_large_expenses(top_n_df: pd.DataFrame) -> pd.DataFrame:
    """Identify merchants that appear multiple times in top transactions.

    Returns:
        DataFrame with Merchant, Count, Total columns
    """
    if top_n_df.empty:
        return pd.DataFrame(columns=['Merchant', 'Count', 'Total'])

    df = top_n_df.copy()
    df['Merchant'] = df['Full Description'].apply(
        lambda x: normalize_merchant_name(x, method='first_three')
    )

    recurring = df.groupby('Merchant').agg(
        Count=('Abs_Amount', 'count'),
        Total=('Abs_Amount', 'sum'),
    ).reset_index()

    # Only show merchants with 2+ appearances
    recurring = recurring[recurring['Count'] >= 2].sort_values('Total', ascending=False)

    return recurring


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    """Render top-N expense tables, category breakdowns, and recurring large expenses."""
    st.header("Top Transactions")
    st.caption("See the biggest expenses hitting your wallet")

    # Controls
    col1, col2, _col3 = st.columns([1, 1, 2])
    with col1:
        period = st.selectbox("Time Period", options=TIME_PERIODS, index=4)
    with col2:
        n = st.slider("Number of transactions", min_value=10, max_value=100, value=25, step=5)

    start_date, end_date = calculate_date_range(
        period,
        transactions_spreadsheet.scrubbed_df,
        anchor_to_data=True,
    )

    # Filter transactions
    df = transactions_spreadsheet.scrubbed_df.copy()
    df = apply_transaction_filters(df, {'exclude_groups': ['Transfer']})

    top_n_df, stats = get_top_transactions(df, n, start_date, end_date)

    if top_n_df.empty:
        st.info("No expense transactions found for the selected period")
        return

    # Summary metrics
    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Total (Top N)", f"${stats['total_top_n']:,.2f}")
    with metric_cols[1]:
        st.metric("Total Spending", f"${stats['total_spending']:,.2f}")
    with metric_cols[2]:
        st.metric("% of Total", f"{stats['pct_of_total']:.1f}%")
    with metric_cols[3]:
        st.metric("All Expenses", f"{stats['num_transactions']}")

    st.divider()

    # Two columns: category breakdown chart + recurring large expenses
    chart_col, table_col = st.columns([3, 2])

    with chart_col:
        st.subheader("Category Breakdown")
        breakdown = get_category_breakdown(top_n_df)

        if not breakdown.empty:
            chart = alt.Chart(breakdown).mark_bar().encode(
                x=alt.X('Total:Q', title='Total ($)'),
                y=alt.Y('Category:N', title=None, sort='-x'),
                color=alt.Color('Category:N',
                                scale=alt.Scale(range=COLOR_PALETTE),
                                legend=None),
                tooltip=[
                    alt.Tooltip('Category:N'),
                    alt.Tooltip('Total:Q', format='$,.2f'),
                    alt.Tooltip('Count:Q', title='# Transactions'),
                ]
            ).properties(
                height=min(len(breakdown) * 30 + 50, CHART_HEIGHT_STANDARD),
                width='container',
            )
            st.altair_chart(chart, use_container_width=True)

    with table_col:
        st.subheader("Recurring Large Expenses")
        recurring = find_recurring_large_expenses(top_n_df)

        if not recurring.empty:
            st.dataframe(
                recurring,
                hide_index=True,
                use_container_width=True,
                column_config={
                    'Merchant': st.column_config.TextColumn('Merchant'),
                    'Count': st.column_config.NumberColumn('Occurrences'),
                    'Total': st.column_config.NumberColumn('Total', format='$%.2f'),
                }
            )
        else:
            st.info("No recurring merchants in top transactions")

    st.divider()

    # Full top N table
    st.subheader(f"Top {n} Transactions")
    display_df = top_n_df.sort_values('Abs_Amount', ascending=False)

    st.dataframe(
        display_df,
        height=TRANSACTION_TABLE_HEIGHT,
        hide_index=True,
        use_container_width=True,
        column_config=get_transaction_column_config(),
    )


def main() -> None:
    """Streamlit entry point for the Top Transactions page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()

    transactions_spreadsheet = load_transactions_data()
    configure_page(transactions_spreadsheet)


if __name__ == "__main__":
    main()
