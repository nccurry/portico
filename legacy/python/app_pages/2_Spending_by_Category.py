"""Explore spending by group, category, merchant, month, and transaction."""

from collections.abc import Mapping, Sequence
from typing import cast
from zlib import crc32

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.elements.arrow import DataframeState

from src.analysis.spending import (
    build_entity_monthly_comparison,
    build_merchant_breakdown,
    build_spending_ledger,
    build_spending_overview,
    summarize_spending,
)
from src.config import get_settings
from src.constants import COLOR_EXPENSE, COLOR_PLACEHOLDER
from src.custom_types import ColumnConfig, SpendingSummary
from src.filters import render_spending_filters
from src.page_helpers import configured_merchant_aliases, render_data_refresh_controls, render_time_frame_control
from src.reporting_periods import latest_data_timestamp, month_lookback_options, rolling_month_window
from src.spreadsheet import TransactionsSpreadsheet, load_transactions_data
from src.value_visibility import mask_value, value_safe_altair_chart, value_safe_dataframe

COMPARISON_VIEWS = ["Previous period", "Last year"]
BREAKDOWNS = ["Group", "Category"]
MONTH_SELECTION = "spending_month_pick"
DETAIL_MONTH_KEY = "spending_detail_month"
CHART_EPOCH_KEY = "spending_chart_epoch"


def _format_currency(value: float) -> str:
    sign = "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _format_signed_currency(value: float) -> str:
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _format_percent(value: float | None) -> str:
    if value is None:
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


def _render_summary_metrics(
    summary: SpendingSummary,
    *,
    comparison_label: str,
) -> None:
    total = float(summary["total_spending"])
    average = float(summary["average_monthly_spending"])
    change = float(summary["change"])
    change_pct = summary["change_pct"]
    with st.container(horizontal=True):
        st.metric("Total spending", _format_currency(total), border=True)
        st.metric("Average monthly", _format_currency(average), border=True)
        st.metric(
            f"Change vs {comparison_label}",
            _format_signed_currency(change),
            _format_percent(None if change_pct is None else float(change_pct)),
            delta_color="inverse",
            border=True,
        )


def _overview_column_config(
    dimension: str,
    comparison_label: str,
) -> ColumnConfig:
    return {
        "Entity": st.column_config.TextColumn(dimension, pinned=True),
        "Group": (st.column_config.TextColumn("Group") if dimension == "Category" else None),
        "Spending": st.column_config.NumberColumn("Spending", format="$%.0f"),
        "Share": st.column_config.NumberColumn("Share", format="%.1f%%"),
        "Average_Monthly": st.column_config.NumberColumn(
            "Avg/month",
            format="$%.0f",
        ),
        "Comparison_Spending": st.column_config.NumberColumn(
            comparison_label.capitalize(),
            format="$%.0f",
        ),
        "Change": st.column_config.NumberColumn("Change", format="$%+.0f"),
        "Change_Pct": st.column_config.NumberColumn("Change %", format="%+.1f%%"),
        "Transactions": st.column_config.NumberColumn("Transactions", format="%d"),
        "Monthly_Trend": st.column_config.LineChartColumn(
            "Monthly trend",
            width="medium",
        ),
    }


def _overview_trend_data(
    overview: pd.DataFrame,
    months: Sequence[str],
    *,
    limit: int,
) -> pd.DataFrame:
    rows = overview[overview["Spending"] > 0].head(limit)
    return pd.DataFrame(
        [
            {
                "Month": month,
                "Month_Date": pd.Timestamp(f"{month}-01"),
                "Entity": str(row["Entity"]),
                "Spending": float(spending),
            }
            for row in rows.to_dict("records")
            for month, spending in zip(
                months,
                cast(Sequence[float], row["Monthly_Trend"]),
                strict=True,
            )
        ]
    )


