"""Tiller-backed budget pulse, comparison, and drill-down."""

import calendar
from collections.abc import Sequence
from typing import cast
from zlib import crc32

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.elements.arrow import DataframeState

from src.analysis.budget import (
    build_budget_history,
    build_budget_performance,
    build_daily_budget_pace,
    filter_budget_transactions,
    get_default_budget_groups,
    get_ytd_group_budget_vs_actual,
    summarize_budget,
    summarize_budget_history,
)
from src.config import get_settings
from src.constants import (
    COLOR_ADDITIONAL_SPENDING,
    COLOR_BUDGET,
    COLOR_NET_WORTH,
    COLOR_OVER_BUDGET,
    COLOR_PLACEHOLDER,
    COLOR_SAVINGS,
    COLOR_UNDER_BUDGET,
)
from src.custom_types import BudgetFilters, ColumnConfig
from src.filters import render_budget_filters
from src.page_helpers import render_data_refresh_controls
from src.reporting_periods import latest_data_timestamp, reporting_anchor, rolling_month_window
from src.spreadsheet import load_categories_data, load_transactions_data
from src.value_visibility import mask_value, value_safe_altair_chart, value_safe_dataframe

SELECTED_GROUP_KEY = "budget_selected_group"


def _format_currency(value: float, *, signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _categories_sheet_url() -> str | None:
    """Return the configured Categories sheet URL without exposing credentials."""
    if get_settings().data.is_demo:
        return None
    try:
        config = st.secrets["connections"]["categories"]
        url = str(config.get("spreadsheet", ""))
    except FileNotFoundError:
        return None
    except KeyError:
        return None
    except TypeError:
        return None
    return url or None


def _passthrough_filters() -> BudgetFilters:
    return {
        "exclude_groups": [],
        "exclude_categories": [],
        "filter_large_expenses": False,
        "expense_threshold": 0,
    }


def _has_adjustments(filters: BudgetFilters) -> bool:
    return bool(filters["exclude_groups"] or filters["exclude_categories"] or filters["filter_large_expenses"])


def _month_progress(
    transactions: pd.DataFrame,
    selected_month: str,
) -> tuple[float, pd.Timestamp | None]:
    dates = pd.to_datetime(transactions["Date"], errors="coerce", utc=True)
    valid = transactions.assign(_Date=dates).dropna(subset=["_Date"])
    latest = None if valid.empty else cast(pd.Timestamp, valid["_Date"].max())
    anchor = reporting_anchor(transactions, anchor_to_data=True)
    selected_period = pd.Period(selected_month, freq="M")
    anchor_period = pd.Period(anchor.strftime("%Y-%m"), freq="M")
    if selected_period > anchor_period:
        return 0.0, latest
    if selected_period == anchor_period:
        days = calendar.monthrange(anchor.year, anchor.month)[1]
        return anchor.day / days, latest
    return 1.0, latest


def _add_status(
    performance: pd.DataFrame,
    *,
    month_progress: float,
) -> pd.DataFrame:
    result = performance.copy()
    result["Status"] = "On pace"
    outside = result["Budget"].le(0) & result["Spent"].gt(0)
    ahead = (
        result["Budget"].gt(0)
        & result["Spent"].le(result["Budget"])
        & (month_progress < 1)
        & result["Pct_Used"].gt(month_progress * 100 + 10)
    )
    over = result["Budget"].gt(0) & result["Spent"].gt(result["Budget"])
    result.loc[ahead, "Status"] = "Ahead of pace"
    result.loc[over, "Status"] = "Over budget"
    result.loc[outside, "Status"] = "Outside plan"
    return result


def create_budget_pulse_chart(
    performance: pd.DataFrame,
    *,
    height_per_row: int = 48,
) -> alt.LayerChart:
    """Compare spending bars with budget targets and typical-spend markers."""
    order = performance.sort_values("Spent", ascending=False)["Entity"].tolist()
    base = alt.Chart(performance).encode(
        y=alt.Y("Entity:N", sort=order, title=None),
    )
    bars = base.mark_bar(cornerRadiusEnd=3).encode(
        x=alt.X("Spent:Q", title="Spending ($)", axis=alt.Axis(format="$,.2s")),
        color=alt.Color(
            "Status:N",
            title=None,
            scale=alt.Scale(
                domain=["On pace", "Ahead of pace", "Over budget", "Outside plan"],
                range=[
                    COLOR_UNDER_BUDGET,
                    COLOR_SAVINGS,
                    COLOR_OVER_BUDGET,
                    COLOR_ADDITIONAL_SPENDING,
                ],
            ),
        ),
        tooltip=[
            alt.Tooltip("Entity:N", title="Name"),
            alt.Tooltip("Status:N"),
            alt.Tooltip("Spent:Q", title="Spent", format="$,.2f"),
            alt.Tooltip("Budget:Q", title="Budget", format="$,.2f"),
            alt.Tooltip("Typical_Spend:Q", title="Typical", format="$,.2f"),
            alt.Tooltip("Vs_Typical:Q", title="Vs typical", format="$,.2f"),
            alt.Tooltip("Outside_Plan:Q", title="Outside plan", format="$,.2f"),
        ],
    )
    targets = base.mark_tick(
        color=COLOR_BUDGET,
        thickness=3,
        size=24,
    ).encode(x=alt.X("Budget:Q"))
    typical = base.mark_point(
        color=COLOR_NET_WORTH,
        filled=True,
        shape="diamond",
        size=90,
    ).encode(
        x=alt.X("Typical_Spend:Q"),
        tooltip=[
            alt.Tooltip("Entity:N", title="Name"),
            alt.Tooltip("Typical_Spend:Q", title="Typical", format="$,.2f"),
        ],
    )
    return cast(
        alt.LayerChart,
        (bars + targets + typical).properties(height=max(240, len(performance) * height_per_row)),
    )


def create_daily_budget_pace_chart(pace: pd.DataFrame) -> alt.LayerChart:
    """Show cumulative actual spending against the selected budget's ideal pace."""
    actual = (
        alt.Chart(pace)
        .mark_line(color=COLOR_NET_WORTH, strokeWidth=3, point=True)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %d", labelAngle=-35)),
            y=alt.Y("Actual_Cumulative:Q", title="Cumulative spending ($)", axis=alt.Axis(format="$,.2s")),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("Actual_Cumulative:Q", title="Actual spending", format="$,.2f"),
                alt.Tooltip("Ideal_Cumulative:Q", title="Ideal pace", format="$,.2f"),
            ],
        )
    )
    ideal = (
        alt.Chart(pace)
        .mark_line(color=COLOR_BUDGET, strokeDash=[6, 4], strokeWidth=2)
        .encode(x=alt.X("Date:T"), y=alt.Y("Ideal_Cumulative:Q"))
    )
    return cast(alt.LayerChart, (actual + ideal).resolve_scale(y="shared").properties(height=270))


