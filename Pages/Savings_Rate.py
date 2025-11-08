import streamlit as st
import pandas as pd
import altair as alt

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet


def configure_page(
        transactions_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    st.header("Income, Expenses & Savings")
    
    # Add filter controls
    with st.expander("⚙️ Filter Settings", expanded=False):
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            exclude_groups = st.multiselect(
                "Exclude Groups",
                options=['Transfer', 'Travel', 'Investment', 'Entertainment', "Shopping", "Donations"],
                default=['Transfer', 'Travel', "Donations"],
                help="Exclude entire transaction groups (Transfer = money movements, Travel = vacations)"
            )
            
            exclude_categories = st.multiselect(
                "Exclude Categories",
                options=[
                    'Tax Return Payment',
                    'Given Gift',
                    'Christmas',
                    '401k',
                    'HSA',
                    'Investment',
                    'RSU',
                    'ESPP',
                    'Home Improvements',
                    'Stock Purchase',
                ],
                default=['Tax Return Payment', 'Given Gift', 'Christmas', '401k', "HSA", "Stock Purchase"],
                help="Exclude specific one-time or non-recurring transaction categories"
            )
        
        with col_filter2:
            # Filter large income
            filter_large_income = st.checkbox(
                "Filter Large Income",
                value=False,
                help="Exclude individual large income transactions above a threshold (bonuses, stock gains)"
            )
            
            income_threshold = 20000  # Default
            
            if filter_large_income:
                income_threshold = st.number_input(
                    "Income Threshold ($)",
                    min_value=5000,
                    max_value=100000,
                    value=10000,
                    step=1000,
                    help="Exclude individual income transactions larger than this amount"
                )
            
            # Filter large expenses
            filter_large_expenses = st.checkbox(
                "Filter Large Expenses",
                value=True,
                help="Exclude individual large expense transactions above a threshold"
            )
            
            expense_threshold = 3000  # Default
            
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Expense Threshold ($)",
                    min_value=1000,
                    max_value=100000,
                    value=3000,
                    step=500,
                    help="Exclude individual expense transactions larger than this amount"
                )
            
            # Savings rate target
            target_rate = st.number_input(
                "Savings Rate Target (%)",
                min_value=0,
                max_value=100,
                value=20,
                step=5,
                help="Your goal savings rate - shown as gold dashed line on chart"
            )
    
    # Get all transactions
    df = transactions_spreadsheet.scrubbed_df.copy()
    
    # Apply group exclusions
    if exclude_groups:
        df = df[~df['Group'].isin(exclude_groups)]
    
    # Apply category exclusions
    if exclude_categories:
        df = df[~df['Category'].isin(exclude_categories)]
    
    # Filter out large expenses if enabled (applies to all categories)
    if filter_large_expenses:
        df = df[(df['Type'] != 'Expense') | (df['Amount'].abs() <= expense_threshold)]
    
    # Filter out large income if enabled
    if filter_large_income:
        df = df[(df['Type'] != 'Income') | (df['Amount'].abs() <= income_threshold)]
    
    # Separate income and expenses
    df_income = df[df['Type'] == 'Income'].copy()
    df_expense = df[df['Type'] == 'Expense'].copy()
    
    # Calculate monthly totals
    monthly_income = df_income.groupby('Month')['Amount'].sum()
    monthly_expense = df_expense.groupby('Month')['Amount'].sum()
    
    # Combine into one dataframe
    df_pivot = pd.DataFrame({
        'Month': monthly_income.index.union(monthly_expense.index)
    })
    df_pivot = df_pivot.merge(
        monthly_income.to_frame('Income'), 
        left_on='Month', 
        right_index=True, 
        how='left'
    ).merge(
        monthly_expense.to_frame('Expense'), 
        left_on='Month', 
        right_index=True, 
        how='left'
    ).fillna(0)
    
    # Income should already be positive, Expense should be negative
    # Keep them in original signs for correct calculation
    # Savings = Income + Expense (since Expense is negative, this subtracts it)
    df_pivot['Savings'] = df_pivot['Income'] + df_pivot['Expense']
    df_pivot['Net'] = df_pivot['Savings']  # Net and Savings are the same
    
    # For display purposes, create absolute value columns
    df_pivot['Income_Display'] = df_pivot['Income'].abs()
    df_pivot['Expense_Display'] = df_pivot['Expense'].abs()
    
    # Calculate savings rate percentage
    # Avoid division by zero - use Income_Display (absolute value) for calculation
    df_pivot['Savings_Rate'] = df_pivot.apply(
        lambda row: (row['Savings'] / row['Income_Display'] * 100) if row['Income_Display'] > 0.01 else 0,
        axis=1
    )
    
    # Sort by month
    df_pivot = df_pivot.sort_values('Month')
    
    # Filter to 2024 onwards (where we have good data)
    df_pivot = df_pivot[df_pivot['Month'] >= '2024-01']
    
    # Exclude current incomplete month
    current_month = pd.Timestamp.now(tz='UTC').strftime('%Y-%m')
    df_pivot = df_pivot[df_pivot['Month'] < current_month]
    
    # Show current month metrics
    if not df_pivot.empty:
        latest = df_pivot.iloc[-1]
        prev = df_pivot.iloc[-2] if len(df_pivot) > 1 else None
        
        metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
        
        with metric_col1:
            st.metric(
                label=f"Latest Month ({latest['Month']})",
                value=f"{latest['Savings_Rate']:.1f}%"
            )
        
        with metric_col2:
            avg_rate = df_pivot['Savings_Rate'].mean()
            st.metric(
                label="Avg Savings Rate",
                value=f"{avg_rate:.1f}%"
            )
        
        with metric_col3:
            avg_savings = df_pivot['Savings'].mean()
            st.metric(
                label="Avg $ Saved/Month",
                value=f"${avg_savings:,.0f}"
            )
        
        with metric_col4:
            saved_amt = latest['Savings']
            st.metric(
                label="Saved (Latest)",
                value=f"${saved_amt:,.2f}",
                delta="Surplus" if saved_amt > 0 else "Deficit"
            )
        
        with metric_col5:
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
    # Common axis settings for both charts (ensures perfect alignment)
    x_axis = alt.X('Month:O', 
                   axis=alt.Axis(labelAngle=-45, title='Month'),
                   sort=None)
    
    # Set consistent Y-axis label formatting for alignment
    y_axis_config = {'labelLimit': 100, 'labelPadding': 5}
    
    # Line chart for savings rate
    line = alt.Chart(df_pivot).mark_line(
        color='lightgreen',
        strokeWidth=3,
        point=True
    ).encode(
        x=x_axis,
        y=alt.Y('Savings_Rate:Q', 
                axis=alt.Axis(title='Savings Rate (%)', **y_axis_config),
                scale=alt.Scale(zero=True)),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Savings_Rate:Q', title='Savings Rate', format='.1f'),
            alt.Tooltip('Savings:Q', title='Amount Saved', format='$,.2f'),
            alt.Tooltip('Income:Q', title='Income', format='$,.2f'),
            alt.Tooltip('Expense:Q', title='Expenses', format='$,.2f')
        ]
    )
    
    # Add zero line (break-even point)
    zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
        color='lightgray',
        strokeWidth=2
    ).encode(y='y:Q')
    
    # Add target line (configurable savings rate goal)
    target_line = alt.Chart(pd.DataFrame({'y': [target_rate]})).mark_rule(
        color='gold',
        strokeDash=[5, 5],
        strokeWidth=2
    ).encode(y='y:Q')
    
    combined_savings = (line + zero_line + target_line).properties(
        height=350,
        title='Savings Rate Over Time',
        width='container'
    )
    
    # Create Income vs Expense bar chart
    df_bars = df_pivot[['Month', 'Income_Display', 'Expense_Display']].copy()
    df_long_bars = df_bars.melt(
        id_vars=['Month'],
        value_vars=['Income_Display', 'Expense_Display'],
        var_name='Category',
        value_name='Amount'
    )
    df_long_bars['Category'] = df_long_bars['Category'].str.replace('_Display', '')
    
    bars = alt.Chart(df_long_bars).mark_bar().encode(
        x=x_axis,  # Use same x-axis as savings rate chart
        y=alt.Y('Amount:Q', 
                axis=alt.Axis(title='Amount ($)', **y_axis_config)),
        color=alt.Color('Category:N',
                       scale=alt.Scale(
                           domain=['Income', 'Expense'],
                           range=['lightgreen', 'lightcoral']
                       ),
                       legend=None),  # Remove legend - colors are self-explanatory
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Category:N', title='Type'),
            alt.Tooltip('Amount:Q', title='Amount', format='$,.2f')
        ]
    )
    
    # Create net cash flow line overlay
    df_net = df_pivot[['Month', 'Net']].copy()
    net_line = alt.Chart(df_net).mark_line(
        color='gold',
        strokeWidth=3,
        point=True
    ).encode(
        x=x_axis,  # Use same x-axis for alignment
        y=alt.Y('Net:Q'),
        tooltip=[
            alt.Tooltip('Month:O', title='Month'),
            alt.Tooltip('Net:Q', title='Net Cash Flow', format='$,.2f')
        ]
    )
    
    combined_income_expense = (bars + net_line).resolve_scale(color='independent').properties(
        height=350,
        title='Monthly Income vs Expenses',
        width='container'
    )
    
    # Display charts stacked vertically
    st.subheader("Savings Rate %")
    st.altair_chart(combined_savings, width='stretch')
    
    st.divider()
    
    st.subheader("Income vs Expenses $")
    st.altair_chart(combined_income_expense, width='stretch')
    
    # Show data table
    with st.expander("📊 View Monthly Savings Data"):
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
    
    # Show large transactions
    with st.expander("💰 View Large Transactions"):
        large_transaction_threshold = st.slider(
            "Minimum Amount to Show ($)",
            min_value=100,
            max_value=5000,
            value=500,
            step=100,
            help="Show transactions larger than this amount"
        )
        
        df_large = df[df['Amount'].abs() > large_transaction_threshold].copy()
        st.caption(f"Showing {len(df_large)} transactions >${large_transaction_threshold:,} (included in savings calculation)")
        
        # Sort by date descending for most recent first
        df_large_display = df_large.copy()
        df_large_display = df_large_display.sort_values('Date', ascending=False)
        
        st.dataframe(
            df_large_display,
            width='stretch',
            height=600,
            hide_index=True,
            column_config={
                'Date': st.column_config.DateColumn('Date', format='YYYY-MM-DD'),
                'Month': st.column_config.TextColumn('Month'),
                'Amount': st.column_config.NumberColumn('Amount', format='$%.2f'),
                'Category': st.column_config.TextColumn('Category'),
                'Group': st.column_config.TextColumn('Group'),
                'Type': st.column_config.TextColumn('Type'),
                'Account': st.column_config.TextColumn('Account'),
                'Full Description': st.column_config.TextColumn('Description')
            }
        )
    
    # Show all filtered transactions
    with st.expander("📋 View All Included Transactions"):
        st.caption(f"Showing {len(df)} transactions after filters (from 2024-01 onwards, excluding current month)")
        
        # Sort by date descending for most recent first
        df_display = df.sort_values('Date', ascending=False).copy()
        
        st.dataframe(
            df_display,
            width='stretch',
            height=600,
            hide_index=True,
            column_config={
                'Date': st.column_config.DateColumn('Date', format='YYYY-MM-DD'),
                'Amount': st.column_config.NumberColumn('Amount', format='$%.2f'),
                'Category': st.column_config.TextColumn('Category'),
                'Group': st.column_config.TextColumn('Group'),
                'Type': st.column_config.TextColumn('Type'),
                'Account': st.column_config.TextColumn('Account'),
                'Full Description': st.column_config.TextColumn('Description')
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