def _render_at_a_glance(
    overview: pd.DataFrame,
    *,
    dimension: str,
    months: Sequence[str],
) -> None:
    ranked = overview[overview["Spending"] > 0].head(10).copy()
    if ranked.empty:
        return

    entities = ranked["Entity"].astype(str).tolist()
    shared_color = alt.Color(
        "Entity:N",
        scale=alt.Scale(domain=entities),
        legend=None,
    )
    trend = _overview_trend_data(overview, months, limit=5)
    trend_entities = trend["Entity"].drop_duplicates().tolist()

    trend_chart = (
        alt.Chart(trend)
        .mark_line(point=len(months) <= 12, strokeWidth=2.5)
        .encode(
            x=alt.X(
                "Month_Date:T",
                title=None,
                axis=alt.Axis(format="%b %Y", labelAngle=-35, labelOverlap=True),
            ),
            y=alt.Y(
                "Spending:Q",
                title="Spending ($)",
                axis=alt.Axis(format="$~s"),
            ),
            color=alt.Color(
                "Entity:N",
                scale=alt.Scale(domain=entities),
                legend=alt.Legend(
                    title=None,
                    orient="bottom",
                    columns=min(3, len(trend_entities)),
                ),
            ),
            tooltip=[
                alt.Tooltip("Month:N", title="Month"),
                alt.Tooltip("Entity:N", title=dimension),
                alt.Tooltip("Spending:Q", title="Spending", format="$,.2f"),
            ],
        )
        .properties(height=320)
    )
    ranking_chart = (
        alt.Chart(ranked)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X(
                "Spending:Q",
                title="Spending ($)",
                axis=alt.Axis(format="$~s"),
            ),
            y=alt.Y(
                "Entity:N",
                title=None,
                sort=entities,
                axis=alt.Axis(labelLimit=190),
            ),
            color=shared_color,
            tooltip=[
                alt.Tooltip("Entity:N", title=dimension),
                alt.Tooltip("Spending:Q", title="Spending", format="$,.2f"),
                alt.Tooltip("Share:Q", title="Share", format=".1f"),
                alt.Tooltip(
                    "Average_Monthly:Q",
                    title="Average monthly",
                    format="$,.2f",
                ),
                alt.Tooltip("Change:Q", title="Change", format="+$,.2f"),
            ],
        )
        .properties(height=320)
    )

    trend_column, ranking_column = st.columns(
        [1.45, 1],
        gap="large",
        vertical_alignment="top",
    )
    with trend_column:
        st.markdown("**Monthly trend · top 5**")
        value_safe_altair_chart(trend_chart, width="stretch")
    with ranking_column:
        entity_label = "categories" if dimension == "Category" else "groups"
        st.markdown(f"**Top {mask_value(str(len(ranked)))} {entity_label} by spending**")
        value_safe_altair_chart(ranking_chart, width="stretch")


def _render_overview(
    overview: pd.DataFrame,
    *,
    dimension: str,
    comparison_label: str,
    state_key: str,
) -> str:
    identity_key = f"spending_selected_{dimension.lower()}"
    remembered = st.session_state.get(identity_key)
    default_position = 0
    if remembered in overview["Entity"].values:
        default_position = int(overview.index[overview["Entity"] == remembered].tolist()[0])
    selection_default = cast(
        DataframeState,
        {"selection": {"rows": [default_position]}},
    )
    event = value_safe_dataframe(
        overview,
        key=state_key,
        width="stretch",
        height=min(680, 38 * (len(overview) + 1) + 8),
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row-required",
        selection_default=selection_default,
        column_config=_overview_column_config(dimension, comparison_label),
    )
    rows = event["selection"]["rows"]
    row_position = rows[0] if rows else 0
    if row_position >= len(overview):
        row_position = 0
    selected = str(overview.iloc[row_position]["Entity"])
    st.session_state[identity_key] = selected
    return selected


def _selected_month_from_event(event: object) -> str | None:
    if not isinstance(event, Mapping):
        return None
    selection = event.get("selection", {})
    if not isinstance(selection, Mapping):
        return None
    selected = selection.get(MONTH_SELECTION)
    if isinstance(selected, list) and selected:
        record = selected[0]
        if isinstance(record, Mapping) and "Month" in record:
            return str(record["Month"])
    if isinstance(selected, Mapping):
        months = selected.get("Month", [])
        if isinstance(months, list) and months:
            return str(months[0])
    return None


def _reset_chart_selection() -> None:
    st.session_state[CHART_EPOCH_KEY] = st.session_state.get(CHART_EPOCH_KEY, 0) + 1


