"""Merchant Analysis - Track spending by merchant/vendor."""
import streamlit as st
import pandas as pd
import altair as alt

from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet
from src.page_helpers import get_transaction_column_config, extract_merchant_name
from src.filters import calculate_date_range
from src.constants import TIME_PERIODS, CHART_HEIGHT_STANDARD, COLOR_PALETTE


def enrich_with_merchant(
    df: pd.DataFrame,
    extraction_method: str = 'first_two',
) -> pd.DataFrame:
    """Add a ``Merchant`` column derived from ``Full Description``.

    Returns a copy — the original DataFrame is never mutated.
    """
    enriched = df.copy()
    enriched['Merchant'] = enriched['Full Description'].apply(
        lambda x: extract_merchant_name(x, extraction_method)
    )
    return enriched


def analyze_merchants(
    df: pd.DataFrame,
    min_transactions: int = 1,
) -> pd.DataFrame:
    """Aggregate spending statistics by merchant.

    Args:
        df: Transaction dataframe **with a ``Merchant`` column** (see
            :func:`enrich_with_merchant`).
        min_transactions: Minimum transactions to include merchant.

    Returns:
        DataFrame with merchant analysis.
    """
    df_expenses = df[df['Type'] == 'Expense'].copy()

    if df_expenses.empty:
        return pd.DataFrame()

    # Group by merchant
    merchant_stats = df_expenses.groupby('Merchant').agg({
        'Amount': ['sum', 'mean', 'count'],
        'Date': ['min', 'max'],
        'Category': lambda x: x.mode().iloc[0] if not x.mode().empty else (x.iloc[0] if not x.empty else 'Unknown'),  # type: ignore[misc]
        'Account': lambda x: x.mode().iloc[0] if not x.mode().empty else (x.iloc[0] if not x.empty else 'Unknown')  # type: ignore[misc]
    }).reset_index()

    # Flatten column names
    merchant_stats.columns = [
        'Merchant', 'Total_Spent', 'Avg_Transaction', 'Num_Transactions',
        'First_Transaction', 'Last_Transaction', 'Primary_Category', 'Primary_Account'
    ]

    # Convert amounts to positive
    merchant_stats['Total_Spent'] = merchant_stats['Total_Spent'].abs()
    merchant_stats['Avg_Transaction'] = merchant_stats['Avg_Transaction'].abs()

    # Filter by minimum transactions
    merchant_stats = merchant_stats[merchant_stats['Num_Transactions'] >= min_transactions]

    # Sort by total spent
    merchant_stats = merchant_stats.sort_values('Total_Spent', ascending=False)

    # Calculate days between first and last transaction
    merchant_stats['Days_Active'] = (
        merchant_stats['Last_Transaction'] - merchant_stats['First_Transaction']
    ).dt.days

    return merchant_stats


def create_top_merchants_chart(
    merchant_stats: pd.DataFrame,
    top_n: int = 20,
) -> alt.Chart:
    """Create horizontal bar chart of top merchants by spending.

    Args:
        merchant_stats: Merchant analysis dataframe
        top_n: Number of top merchants to show

    Returns:
        Altair chart
    """
    if merchant_stats.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(  # type: ignore[no-any-return]
            text=alt.value("No merchant data available")
        )

    top_merchants = merchant_stats.head(top_n).copy()

    chart = alt.Chart(top_merchants).mark_bar().encode(
        x=alt.X('Total_Spent:Q', title='Total Spent ($)'),
        y=alt.Y('Merchant:N', sort='-x', title='Merchant', axis=alt.Axis(labelLimit=200)),
        color=alt.Color('Primary_Category:N',
                       scale=alt.Scale(range=COLOR_PALETTE),
                       legend=alt.Legend(title='Category')),
        tooltip=[
            alt.Tooltip('Merchant:N', title='Merchant'),
            alt.Tooltip('Total_Spent:Q', title='Total Spent', format='$,.2f'),
            alt.Tooltip('Num_Transactions:Q', title='# Transactions'),
            alt.Tooltip('Avg_Transaction:Q', title='Avg Transaction', format='$,.2f'),
            alt.Tooltip('Primary_Category:N', title='Category')
        ]
    ).properties(
        height=max(CHART_HEIGHT_STANDARD, top_n * 20),
        title=f'Top {top_n} Merchants by Total Spending'
    ).configure_axis(
        labelLimit=200
    )

    return chart  # type: ignore[no-any-return]


