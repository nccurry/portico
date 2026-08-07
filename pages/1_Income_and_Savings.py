import streamlit as st
import pandas as pd
import altair as alt

from src.spreadsheet import load_transactions_data, TransactionsSpreadsheet
from src.filters import render_income_expense_filters, apply_transaction_filters
from src.page_helpers import get_transaction_column_config, display_transactions_expander, render_data_refresh_controls
from src.reporting_periods import completed_month_window, current_month_string
from src.analysis.income import (
    calculate_savings_summary,
    process_income_expense_data,
    summarize_filtered_transactions,
)
from src.constants import (
    CHART_HEIGHT_STANDARD,
    COLOR_INCOME,
    COLOR_EXPENSE,
    COLOR_SAVINGS,
    DEFAULT_LARGE_TRANSACTION_THRESHOLD
)


def display_summary_metrics(df_pivot: pd.DataFrame) -> None:
    """Display summary metrics for latest month and averages."""
    if df_pivot.empty:
        st.warning("No data available for the selected filters")
        return

    summary = calculate_savings_summary(df_pivot)
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric(
            label="Monthly Avg Rate",
            value=f"{summary['avg_monthly_rate']:.1f}%",
            help="Average of each month's savings rate (treats each month equally)"
        )

    with metric_col2:
        st.metric(
            label="Overall Rate",
            value=f"{summary['overall_rate']:.1f}%",
            help="Total saved / Total income (weighted by income amount)"
        )

    with metric_col3:
        st.metric(
            label="Monthly Avg Amount",
            value=f"${summary['avg_monthly_amount']:,.0f}"
        )

    with metric_col4:
        st.metric(
            label="Overall Amount",
            value=f"${summary['total_saved']:,.0f}",
            help=f"Total saved over {summary['num_months']} months"
        )


def create_savings_rate_chart(
        df_pivot: pd.DataFrame,
        target_rate: int,
) -> alt.LayerChart:
    """Create savings rate line chart with target line.

    Args:
        df_pivot: Monthly summary data
        target_rate: Target savings rate percentage

    Returns:
        Altair chart
    """
    x_axis = alt.X('Month:O', axis=alt.Axis(labelAngle=-45, title='Month'), sort=None)

    line = alt.Chart(df_pivot).mark_line(
        color=COLOR_INCOME,
        strokeWidth=3,
        point=True
    ).encode(
        x=x_axis,
        y=alt.Y('Savings_Rate:Q',
                axis=alt.Axis(title='Savings Rate (%)', labelLimit=100, labelPadding=5),
                scale=alt.Scale(zero=True)),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Savings_Rate:Q', title='Savings Rate', format='.1f'),
            alt.Tooltip('Savings:Q', title='Amount Saved', format='$,.2f'),
            alt.Tooltip('Income:Q', title='Income', format='$,.2f'),
            alt.Tooltip('Expense:Q', title='Expenses', format='$,.2f')
        ]
    )

    # Zero line (break-even point)
    zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
        color='lightgray',
        strokeWidth=2
    ).encode(y='y:Q')

    # Target line (configurable savings rate goal)
    target_line = alt.Chart(pd.DataFrame({'y': [target_rate]})).mark_rule(
        color=COLOR_SAVINGS,
        strokeDash=[5, 5],
        strokeWidth=2
    ).encode(y='y:Q')

    return (line + zero_line + target_line).properties(  # type: ignore[no-any-return]
        height=CHART_HEIGHT_STANDARD,
        title='Savings Rate Over Time',
        width='container'
    )


def create_income_expense_chart(
        df_pivot: pd.DataFrame,
) -> alt.LayerChart:
    """Create income vs expense bar chart with net cash flow overlay.

    Args:
        df_pivot: Monthly summary data

    Returns:
        Altair chart
    """
    x_axis = alt.X('Month:O', axis=alt.Axis(labelAngle=-45, title='Month'), sort=None)

    # Prepare bar chart data
    df_bars = df_pivot[['Month', 'Income', 'Expense']].copy()
    df_long_bars = df_bars.melt(
        id_vars=['Month'],
        value_vars=['Income', 'Expense'],
        var_name='Category',
        value_name='Amount'
    )
    df_long_bars['Display_Amount'] = df_long_bars['Amount'].abs()

    # Bar chart
    bars = alt.Chart(df_long_bars).mark_bar().encode(
        x=x_axis,
        y=alt.Y(
            'Amount:Q',
            stack='zero',
            axis=alt.Axis(title='Amount ($)', labelLimit=100, labelPadding=5),
        ),
        color=alt.Color('Category:N',
                       scale=alt.Scale(
                           domain=['Income', 'Expense'],
                           range=[COLOR_INCOME, COLOR_EXPENSE]
                       ),
                       legend=None),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Category:N', title='Type'),
            alt.Tooltip('Display_Amount:Q', title='Amount', format='$,.2f')
        ]
    )

    # Net cash flow line overlay
    df_net = df_pivot[['Month', 'Net']].copy()
    net_line = alt.Chart(df_net).mark_line(
        color=COLOR_SAVINGS,
        strokeWidth=3,
        point=True
    ).encode(
        x=x_axis,
        y=alt.Y('Net:Q'),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Net:Q', title='Net Cash Flow', format='$,.2f')
        ]
    )

    return (bars + net_line).resolve_scale(color='independent').properties(  # type: ignore[no-any-return]
        height=CHART_HEIGHT_STANDARD,
        title='Monthly Income vs Expenses',
        width='container'
    )