def _entity_history_chart(
    monthly: pd.DataFrame,
    *,
    selected_month: str | None,
) -> alt.LayerChart:
    data = monthly.copy()
    data["Month_Date"] = pd.to_datetime(data["Month"] + "-01")
    month_pick = alt.selection_point(
        name=MONTH_SELECTION,
        fields=["Month"],
        on="click",
        toggle=False,
        clear="dblclick",
    )
    x_axis = alt.X(
        "Month_Date:T",
        title=None,
        axis=alt.Axis(format="%b %Y", labelAngle=-35, labelOverlap=True),
    )
    current = (
        alt.Chart(data)
        .mark_bar(color=COLOR_EXPENSE, opacity=0.85, size=20)
        .encode(
            x=x_axis,
            y=alt.Y(
                "Current_Spend:Q",
                title="Monthly spending ($)",
                axis=alt.Axis(format="$~s"),
            ),
            tooltip=[
                alt.Tooltip("Month:N", title="Month"),
                alt.Tooltip("Current_Spend:Q", title="Spending", format="$,.2f"),
            ],
        )
    )
    comparison = (
        alt.Chart(data)
        .mark_line(
            color=COLOR_PLACEHOLDER,
            point=True,
            strokeDash=[5, 4],
            strokeWidth=2.5,
        )
        .encode(
            x=x_axis,
            y=alt.Y("Comparison_Spend:Q"),
            tooltip=[
                alt.Tooltip("Comparison_Month:N", title="Comparison month"),
                alt.Tooltip(
                    "Comparison_Spend:Q",
                    title="Comparison spending",
                    format="$,.2f",
                ),
            ],
        )
    )
    click_target = alt.Chart(data).mark_point(opacity=0.001, size=1600).encode(x=x_axis).add_params(month_pick)
    layers: list[alt.Chart] = [current, comparison, click_target]
    if selected_month is not None:
        selected = data[data["Month"] == selected_month]
        layers.append(
            alt.Chart(selected).mark_rule(color=COLOR_PLACEHOLDER, opacity=0.8, strokeWidth=2).encode(x=x_axis)
        )
    return cast(alt.LayerChart, alt.layer(*layers).properties(height=300))


def _entity_rows(
    ledger: pd.DataFrame,
    *,
    dimension: str,
    entity: str,
    month: str | None = None,
) -> pd.DataFrame:
    rows = ledger[ledger["Included"] & (ledger[dimension].astype(str) == entity)].copy()
    if month is not None:
        rows = rows[rows["Month"].astype(str) == month].copy()
    return rows


def _render_breakdown_table(
    overview: pd.DataFrame,
    *,
    comparison_label: str,
) -> None:
    if overview.empty:
        st.info("No category spending in this selection.")
        return
    columns = [
        "Entity",
        "Spending",
        "Share",
        "Comparison_Spending",
        "Change",
        "Change_Pct",
        "Transactions",
    ]
    value_safe_dataframe(
        overview[columns],
        width="stretch",
        hide_index=True,
        column_config=_overview_column_config("Category", comparison_label),
    )


def _render_merchant_table(ledger: pd.DataFrame) -> None:
    try:
        aliases = configured_merchant_aliases()
    except ValueError as error:
        st.error(str(error), icon=":material/error:")
        return
    merchants = build_merchant_breakdown(ledger, aliases=aliases)
    if merchants.empty:
        st.info("No merchant spending in this selection.")
        return
    value_safe_dataframe(
        merchants,
        width="stretch",
        hide_index=True,
        column_config={
            "Merchant": st.column_config.TextColumn("Merchant", pinned=True),
            "Spending": st.column_config.NumberColumn("Spending", format="$%.2f"),
            "Share": st.column_config.NumberColumn("Share", format="%.1f%%"),
            "Transactions": st.column_config.NumberColumn(
                "Transactions",
                format="%d",
            ),
            "Average_Transaction": st.column_config.NumberColumn(
                "Avg transaction",
                format="$%.2f",
            ),
            "Last_Transaction": st.column_config.DateColumn(
                "Last transaction",
                format="MMM DD, YYYY",
            ),
        },
    )


def _render_transactions(rows: pd.DataFrame) -> None:
    if rows.empty:
        st.info("No transactions in this selection.")
        return
    columns = [
        "Date",
        "Full Description",
        "Group",
        "Category",
        "Account",
        "Net_Spend",
    ]
    available = [column for column in columns if column in rows]
    display = (
        rows.assign(_Magnitude=rows["Net_Spend"].abs())
        .sort_values(["_Magnitude", "Date"], ascending=[False, False])[available]
        .rename(
            columns={
                "Full Description": "Description",
                "Net_Spend": "Spending",
            }
        )
    )
    value_safe_dataframe(
        display,
        width="stretch",
        hide_index=True,
        height=min(600, 38 * (len(display) + 1) + 8),
        column_config={
            "Date": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
            "Description": st.column_config.TextColumn(
                "Description",
                width="large",
                pinned=True,
            ),
            "Spending": st.column_config.NumberColumn(
                "Spending",
                format="$%.2f",
            ),
        },
    )