def create_frequency_vs_amount_chart(merchant_stats: pd.DataFrame) -> alt.Chart:
    """Create scatter plot of transaction frequency vs average amount.

    Args:
        merchant_stats: Merchant analysis dataframe

    Returns:
        Altair chart
    """
    if merchant_stats.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(  # type: ignore[no-any-return]
            text=alt.value("No merchant data available")
        )

    # Take top 50 by total spending for readability
    top_merchants = merchant_stats.head(50).copy()

    chart = alt.Chart(top_merchants).mark_circle(size=100).encode(
        x=alt.X('Num_Transactions:Q',
               title='Number of Transactions',
               scale=alt.Scale(type='log')),
        y=alt.Y('Avg_Transaction:Q',
               title='Average Transaction Amount ($)',
               scale=alt.Scale(type='log')),
        color=alt.Color('Primary_Category:N',
                       scale=alt.Scale(range=COLOR_PALETTE),
                       legend=alt.Legend(title='Category')),
        size=alt.Size('Total_Spent:Q',
                     scale=alt.Scale(range=[50, 500]),
                     legend=alt.Legend(title='Total Spent ($)')),
        tooltip=[
            alt.Tooltip('Merchant:N', title='Merchant'),
            alt.Tooltip('Total_Spent:Q', title='Total Spent', format='$,.2f'),
            alt.Tooltip('Num_Transactions:Q', title='# Transactions'),
            alt.Tooltip('Avg_Transaction:Q', title='Avg Transaction', format='$,.2f'),
            alt.Tooltip('Primary_Category:N', title='Category')
        ]
    ).properties(
        height=CHART_HEIGHT_STANDARD,
        title='Transaction Frequency vs Average Amount (Top 50 Merchants)'
    )

    return chart  # type: ignore[no-any-return]


