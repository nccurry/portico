"""Explore merchant spending, trends, composition, and transactions."""

from collections.abc import Sequence
from typing import cast
from zlib import crc32

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.elements.arrow import DataframeState

from src.analysis.merchants import (
    build_merchant_description_breakdown,
    build_merchant_dimension_breakdown,
    build_merchant_monthly_comparison,
    build_merchant_overview,
    enrich_with_merchant,
    summarize_merchant_period,
)
from src.analysis.spending import build_spending_ledger
from src.config import get_settings
from src.constants import COLOR_NET_WORTH, COLOR_PLACEHOLDER
from src.custom_types import ColumnConfig
from src.filters import render_spending_filters
from src.page_helpers import configured_merchant_aliases, render_data_refresh_controls, render_time_frame_control
from src.reporting_periods import latest_data_timestamp, month_lookback_options, rolling_month_window
from src.spreadsheet import TransactionsSpreadsheet, load_transactions_data
from src.value_visibility import mask_value, value_safe_altair_chart, value_safe_dataframe

COMPARISON_VIEWS = ["Previous period", "Last year"]
SELECTED_MERCHANT_KEY = "merchant_selected_name"
DETAIL_MONTH_KEY = "merchant_detail_month"


def _format_currency(value: float) -> str:
    sign = "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _format_signed_currency(value: float) -> str:
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _format_percent(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    sign = "+" if value > 0 else ""
    return mask_value(f"{sign}{value:.1f}%")


def _month_label(month: str) -> str:
    return pd.Period(month, freq="M").strftime("%B %Y")


def _month_sequence(start_month: str, end_month: str) -> list[str]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    if end <= start:
        return []
    return [str(month) for month in pd.period_range(start, end - 1, freq="M")]


def _analysis_periods(
    *,
    transactions: pd.DataFrame,
    lookback_months: int,
    comparison: str,
) -> tuple[list[str], list[str], str, str, str, str]:
    current_start, current_last = rolling_month_window(lookback_months, transactions)
    current_end = str(pd.Period(current_last, freq="M") + 1)
    current_months = _month_sequence(current_start, current_end)
    if comparison == "Previous period":
        comparison_end = current_start
        comparison_start = str(pd.Period(current_start, freq="M") - lookback_months)
    else:
        comparison_start = str(pd.Period(current_start, freq="M") - 12)
        comparison_end = str(pd.Period(current_end, freq="M") - 12)
    comparison_months = _month_sequence(comparison_start, comparison_end)
    return (
        current_months,
        comparison_months,
        current_start,
        current_end,
        comparison_start,
        comparison_end,
    )


def _comparison_label(comparison: str, lookback_months: int) -> str:
    if comparison == "Previous period":
        return f"previous {lookback_months} months"
    return "same months last year"


def _overview_column_config(comparison_label: str) -> ColumnConfig:
    return {
        "Merchant": st.column_config.TextColumn("Merchant", pinned=True),
        "Spending": st.column_config.NumberColumn("Spending", format="$%.0f"),
        "Share": st.column_config.NumberColumn("Share", format="%.1f%%"),
        "Average_Monthly": st.column_config.NumberColumn("Avg/month", format="$%.0f"),
        "Change": st.column_config.NumberColumn(f"Change vs {comparison_label}", format="$%+.0f"),
        "Change_Pct": st.column_config.NumberColumn("Change %", format="%+.1f%%"),
        "Transactions": st.column_config.NumberColumn("Transactions", format="%d"),
        "Average_Transaction": st.column_config.NumberColumn("Avg purchase", format="$%.0f"),
        "Primary_Category": st.column_config.TextColumn("Main category"),
        "Monthly_Trend": st.column_config.LineChartColumn(
            "Monthly trend",
            color=COLOR_NET_WORTH,
            y_min=0,
        ),
    }


def _render_summary_metrics(overview: pd.DataFrame, *, num_months: int) -> None:
    summary = summarize_merchant_period(overview, num_months=num_months)
    with st.container(horizontal=True):
        st.metric(
            "Total spending",
            _format_currency(summary["total_spending"]),
            border=True,
        )
        st.metric(
            "Average monthly",
            _format_currency(summary["average_monthly_spending"]),
            border=True,
        )
        st.metric("Merchants", mask_value(f"{summary['merchant_count']:,}"), border=True)
        st.metric(
            "At repeat merchants",
            mask_value(f"{summary['repeat_spending_share']:.1f}%"),
            border=True,
        )


def _render_overview_table(
    overview: pd.DataFrame,
    *,
    comparison_label: str,
    state_key: str,
) -> str:
    remembered = st.session_state.get(SELECTED_MERCHANT_KEY)
    default_position = 0
    if remembered in overview["Merchant"].values:
        default_position = int(overview.index[overview["Merchant"] == remembered].tolist()[0])
    selection_default = cast(
        DataframeState,
        {"selection": {"rows": [default_position]}},
    )
    display_columns = [
        "Merchant",
        "Spending",
        "Share",
        "Average_Monthly",
        "Change",
        "Change_Pct",
        "Transactions",
        "Average_Transaction",
        "Primary_Category",
        "Monthly_Trend",
    ]
    event = value_safe_dataframe(
        overview[display_columns],
        key=state_key,
        width="stretch",
        height=min(620, 38 * (len(overview) + 1) + 8),
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row-required",
        selection_default=selection_default,
        column_config=_overview_column_config(comparison_label),
    )
    rows = event["selection"]["rows"]
    position = rows[0] if rows else 0
    if position >= len(overview):
        position = 0
    selected = str(overview.iloc[position]["Merchant"])
    st.session_state[SELECTED_MERCHANT_KEY] = selected
    return selected


def _ranking_chart(overview: pd.DataFrame, selected_merchant: str) -> alt.Chart:
    ranked = overview.head(12).copy()
    if selected_merchant not in ranked["Merchant"].values:
        ranked = pd.concat(
            [
                ranked,
                overview[overview["Merchant"] == selected_merchant],
            ],
            ignore_index=True,
        )
    ranked["Selected"] = ranked["Merchant"].eq(selected_merchant)
    return cast(
        alt.Chart,
        alt.Chart(ranked)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "Spending:Q",
                title="Spending ($)",
                axis=alt.Axis(format="$~s"),
            ),
            y=alt.Y(
                "Merchant:N",
                title=None,
                sort="-x",
                axis=alt.Axis(labelLimit=190),
            ),
            color=alt.condition(
                "datum.Selected",
                alt.value(COLOR_NET_WORTH),
                alt.value(COLOR_PLACEHOLDER),
            ),
            tooltip=[
                alt.Tooltip("Merchant:N", title="Merchant"),
                alt.Tooltip("Spending:Q", title="Spending", format="$,.2f"),
                alt.Tooltip("Share:Q", title="Share", format=".1f"),
                alt.Tooltip("Transactions:Q", title="Transactions"),
                alt.Tooltip(
                    "Average_Transaction:Q",
                    title="Average purchase",
                    format="$,.2f",
                ),
            ],
        )
        .properties(height=max(320, 29 * len(ranked))),
    )


