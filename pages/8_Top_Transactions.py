"""Filter, summarize, and inspect individual transactions."""

from typing import cast

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis.top_transactions import (
    BREAKDOWN_DIMENSIONS,
    FOCUS_OPTIONS,
    build_transaction_breakdown,
    build_transaction_inventory,
    filter_transaction_focus,
    summarize_transaction_inventory,
)
from src.constants import (
    COLOR_EXPENSE,
    COLOR_INCOME,
    COLOR_NET_WORTH,
    COLOR_PLACEHOLDER,
    TRANSACTION_TABLE_HEIGHT,
)
from src.page_helpers import configured_merchant_aliases, render_data_refresh_controls
from src.reporting_periods import latest_data_timestamp, reporting_anchor
from src.spreadsheet import TransactionsSpreadsheet, load_transactions_data
from src.value_visibility import mask_value, value_safe_altair_chart, value_safe_dataframe


LOOKBACK_DAYS = {"3M": 90, "6M": 180, "1Y": 365, "2Y": 730, "All": None}
TYPE_VIEWS = {
    "All": (),
    "Expenses": ("Expense",),
    "Income": ("Income",),
    "Transfers": ("Transfer",),
}


def _format_currency(value: float, *, signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _create_transaction_chart(transactions: pd.DataFrame) -> alt.LayerChart:
    zero = (
        alt.Chart(pd.DataFrame({"Amount": [0.0]})).mark_rule(color=COLOR_PLACEHOLDER, opacity=0.55).encode(y="Amount:Q")
    )
    points = (
        alt.Chart(transactions)
        .mark_circle(size=72, opacity=0.72)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %Y")),
            y=alt.Y("Amount:Q", title="Amount", axis=alt.Axis(format="$,.2s")),
            color=alt.Color(
                "Type:N",
                title=None,
                scale=alt.Scale(
                    domain=["Income", "Expense", "Transfer"],
                    range=[COLOR_INCOME, COLOR_EXPENSE, COLOR_PLACEHOLDER],
                ),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("Full Description:N", title="Description"),
                alt.Tooltip("Merchant:N", title="Merchant"),
                alt.Tooltip("Type:N", title="Type"),
                alt.Tooltip("Category:N", title="Category"),
                alt.Tooltip("Amount:Q", title="Amount", format="$,.2f"),
            ],
        )
    )
    return cast(
        alt.LayerChart,
        alt.layer(zero, points).properties(height=300),
    )


def _create_breakdown_chart(breakdown: pd.DataFrame) -> alt.Chart:
    return cast(
        alt.Chart,
        (
            alt.Chart(breakdown.head(12))
            .mark_bar(color=COLOR_NET_WORTH)
            .encode(
                x=alt.X(
                    "Magnitude:Q",
                    title=None,
                    axis=alt.Axis(format="$,.2s"),
                ),
                y=alt.Y("Entity:N", title=None, sort="-x"),
                tooltip=[
                    alt.Tooltip("Entity:N", title="Name"),
                    alt.Tooltip("Transactions:Q", title="Transactions"),
                    alt.Tooltip("Magnitude:Q", title="Total magnitude", format="$,.2f"),
                    alt.Tooltip("Outflow:Q", title="Money out", format="$,.2f"),
                    alt.Tooltip("Inflow:Q", title="Money in", format="$,.2f"),
                    alt.Tooltip("Share:Q", title="Share (%)", format=".1f"),
                ],
            )
            .properties(height=300)
        ),
    )


def _transaction_flags(transactions: pd.DataFrame) -> list[str]:
    flags = []
    for row in transactions.itertuples():
        row_flags = []
        if row.Is_One_Off:
            row_flags.append("One-off")
        if row.Is_Unusual:
            row_flags.append("Unusual amount")
        if row.Is_Reversal:
            row_flags.append("Refund / reversal")
        flags.append(", ".join(row_flags))
    return flags


