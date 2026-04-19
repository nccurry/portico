"""Subscription Tracker - Automatically detect and track recurring charges."""
import streamlit as st
import pandas as pd
import altair as alt

from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet
from src.page_helpers import get_transaction_column_config, extract_merchant_name
from src.constants import CHART_HEIGHT_STANDARD, COLOR_EXPENSE


def detect_recurring_transactions(
    df: pd.DataFrame,
    min_occurrences: int = 3,
    min_months: int = 3,
    amount_tolerance: float = 0.01
) -> pd.DataFrame:
    """Detect potential subscriptions using amount + merchant patterns.

    Args:
        df: Transaction dataframe
        min_occurrences: Minimum number of occurrences to flag as subscription
        min_months: Minimum number of unique months to flag as subscription
        amount_tolerance: Tolerance for amount matching (as fraction, e.g., 0.01 = 1%)

    Returns:
        DataFrame of detected subscriptions with summary info
    """
    # Filter to expenses only, excluding mortgage, loans, investments, and other non-subscription categories
    excluded_categories = [
        'Mortgage Payment',
        'Auto Loan Payment',
        'Student Loan Payment',
        'Personal Loan Payment',
        'Car Payment',
        'Rent',
        'Investment',
        'Stock Purchase',
        '401k',
        'HSA',
        'RSU',
        'ESPP'
    ]

    df_expenses = df[
        (df['Type'] == 'Expense') &
        (~df['Category'].isin(excluded_categories)) &
        (~df['Category'].str.contains('Mortgage|Loan|Investment|401k|HSA|RSU|ESPP', case=False, na=False, regex=True))
    ].copy()

    # Extract merchant name (first few words of description)
    df_expenses['Merchant'] = df_expenses['Full Description'].apply(lambda x: extract_merchant_name(x, 'first_three'))

    # Round amounts to avoid minor differences (e.g., tax variations)
    df_expenses['Amount_Rounded'] = df_expenses['Amount'].abs().round(2)

    # Group by Merchant + Amount
    grouped = df_expenses.groupby(['Merchant', 'Amount_Rounded']).agg({
        'Date': ['count', 'min', 'max'],
        'Month': 'nunique',
        'Amount': 'mean',
        'Category': lambda x: x.mode().iloc[0] if not x.mode().empty else (x.iloc[0] if not x.empty else ''),
        'Account': lambda x: x.mode().iloc[0] if not x.mode().empty else (x.iloc[0] if not x.empty else '')
    }).reset_index()

    # Flatten column names
    grouped.columns = ['Merchant', 'Amount_Rounded', 'Count', 'First_Date', 'Last_Date',
                      'Unique_Months', 'Avg_Amount', 'Category', 'Account']

    # Calculate days between transactions (guard against Count == 1)
    count_minus_1 = (grouped['Count'] - 1).replace(0, 1)
    grouped['Days_Between'] = (grouped['Last_Date'] - grouped['First_Date']).dt.days / count_minus_1
    grouped.loc[grouped['Count'] == 1, 'Days_Between'] = 0

    # Flag as subscription if:
    # - Appears min_occurrences+ times
    # - Roughly monthly cadence (20-40 days between charges on average)
    # - Spans min_months+ unique months
    subscriptions = grouped[
        (grouped['Count'] >= min_occurrences) &
        (grouped['Unique_Months'] >= min_months) &
        (grouped['Days_Between'] >= 20) &
        (grouped['Days_Between'] <= 40)
    ].copy()

    # Sort by amount (most expensive first)
    subscriptions = subscriptions.sort_values('Avg_Amount', ascending=False)

    # Calculate annual cost estimate
    subscriptions['Annual_Cost'] = subscriptions['Avg_Amount'].abs() * 12

    return subscriptions