def _merchant_history_chart(
    history: pd.DataFrame,
    *,
    comparison_label: str,
) -> alt.LayerChart:
    x = alt.X(
        "Month_Label:N",
        title=None,
        sort=alt.SortField("Month_Index", order="ascending"),
        axis=alt.Axis(labelAngle=-35),
    )
    current = (
        alt.Chart(history)
        .mark_bar(color=COLOR_NET_WORTH, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=x,
            y=alt.Y(
                "Current_Spending:Q",
                title="Monthly spending ($)",
                axis=alt.Axis(format="$~s"),
                scale=alt.Scale(zero=True),
            ),
            tooltip=[
                alt.Tooltip("Current_Month:N", title="Month"),
                alt.Tooltip("Current_Spending:Q", title="Spending", format="$,.2f"),
                alt.Tooltip("Current_Transactions:Q", title="Transactions"),
            ],
        )
    )
    comparison = (
        alt.Chart(history)
        .mark_line(color=COLOR_PLACEHOLDER, point=True, strokeWidth=2)
        .encode(
            x=x,
            y=alt.Y("Comparison_Spending:Q", title="Monthly spending ($)"),
            tooltip=[
                alt.Tooltip("Comparison_Month:N", title=comparison_label.title()),
                alt.Tooltip("Comparison_Spending:Q", title="Spending", format="$,.2f"),
                alt.Tooltip("Comparison_Transactions:Q", title="Transactions"),
            ],
        )
    )
    return cast(
        alt.LayerChart,
        alt.layer(current, comparison).resolve_scale(y="shared").properties(height=380),
    )


def _breakdown_column_config(label: str) -> ColumnConfig:
    return {
        "Entity": st.column_config.TextColumn(label, pinned=True),
        "Spending": st.column_config.NumberColumn("Spending", format="$%.2f"),
        "Share": st.column_config.NumberColumn("Share", format="%.1f%%"),
        "Transactions": st.column_config.NumberColumn("Transactions", format="%d"),
    }