def _performance_column_config(entity_label: str) -> ColumnConfig:
    return {
        "Entity": st.column_config.TextColumn(entity_label, pinned=True),
        "Status": st.column_config.TextColumn("Status"),
        "Budget": st.column_config.NumberColumn("Budget", format="$%.2f"),
        "Spent": st.column_config.NumberColumn("Spent", format="$%.2f"),
        "Remaining": st.column_config.NumberColumn("Remaining", format="$%.2f"),
        "Pct_Used": st.column_config.NumberColumn("Used", format="%.1f%%"),
        "Vs_Typical": st.column_config.NumberColumn("Vs typical", format="$%.2f"),
        "Outside_Plan": st.column_config.NumberColumn("Outside plan", format="$%.2f"),
        "Success_Rate": st.column_config.NumberColumn("12-mo hit rate", format="%.0f%%"),
        "Trend": st.column_config.LineChartColumn(
            "13-month trend",
            color=COLOR_NET_WORTH,
        ),
    }


def _select_group(performance: pd.DataFrame, *, state_key: str) -> str:
    remembered = st.session_state.get(SELECTED_GROUP_KEY)
    default_position = 0
    if isinstance(remembered, str) and remembered in performance["Entity"].values:
        default_position = int(performance.index[performance["Entity"].eq(remembered)].tolist()[0])
    selection_default = cast(
        DataframeState,
        {"selection": {"rows": [default_position]}},
    )
    display_columns = [
        "Entity",
        "Status",
        "Budget",
        "Spent",
        "Remaining",
        "Pct_Used",
        "Vs_Typical",
        "Outside_Plan",
        "Success_Rate",
        "Trend",
    ]
    event = value_safe_dataframe(
        performance[display_columns],
        key=state_key,
        width="stretch",
        height=min(610, 38 * (len(performance) + 1) + 8),
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row-required",
        selection_default=selection_default,
        column_config=_performance_column_config("Group"),
    )
    rows = event["selection"]["rows"]
    position = rows[0] if rows else 0
    if position >= len(performance):
        position = 0
    selected = str(performance.iloc[position]["Entity"])
    st.session_state[SELECTED_GROUP_KEY] = selected
    return selected


