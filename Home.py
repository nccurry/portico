import streamlit as st
import pandas as pd

from src.sidebar import configure_sidebar
from src.spreadsheet import TransactionsSpreadsheet, BalanceHistorySpreadsheet


def configure_page(
        transaction_spreadsheet: TransactionsSpreadsheet,
        balance_history_spreadsheet: BalanceHistorySpreadsheet
) -> None:
    st.header("Account Balances")
    
    # Get all account groups (filter out NaN/None values and convert to strings)
    groups = balance_history_spreadsheet.get_groups()
    groups = [str(g) for g in groups if pd.notna(g) and g != '']
    
    # Calculate total net worth across all groups
    total_net_worth = 0.0
    group_balances = {}
    
    for group in groups:
        _, total = balance_history_spreadsheet.get_latest_balance_by_group(group)
        group_balances[group] = total
        total_net_worth += total
    
    # Display total net worth prominently
    st.metric(
        label="Total Net Worth",
        value=f"${total_net_worth:,.2f}"
    )
    
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

    transactions_spreadsheet = TransactionsSpreadsheet()
    balance_history_spreadsheet = BalanceHistorySpreadsheet()

    configure_sidebar(transactions_spreadsheet, balance_history_spreadsheet)
    configure_page(transactions_spreadsheet, balance_history_spreadsheet)

if __name__ == "__main__":
    main()