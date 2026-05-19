import streamlit as st
import pandas as pd
import altair as alt

from src.spreadsheet import load_transactions_data, TransactionsSpreadsheet
from src.filters import render_spending_filters, apply_transaction_filters, calculate_date_range
from src.page_helpers import get_transaction_column_config, display_transactions_expander
from src.custom_types import SpendingFilters, DistributionStats, SpendingSummary
from src.constants import (
    TIME_PERIODS,
    CHART_HEIGHT_STANDARD,
    COLOR_PALETTE,
    DEFAULT_LARGE_TRANSACTION_THRESHOLD
)


def process_spending_data(
    transactions_spreadsheet: TransactionsSpreadsheet,
    filters: SpendingFilters,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply filters and calculate spending by category.

    Args:
        transactions_spreadsheet: Transactions data
        filters: Dictionary of filter settings
        start_date: Period start date
        end_date: Period end date

    Returns:
        Tuple of (filtered_df, category_summary_df)
    """
    # Get all transactions and apply filters
    df = transactions_spreadsheet.scrubbed_df.copy()
    df = apply_transaction_filters(df, filters)

    # Filter to date range and expenses only
    df_period = df[
        (df['Date'] >= start_date) &
        (df['Date'] <= end_date) &
        (df['Type'] == 'Expense')
    ].copy()

    # Group by category
    df_by_category = df_period.groupby('Category')['Amount'].sum().reset_index()
    df_by_category['Amount'] = df_by_category['Amount'].abs()
    df_by_category = df_by_category.sort_values('Amount', ascending=False)

    # Calculate totals and percentages
    total_spending = df_by_category['Amount'].sum()
    if total_spending > 0:
        df_by_category['Percentage'] = (df_by_category['Amount'] / total_spending * 100).round(1)
    else:
        df_by_category['Percentage'] = 0

    return df_period, df_by_category


def calculate_spending_summary(df_by_category: pd.DataFrame) -> SpendingSummary:
    """Derive aggregate spending metrics from the category breakdown.

    Parameters
    ----------
    df_by_category:
        Output of :func:`process_spending_data` — one row per category with
        ``Amount`` (absolute) and ``Percentage`` columns, sorted descending.

    Returns
    -------
    SpendingSummary
        ``total_spending``, ``top_category``, ``top_category_amount``, and
        ``num_categories``.
    """
    if df_by_category.empty:
        return SpendingSummary(
            total_spending=0.0,
            top_category="",
            top_category_amount=0.0,
            num_categories=0,
        )
    return SpendingSummary(
        total_spending=float(df_by_category["Amount"].sum()),
        top_category=str(df_by_category.iloc[0]["Category"]),
        top_category_amount=float(df_by_category.iloc[0]["Amount"]),
        num_categories=len(df_by_category),
    )


def display_summary_metrics(df_by_category: pd.DataFrame) -> None:
    """Display summary metrics for spending."""
    summary = calculate_spending_summary(df_by_category)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Total Spending",
            value=f"${summary['total_spending']:,.2f}"
        )

    with col2:
        if summary["top_category"]:
            st.metric(
                label="Top Category",
                value=summary["top_category"],
                delta=f"${summary['top_category_amount']:,.2f}"
            )

    with col3:
        st.metric(
            label="Active Categories",
            value=summary["num_categories"]
        )


def create_spending_trend_chart(
    df_period: pd.DataFrame,
    top_categories: list[str],
    color_scale: alt.Scale
) -> alt.Chart:
    """Create line chart showing monthly spending trend for top categories.

    Args:
        df_period: Filtered transaction data
        top_categories: List of top category names
        color_scale: Altair color scale for consistency

    Returns:
        Altair chart
    """
    # Get monthly spending for top categories
    df_monthly = df_period[df_period['Category'].isin(top_categories)].copy()
    df_monthly['Amount'] = df_monthly['Amount'].abs()
    df_monthly_grouped = df_monthly.groupby(['Month', 'Category'])['Amount'].sum().reset_index()

    # Create line chart with shared color scale
    chart = alt.Chart(df_monthly_grouped).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X('Month:O', axis=alt.Axis(labelAngle=-45), title='Month'),
        y=alt.Y('Amount:Q', title='Amount ($)'),
        color=alt.Color('Category:N', scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Category:N', title='Category'),
            alt.Tooltip('Amount:Q', title='Amount', format='$,.2f')
        ]
    ).properties(
        height=CHART_HEIGHT_STANDARD,
        title='Top 5 Categories - Monthly Trend'
    )

    return chart  # type: ignore[no-any-return]


def create_top_categories_chart(
    df_by_category: pd.DataFrame,
    color_scale: alt.Scale
) -> alt.Chart:
    """Create horizontal bar chart for top 10 categories.

    Args:
        df_by_category: Category summary data
        color_scale: Altair color scale for consistency

    Returns:
        Altair chart
    """
    df_top10 = df_by_category.head(10)

    chart = alt.Chart(df_top10).mark_bar().encode(
        x=alt.X('Amount:Q', title='Amount ($)'),
        y=alt.Y('Category:N', sort=df_top10['Category'].tolist(), title='Category',
                axis=alt.Axis(labelLimit=200)),
        color=alt.Color('Category:N', scale=color_scale, legend=None),
        tooltip=[
            alt.Tooltip('Category:N', title='Category'),
            alt.Tooltip('Amount:Q', title='Amount', format='$,.2f'),
            alt.Tooltip('Percentage:Q', title='% of Total', format='.1f')
        ]
    ).properties(
        height=CHART_HEIGHT_STANDARD,
        title='Top 10 Categories by Amount'
    ).configure_axis(
        labelLimit=200
    )

    return chart  # type: ignore[no-any-return]


def create_amount_histogram(df_period: pd.DataFrame) -> alt.Chart:
    """Create histogram showing distribution of transaction amounts.

    Args:
        df_period: Filtered transaction data

    Returns:
        Altair chart
    """
    if df_period.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(  # type: ignore[no-any-return]
            text=alt.value("No transaction data available")
        )

    df_hist = df_period.copy()
    df_hist['Amount_Abs'] = df_hist['Amount'].abs()

    bins = [0, 10, 25, 50, 100, 250, 500, 1000, 5000, 100000]
    labels = ['$0-10', '$10-25', '$25-50', '$50-100', '$100-250',
              '$250-500', '$500-1K', '$1K-5K', '$5K+']

    df_hist['Amount_Range'] = pd.cut(df_hist['Amount_Abs'], bins=bins, labels=labels, include_lowest=True)
    bin_counts = df_hist.groupby('Amount_Range', observed=True).size().reset_index(name='Count')

    chart = alt.Chart(bin_counts).mark_bar().encode(
        x=alt.X('Amount_Range:N',
               title='Transaction Amount Range',
               sort=labels,
               axis=alt.Axis(labelAngle=-45)),
        y=alt.Y('Count:Q', title='Number of Transactions'),
        color=alt.value(COLOR_PALETTE[0]),
        tooltip=[
            alt.Tooltip('Amount_Range:N', title='Amount Range'),
            alt.Tooltip('Count:Q', title='# Transactions', format=',')
        ]
    ).properties(
        height=CHART_HEIGHT_STANDARD,
        title='Transaction Count by Amount Range'
    )

    return chart  # type: ignore[no-any-return]


def create_category_boxplot(df_period: pd.DataFrame) -> alt.Chart:
    """Create box plot showing amount distribution by category.

    Args:
        df_period: Filtered transaction data

    Returns:
        Altair chart
    """
    if df_period.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(  # type: ignore[no-any-return]
            text=alt.value("No transaction data available")
        )

    # Get top 10 categories by total spending
    top_categories = (df_period.groupby('Category')['Amount']
                     .sum()
                     .abs()
                     .nlargest(10)
                     .index.tolist())

    df_box = df_period[df_period['Category'].isin(top_categories)].copy()
    df_box['Amount_Abs'] = df_box['Amount'].abs()

    # Create box plot
    chart = alt.Chart(df_box).mark_boxplot(size=30).encode(
        x=alt.X('Amount_Abs:Q',
               title='Transaction Amount ($)',
               scale=alt.Scale(type='log', base=10)),
        y=alt.Y('Category:N',
               title='Category',
               sort='-x',
               axis=alt.Axis(labelLimit=200)),
        color=alt.Color('Category:N',
                       scale=alt.Scale(range=COLOR_PALETTE),
                       legend=None),
        tooltip=[
            alt.Tooltip('Category:N', title='Category')
        ]
    ).properties(
        height=max(300, len(top_categories) * 40),
        title='Amount Distribution by Category (Top 10)'
    )

    return chart  # type: ignore[no-any-return]


def calculate_distribution_stats(df_period: pd.DataFrame) -> DistributionStats:
    """Calculate summary statistics about transaction amount distribution.

    Args:
        df_period: Filtered transaction data

    Returns:
        Dictionary of statistics
    """
    amounts = df_period['Amount'].abs()

    # Calculate percentiles
    p25 = amounts.quantile(0.25)
    p50 = amounts.quantile(0.50)  # Median
    p75 = amounts.quantile(0.75)
    p80 = amounts.quantile(0.80)
    p90 = amounts.quantile(0.90)

    # Calculate mean
    mean = amounts.mean()

    # Count transactions in different ranges
    small_count = len(amounts[amounts < 25])
    medium_count = len(amounts[(amounts >= 25) & (amounts < 250)])
    large_count = len(amounts[amounts >= 250])

    # Calculate what % of spending each represents
    total_spending = amounts.sum()
    small_pct = (amounts[amounts < 25].sum() / total_spending * 100) if total_spending > 0 else 0
    medium_pct = (amounts[(amounts >= 25) & (amounts < 250)].sum() / total_spending * 100) if total_spending > 0 else 0
    large_pct = (amounts[amounts >= 250].sum() / total_spending * 100) if total_spending > 0 else 0

    # Pareto analysis - what % of transactions account for 80% of spending
    sorted_amounts = amounts.sort_values(ascending=False)
    cumsum = sorted_amounts.cumsum()
    threshold_80 = total_spending * 0.8
    transactions_for_80 = min(len(cumsum[cumsum <= threshold_80]) + 1, len(amounts))
    pareto_pct = (transactions_for_80 / len(amounts) * 100) if len(amounts) > 0 else 0

    return {
        'median': p50,
        'mean': mean,
        'p25': p25,
        'p75': p75,
        'p80': p80,
        'p90': p90,
        'small_count': small_count,
        'medium_count': medium_count,
        'large_count': large_count,
        'small_pct': small_pct,
        'medium_pct': medium_pct,
        'large_pct': large_pct,
        'pareto_pct': pareto_pct
    }


def display_distribution_section(
    df_period: pd.DataFrame,
    df_by_category: pd.DataFrame,
) -> None:
    """Display the amount distribution analysis section.

    Args:
        df_period: Filtered transaction data
        df_by_category: Category summary data
    """
    if df_period.empty:
        st.info("No transaction data available for the selected filters and time period")
        return

    # Calculate statistics
    stats = calculate_distribution_stats(df_period)

    # Display summary metrics
    st.subheader("Transaction Amount Summary")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Median Transaction",
            value=f"${stats['median']:.2f}"
        )

    with col2:
        st.metric(
            label="Average Transaction",
            value=f"${stats['mean']:.2f}"
        )

    with col3:
        st.metric(
            label="75th Percentile",
            value=f"${stats['p75']:.2f}"
        )

    with col4:
        st.metric(
            label="90th Percentile",
            value=f"${stats['p90']:.2f}"
        )

    with col5:
        st.metric(
            label="Total Transactions",
            value=f"{len(df_period):,}"
        )

    st.divider()

    # Small vs Medium vs Large breakdown
    st.subheader("Spending Distribution Analysis")

    breakdown_col1, breakdown_col2, breakdown_col3 = st.columns(3)

    with breakdown_col1:
        st.markdown("### Small (<$25)")
        st.metric("# Transactions", f"{stats['small_count']:,}")
        st.metric("% of Total $", f"{stats['small_pct']:.1f}%")
        pct_of_count = (stats['small_count'] / len(df_period) * 100) if len(df_period) > 0 else 0
        st.caption(f"{pct_of_count:.1f}% of all transactions")

    with breakdown_col2:
        st.markdown("### Medium ($25-$250)")
        st.metric("# Transactions", f"{stats['medium_count']:,}")
        st.metric("% of Total $", f"{stats['medium_pct']:.1f}%")
        pct_of_count = (stats['medium_count'] / len(df_period) * 100) if len(df_period) > 0 else 0
        st.caption(f"{pct_of_count:.1f}% of all transactions")

    with breakdown_col3:
        st.markdown("### Large (>$250)")
        st.metric("# Transactions", f"{stats['large_count']:,}")
        st.metric("% of Total $", f"{stats['large_pct']:.1f}%")
        pct_of_count = (stats['large_count'] / len(df_period) * 100) if len(df_period) > 0 else 0
        st.caption(f"{pct_of_count:.1f}% of all transactions")

    st.divider()

    # Pareto insight
    st.subheader("80/20 Analysis (Pareto Principle)")
    st.info(
        f"**Key Insight:** The top {stats['pareto_pct']:.1f}% of your transactions "
        f"account for 80% of your total spending.\n\n"
        f"This means {100 - stats['pareto_pct']:.1f}% of transactions are smaller purchases "
        f"that make up only 20% of your spending."
    )

    st.divider()

    # Visualizations
    viz_col1, viz_col2 = st.columns(2)

    with viz_col1:
        st.subheader("Transaction Count by Amount")
        histogram = create_amount_histogram(df_period)
        st.altair_chart(histogram, width='stretch')

    with viz_col2:
        st.subheader("Distribution by Category")
        boxplot = create_category_boxplot(df_period)
        st.altair_chart(boxplot, width='stretch')

    # Explanation
    with st.expander("How to Read These Charts"):
        st.markdown("""
        **Histogram (Left):**
        - Shows how many transactions fall in each dollar amount range
        - Taller bars = more transactions in that range
        - Most spending patterns show many small transactions and few large ones

        **Box Plot (Right):**
        - Each box shows the distribution for one category
        - The line in the box = median (50th percentile)
        - The box edges = 25th and 75th percentiles (where middle 50% of transactions fall)
        - Dots outside = outliers (unusually large/small transactions)
        - Log scale on X-axis allows easier comparison across wide ranges
        """)


def display_data_tables(df_period: pd.DataFrame, df_by_category: pd.DataFrame) -> None:
    """Display expandable data tables for transactions.

    Args:
        df_period: Filtered transaction data
        df_by_category: Category summary data
    """
    # Large transactions table
    with st.expander("View Large Transactions"):
        large_transaction_threshold = st.slider(
            "Minimum Amount to Show ($)",
            min_value=100,
            max_value=5000,
            value=DEFAULT_LARGE_TRANSACTION_THRESHOLD,
            step=100,
            help="Show transactions larger than this amount"
        )

        df_large = df_period[df_period['Amount'].abs() > large_transaction_threshold].copy()
        st.caption(f"Showing {len(df_large)} transactions >${large_transaction_threshold:,}")

        df_large_display = df_large.sort_values('Date', ascending=False)

        st.dataframe(
            df_large_display,
            width='stretch',
            height=600,
            hide_index=True,
            column_config=get_transaction_column_config()
        )

    # All transactions table
    display_transactions_expander(df_period, "View All Transactions")


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
) -> None:
    """Render sidebar filters, category breakdowns, and distribution charts."""
    st.header("Spending by Category")

    all_categories = transactions_spreadsheet.get_all_categories()
    all_groups = transactions_spreadsheet.get_all_groups()

    # Render filter controls
    filters = render_spending_filters(all_categories, all_groups)

    # Time period selector
    period = st.selectbox(
        "Time Period",
        TIME_PERIODS,
        index=2  # Default to Last 3 Months
    )

    # Calculate date range based on selection
    start_date, end_date = calculate_date_range(period, transactions_spreadsheet.scrubbed_df)

    # Process data
    df_period, df_by_category = process_spending_data(
        transactions_spreadsheet,
        filters,
        start_date,
        end_date
    )

    # Display summary metrics
    display_summary_metrics(df_by_category)

    st.divider()

    if not df_by_category.empty:
        # Create shared color scale for consistent colors across both charts
        top_10_categories = df_by_category.head(10)['Category'].tolist()
        color_scale = alt.Scale(
            domain=top_10_categories,
            range=COLOR_PALETTE[:len(top_10_categories)]
        )

        # Category Analysis
        st.subheader("Category Analysis")
        viz_col1, viz_col2 = st.columns(2)

        with viz_col1:
            top_5_categories = df_by_category.head(5)['Category'].tolist()
            trend_chart = create_spending_trend_chart(df_period, top_5_categories, color_scale)
            st.altair_chart(trend_chart, width='stretch')

        with viz_col2:
            categories_chart = create_top_categories_chart(df_by_category, color_scale)
            st.altair_chart(categories_chart, width='stretch')

        with st.expander("View All Categories"):
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

        st.divider()

        # Amount Distribution
        display_distribution_section(df_period, df_by_category)

        st.divider()

        # Transaction Details
        st.subheader("Transaction Details")
        display_data_tables(df_period, df_by_category)
    else:
        st.info("No spending data found for the selected filters and time period")


def main() -> None:
    """Streamlit entry point for the Spending by Category page."""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()

    configure_page(transactions_spreadsheet)


if __name__ == "__main__":
    main()