def display_data_tables(
        df: pd.DataFrame,
        df_pivot: pd.DataFrame,
        df_filtered_by_amount: pd.DataFrame,
) -> None:
    """Display expandable data tables for monthly summary and transactions.

    Args:
        df: Fully filtered transactions dataframe (including amount filters)
        df_pivot: Monthly summary dataframe
        df_filtered_by_amount: Transactions filtered out by amount thresholds only
    """
    # Monthly summary table
    with st.expander("View Monthly Savings Data"):
        display_df = df_pivot[['Month', 'Income_Display', 'Expense_Display', 'Savings', 'Savings_Rate']].copy()

        st.dataframe(
            display_df,
            width='stretch',
            hide_index=True,
            column_config={
                'Month': st.column_config.TextColumn('Month'),
                'Income_Display': st.column_config.NumberColumn('Income', format='$%.2f'),
                'Expense_Display': st.column_config.NumberColumn('Expenses', format='$%.2f'),
                'Savings': st.column_config.NumberColumn('Saved', format='$%.2f'),
                'Savings_Rate': st.column_config.NumberColumn('Savings Rate', format='%.1f%%')
            }
        )

    # Transactions filtered out by amount thresholds
    if not df_filtered_by_amount.empty:
        with st.expander(f"Filtered Large Transactions ({len(df_filtered_by_amount)} excluded from savings calculation)"):
            st.caption(
                "These transactions match your category/group filters but were excluded due to "
                "exceeding the income or expense thresholds. They are NOT included in the savings rate calculation above."
            )

            # Show summary stats
            filtered_summary = summarize_filtered_transactions(df_filtered_by_amount)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Total Amount Filtered",
                    f"${filtered_summary['total_amount']:,.2f}",
                )
            with col2:
                st.metric(
                    "Large Income Excluded",
                    f"${filtered_summary['income_amount']:,.2f}",
                )
            with col3:
                st.metric(
                    "Large Expenses Excluded",
                    f"${filtered_summary['expense_amount']:,.2f}",
                )

            st.divider()

            df_filtered_display = df_filtered_by_amount.sort_values('Date', ascending=False)

            st.dataframe(
                df_filtered_display,
                width='stretch',
                height=400,
                hide_index=True,
                column_config=get_transaction_column_config()
            )

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

        df_large = df[df['Amount'].abs() > large_transaction_threshold].copy()
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
    display_transactions_expander(df, "View All Included Transactions")


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
) -> None:
    """Render sidebar filters, summary metrics, and charts for income vs. expenses."""
    st.header("Income, Expenses & Savings")
    st.caption(
        "Controlled baseline: dependable income compared with routine expenses you can plan around."
    )

    # Time frame selector
    time_frame_col1, _time_frame_col2 = st.columns([1, 4])
    with time_frame_col1:
        time_frame_months = st.selectbox(
            "Time Frame",
            options=[3, 6, 12, 24],
            index=2,  # Default to 12 months
            format_func=lambda x: f"Last {x} Months"
        )

    all_categories = transactions_spreadsheet.get_all_categories()
    all_groups = transactions_spreadsheet.get_all_groups()

    # Render filter controls and get selections
    filters = render_income_expense_filters(all_categories, all_groups)

    # Calculate date range based on time frame
    current_month = current_month_string(transactions_spreadsheet.scrubbed_df, anchor_to_data=True)
    start_month, _end_month = completed_month_window(
        time_frame_months,
        transactions_spreadsheet.scrubbed_df,
        anchor_to_data=True,
    )

    # Process data with filters
    df_pivot = process_income_expense_data(transactions_spreadsheet, filters)

    # Apply time frame filter to monthly data
    df_pivot = df_pivot[
        (df_pivot['Month'] >= start_month) &
        (df_pivot['Month'] < current_month)
    ]

    # Get filtered transactions for detail tables
    df = transactions_spreadsheet.scrubbed_df.copy()
    df = apply_transaction_filters(df, filters)
    df = df[
        (df['Month'] >= start_month) &
        (df['Month'] < current_month)
    ]

    # Calculate transactions that were filtered out by amount thresholds only
    # Apply filters WITHOUT amount thresholds to see what would have been included
    filters_no_amount = filters.copy()
    filters_no_amount['filter_large_income'] = False
    filters_no_amount['filter_large_expenses'] = False

    df_without_amount_filter = transactions_spreadsheet.scrubbed_df.copy()
    df_without_amount_filter = apply_transaction_filters(df_without_amount_filter, filters_no_amount)
    df_without_amount_filter = df_without_amount_filter[
        (df_without_amount_filter['Month'] >= start_month) &
        (df_without_amount_filter['Month'] < current_month)
    ]

    # Find transactions that were excluded by amount filters
    # These are in df_without_amount_filter but not in df
    df_filtered_by_amount = df_without_amount_filter[
        ~df_without_amount_filter.index.isin(df.index)
    ].copy()

    # Display summary metrics
    display_summary_metrics(df_pivot)

    st.divider()

    # Display charts
    st.subheader("Savings Rate %")
    savings_chart = create_savings_rate_chart(df_pivot, filters['target_rate'])
    st.altair_chart(savings_chart, width='stretch')

    st.divider()

    st.subheader("Income vs Expenses $")
    income_expense_chart = create_income_expense_chart(df_pivot)
    st.altair_chart(income_expense_chart, width='stretch')

    # Display data tables
    display_data_tables(df, df_pivot, df_filtered_by_amount)


def main() -> None:
    """Streamlit entry point for the Income & Savings page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()

    transactions_spreadsheet = load_transactions_data()

    configure_page(transactions_spreadsheet)


if __name__ == "__main__":
    main()