def _render_excluded_rows(ledger: pd.DataFrame) -> None:
    excluded = ledger[~ledger["Included"]].copy()
    if excluded.empty:
        return
    with st.expander(
        f"Excluded from this view ({mask_value(str(len(excluded)))})",
        icon=":material/filter_alt:",
    ):
        display = excluded[
            [
                "Date",
                "Full Description",
                "Group",
                "Category",
                "Net_Spend",
                "Exclusion_Reason",
            ]
        ].rename(
            columns={
                "Full Description": "Description",
                "Net_Spend": "Spending",
                "Exclusion_Reason": "Exclusion reason",
            }
        )
        value_safe_dataframe(
            display,
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
                "Spending": st.column_config.NumberColumn(
                    "Spending",
                    format="$%.2f",
                ),
            },
        )


def _render_entity_detail(
    current_ledger: pd.DataFrame,
    comparison_ledger: pd.DataFrame,
    overview: pd.DataFrame,
    *,
    dimension: str,
    entity: str,
    current_months: Sequence[str],
    comparison_months: Sequence[str],
    comparison_label: str,
    chart_key: str,
) -> None:
    row = overview[overview["Entity"] == entity].iloc[0]
    group = str(row["Group"])
    detail_title = entity if dimension == "Group" or not group else f"{entity} · {group}"
    with st.container(border=True):
        st.subheader(detail_title)
        with st.container(horizontal=True):
            st.metric(
                "Spending",
                _format_currency(float(row["Spending"])),
                border=True,
            )
            st.metric(
                "Average monthly",
                _format_currency(float(row["Average_Monthly"])),
                border=True,
            )
            st.metric(
                "Share of view",
                mask_value(f"{float(row['Share']):.1f}%"),
                border=True,
            )
            st.metric(
                f"Change vs {comparison_label}",
                _format_signed_currency(float(row["Change"])),
                _format_percent(None if pd.isna(row["Change_Pct"]) else float(row["Change_Pct"])),
                delta_color="inverse",
                border=True,
            )

        monthly = build_entity_monthly_comparison(
            current_ledger,
            comparison_ledger,
            dimension=dimension,
            entity=entity,
            current_months=current_months,
            comparison_months=comparison_months,
        )
        selected_month = st.session_state.get(DETAIL_MONTH_KEY)
        if selected_month not in current_months:
            selected_month = None
        with st.container(horizontal=True):
            st.badge("Current spending", color="red")
            st.badge(comparison_label.capitalize(), color="gray")
        epoch = st.session_state.get(CHART_EPOCH_KEY, 0)
        chart_event = value_safe_altair_chart(
            _entity_history_chart(monthly, selected_month=selected_month),
            key=f"{chart_key}_{epoch}",
            width="stretch",
            on_select="rerun",
            selection_mode=MONTH_SELECTION,
        )
        selected_from_chart = _selected_month_from_event(chart_event)
        if selected_from_chart in current_months:
            st.session_state[DETAIL_MONTH_KEY] = selected_from_chart

        month_options = ["All months", *reversed(current_months)]
        current_value = st.session_state.get(DETAIL_MONTH_KEY)
        if current_value not in month_options:
            st.session_state[DETAIL_MONTH_KEY] = "All months"
        detail_month = st.selectbox(
            "Detail month",
            month_options,
            format_func=lambda value: value if value == "All months" else _month_label(value),
            key=DETAIL_MONTH_KEY,
            on_change=_reset_chart_selection,
            persist_state="page",
        )
        selected_detail_month = None if detail_month == "All months" else detail_month
        current_scope = _entity_rows(
            current_ledger,
            dimension=dimension,
            entity=entity,
            month=selected_detail_month,
        )
        comparison_entity = _entity_rows(
            comparison_ledger,
            dimension=dimension,
            entity=entity,
        )
        if selected_detail_month is None:
            comparison_scope = comparison_entity
            scope_current_months = list(current_months)
        else:
            month_position = list(current_months).index(selected_detail_month)
            comparison_month = list(comparison_months)[month_position]
            comparison_scope = comparison_entity[comparison_entity["Month"].astype(str) == comparison_month].copy()
            scope_current_months = [selected_detail_month]

        scope_comparison_label = comparison_label if selected_detail_month is None else "comparison month"

        if dimension == "Group":
            categories_tab, merchants_tab, transactions_tab = st.tabs(["Categories", "Merchants", "Transactions"])
            with categories_tab:
                category_overview = build_spending_overview(
                    current_scope,
                    comparison_scope,
                    dimension="Category",
                    months=scope_current_months,
                )
                _render_breakdown_table(
                    category_overview,
                    comparison_label=scope_comparison_label,
                )
            with merchants_tab:
                _render_merchant_table(current_scope)
            with transactions_tab:
                _render_transactions(current_scope)
        else:
            merchants_tab, transactions_tab = st.tabs(["Merchants", "Transactions"])
            with merchants_tab:
                _render_merchant_table(current_scope)
            with transactions_tab:
                _render_transactions(current_scope)


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    """Render the spending overview and selected-entity drill-down."""
    st.title("Spending by category")
    settings = get_settings()
    try:
        aliases = configured_merchant_aliases()
    except ValueError as error:
        st.error(f"Merchant alias configuration is invalid: {error}")
        return
    lookback_options = month_lookback_options(settings.lookback.lookback_months)
    default_lookback = next(
        label for label, months in lookback_options.items() if months == settings.lookback.default_lookback_months
    )
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
            key="spending_lookback",
        )
        transaction_set_label = st.segmented_control(
            "View",
            [transaction_set.label for transaction_set in transaction_sets],
            default=default_transaction_set.label,
            required=True,
            key="spending_view",
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
            key="spending_comparison",
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
    current_ledger = build_spending_ledger(
        transactions,
        filters,
        start_month=current_start,
        end_month=current_end,
        transaction_set_key=transaction_set.key,
        transaction_sets=settings.transaction_sets,
        merchant_aliases=aliases,
    )
    comparison_ledger = build_spending_ledger(
        transactions,
        filters,
        start_month=comparison_start,
        end_month=comparison_end,
        transaction_set_key=transaction_set.key,
        transaction_sets=settings.transaction_sets,
        merchant_aliases=aliases,
    )
    comparison_text = _comparison_label(str(comparison), lookback_months)
    summary = summarize_spending(
        current_ledger,
        comparison_ledger,
        num_months=lookback_months,
    )
    _render_summary_metrics(summary, comparison_label=comparison_text)

    excluded = current_ledger[~current_ledger["Included"]]
    if not excluded.empty:
        excluded_spending = float(excluded["Net_Spend"].sum())
        st.badge(
            f"{mask_value(f'{len(excluded):,}')} excluded · {_format_currency(excluded_spending)} net spending",
            color="gray",
        )

    with st.container(border=True):
        st.subheader("Where the money went")
        dimension = st.segmented_control(
            "Breakdown",
            BREAKDOWNS,
            default="Category",
            required=True,
            key="spending_breakdown",
            persist_state="page",
        )
        overview = build_spending_overview(
            current_ledger,
            comparison_ledger,
            dimension=str(dimension),
            months=current_months,
        )
        if overview.empty or not bool(current_ledger["Included"].any()):
            st.info("No spending is included in this view. Adjust the filters to continue.")
            _render_excluded_rows(current_ledger)
            return
        _render_at_a_glance(
            overview,
            dimension=str(dimension),
            months=current_months,
        )
        selected_entity = _render_overview(
            overview,
            dimension=str(dimension),
            comparison_label=comparison_text,
            state_key=(
                f"spending_overview_{dimension}_{lookback}_{transaction_set.key}_{comparison}_{crc32(repr(filters).encode()):08x}"
            ),
        )

    _render_entity_detail(
        current_ledger,
        comparison_ledger,
        overview,
        dimension=str(dimension),
        entity=selected_entity,
        current_months=current_months,
        comparison_months=comparison_months,
        comparison_label=comparison_text,
        chart_key=f"spending_history_{dimension}_{selected_entity}",
    )
    _render_excluded_rows(current_ledger)


def main() -> None:
    """Streamlit entry point for the Spending by Category page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    configure_page(load_transactions_data())


if __name__ == "__main__":
    main()