def create_subscription_timeline(
    df: pd.DataFrame,
    subscriptions: pd.DataFrame,
) -> alt.Chart:
    """Create a timeline showing when subscriptions started/ended.

    Args:
        df: Full transaction dataframe
        subscriptions: Detected subscriptions dataframe

    Returns:
        Altair chart
    """
    if subscriptions.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(
            text=alt.value("No subscriptions detected")
        )

    # For each subscription, get all matching transactions
    timeline_data = []
    for _, sub in subscriptions.iterrows():
        merchant = sub['Merchant']
        amount = sub['Amount_Rounded']

        # Find matching transactions
        matches = df[
            (df['Full Description'].str.contains(merchant.split()[0], case=False, na=False)) &
            (df['Amount'].abs().round(2) == amount)
        ].copy()

        if not matches.empty:
            timeline_data.append({
                'Merchant': merchant[:30],  # Truncate long names
                'First_Date': matches['Date'].min(),
                'Last_Date': matches['Date'].max(),
                'Amount': sub['Avg_Amount']
            })

    timeline_df = pd.DataFrame(timeline_data)

    if timeline_df.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(
            text=alt.value("No subscription data available")
        )

    # Create Gantt-style chart
    chart = alt.Chart(timeline_df).mark_bar().encode(
        x=alt.X('First_Date:T', title='Timeline'),
        x2='Last_Date:T',
        y=alt.Y('Merchant:N', title='Subscription', sort='-x'),
        color=alt.Color('Amount:Q',
                       scale=alt.Scale(scheme='reds'),
                       legend=alt.Legend(title='Monthly Cost ($)')),
        tooltip=[
            alt.Tooltip('Merchant:N', title='Merchant'),
            alt.Tooltip('First_Date:T', title='Started', format='%Y-%m-%d'),
            alt.Tooltip('Last_Date:T', title='Last Charge', format='%Y-%m-%d'),
            alt.Tooltip('Amount:Q', title='Monthly Cost', format='$,.2f')
        ]
    ).properties(
        height=max(300, len(timeline_df) * 25),
        title='Subscription Timeline'
    )

    return chart