def _render_merchant_detail(
    current_ledger: pd.DataFrame,
    comparison_ledger: pd.DataFrame,
    overview: pd.DataFrame,
    *,
    merchant: str,
    current_months: Sequence[str],
    comparison_months: Sequence[str],
    comparison_label: str,
) -> None:
    row = overview[overview["Merchant"] == merchant].iloc[0]
    st.subheader(merchant)
    with st.container(horizontal=True):
        st.metric("Spending", _format_currency(float(row["Spending"])), border=True)
        st.metric(
            f"Change vs {comparison_label}",
            _format_signed_currency(float(row["Change"])),
            _format_percent(None if pd.isna(row["Change_Pct"]) else float(row["Change_Pct"])),
            delta_color="inverse",
            border=True,
        )
        st.metric("Transactions", mask_value(f"{int(row['Transactions']):,}"), border=True)
        st.metric(
            "Average purchase",
            _format_currency(float(row["Average_Transaction"])),
            border=True,
        )

    history = build_merchant_monthly_comparison(
        current_ledger,
        comparison_ledger,
        merchant=merchant,
        current_months=current_months,
        comparison_months=comparison_months,
    )
    with st.container(border=True):
        st.markdown(f"**Monthly spending · gray is {comparison_label}**")
        value_safe_altair_chart(
            _merchant_history_chart(history, comparison_label=comparison_label),
            width="stretch",
        )

    month_options = ["All months", *reversed(current_months)]
    if st.session_state.get(DETAIL_MONTH_KEY) not in month_options:
        st.session_state[DETAIL_MONTH_KEY] = "All months"
    selected_month = st.selectbox(
        "Detail month",
        month_options,
        format_func=lambda value: value if value == "All months" else _month_label(str(value)),
        key=DETAIL_MONTH_KEY,
        persist_state="page",
    )
    scoped = current_ledger[current_ledger["Included"] & current_ledger["Merchant"].astype(str).eq(merchant)].copy()
    if selected_month != "All months":
        scoped = scoped[scoped["Month"].astype(str).eq(str(selected_month))]

    breakdown_tab, descriptions_tab, transactions_tab = st.tabs(["Breakdown", "Descriptions", "Transactions"])
    with breakdown_tab:
        category_column, account_column = st.columns(2)
        with category_column:
            st.markdown("**Categories**")
            categories = build_merchant_dimension_breakdown(
                scoped,
                merchant=merchant,
                dimension="Category",
            )
            value_safe_dataframe(
                categories,
                width="stretch",
                hide_index=True,
                column_config=_breakdown_column_config("Category"),
            )
        with account_column:
            st.markdown("**Accounts**")
            accounts = build_merchant_dimension_breakdown(
                scoped,
                merchant=merchant,
                dimension="Account",
            )
            value_safe_dataframe(
                accounts,
                width="stretch",
                hide_index=True,
                column_config=_breakdown_column_config("Account"),
            )
    with descriptions_tab:
        descriptions = build_merchant_description_breakdown(
            scoped,
            merchant=merchant,
        )
        value_safe_dataframe(
            descriptions,
            width="stretch",
            hide_index=True,
            column_config={
                "Description": st.column_config.TextColumn("Description", pinned=True, width="large"),
                "Spending": st.column_config.NumberColumn("Spending", format="$%.2f"),
                "Transactions": st.column_config.NumberColumn("Transactions", format="%d"),
                "Last_Transaction": st.column_config.DateColumn("Last transaction", format="MMM DD, YYYY"),
            },
        )
    with transactions_tab:
        columns = [
            "Date",
            "Full Description",
            "Category",
            "Group",
            "Account",
            "Net_Spend",
        ]
        transactions = scoped.sort_values(["Net_Spend", "Date"], ascending=[False, False])[columns].rename(
            columns={
                "Full Description": "Description",
                "Net_Spend": "Spending",
            }
        )
        value_safe_dataframe(
            transactions,
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
                "Description": st.column_config.TextColumn("Description", pinned=True, width="large"),
                "Spending": st.column_config.NumberColumn("Spending", format="$%.2f"),
            },
        )


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    """Render merchant ranking and selected-merchant drill-down."""
    st.title("Spending by merchant")
    settings = get_settings()
    lookback_options = month_lookback_options(settings.lookback.lookback_months)
    default_lookback = next(
        label for label, months in lookback_options.items() if months == settings.lookback.default_lookback_months
    )
    try:
        merchant_aliases = configured_merchant_aliases()
    except ValueError as error:
        st.error(f"Merchant alias configuration is invalid: {error}")
        return
    transactions = transactions_spreadsheet.scrubbed_df.copy()
    expenses = transactions[transactions["Type"] == "Expense"]
    if expenses.empty:
        st.info("No expense transactions are available.")
        return

    latest = latest_data_timestamp(expenses)
    if latest is not None:
        latest_label = latest.strftime("%B %d, %Y").replace(" 0", " ")
        st.caption(f"Spending through {latest_label}")

    expense_categories = sorted(expenses["Category"].dropna().astype(str).unique())
    expense_groups = sorted(expenses["Group"].dropna().astype(str).unique())
    spending_filter_set = settings.filter_set("spending")
    transaction_sets = [settings.transaction_set(key) for key in spending_filter_set.options]
    default_transaction_set = settings.transaction_set(spending_filter_set.default)
    controls = st.container(horizontal=True, wrap=True, vertical_alignment="bottom")
    with controls:
        lookback = render_time_frame_control(
            list(lookback_options),
            default=default_lookback,
            key="merchant_lookback",
        )
        transaction_set_label = st.segmented_control(
            "View",
            [transaction_set.label for transaction_set in transaction_sets],
            default=default_transaction_set.label,
            required=True,
            key="merchant_view",
            persist_state="page",
            width="content",
        )
        transaction_set = next(
            configured for configured in transaction_sets if configured.label == transaction_set_label
        )
        comparison = st.segmented_control(
            "Compare with",
            COMPARISON_VIEWS,
            default="Previous period",
            required=True,
            key="merchant_comparison",
            persist_state="page",
            width="content",
        )
        filters = render_spending_filters(
            expense_categories,
            expense_groups,
            transaction_set=transaction_set,
        )

    lookback_months = lookback_options[str(lookback)]
    (
        current_months,
        comparison_months,
        current_start,
        current_end,
        comparison_start,
        comparison_end,
    ) = _analysis_periods(
        transactions=transactions,
        lookback_months=lookback_months,
        comparison=str(comparison),
    )
    current_ledger = enrich_with_merchant(
        build_spending_ledger(
            transactions,
            filters,
            start_month=current_start,
            end_month=current_end,
            transaction_set_key=transaction_set.key,
            transaction_sets=settings.transaction_sets,
            merchant_aliases=merchant_aliases,
        ),
        "normalized",
        aliases=merchant_aliases,
    )
    comparison_ledger = enrich_with_merchant(
        build_spending_ledger(
            transactions,
            filters,
            start_month=comparison_start,
            end_month=comparison_end,
            transaction_set_key=transaction_set.key,
            transaction_sets=settings.transaction_sets,
            merchant_aliases=merchant_aliases,
        ),
        "normalized",
        aliases=merchant_aliases,
    )
    overview = build_merchant_overview(
        current_ledger,
        comparison_ledger,
        months=current_months,
    )
    if overview.empty or not bool(current_ledger["Included"].any()):
        st.info("No spending is included in this view. Adjust the filters to continue.")
        return

    _render_summary_metrics(overview, num_months=lookback_months)
    excluded = current_ledger[~current_ledger["Included"]]
    if not excluded.empty:
        st.badge(
            f"{mask_value(f'{len(excluded):,}')} excluded · "
            f"{_format_currency(float(excluded['Net_Spend'].sum()))} net spending",
            color="gray",
        )
    if merchant_aliases:
        st.badge(
            f"{mask_value(str(len(set(merchant_aliases.values()))))} aliased vendors · "
            f"{mask_value(str(len(merchant_aliases)))} rules",
            color="gray",
        )

    comparison_text = _comparison_label(str(comparison), lookback_months)
    with st.container(border=True):
        st.subheader("Where the money went")
        search = st.text_input(
            "Find a merchant",
            placeholder="Search normalized merchant names",
            key="merchant_search",
            persist_state="page",
        )
        filtered = overview[
            overview["Merchant"].str.contains(
                str(search),
                case=False,
                na=False,
                regex=False,
            )
        ].reset_index(drop=True)
        if filtered.empty:
            st.info("No merchants match that search.")
            return

        ranking_column, table_column = st.columns(
            [1, 1.7],
            gap="large",
            vertical_alignment="top",
        )
        with table_column:
            selected_merchant = _render_overview_table(
                filtered,
                comparison_label=comparison_text,
                state_key=(
                    f"merchant_overview_{lookback}_{transaction_set.key}_{comparison}_{crc32(repr(filters).encode()):08x}"
                ),
            )
        with ranking_column:
            st.markdown("**Top merchants by spending**")
            value_safe_altair_chart(
                _ranking_chart(overview, selected_merchant),
                width="stretch",
            )

    _render_merchant_detail(
        current_ledger,
        comparison_ledger,
        overview,
        merchant=selected_merchant,
        current_months=current_months,
        comparison_months=comparison_months,
        comparison_label=comparison_text,
    )


def main() -> None:
    """Streamlit entry point for the Spending by Merchant page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    configure_page(load_transactions_data())


if __name__ == "__main__":
    main()
