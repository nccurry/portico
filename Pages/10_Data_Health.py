"""Data Health page: surface sheet mapping and data-quality issues."""

import pandas as pd
import streamlit as st

from src.analysis.data_health import DataHealthReport, build_data_health_report
from src.custom_types import ColumnConfig
from src.page_helpers import get_transaction_column_config, render_data_refresh_controls
from src.spreadsheet import (
    BalanceHistorySpreadsheet,
    CategoriesSpreadsheet,
    TransactionsSpreadsheet,
    load_balance_history_data,
    load_categories_data,
    load_transactions_data,
)


def _display_issue_table(
    title: str,
    df: pd.DataFrame,
    *,
    height: int = 350,
    column_config: ColumnConfig | None = None,
) -> None:
    """Display one data-health issue table."""
    with st.expander(f"{title} ({len(df)})", expanded=not df.empty):
        if df.empty:
            st.success("No issues found")
            return

        st.dataframe(
            df,
            width="stretch",
            height=height,
            hide_index=True,
            column_config=column_config,
        )


def _render_summary(report: DataHealthReport) -> None:
    """Display top-level data-health counts."""
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Uncategorized", len(report["uncategorized_transactions"]))
    with col2:
        st.metric("Sign Issues", len(report["sign_anomalies"]))
    with col3:
        st.metric("Unmapped Accounts", len(report["missing_account_mappings"]))
    with col4:
        st.metric("Stale Accounts", len(report["stale_accounts"]))
    with col5:
        st.metric("Unbudgeted Categories", len(report["categories_without_budget"]))


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet,
    categories_spreadsheet: CategoriesSpreadsheet,
) -> None:
    """Render data-quality findings for imported Tiller sheets."""
    st.header("Data Health")
    st.caption("Find mapping gaps and suspicious rows before they distort reports.")

    stale_days = st.slider(
        "Stale account threshold",
        min_value=1,
        max_value=60,
        value=7,
        step=1,
        help="Flag accounts whose latest balance row is older than this many days",
    )

    report = build_data_health_report(
        transactions_spreadsheet.scrubbed_df,
        balance_history_spreadsheet.scrubbed_df,
        categories_spreadsheet.budget_df,
        stale_days=stale_days,
    )

    _render_summary(report)
    st.divider()

    _display_issue_table(
        "Uncategorized or Missing Transaction Metadata",
        report["uncategorized_transactions"].sort_values("Date", ascending=False),
        column_config=get_transaction_column_config(),
    )
    _display_issue_table(
        "Income/Expense Sign Anomalies",
        report["sign_anomalies"].sort_values("Date", ascending=False),
        column_config=get_transaction_column_config(),
    )
    _display_issue_table(
        "Balance Accounts Missing Group Mapping",
        report["missing_account_mappings"].sort_values("Account"),
        column_config={
            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "Balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
        },
    )
    _display_issue_table(
        "Stale Balance Accounts",
        report["stale_accounts"].sort_values("Days_Stale", ascending=False),
        column_config={
            "Date": st.column_config.DateColumn("Latest Date", format="YYYY-MM-DD"),
            "Balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
            "Days_Stale": st.column_config.NumberColumn("Days Stale"),
        },
    )
    _display_issue_table(
        "Expense Categories With Spending But No Budget",
        report["categories_without_budget"],
        column_config={
            "Spent": st.column_config.NumberColumn("Spent", format="$%.2f"),
        },
    )


def main() -> None:
    """Streamlit entry point for the Data Health page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()
    categories_spreadsheet = load_categories_data()

    configure_page(transactions_spreadsheet, balance_history_spreadsheet, categories_spreadsheet)


if __name__ == "__main__":
    main()