def create_subscription_cost_chart(subscriptions: pd.DataFrame) -> alt.Chart:
    """Create bar chart of monthly subscription costs.

    Args:
        subscriptions: Detected subscriptions dataframe

    Returns:
        Altair chart
    """
    if subscriptions.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(
            text=alt.value("No subscriptions detected")
        )

    # Take top 15 by cost
    top_subs = subscriptions.head(15).copy()
    top_subs['Merchant_Short'] = top_subs['Merchant'].str[:30]

    chart = alt.Chart(top_subs).mark_bar().encode(
        x=alt.X('Avg_Amount:Q', title='Monthly Cost ($)'),
        y=alt.Y('Merchant_Short:N',
               sort='-x',
               title='Subscription',
               axis=alt.Axis(labelLimit=200)),
        color=alt.value(COLOR_EXPENSE),
        tooltip=[
            alt.Tooltip('Merchant:N', title='Merchant'),
            alt.Tooltip('Avg_Amount:Q', title='Monthly Cost', format='$,.2f'),
            alt.Tooltip('Annual_Cost:Q', title='Annual Cost', format='$,.2f'),
            alt.Tooltip('Count:Q', title='# Charges'),
            alt.Tooltip('Category:N', title='Category')
        ]
    ).properties(
        height=CHART_HEIGHT_STANDARD,
        title='Monthly Subscription Costs (Top 15)'
    ).configure_axis(
        labelLimit=200
    )

    return chart


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    """Detect recurring charges and render subscription timelines and tables."""
    st.header("Subscription Tracker")
    st.caption("Automatically detect recurring charges and subscriptions")

    # Detection settings
    with st.expander("⚙️ Detection Settings", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            min_occurrences = st.number_input(
                "Minimum Occurrences",
                min_value=2,
                max_value=12,
                value=3,
                help="Minimum number of times a charge must appear to be considered a subscription"
            )

            min_months = st.number_input(
                "Minimum Months",
                min_value=2,
                max_value=12,
                value=3,
                help="Minimum number of unique months a charge must span"
            )

        with col2:
            st.info(
                "Subscriptions are detected by finding recurring charges with:\n"
                "- Same merchant and amount\n"
                "- Roughly monthly cadence (20-40 days apart)\n"
                "- Minimum number of occurrences and months\n\n"
                "**Excluded:** Mortgage, loans, rent, investments (401k, HSA, stock purchases)"
            )

    # Get all transactions
    df = transactions_spreadsheet.scrubbed_df.copy()

    # Detect subscriptions
    with st.spinner("Detecting subscriptions..."):
        subscriptions = detect_recurring_transactions(
            df,
            min_occurrences=min_occurrences,
            min_months=min_months
        )

    # Display summary metrics
    if not subscriptions.empty:
        total_monthly = subscriptions['Avg_Amount'].abs().sum()
        total_annual = subscriptions['Annual_Cost'].abs().sum()
        num_subs = len(subscriptions)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Detected Subscriptions",
                value=num_subs
            )

        with col2:
            st.metric(
                label="Total Monthly Cost",
                value=f"${total_monthly:,.2f}"
            )

        with col3:
            st.metric(
                label="Projected Annual Cost",
                value=f"${total_annual:,.2f}"
            )

        with col4:
            avg_cost = total_monthly / num_subs
            st.metric(
                label="Average Subscription",
                value=f"${avg_cost:,.2f}/mo"
            )

        st.divider()

        # Display visualizations
        viz_col1, viz_col2 = st.columns([2, 1])

        with viz_col1:
            st.subheader("Subscription Timeline")
            timeline_chart = create_subscription_timeline(df, subscriptions)
            st.altair_chart(timeline_chart, width='stretch')

        with viz_col2:
            st.subheader("Monthly Costs")
            cost_chart = create_subscription_cost_chart(subscriptions)
            st.altair_chart(cost_chart, width='stretch')

        st.divider()

        # Display subscription details table
        st.subheader("Detected Subscriptions")

        # Prepare display dataframe
        display_df = subscriptions[[
            'Merchant', 'Category', 'Avg_Amount', 'Annual_Cost',
            'Count', 'Unique_Months', 'First_Date', 'Last_Date', 'Account'
        ]].copy()

        st.dataframe(
            display_df,
            width='stretch',
            height=600,
            hide_index=True,
            column_config={
                'Merchant': st.column_config.TextColumn('Merchant'),
                'Category': st.column_config.TextColumn('Category'),
                'Avg_Amount': st.column_config.NumberColumn('Monthly Cost', format='$%.2f'),
                'Annual_Cost': st.column_config.NumberColumn('Annual Cost', format='$%.2f'),
                'Count': st.column_config.NumberColumn('# Charges'),
                'Unique_Months': st.column_config.NumberColumn('# Months'),
                'First_Date': st.column_config.DateColumn('First Charge', format='YYYY-MM-DD'),
                'Last_Date': st.column_config.DateColumn('Last Charge', format='YYYY-MM-DD'),
                'Account': st.column_config.TextColumn('Account')
            }
        )

        # Show individual transactions for each subscription
        with st.expander("📋 View Individual Charges by Subscription"):
            selected_merchant = st.selectbox(
                "Select Subscription",
                options=subscriptions['Merchant'].tolist()
            )

            if selected_merchant:
                # Get the amount for this subscription
                sub_amount = subscriptions[subscriptions['Merchant'] == selected_merchant]['Amount_Rounded'].iloc[0]

                # Find all matching transactions
                merchant_first_word = selected_merchant.split()[0]
                matching_transactions = df[
                    (df['Full Description'].str.contains(merchant_first_word, case=False, na=False)) &
                    (df['Amount'].abs().round(2) == sub_amount)
                ].copy()

                matching_transactions = matching_transactions.sort_values('Date', ascending=False)

                st.caption(f"Showing {len(matching_transactions)} charges for {selected_merchant}")

                st.dataframe(
                    matching_transactions,
                    width='stretch',
                    height=400,
                    hide_index=True,
                    column_config=get_transaction_column_config()
                )
    else:
        st.info(
            "No recurring subscriptions detected with current settings. "
            "Try adjusting the detection parameters or check if you have enough transaction history."
        )


def main() -> None:
    """Streamlit entry point for the Subscriptions page."""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()