def _history_chart(
    history: pd.DataFrame,
    *,
    typical_spend: float,
    selected_month: str,
) -> alt.LayerChart:
    chart_data = history.copy()
    chart_data["Date"] = pd.PeriodIndex(chart_data["Month"], freq="M").to_timestamp()
    chart_data["Selected"] = chart_data["Month"].eq(selected_month)
    bars = (
        alt.Chart(chart_data)
        .mark_bar(
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
        )
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=-35)),
            y=alt.Y("Spent:Q", title="Spending ($)", axis=alt.Axis(format="$,.2s")),
            color=alt.condition(
                "datum.Selected",
                alt.value(COLOR_NET_WORTH),
                alt.value(COLOR_PLACEHOLDER),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Month", format="%B %Y"),
                alt.Tooltip("Spent:Q", title="Spent", format="$,.2f"),
                alt.Tooltip("Budget:Q", title="Budget", format="$,.2f"),
                alt.Tooltip("Outside_Plan:Q", title="Outside plan", format="$,.2f"),
            ],
        )
    )
    budget = (
        alt.Chart(chart_data)
        .mark_line(
            color=COLOR_BUDGET,
            strokeWidth=2,
        )
        .encode(x=alt.X("Date:T"), y=alt.Y("Budget:Q"))
    )
    typical = (
        alt.Chart(pd.DataFrame({"Typical": [typical_spend]}))
        .mark_rule(
            color=COLOR_SAVINGS,
            strokeDash=[6, 4],
        )
        .encode(y=alt.Y("Typical:Q"))
    )
    return cast(
        alt.LayerChart,
        (bars + budget + typical).properties(height=320),
    )


def _render_summary(
    history: pd.DataFrame,
    group_performance: pd.DataFrame,
    category_performance: pd.DataFrame,
    *,
    selected_month: str,
    month_progress: float,
) -> None:
    pulse = summarize_budget_history(history, selected_month)
    outside_categories = int(
        (category_performance["Budget"].le(0) & category_performance["Spent"].abs().gt(0.005)).sum()
    )
    groups_within = int(
        (group_performance["Budget"].gt(0) & group_performance["Spent"].le(group_performance["Budget"])).sum()
    )
    budgeted_groups = int(group_performance["Budget"].gt(0).sum())
    pace_delta = pulse["pct_used"] - month_progress * 100
    with st.container(horizontal=True):
        st.metric(
            "Spending",
            _format_currency(pulse["spent"]),
            delta=(
                f"{_format_currency(pulse['vs_typical'], signed=True)} vs typical" if pulse["typical_spend"] else None
            ),
            delta_color="inverse",
            border=True,
        )
        st.metric(
            "Remaining",
            _format_currency(pulse["remaining"]),
            delta=f"{_format_currency(pulse['budget'])} budget",
            delta_color="off",
            border=True,
        )
        st.metric(
            "Budget used",
            mask_value(f"{pulse['pct_used']:.1f}%"),
            delta=(
                f"{mask_value(f'{pace_delta:+.1f} pts')} vs month elapsed"
                if month_progress < 1
                else f"{mask_value(str(groups_within))} of {mask_value(str(budgeted_groups))} groups within budget"
            ),
            delta_color="inverse" if month_progress < 1 else "off",
            border=True,
        )
        st.metric(
            "Outside the plan",
            _format_currency(pulse["outside_plan"]),
            delta=f"{mask_value(str(outside_categories))} unbudgeted categories",
            delta_color="off",
            border=True,
        )


def _render_daily_budget_pace(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    *,
    selected_month: str,
    groups: Sequence[str],
    filters: BudgetFilters,
) -> None:
    """Render the selected budget's cumulative daily pace."""
    anchor = reporting_anchor(transactions_df, anchor_to_data=True)
    selected_period = pd.Period(selected_month, freq="M")
    anchor_period = pd.Period(anchor.strftime("%Y-%m"), freq="M")
    through_date = anchor if selected_period >= anchor_period else selected_period.end_time
    pace = build_daily_budget_pace(
        budget_df,
        transactions_df,
        selected_month,
        filters,
        groups,
        through_date=through_date,
    )
    with st.container(border=True):
        st.subheader(
            "Daily budget pace",
            help=(
                "Cumulative spending compared with a straight-line share of your selected budget. "
                "Unbudgeted categories in the selected groups count toward actual spending."
            ),
        )
        if pace.empty:
            st.info("No daily pace is available for this month.")
            return
        value_safe_altair_chart(create_daily_budget_pace_chart(pace), width="stretch")


