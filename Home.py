import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, timezone

from src.sidebar import configure_sidebar
from src.spreadsheet import load_transactions_data, load_balance_history_data, TransactionsSpreadsheet, BalanceHistorySpreadsheet


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
    
    for group in groups:
        accounts_df, total = balance_history_spreadsheet.get_latest_balance_by_group(group)
        
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
    
    # Calculate net worth sparkline (last 12 months)
    end_date = pd.Timestamp.now(tz='UTC')
    start_date = end_date - timedelta(days=365)
    
    # Get all snapshot dates across all accounts
    df_all = balance_history_spreadsheet.scrubbed_df.copy()
    all_snapshot_dates = df_all[df_all["Date"].between(start_date, end_date)]["Date"].unique()
    all_snapshot_dates = sorted(all_snapshot_dates)
    
    # Calculate net worth for each snapshot date
    net_worth_by_date = []
    for date in all_snapshot_dates:
        net_worth_at_date = 0
        
        for group in groups:
            # Get accounts for this group
            group_data = df_all[df_all["Group"] == group]
            account_ids = group_data["Account ID"].unique()
            
            # Sum balances for all accounts in this group at this date
            group_total = 0
            for account_id in account_ids:
                account_data = group_data[
                    (group_data["Account ID"] == account_id) & 
                    (group_data["Date"] <= date)
                ].sort_values("Date")
                
                if not account_data.empty:
                    group_total += account_data.iloc[-1]["Balance"]
            
            # Add or subtract based on class
            if group_classes.get(group) == "Liability":
                net_worth_at_date -= group_total
            else:
                net_worth_at_date += group_total
        
        net_worth_by_date.append({"Date": date, "NetWorth": net_worth_at_date})
    
    df_net_worth = pd.DataFrame(net_worth_by_date)
    
    # Display net worth sparkline
    if not df_net_worth.empty and len(df_net_worth) > 1:
        nw_chart = alt.Chart(df_net_worth).mark_line(
            color='gold',
            strokeWidth=3,
            interpolate='monotone'
        ).encode(
            x=alt.X('Date:T', axis=None),
            y=alt.Y('NetWorth:Q', axis=None, scale=alt.Scale(domainMin=1500000))
        ).properties(
            height=60
        ).configure_view(
            strokeWidth=0
        )
        st.altair_chart(nw_chart, width='stretch')
    else:
        # Flat line at current net worth
        flat_line_data = pd.DataFrame([
            {'x': 0, 'y': total_net_worth},
            {'x': 1, 'y': total_net_worth}
        ])
        nw_chart = alt.Chart(flat_line_data).mark_line(
            color='lightgray',
            strokeWidth=3,
            strokeDash=[5, 5]
        ).encode(
            x=alt.X('x:Q', axis=None),
            y=alt.Y('y:Q', axis=None, scale=alt.Scale(zero=False))
        ).properties(
            height=60
        ).configure_view(
            strokeWidth=0
        )
        st.altair_chart(nw_chart, width='stretch')
    
    st.divider()
    
    # Display each group with its accounts
    cols = st.columns(3)
    
    for idx, group in enumerate(sorted(groups)):
        with cols[idx % 3]:
            accounts_df, group_total = balance_history_spreadsheet.get_latest_balance_by_group(group)
            
            # Show group total as a metric
            st.metric(
                label=group,
                value=f"${group_total:,.2f}"
            )
            
            # Get 12-month balance history for sparkline
            end_date = pd.Timestamp.now(tz='UTC')
            start_date = end_date - timedelta(days=365)
            
            # Get all accounts in this group
            df_raw = balance_history_spreadsheet.scrubbed_df.copy()
            df_raw = df_raw[df_raw["Group"] == group]
            account_ids = df_raw["Account ID"].unique()
            
            # Get unique snapshot dates across all accounts in the group
            snapshot_dates = df_raw[df_raw["Date"].between(start_date, end_date)]["Date"].unique()
            snapshot_dates = sorted(snapshot_dates)
            
            # For each snapshot date, calculate total balance for the group
            balances_by_date = []
            for date in snapshot_dates:
                # For each account, get the latest balance up to this date
                total = 0
                for account_id in account_ids:
                    account_data = df_raw[
                        (df_raw["Account ID"] == account_id) & 
                        (df_raw["Date"] <= date)
                    ].sort_values("Date")
                    
                    if not account_data.empty:
                        total += account_data.iloc[-1]["Balance"]
                
                balances_by_date.append({"Date": date, "Balance": total})
            
            df_sparkline = pd.DataFrame(balances_by_date)
            
            # Determine color based on account class (red for liabilities, green for assets)
            is_liability = group_classes.get(group) == "Liability"
            sparkline_color = 'lightcoral' if is_liability else 'lightgreen'
            
            # Create sparkline chart
            if not df_sparkline.empty and len(df_sparkline) > 1:
                # Have historical data - show trend line
                chart = alt.Chart(df_sparkline).mark_line(
                    color=sparkline_color,
                    strokeWidth=2,
                    interpolate='monotone'
                ).encode(
                    x=alt.X('Date:T', axis=None),
                    y=alt.Y('Balance:Q', axis=None, scale=alt.Scale(zero=False))
                ).properties(
                    height=50
                ).configure_view(
                    strokeWidth=0
                )
                st.altair_chart(chart, width='stretch')
            else:
                # Not enough history - show flat line at current balance
                flat_line_data = pd.DataFrame([
                    {'x': 0, 'y': group_total},
                    {'x': 1, 'y': group_total}
                ])
                chart = alt.Chart(flat_line_data).mark_line(
                    color='lightgray',
                    strokeWidth=2,
                    strokeDash=[5, 5]  # Dashed line to indicate it's not real data
                ).encode(
                    x=alt.X('x:Q', axis=None),
                    y=alt.Y('y:Q', axis=None, scale=alt.Scale(zero=False))
                ).properties(
                    height=50
                ).configure_view(
                    strokeWidth=0
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

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)

if __name__ == "__main__":
    main()