def _render_transaction_table(transactions: pd.DataFrame) -> None:
    display = transactions.copy()
    display["Flags"] = _transaction_flags(display)
    display = display[
        [
            "Date",
            "Full Description",
            "Merchant",
            "Type",
            "Group",
            "Category",
            "Account",
            "Institution",
            "Amount",
            "Occurrences",
            "Flags",
        ]
    ].rename(columns={"Full Description": "Description"})

    with st.container(border=True):
        with st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
        ):
            st.subheader("Matching transactions")
            st.download_button(
                "Download CSV",
                display.to_csv(index=False).encode("utf-8"),
                file_name="filtered-transactions.csv",
                mime="text/csv",
                icon=":material/download:",
                on_click="ignore",
            )
        value_safe_dataframe(
            display,
            height=TRANSACTION_TABLE_HEIGHT,
            hide_index=True,
            width="stretch",
            column_order=[
                "Date",
                "Description",
                "Amount",
                "Type",
                "Group",
                "Category",
                "Merchant",
                "Account",
                "Institution",
                "Occurrences",
                "Flags",
            ],
            column_config={
                "Date": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
                "Description": st.column_config.TextColumn(
                    "Description",
                    pinned=True,
                    width="large",
                ),
                "Amount": st.column_config.NumberColumn("Amount", format="$%+,.2f"),
                "Occurrences": st.column_config.NumberColumn(
                    "Merchant occurrences",
                    format="%d",
                ),
            },
        )


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    """Render the transaction filtering and inspection workbench."""
    st.header("Transactions")
    transactions = transactions_spreadsheet.scrubbed_df.copy()
    if transactions.empty:
        st.info("No transactions are available.", icon=":material/receipt_long:")
        return

    latest = latest_data_timestamp(transactions)
    if latest is not None:
        st.caption(f"Latest transaction {latest.strftime('%b %d, %Y')}")

    control_columns = st.columns([2, 2, 3], vertical_alignment="bottom")
    with control_columns[0]:
        lookback = st.segmented_control(
            "Time frame",
            list(LOOKBACK_DAYS),
            default="1Y",
            key="top_transactions_lookback",
            persist_state="page",
            width="stretch",
        )
    with control_columns[1]:
        type_view = st.segmented_control(
            "Type",
            list(TYPE_VIEWS),
            default="All",
            key="top_transactions_type",
            persist_state="page",
            width="stretch",
        )
    with control_columns[2]:
        focus = st.segmented_control(
            "Focus",
            list(FOCUS_OPTIONS),
            default="All transactions",
            key="top_transactions_focus",
            persist_state="page",
            width="stretch",
        )

    all_groups = sorted(transactions["Group"].dropna().astype(str).unique())
    all_categories = sorted(transactions["Category"].dropna().astype(str).unique())
    all_accounts = sorted(transactions["Account"].dropna().astype(str).unique())
    filter_columns = st.columns([5, 1], vertical_alignment="bottom")
    with filter_columns[0]:
        search = st.text_input(
            "Search transactions",
            placeholder="Description, merchant, category, group, account, institution",
            key="top_transactions_search",
            persist_state="page",
        )
    with filter_columns[1]:
        with st.popover(
            "More filters",
            icon=":material/tune:",
            width="stretch",
        ):
            groups = st.multiselect(
                "Groups",
                all_groups,
                placeholder="All groups",
                key="top_transactions_groups",
                persist_state="page",
            )
            categories = st.multiselect(
                "Categories",
                all_categories,
                placeholder="All categories",
                key="top_transactions_categories",
                persist_state="page",
            )
            accounts = st.multiselect(
                "Accounts",
                all_accounts,
                placeholder="All accounts",
                key="top_transactions_accounts",
                persist_state="page",
            )
            minimum_magnitude = float(
                st.number_input(
                    "Minimum amount",
                    min_value=0.0,
                    value=0.0,
                    step=50.0,
                    key="top_transactions_minimum",
                    persist_state="page",
                )
            )
            maximum_input = st.number_input(
                "Maximum amount",
                min_value=0.0,
                value=None,
                step=1_000.0,
                placeholder="No maximum",
                key="top_transactions_maximum",
                persist_state="page",
            )
            largest_count = int(
                st.number_input(
                    "Largest result count",
                    min_value=5,
                    max_value=500,
                    value=25,
                    step=5,
                    key="top_transactions_largest_count",
                    persist_state="page",
                )
            )
    maximum_magnitude = float(maximum_input) if maximum_input is not None else None

    selected_lookback = str(lookback) if lookback in LOOKBACK_DAYS else "1Y"
    selected_type = str(type_view) if type_view in TYPE_VIEWS else "All"
    selected_focus = str(focus) if focus in FOCUS_OPTIONS else "All transactions"
    end_date = reporting_anchor(transactions, anchor_to_data=True)
    lookback_days = LOOKBACK_DAYS[selected_lookback]
    start_date = (
        pd.Timestamp(transactions["Date"].min())
        if lookback_days is None
        else end_date - pd.Timedelta(days=lookback_days)
    )
    try:
        aliases = configured_merchant_aliases()
    except ValueError as error:
        st.error(str(error), icon=":material/error:")
        return

    inventory = build_transaction_inventory(
        transactions,
        start_date,
        end_date,
        transaction_types=TYPE_VIEWS[selected_type],
        groups=groups,
        categories=categories,
        accounts=accounts,
        search=str(search),
        minimum_magnitude=minimum_magnitude,
        maximum_magnitude=maximum_magnitude,
        aliases=aliases,
    )
    results = filter_transaction_focus(
        inventory,
        selected_focus,
        largest_count=largest_count,
    )
    if results.empty:
        st.info(
            "No transactions match this view.",
            icon=":material/search_off:",
        )
        return

    summary = summarize_transaction_inventory(results)
    with st.container(horizontal=True):
        st.metric(
            "Transactions",
            mask_value(f"{summary['transaction_count']:,}"),
            border=True,
            width="stretch",
        )
        st.metric(
            "Money out",
            _format_currency(summary["outflow"]),
            border=True,
            width="stretch",
        )
        st.metric(
            "Money in",
            _format_currency(summary["inflow"]),
            border=True,
            width="stretch",
        )
        st.metric(
            "Net amount",
            _format_currency(summary["net_amount"], signed=True),
            border=True,
            width="stretch",
        )

    chart_column, breakdown_column = st.columns(
        [2, 1],
        gap="large",
        vertical_alignment="top",
    )
    with chart_column:
        with st.container(border=True):
            with st.container(
                horizontal=True,
                horizontal_alignment="distribute",
                vertical_alignment="center",
            ):
                st.subheader("Transactions over time")
                st.badge(
                    f"Median {_format_currency(summary['median_magnitude'])}",
                    color="gray",
                )
            value_safe_altair_chart(_create_transaction_chart(results), width="stretch")
    with breakdown_column:
        with st.container(border=True):
            dimension = st.segmented_control(
                "Summarize by",
                list(BREAKDOWN_DIMENSIONS),
                default="Group",
                key="top_transactions_breakdown",
                persist_state="page",
                width="stretch",
            )
            selected_dimension = str(dimension) if dimension in BREAKDOWN_DIMENSIONS else "Group"
            breakdown = build_transaction_breakdown(results, selected_dimension)
            value_safe_altair_chart(_create_breakdown_chart(breakdown), width="stretch")

    _render_transaction_table(results)


def main() -> None:
    """Streamlit entry point for the Transactions page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    configure_page(load_transactions_data())


if __name__ == "__main__":
    main()