def _render_group_detail(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    *,
    selected_month: str,
    selected_group: str,
    filters: BudgetFilters,
    group_history: pd.DataFrame,
    group_performance: pd.DataFrame,
    month_progress: float,
) -> None:
    group_row = group_performance[group_performance["Entity"].eq(selected_group)].iloc[0]
    history = group_history[group_history["Entity"].eq(selected_group)]
    with st.container(border=True):
        st.subheader(selected_group)
        with st.container(horizontal=True):
            st.metric("Spent", _format_currency(float(group_row["Spent"])))
            st.metric("Budget", _format_currency(float(group_row["Budget"])))
            st.metric(
                "Typical month",
                _format_currency(float(group_row["Typical_Spend"])),
            )
            st.metric(
                "Outside the plan",
                _format_currency(float(group_row["Outside_Plan"])),
            )
        value_safe_altair_chart(
            _history_chart(
                history,
                typical_spend=float(group_row["Typical_Spend"]),
                selected_month=selected_month,
            ),
            width="stretch",
        )

        category_history = build_budget_history(
            budget_df,
            transactions_df,
            selected_month,
            filters,
            [selected_group],
            dimension="Category",
            lookback_months=get_settings().budget.history_months,
        )
        categories = _add_status(
            build_budget_performance(category_history, selected_month),
            month_progress=month_progress,
        )
        if categories.empty:
            st.info("No category spending is available for this group and month.")
            return

        st.markdown("**What drove spending**")
        chart_column, table_column = st.columns(
            [1, 1.45],
            gap="large",
            vertical_alignment="top",
        )
        with chart_column:
            value_safe_altair_chart(
                create_budget_pulse_chart(categories.head(10), height_per_row=42),
                width="stretch",
            )
        with table_column:
            category_config = dict(_performance_column_config("Category"))
            category_config["Budget_Variance"] = st.column_config.NumberColumn("Vs budget", format="$%.2f")
            value_safe_dataframe(
                categories[
                    [
                        "Entity",
                        "Status",
                        "Budget",
                        "Spent",
                        "Budget_Variance",
                        "Vs_Typical",
                        "Success_Rate",
                    ]
                ],
                width="stretch",
                height=min(510, 38 * (len(categories) + 1) + 8),
                hide_index=True,
                column_config=category_config,
            )

        current_transactions = filter_budget_transactions(
            transactions_df,
            selected_month,
            filters,
            groups=[selected_group],
        ).copy()
        current_transactions["Net spend"] = -pd.to_numeric(current_transactions["Amount"], errors="coerce").fillna(0.0)
        category_options = ["All categories", *categories["Entity"].tolist()]
        transaction_category = str(
            st.selectbox(
                "Transactions",
                category_options,
                key=f"budget_transaction_category_{selected_group}",
            )
        )
        if transaction_category != "All categories":
            current_transactions = current_transactions[current_transactions["Category"].eq(transaction_category)]
        current_transactions = current_transactions.sort_values(["Net spend", "Date"], ascending=[False, False])
        if current_transactions.empty:
            st.info("No transactions match this category selection.")
        else:
            value_safe_dataframe(
                current_transactions[
                    [
                        "Date",
                        "Category",
                        "Full Description",
                        "Account",
                        "Net spend",
                    ]
                ].rename(columns={"Full Description": "Description"}),
                width="stretch",
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
                    "Description": st.column_config.TextColumn("Description", pinned=True, width="large"),
                    "Net spend": st.column_config.NumberColumn("Net spend", format="$%.2f"),
                },
            )


def _render_ytd(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    *,
    selected_month: str,
    groups: Sequence[str],
    filters: BudgetFilters,
) -> None:
    ytd = get_ytd_group_budget_vs_actual(
        budget_df,
        transactions_df,
        selected_month,
        filters,
        groups,
    )
    summary = summarize_budget(ytd)
    with st.expander("Year-to-date position"):
        with st.container(horizontal=True):
            st.metric("YTD spending", _format_currency(summary["spent"]))
            st.metric("YTD budget", _format_currency(summary["budget"]))
            st.metric("YTD remaining", _format_currency(summary["remaining"]))
            st.metric("YTD used", mask_value(f"{summary['pct_used']:.1f}%"))
        value_safe_dataframe(
            ytd[["Group", "Budget", "Spent", "Remaining", "Pct_Used"]],
            width="stretch",
            hide_index=True,
            column_config={
                "Budget": st.column_config.NumberColumn("Budget", format="$%.2f"),
                "Spent": st.column_config.NumberColumn("Spent", format="$%.2f"),
                "Remaining": st.column_config.NumberColumn("Remaining", format="$%.2f"),
                "Pct_Used": st.column_config.NumberColumn("Used", format="%.1f%%"),
            },
        )


