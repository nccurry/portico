"""Data Health page: surface sheet mapping and data-quality issues."""

import pandas as pd
import streamlit as st

from src.analysis.data_health import DataHealthReport, build_data_health_report
from src.analysis.duplicates import (
    find_duplicates_efficient,
    summarize_duplicates,
    summarize_duplicates_by_month,
)
from src.constants import DEFAULT_DUPLICATE_DAYS_THRESHOLD, MIN_DUPLICATE_AMOUNT
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


def _render_summary(report: DataHealthReport, duplicate_count: int) -> None:
    """Display top-level data-health counts."""
    with st.container(horizontal=True):
        st.metric("Uncategorized", len(report["uncategorized_transactions"]), border=True)
        st.metric("Sign Issues", len(report["sign_anomalies"]), border=True)
        st.metric("Potential Duplicates", duplicate_count, border=True)
        st.metric("Unmapped Accounts", len(report["missing_account_mappings"]), border=True)
        st.metric("Stale Accounts", len(report["stale_accounts"]), border=True)
        st.metric("Unbudgeted Categories", len(report["categories_without_budget"]), border=True)


def _display_duplicate_results(duplicates: pd.DataFrame) -> None:
    """Display potential duplicate pairs and their monthly summary."""
    summary = summarize_duplicates(duplicates)
    with st.expander(
        f"Potential Duplicate Transaction Pairs ({summary['pair_count']})",
        expanded=bool(summary["pair_count"]),
    ):
        if not summary["pair_count"]:
            st.success("No potential duplicates found with current settings.")
            st.info("Try adjusting the detection settings if you think there might be duplicates.")
            return

        st.caption(
            f"Flagged amount: ${summary['total_amount']:,.2f} | "
            f"Affected months: {summary['affected_months']}"
        )
        st.dataframe(
            duplicates.sort_values("Date1", ascending=False),
            width="stretch",
            height=600,
            hide_index=True,
            column_config={
                "Date1": st.column_config.DateColumn("Date 1", format="YYYY-MM-DD"),
                "Date2": st.column_config.DateColumn("Date 2", format="YYYY-MM-DD"),
                "Days_Apart": st.column_config.NumberColumn("Days Apart"),
                "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "Category": st.column_config.TextColumn("Category"),
                "Month": st.column_config.TextColumn("Month"),
                "Account1": st.column_config.TextColumn("Account 1"),
                "Account2": st.column_config.TextColumn("Account 2"),
                "Description1": st.column_config.TextColumn("Description 1"),
                "Description2": st.column_config.TextColumn("Description 2"),
            },
        )

        st.markdown("**Duplicates by month**")
        st.dataframe(
            summarize_duplicates_by_month(duplicates),
            width="stretch",
            hide_index=True,
            column_config={
                "Month": st.column_config.TextColumn("Month"),
                "Count": st.column_config.NumberColumn("Duplicate Pairs"),
                "Total_Amount": st.column_config.NumberColumn("Total Amount", format="$%.2f"),
            },
        )


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet,
    categories_spreadsheet: CategoriesSpreadsheet,
) -> None:
    """Render data-quality findings for imported Tiller sheets."""
    st.header("Data Health")
    st.caption("Find mapping gaps and suspicious rows before they distort reports.")

    with st.expander("Health check settings", expanded=False):
        stale_days = st.slider(
            "Stale account threshold",
            min_value=1,
            max_value=60,
            value=7,
            step=1,
            help="Flag accounts whose latest balance row is older than this many days",
        )

        st.markdown("**Duplicate detection**")
        col1, col2 = st.columns(2)
        with col1:
            days_threshold = st.number_input(
                "Days Apart (Max)",
                min_value=0,
                max_value=7,
                value=DEFAULT_DUPLICATE_DAYS_THRESHOLD,
                help="Consider transactions duplicates if within this many days",
            )
            min_amount = st.number_input(
                "Minimum Amount ($)",
                min_value=0.0,
                max_value=1000.0,
                value=MIN_DUPLICATE_AMOUNT,
                step=10.0,
                help="Only check for duplicates above this amount",
            )
        with col2:
            check_same_account = st.checkbox(
                "Require Same Account",
                value=True,
                help="Only flag as duplicate if on the same account",
            )
            check_same_category = st.checkbox(
                "Require Same Category",
                value=False,
                help="Only flag as duplicate if same category",
            )
            require_same_description = st.checkbox(
                "Require Same Description",
                value=True,
                help="Only flag as duplicate if descriptions match",
            )

    transactions_df = transactions_spreadsheet.scrubbed_df

    report = build_data_health_report(
        transactions_df,
        balance_history_spreadsheet.scrubbed_df,
        categories_spreadsheet.budget_df,
        stale_days=stale_days,
    )
    duplicates = find_duplicates_efficient(
        transactions_df,
        days_threshold=days_threshold,
        min_amount=min_amount,
        check_same_account=check_same_account,
        check_same_category=check_same_category,
        require_same_description=require_same_description,
    )

    _render_summary(report, len(duplicates))
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
    _display_duplicate_results(duplicates)
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