def create_merchant_timeline(
    df: pd.DataFrame,
    merchant_stats: pd.DataFrame,
    top_n: int = 10,
) -> alt.Chart:
    """Create timeline showing spending at top merchants over time.

    Args:
        df: Full transaction dataframe with Merchant column
        merchant_stats: Merchant analysis dataframe
        top_n: Number of top merchants to show

    Returns:
        Altair chart
    """
    if merchant_stats.empty or df.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(  # type: ignore[no-any-return]
            text=alt.value("No merchant data available")
        )

    # Get top N merchants
    top_merchants_list = merchant_stats.head(top_n)['Merchant'].tolist()

    # Filter to those merchants
    df_top = df[df['Merchant'].isin(top_merchants_list) & (df['Type'] == 'Expense')].copy()

    if df_top.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(  # type: ignore[no-any-return]
            text=alt.value("No timeline data available")
        )

    # Group by merchant and month
    df_top['Amount_Abs'] = df_top['Amount'].abs()
    timeline = df_top.groupby(['Merchant', 'Month'])['Amount_Abs'].sum().reset_index()

    # Create line chart
    chart = alt.Chart(timeline).mark_line(point=True).encode(
        x=alt.X('Month:O', axis=alt.Axis(labelAngle=-45), title='Month'),
        y=alt.Y('Amount_Abs:Q', title='Amount Spent ($)'),
        color=alt.Color('Merchant:N',
                       scale=alt.Scale(range=COLOR_PALETTE),
                       legend=alt.Legend(title='Merchant')),
        tooltip=[
            alt.Tooltip('Merchant:N', title='Merchant'),
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Amount_Abs:Q', title='Amount', format='$,.2f')
        ]
    ).properties(
        height=CHART_HEIGHT_STANDARD,
        title=f'Spending Timeline - Top {top_n} Merchants'
    )

    return chart  # type: ignore[no-any-return]


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    """Render top-merchant charts, spending timelines, and per-merchant tables."""
    st.header("Merchant Analysis")
    st.caption("Track spending patterns by merchant/vendor")

    # Settings
    with st.expander("⚙️ Analysis Settings", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            time_period = st.selectbox(
                "Time Period",
                TIME_PERIODS,
                index=4  # Default to Last 12 Months
            )

        with col2:
            extraction_method = st.selectbox(
                "Merchant Name Extraction",
                ['first_word', 'first_two', 'first_three'],
                index=1,
                help="How to extract merchant name from transaction description"
            )

        with col3:
            min_transactions = st.number_input(
                "Minimum Transactions",
                min_value=1,
                max_value=20,
                value=2,
                help="Only show merchants with at least this many transactions"
            )

    # Get transactions
    df = transactions_spreadsheet.scrubbed_df.copy()

    # Calculate date range
    start_date, end_date = calculate_date_range(time_period, df)

    # Filter to date range
    df_period = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)].copy()

    # Analyze merchants
    with st.spinner("Analyzing merchants..."):
        df_period = enrich_with_merchant(df_period, extraction_method)

        merchant_stats = analyze_merchants(
            df_period,
            min_transactions=min_transactions,
        )

    # Display summary metrics
    if not merchant_stats.empty:
        total_spent = merchant_stats['Total_Spent'].sum()
        num_merchants = len(merchant_stats)
        top_merchant = merchant_stats.iloc[0]
        avg_per_merchant = total_spent / num_merchants

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Total Merchants",
                value=num_merchants
            )

        with col2:
            st.metric(
                label="Total Spent",
                value=f"${total_spent:,.2f}"
            )

        with col3:
            st.metric(
                label="Top Merchant",
                value=top_merchant['Merchant'][:20],
                delta=f"${top_merchant['Total_Spent']:,.2f}"
            )

        with col4:
            st.metric(
                label="Avg Spent/Merchant",
                value=f"${avg_per_merchant:,.2f}"
            )

        st.divider()

        # Display visualizations
        tab1, tab2, tab3 = st.tabs(["Top Merchants", "Frequency Analysis", "Timeline"])

        with tab1:
            top_n = st.slider("Number of merchants to show", 10, 50, 20, key="top_merchants_slider")
            chart = create_top_merchants_chart(merchant_stats, top_n)
            st.altair_chart(chart, width='stretch')

        with tab2:
            freq_chart = create_frequency_vs_amount_chart(merchant_stats)
            st.altair_chart(freq_chart, width='stretch')
            st.caption(
                "Bubble size represents total spending. "
                "Top-right quadrant = frequent high-value purchases. "
                "Bottom-right = frequent low-value purchases."
            )

        with tab3:
            timeline_n = st.slider("Number of merchants to show", 5, 20, 10, key="timeline_slider")
            timeline_chart = create_merchant_timeline(df_period, merchant_stats, timeline_n)
            st.altair_chart(timeline_chart, width='stretch')

        st.divider()

        # Search and filter merchants
        st.subheader("Merchant Details")

        search_term = st.text_input(
            "Search merchants",
            placeholder="Type to filter merchants..."
        )

        # Filter merchant stats based on search
        if search_term:
            filtered_stats = merchant_stats[
                merchant_stats['Merchant'].str.contains(search_term, case=False, na=False)
            ]
        else:
            filtered_stats = merchant_stats

        st.caption(f"Showing {len(filtered_stats)} merchants")

        # Display merchant stats table
        st.dataframe(
            filtered_stats,
            width='stretch',
            height=400,
            hide_index=True,
            column_config={
                'Merchant': st.column_config.TextColumn('Merchant'),
                'Total_Spent': st.column_config.NumberColumn('Total Spent', format='$%.2f'),
                'Num_Transactions': st.column_config.NumberColumn('# Transactions'),
                'Avg_Transaction': st.column_config.NumberColumn('Avg Transaction', format='$%.2f'),
                'Primary_Category': st.column_config.TextColumn('Category'),
                'Primary_Account': st.column_config.TextColumn('Account'),
                'First_Transaction': st.column_config.DateColumn('First Purchase', format='YYYY-MM-DD'),
                'Last_Transaction': st.column_config.DateColumn('Last Purchase', format='YYYY-MM-DD'),
                'Days_Active': st.column_config.NumberColumn('Days Active')
            }
        )

        # Show transactions for selected merchant
        with st.expander("📋 View Transactions by Merchant"):
            selected_merchant = st.selectbox(
                "Select Merchant",
                options=filtered_stats['Merchant'].tolist()
            )

            if selected_merchant:
                merchant_transactions = df_period[
                    df_period['Merchant'] == selected_merchant
                ].sort_values('Date', ascending=False)

                st.caption(f"Showing {len(merchant_transactions)} transactions for {selected_merchant}")

                st.dataframe(
                    merchant_transactions,
                    width='stretch',
                    height=400,
                    hide_index=True,
                    column_config=get_transaction_column_config()
                )
    else:
        st.info(
            "No merchant data found for the selected time period and filters. "
            "Try adjusting the settings or selecting a different time period."
        )


def main() -> None:
    """Streamlit entry point for the Merchant Analysis page."""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()