def main() -> None:
    """Render the monthly budget pulse and drill-down."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    st.title("Budget")

    transactions_spreadsheet = load_transactions_data()
    categories_spreadsheet = load_categories_data()
    transactions_df = transactions_spreadsheet.scrubbed_df.copy()
    budget_df = categories_spreadsheet.budget_df.copy()
    if transactions_df.empty:
        st.info("No transaction data is available.")
        return

    latest = latest_data_timestamp(transactions_df)
    if latest is not None:
        st.caption(f"Spending through {latest.strftime('%B %d, %Y').replace(' 0', ' ')}")

    current_month = rolling_month_window(1)[1]
    latest_month = latest.strftime("%Y-%m") if latest is not None else current_month
    months = sorted(
        {*transactions_df["Month"].dropna().astype(str).unique(), current_month, latest_month},
        reverse=True,
    )
    if not months:
        st.info("No monthly transaction data is available.")
        return

    available_groups = transactions_spreadsheet.get_all_groups()
    controls = st.columns([1, 3.2, 1.15, 1.15], vertical_alignment="bottom")
    with controls[0]:
        selected_month = st.selectbox(
            "Month",
            months,
            index=months.index(latest_month),
            key="budget_month",
            persist_state="page",
        )
    default_groups = get_default_budget_groups(
        budget_df,
        str(selected_month),
        available_groups,
    )
    with controls[1]:
        selected_groups_value = st.pills(
            "Budget groups",
            available_groups,
            default=default_groups,
            selection_mode="multi",
            key=f"budget_groups_{selected_month}",
            persist_state="session",
        )
    selected_groups = list(selected_groups_value or [])
    with controls[2]:
        adjusted_filters = render_budget_filters(
            transactions_spreadsheet.get_all_categories(),
            selected_groups,
        )
    with controls[3]:
        sheet_url = _categories_sheet_url()
        if sheet_url:
            st.link_button(
                "Edit in Tiller",
                sheet_url,
                icon=":material/open_in_new:",
                width="stretch",
            )

    if not selected_groups:
        message = (
            "Select at least one budget group."
            if default_groups
            else f"No positive expense budgets are configured for {selected_month}."
        )
        st.info(message)
        return

    adjusted = _has_adjustments(adjusted_filters)
    filters = adjusted_filters if adjusted else _passthrough_filters()
    if adjusted:
        st.badge("Adjusted view", icon=":material/tune:", color="orange")

    group_history = build_budget_history(
        budget_df,
        transactions_df,
        str(selected_month),
        filters,
        selected_groups,
        lookback_months=get_settings().budget.history_months,
    )
    group_performance = build_budget_performance(
        group_history,
        str(selected_month),
    )
    if group_performance.empty:
        st.info("No budget or spending data is available for this selection.")
        return

    month_progress, _ = _month_progress(transactions_df, str(selected_month))
    group_performance = _add_status(
        group_performance,
        month_progress=month_progress,
    )
    category_history = build_budget_history(
        budget_df,
        transactions_df,
        str(selected_month),
        filters,
        selected_groups,
        dimension="Category",
        lookback_months=get_settings().budget.history_months,
    )
    category_performance = build_budget_performance(
        category_history,
        str(selected_month),
    )
    _render_summary(
        group_history,
        group_performance,
        category_performance,
        selected_month=str(selected_month),
        month_progress=month_progress,
    )
    _render_daily_budget_pace(
        budget_df,
        transactions_df,
        selected_month=str(selected_month),
        groups=selected_groups,
        filters=filters,
    )

    with st.container(border=True):
        st.subheader("This month against the plan")
        value_safe_altair_chart(
            create_budget_pulse_chart(group_performance),
            width="stretch",
        )
        selected_group = _select_group(
            group_performance,
            state_key=(
                f"budget_group_performance_{selected_month}_{crc32(repr((selected_groups, filters)).encode()):08x}"
            ),
        )

    _render_group_detail(
        budget_df,
        transactions_df,
        selected_month=str(selected_month),
        selected_group=selected_group,
        filters=filters,
        group_history=group_history,
        group_performance=group_performance,
        month_progress=month_progress,
    )
    _render_ytd(
        budget_df,
        transactions_df,
        selected_month=str(selected_month),
        groups=selected_groups,
        filters=filters,
    )


if __name__ == "__main__":
    main()
