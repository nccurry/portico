import streamlit as st
import pandas as pd
from datetime import timedelta

from src.spreadsheet import (
    load_transactions_data, 
    load_balance_history_data, 
    calculate_group_sparkline,
    calculate_net_worth_sparkline,
    TransactionsSpreadsheet, 
    BalanceHistorySpreadsheet
)
from src.page_helpers import create_sparkline_chart
from src.constants import (
    SPARKLINE_HISTORY_DAYS,
    CHART_HEIGHT_SPARKLINE,
    CHART_HEIGHT_NET_WORTH_SPARKLINE,
    COLOR_NET_WORTH,
    COLOR_ASSET,
    COLOR_LIABILITY
)


def configure_page(
        transaction_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    st.header("Account Balances")
    
    # Get all account groups (filter out NaN/None values and convert to strings)
    groups = balance_history_spreadsheet.get_groups()
    groups = [str(g) for g in groups if pd.notna(g) and g != '']
    
    # Calculate total net worth across all groups
    # Assets add to net worth, Liabilities subtract
    total_net_worth = 0.0
    group_balances = {}
    group_classes = {}  # Track whether each group is Asset or Liability
    group_accounts = {}  # Cache accounts_df to avoid redundant calls

    for group in groups:
        accounts_df, total = balance_history_spreadsheet.get_latest_balance_by_group(group)
        group_accounts[group] = accounts_df
        
        # Check if this group contains liabilities (debt)
        account_class = "Asset"  # Default
        if not accounts_df.empty:
            # Get the class for accounts in this group
            df_check = balance_history_spreadsheet.scrubbed_df[
                balance_history_spreadsheet.scrubbed_df["Group"] == group
            ]
            if not df_check.empty:
                account_class = df_check.iloc[0]["Class"]
        
        # Store class for later use in sparkline coloring
        group_classes[group] = account_class
        
        # Liabilities subtract from net worth, Assets add
        if account_class == "Liability":
            total_net_worth -= total
        else:
            total_net_worth += total
        
        # Always store balance as positive for display
        group_balances[group] = total
    
    # Display total net worth prominently
    st.metric(
        label="Total Net Worth",
        value=f"${total_net_worth:,.2f}"
    )
    
    # Calculate net worth sparkline (cached for performance)
    end_date = pd.Timestamp.now(tz='UTC')
    start_date = end_date - timedelta(days=SPARKLINE_HISTORY_DAYS)
    
    df_net_worth = calculate_net_worth_sparkline(
        balance_history_spreadsheet.scrubbed_df,
        start_date,
        end_date
    )
    
    # Display net worth sparkline using helper function
    nw_chart = create_sparkline_chart(
        df=df_net_worth,
        value_column='NetWorth',
        date_column='Date',
        color=COLOR_NET_WORTH,
        height=CHART_HEIGHT_NET_WORTH_SPARKLINE,
        current_value=total_net_worth,
        use_min_scale=True
    )
    st.altair_chart(nw_chart, width='stretch')
    
    st.divider()
    
    # Display each group with its accounts
    cols = st.columns(3)
    
    for idx, group in enumerate(sorted(groups)):
        with cols[idx % 3]:
            accounts_df = group_accounts[group]
            group_total = group_balances[group]
            
            # Show group total as a metric
            st.metric(
                label=group,
                value=f"${group_total:,.2f}"
            )
            
            # Get 12-month balance history for sparkline (cached)
            end_date = pd.Timestamp.now(tz='UTC')
            start_date = end_date - timedelta(days=SPARKLINE_HISTORY_DAYS)
            
            df_sparkline = calculate_group_sparkline(
                balance_history_spreadsheet.scrubbed_df,
                group,
                start_date,
                end_date
            )
            
            # Determine color based on account class (red for liabilities, green for assets)
            is_liability = group_classes.get(group) == "Liability"
            sparkline_color = COLOR_LIABILITY if is_liability else COLOR_ASSET
            
            # Create sparkline chart using helper function
            chart = create_sparkline_chart(
                df=df_sparkline,
                value_column='Balance',
                date_column='Date',
                color=sparkline_color,
                height=CHART_HEIGHT_SPARKLINE,
                current_value=group_total,
                use_min_scale=False
            )
            st.altair_chart(chart, width='stretch')
            
            # Show individual accounts in an expander
            with st.expander(f"View {group} Accounts"):
                if not accounts_df.empty:
                    st.dataframe(
                        accounts_df,
                        width='stretch',
                        hide_index=True,
                        column_config={
                            "Balance": st.column_config.NumberColumn(
                                "Balance",
                                format="$%.2f"
                            )
                        }
                    )
                else:
                    st.info("No accounts in this group")

def main() -> None:
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_page(transactions_spreadsheet, balance_history_spreadsheet)

if __name__ == "__main__":
    main()