"""Subscription inventory, history, and recurring-charge discovery."""

from collections.abc import Iterable
from typing import Any, Literal, cast

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis.subscriptions import (
    build_subscription_history,
    build_subscription_inventory,
    build_subscription_lifecycles,
    find_subscription_candidates,
    get_subscription_transactions,
    summarize_subscriptions,
)
from src.constants import DEFAULT_EXCLUDE_CATEGORIES_SUBSCRIPTIONS
from src.custom_types import SubscriptionSummary
from src.page_helpers import get_transaction_column_config, render_data_refresh_controls
from src.spreadsheet import TransactionsSpreadsheet, load_transactions_data
from src.value_visibility import mask_value, value_safe_altair_chart, value_safe_dataframe

COLOR_ACTIVE = "#57CC57"
COLOR_INACTIVE = "#7D8590"
COLOR_SPEND = "#4E79A7"

TimelineScope = Literal["Active and recent", "All merchants"]


def prepare_lifecycle_timeline(
    lifecycles: pd.DataFrame,
    *,
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
    scope: TimelineScope,
) -> pd.DataFrame:
    """Filter, clip, and order lifecycle episodes for the selected history view."""
    if lifecycles.empty:
        return lifecycles.copy()

    start = _as_utc(range_start)
    end = _as_utc(range_end)
    timeline = lifecycles.copy()
    date_columns = [
        "Episode_Start",
        "Observed_End",
        "Active_Until",
        "Inactive_After",
        "Display_End",
        "Next_Expected_Date",
        "Price_Change_Date",
    ]
    for column in date_columns:
        timeline[column] = pd.to_datetime(timeline[column], errors="coerce", utc=True)

    overlapping = (timeline["Episode_Start"] <= end) & (timeline["Display_End"] >= start)
    timeline = timeline.loc[overlapping].copy()
    if timeline.empty:
        return timeline

    if scope == "Active and recent":
        current = lifecycles[lifecycles["Is_Current"].fillna(False)].copy()
        for column in ["Episode_Start", "Observed_End"]:
            current[column] = pd.to_datetime(current[column], errors="coerce", utc=True)
        visible_merchants = current.loc[
            (current["Status"] == "Active") | (current["Observed_End"] >= start),
            "Merchant",
        ]
        timeline = timeline[timeline["Merchant"].isin(visible_merchants)].copy()
        if timeline.empty:
            return timeline

    merchant_order = _lifecycle_merchant_order(lifecycles, timeline["Merchant"].unique())
    timeline["_Merchant_Order"] = timeline["Merchant"].map(
        {merchant: position for position, merchant in enumerate(merchant_order)}
    )
    timeline["Observed_Clip_Start"] = timeline["Episode_Start"].mask(
        timeline["Episode_Start"] < start,
        start,
    )
    timeline["Observed_Clip_End"] = timeline["Observed_End"].mask(
        timeline["Observed_End"] > end,
        end,
    )
    timeline["Tail_Clip_Start"] = timeline["Observed_End"].mask(
        timeline["Observed_End"] < start,
        start,
    )
    timeline["Tail_Clip_End"] = timeline["Display_End"].mask(
        timeline["Display_End"] > end,
        end,
    )
    timeline["Show_Endpoint"] = timeline["Observed_End"].between(start, end, inclusive="both")
    return timeline.sort_values(
        ["_Merchant_Order", "Episode_Start", "Episode"],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def create_lifecycle_timeline_chart(
    timeline: pd.DataFrame,
    *,
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
) -> alt.LayerChart:
    """Show observed merchant lifecycles and their inferred status tails."""
    start = _as_utc(range_start)
    end = _as_utc(range_end)
    merchant_order = timeline["Merchant"].drop_duplicates().astype(str).tolist()
    chart_height = max(260, len(merchant_order) * 26)
    date_scale = alt.Scale(domain=[start.isoformat(), end.isoformat()])
    status_scale = alt.Scale(
        domain=["Active", "Inactive"],
        range=[COLOR_ACTIVE, COLOR_INACTIVE],
    )
    y_encoding = alt.Y(
        "Merchant:N",
        title=None,
        sort=merchant_order,
        axis=alt.Axis(labelLimit=220),
    )
    color_encoding = alt.Color(
        "Status:N",
        title=None,
        scale=status_scale,
        legend=alt.Legend(orient="top"),
    )
    tooltips = [
        alt.Tooltip("Merchant:N", title="Merchant"),
        alt.Tooltip("Status:N", title="Status"),
        alt.Tooltip("Episode:O", title="Episode"),
        alt.Tooltip("Episode_Start:T", title="Started", format="%Y-%m-%d"),
        alt.Tooltip("Observed_End:T", title="Last observed", format="%Y-%m-%d"),
        alt.Tooltip("Display_End:T", title="Inferred through", format="%Y-%m-%d"),
        alt.Tooltip("Observed_Duration_Days:Q", title="Observed days", format=",.0f"),
        alt.Tooltip("Lifecycle_Duration_Days:Q", title="Lifecycle days", format=",.0f"),
        alt.Tooltip("Cadence:N", title="Cadence"),
        alt.Tooltip("Charge_Count:Q", title="Charges", format=",.0f"),
        alt.Tooltip("Latest_Charge_Amount:Q", title="Latest charge", format="$,.2f"),
        alt.Tooltip("Monthly_Run_Rate:Q", title="Est. monthly", format="$,.2f"),
        alt.Tooltip("Next_Expected_Date:T", title="Next expected", format="%Y-%m-%d"),
        alt.Tooltip("Price_Change:Q", title="Latest price change", format="+$,.2f"),
        alt.Tooltip("Price_Change_Date:T", title="Price change date", format="%Y-%m-%d"),
        alt.Tooltip("Category:N", title="Tiller category"),
        alt.Tooltip("Account:N", title="Account"),
    ]
    base = alt.Chart(timeline).encode(
        y=y_encoding,
        color=color_encoding,
        tooltip=tooltips,
    )
    inferred = (
        base.transform_filter(alt.datum.Tail_Clip_End >= alt.datum.Tail_Clip_Start)
        .mark_bar(size=12, opacity=0.28)
        .encode(
            x=alt.X(
                "Tail_Clip_Start:T",
                title=None,
                scale=date_scale,
                axis=alt.Axis(format="%b %Y", labelAngle=-35),
            ),
            x2="Tail_Clip_End:T",
        )
    )
    observed = (
        base.transform_filter(alt.datum.Observed_Clip_End >= alt.datum.Observed_Clip_Start)
        .mark_bar(size=12)
        .encode(
            x=alt.X("Observed_Clip_Start:T", title=None, scale=date_scale),
            x2="Observed_Clip_End:T",
        )
    )
    endpoint = (
        base.transform_filter(alt.datum.Show_Endpoint)
        .mark_point(
            filled=True,
            size=58,
        )
        .encode(x=alt.X("Observed_End:T", title=None, scale=date_scale))
    )
    latest_rule = (
        alt.Chart(pd.DataFrame({"Latest_Data_Date": [end]}))
        .mark_rule(
            color=COLOR_INACTIVE,
            strokeDash=[5, 5],
            strokeWidth=1.5,
        )
        .encode(
            x=alt.X("Latest_Data_Date:T", title=None, scale=date_scale),
            tooltip=[alt.Tooltip("Latest_Data_Date:T", title="Latest data", format="%Y-%m-%d")],
        )
    )
    return (inferred + observed + endpoint + latest_rule).properties(height=chart_height)  # type: ignore[no-any-return]


def _lifecycle_merchant_order(
    lifecycles: pd.DataFrame,
    visible_merchants: Iterable[object],
) -> list[str]:
    """Order timeline rows by lifecycle status, recency, and duration."""
    visible = {str(merchant) for merchant in visible_merchants}
    current = lifecycles[
        lifecycles["Is_Current"].fillna(False) & lifecycles["Merchant"].astype(str).isin(visible)
    ].copy()
    if current.empty:
        return sorted(visible)

    current["Episode_Start"] = pd.to_datetime(current["Episode_Start"], errors="coerce", utc=True)
    current["Display_End"] = pd.to_datetime(current["Display_End"], errors="coerce", utc=True)
    current["_Status_Order"] = current["Status"].map({"Active": 0, "Inactive": 1}).fillna(2)
    current["_Sort_Date"] = current["Episode_Start"].where(
        current["Status"] == "Active",
        current["Display_End"],
    )
    current = current.sort_values(
        ["_Status_Order", "_Sort_Date", "Lifecycle_Duration_Days", "Merchant"],
        ascending=[True, False, True, True],
    )
    ordered = current["Merchant"].astype(str).drop_duplicates().tolist()
    return [*ordered, *sorted(visible.difference(ordered))]


def _as_utc(value: pd.Timestamp) -> pd.Timestamp:
    """Return one timestamp normalized to UTC for lifecycle comparisons."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def create_spend_history_chart(history: pd.DataFrame) -> alt.LayerChart:
    """Show actual monthly subscription spend and its rolling average."""
    bars = (
        alt.Chart(history)
        .mark_bar(color=COLOR_SPEND, opacity=0.65)
        .encode(
            x=alt.X("Month:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=-35)),
            y=alt.Y("Actual_Spend:Q", title="Actual spend ($)", axis=alt.Axis(format="$,.0f")),
            tooltip=[
                alt.Tooltip("Month:T", title="Month", format="%B %Y"),
                alt.Tooltip("Actual_Spend:Q", title="Actual spend", format="$,.2f"),
            ],
        )
    )
    rolling = (
        alt.Chart(history)
        .mark_line(
            color=COLOR_ACTIVE,
            strokeWidth=3,
            point=True,
        )
        .encode(
            x=alt.X("Month:T", title=None),
            y=alt.Y("Rolling_Average:Q", title="Actual spend ($)"),
            tooltip=[
                alt.Tooltip("Month:T", title="Month", format="%B %Y"),
                alt.Tooltip("Rolling_Average:Q", title="3-month average", format="$,.2f"),
            ],
        )
    )
    return (bars + rolling).properties(height=280)  # type: ignore[no-any-return]


def create_active_history_chart(history: pd.DataFrame) -> alt.Chart:
    """Show the inferred number of active subscription merchants by month."""
    chart = (
        alt.Chart(history)
        .mark_line(
            color=COLOR_ACTIVE,
            strokeWidth=3,
            point=True,
        )
        .encode(
            x=alt.X("Month:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=-35)),
            y=alt.Y("Active_Merchants:Q", title="Active merchants", axis=alt.Axis(tickMinStep=1)),
            tooltip=[
                alt.Tooltip("Month:T", title="Month", format="%B %Y"),
                alt.Tooltip("Active_Merchants:Q", title="Active merchants"),
            ],
        )
        .properties(height=170)
    )
    return chart  # type: ignore[no-any-return]


def create_charge_history_chart(charges: pd.DataFrame) -> alt.Chart:
    """Show the exact charge amounts for one subscription merchant."""
    chart_data = charges.copy()
    chart_data["Charge"] = chart_data["Amount"].abs()
    chart = (
        alt.Chart(chart_data)
        .mark_line(
            color=COLOR_SPEND,
            point=alt.OverlayMarkDef(filled=True, size=75),
            strokeWidth=2,
        )
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Charge:Q", title="Charge amount ($)", axis=alt.Axis(format="$,.0f")),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%Y-%m-%d"),
                alt.Tooltip("Charge:Q", title="Charge", format="$,.2f"),
                alt.Tooltip("Category:N", title="Category"),
                alt.Tooltip("Account:N", title="Account"),
            ],
        )
        .properties(height=230)
    )
    return chart  # type: ignore[no-any-return]


def _table_data(inventory: pd.DataFrame, *, include_evidence: bool = False) -> pd.DataFrame:
    """Prepare concise, user-facing inventory columns."""
    columns = [
        "Merchant",
        "Monthly_Run_Rate",
        "Cadence",
        "Category",
        "First_Date",
        "Last_Date",
        "Next_Expected_Date",
        "Confidence",
        "Price_Change",
    ]
    if include_evidence:
        columns.append("Evidence")
    display = inventory[columns].copy()
    display["Price_Change"] = display["Price_Change"].map(
        lambda amount: mask_value(f"{'+' if float(amount) > 0 else '-'}${abs(float(amount)):,.2f}") if amount else ""
    )
    return display


def _render_inventory_table(
    inventory: pd.DataFrame,
    *,
    key: str,
    include_evidence: bool = False,
) -> str | None:
    """Render a selectable inventory table and return the selected merchant."""
    display = _table_data(inventory, include_evidence=include_evidence)
    event = cast(
        Any,
        value_safe_dataframe(
            display,
            key=key,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Merchant": st.column_config.TextColumn("Merchant", pinned=True),
                "Monthly_Run_Rate": st.column_config.NumberColumn("Est. monthly", format="$%.2f"),
                "Cadence": st.column_config.TextColumn("Cadence"),
                "Category": st.column_config.TextColumn("Tiller category"),
                "First_Date": st.column_config.DateColumn("Started", format="MMM YYYY"),
                "Last_Date": st.column_config.DateColumn("Last charge", format="YYYY-MM-DD"),
                "Next_Expected_Date": st.column_config.DateColumn("Next expected", format="YYYY-MM-DD"),
                "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=100),
                "Price_Change": st.column_config.TextColumn("Latest change"),
                "Evidence": st.column_config.TextColumn("Why it was flagged", width="large"),
            },
        ),
    )
    selected_rows = cast(list[int], event.selection.rows)
    if not selected_rows:
        return None
    return str(inventory.iloc[selected_rows[0]]["Merchant"])


def _render_merchant_detail(
    transactions: pd.DataFrame,
    inventory: pd.DataFrame,
    merchant: str,
    *,
    categories: list[str] | None,
    excluded_categories: list[str] | None = None,
) -> None:
    """Render evidence and transaction history for a selected merchant."""
    row = inventory[inventory["Merchant"] == merchant].iloc[0]
    charges = get_subscription_transactions(
        transactions,
        merchant,
        categories=categories,
        excluded_categories=excluded_categories,
    )
    accounts = sorted(charges["Account"].dropna().astype(str).unique())

    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.subheader(merchant)
            st.badge(str(row["Status"]), color=_status_color(str(row["Status"])))
            st.badge(str(row["Bundle_Type"]), color="blue")

        st.caption(
            f"Tiller category: {row['Category']} | Account{'s' if len(accounts) != 1 else ''}: {', '.join(accounts)}"
        )

        metric_row = st.container(horizontal=True)
        metric_row.metric("Charges", mask_value(f"{int(row['Charge_Count']):,}"), border=True)
        metric_row.metric("Est. monthly", _format_optional_currency(row["Monthly_Run_Rate"]), border=True)
        metric_row.metric(
            "Last 12 months",
            mask_value(f"${float(row['Trailing_12_Month_Spend']):,.2f}"),
            border=True,
        )
        metric_row.metric("Cadence", str(row["Cadence"]), border=True)

        if _is_missing_number(row["Monthly_Run_Rate"]):
            st.caption("Not enough history to estimate a monthly run rate yet.")
        elif str(row["Bundle_Type"]) == "Merchant bundle":
            st.caption("Monthly cost is the merchant's average actual spend over up to 12 calendar months.")

        price_change = float(row["Price_Change"])
        if price_change > 0:
            st.error(
                f"Latest detected price increase: {mask_value(f'+${price_change:,.2f}')} on "
                f"{pd.Timestamp(row['Price_Change_Date']):%B %d, %Y}.",
                icon=":material/trending_up:",
            )
        elif price_change < 0:
            st.success(
                f"Latest detected price decrease: {mask_value(f'-${abs(price_change):,.2f}')} on "
                f"{pd.Timestamp(row['Price_Change_Date']):%B %d, %Y}.",
                icon=":material/trending_down:",
            )

        value_safe_altair_chart(create_charge_history_chart(charges), width="stretch")
        monthly_totals = (
            charges.assign(Month=charges["Date"].map(lambda value: _month_label(value)))
            .groupby("Month")["Amount_Abs"]
            .sum()
            .rename("Actual_Spend")
            .reset_index()
            .sort_values("Month", ascending=False)
        )
        with st.expander("Monthly totals", icon=":material/calendar_month:"):
            value_safe_dataframe(
                monthly_totals,
                width="stretch",
                hide_index=True,
                column_config={
                    "Month": st.column_config.DateColumn("Month", format="MMM YYYY"),
                    "Actual_Spend": st.column_config.NumberColumn("Actual spend", format="$%.2f"),
                },
            )
        with st.expander("Individual charges", icon=":material/receipt_long:"):
            value_safe_dataframe(
                charges.drop(columns=["Amount_Abs", "Merchant", "Month_Key"], errors="ignore"),
                width="stretch",
                height=350,
                hide_index=True,
                column_config=get_transaction_column_config(),
            )


def _format_optional_currency(value: object) -> str:
    """Format nullable currency values without implying false precision."""
    return "Pending" if _is_missing_number(value) else mask_value(f"${float(cast(float, value)):,.2f}")


def _is_missing_number(value: object) -> bool:
    """Return whether a dataframe scalar is a missing numeric value."""
    return value is None or bool(pd.isna(cast(float, value)))


def _month_label(value: pd.Timestamp) -> pd.Timestamp:
    """Return a timezone-naive month start for display grouping."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.to_period("M").to_timestamp()


def filter_subscription_history(history: pd.DataFrame, lookback: str) -> pd.DataFrame:
    """Return the requested number of trailing calendar-month rows."""
    months = {
        "Last 3 months": 3,
        "Last 6 months": 6,
        "Last 12 months": 12,
        "Last 24 months": 24,
    }.get(lookback)
    return history.tail(months) if months else history


def _status_color(status: str) -> Literal["green", "gray"]:
    """Map inferred lifecycle status to a restrained badge color."""
    if status == "Active":
        return "green"
    return "gray"


def prepare_active_inventory(
    inventory: pd.DataFrame,
    lifecycles: pd.DataFrame,
) -> pd.DataFrame:
    """Show active merchants by the start of their current lifecycle episode."""
    active = inventory[inventory["Status"] == "Active"].copy()
    if active.empty or lifecycles.empty:
        return active.sort_values(["First_Date", "Merchant"], ascending=[False, True])

    current_starts = (
        lifecycles[lifecycles["Is_Current"].fillna(False)]
        .drop_duplicates("Merchant", keep="last")
        .set_index("Merchant")["Episode_Start"]
    )
    active["First_Date"] = active["Merchant"].map(current_starts).fillna(active["First_Date"])
    return active.sort_values(["First_Date", "Merchant"], ascending=[False, True])


@st.cache_data(show_spinner=False)
def _analyze_subscription_data(
    transactions: pd.DataFrame,
    subscription_categories: tuple[str, ...],
    discovery_exclusions: tuple[str, ...],
    discovery_confidence: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, SubscriptionSummary]:
    """Build all subscription views once for a stable set of inputs."""
    categories = list(subscription_categories)
    inventory = build_subscription_inventory(transactions, categories)
    lifecycles = build_subscription_lifecycles(transactions, inventory, categories)
    candidates = find_subscription_candidates(
        transactions,
        categories,
        excluded_categories=list(discovery_exclusions),
        min_confidence=discovery_confidence,
    )
    history = build_subscription_history(
        transactions,
        inventory,
        categories,
        lifecycles=lifecycles,
    )
    summary = summarize_subscriptions(inventory, transactions, categories)
    return inventory, lifecycles, candidates, history, summary


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    """Render the subscription inventory dashboard."""
    transactions = transactions_spreadsheet.scrubbed_df.copy()
    st.title("Subscriptions")
    if transactions.empty:
        st.info(
            "No transactions are available. Refresh the Tiller data to build a subscription inventory.",
            icon=":material/info:",
        )
        return

    latest_data_date = pd.Timestamp(transactions["Date"].max())
    all_categories = transactions_spreadsheet.get_all_categories()
    default_subscription_categories = [category for category in all_categories if "subscription" in category.lower()]
    default_discovery_exclusions = [
        category
        for category in DEFAULT_EXCLUDE_CATEGORIES_SUBSCRIPTIONS
        if category in all_categories and not category.lower().endswith("bill")
    ]

    st.caption(
        f"Transaction history through {latest_data_date:%B} {latest_data_date.day}, {latest_data_date:%Y}. "
        "Subscription categories come from Tiller. Activity stays Active until the full cadence-based "
        "inactivity window passes; cadence and future charges are inferred from your transaction history."
    )
    latest_utc = pd.to_datetime(latest_data_date, utc=True)
    days_stale = (pd.Timestamp.now(tz="UTC").normalize() - latest_utc.normalize()).days
    if days_stale > 45:
        st.warning(
            f"The newest transaction is {mask_value(str(days_stale))} days old. Statuses and forecasts may be stale.",
            icon=":material/history:",
        )

    with st.expander("Subscription settings", icon=":material/tune:"):
        subscription_categories = st.multiselect(
            "Tiller subscription categories",
            options=all_categories,
            default=default_subscription_categories,
            help="These categories define the known subscription inventory.",
        )
        discovery_exclusions = st.multiselect(
            "Additional discovery exclusions",
            options=[category for category in all_categories if category not in subscription_categories],
            default=default_discovery_exclusions,
            help="Explicit bill, transfer, loan, rent, and investment categories are always excluded.",
        )
        discovery_confidence = st.slider(
            "Minimum discovery confidence",
            min_value=70,
            max_value=100,
            value=80,
            step=5,
        )

    inventory, lifecycles, candidates, history, summary = _analyze_subscription_data(
        transactions,
        tuple(subscription_categories),
        tuple(discovery_exclusions),
        discovery_confidence,
    )

    annual_change = summary["annual_change_pct"]
    metric_row = st.container(horizontal=True)
    metric_row.metric(
        "Active subscriptions",
        mask_value(f"{summary['active_count']:,}"),
        border=True,
    )
    metric_row.metric(
        "Estimated monthly run rate",
        mask_value(f"${summary['monthly_run_rate']:,.2f}"),
        border=True,
    )
    metric_row.metric(
        "Spent in the last 12 months",
        mask_value(f"${summary['trailing_12_month_spend']:,.2f}"),
        border=True,
    )
    metric_row.metric(
        "12-month change",
        "Not available" if annual_change is None else mask_value(f"{annual_change:+.1f}%"),
        delta=(
            None
            if annual_change is None
            else mask_value(f"${summary['trailing_12_month_spend'] - summary['prior_12_month_spend']:+,.2f}")
        ),
        delta_color="inverse",
        border=True,
    )
    if summary["pending_estimate_count"]:
        st.caption(
            f"{mask_value(str(summary['pending_estimate_count']))} active subscription"
            f"{'s are' if summary['pending_estimate_count'] != 1 else ' is'} excluded from the run rate "
            "until more charge history is available."
        )

    st.subheader("Active subscriptions")
    active = prepare_active_inventory(inventory, lifecycles)
    if active.empty:
        st.info(
            "No active subscriptions are present in the selected Tiller categories.",
            icon=":material/info:",
        )
    else:
        st.caption("Newest subscriptions appear first. Select a row to inspect its charges.")
        selected = _render_inventory_table(active, key="active_subscriptions")
        if selected:
            _render_merchant_detail(
                transactions,
                active,
                selected,
                categories=subscription_categories,
            )

    st.subheader("Subscription history")
    if history.empty:
        st.info(
            (
                "Select at least one Tiller subscription category to see spending history."
                if not subscription_categories
                else "No subscription expenses were found in the selected Tiller categories."
            ),
            icon=":material/info:",
        )
    else:
        controls = st.container(horizontal=True, vertical_alignment="bottom")
        lookback = controls.selectbox(
            "Lookback",
            options=[
                "Last 3 months",
                "Last 6 months",
                "Last 12 months",
                "Last 24 months",
                "All history",
            ],
            index=2,
            key="subscription_history_lookback",
        )
        scope_choice = controls.segmented_control(
            "Timeline scope",
            options=["Active and recent", "All merchants"],
            default="Active and recent",
            key="subscription_timeline_scope",
        )
        st.caption(
            "Lookback affects these charts only; status, cadence, forecasts, and discovery use all available "
            "transactions. Active and recent includes active merchants plus inactive merchants last charged "
            "within the selected range."
        )
        visible_history = filter_subscription_history(history, str(lookback))
        range_start = _as_utc(pd.Timestamp(visible_history["Month"].min()))
        range_end = _as_utc(latest_data_date)
        visible_lifecycles = prepare_lifecycle_timeline(
            lifecycles,
            range_start=range_start,
            range_end=range_end,
            scope=cast(TimelineScope, scope_choice or "Active and recent"),
        )
        with st.container(border=True):
            st.markdown("**Subscription lifecycles**")
            st.caption("Solid bars show observed charge history; translucent tails show the inferred lifecycle.")
            if visible_lifecycles.empty:
                st.info(
                    "No subscription lifecycles overlap this history range.",
                    icon=":material/info:",
                )
            else:
                value_safe_altair_chart(
                    create_lifecycle_timeline_chart(
                        visible_lifecycles,
                        range_start=range_start,
                        range_end=range_end,
                    ),
                    width="stretch",
                )
            st.markdown("**Actual spend and 3-month average**")
            value_safe_altair_chart(create_spend_history_chart(visible_history), width="stretch")
            st.markdown("**Active subscription merchants**")
            value_safe_altair_chart(create_active_history_chart(visible_history), width="stretch")

    st.subheader("Potential subscriptions")
    st.caption(
        "Strong recurring patterns outside your subscription categories. "
        "Bill categories and fixed financial obligations are not included."
    )
    if candidates.empty:
        st.caption("No strong uncategorized subscription candidates were found.")
    else:
        selected = _render_inventory_table(
            candidates,
            key="subscription_candidates",
            include_evidence=True,
        )
        if selected:
            _render_merchant_detail(
                transactions,
                candidates,
                selected,
                categories=None,
                excluded_categories=[*subscription_categories, *discovery_exclusions],
            )

    inactive = inventory[inventory["Status"] == "Inactive"].sort_values(
        ["Last_Date", "Merchant"], ascending=[False, True]
    )
    st.subheader("Inactive subscriptions")
    if inactive.empty:
        st.caption("No inactive subscriptions are present in the selected categories.")
    else:
        st.caption("Most recently seen subscriptions appear first.")
        selected = _render_inventory_table(inactive, key="inactive_subscriptions")
        if selected:
            _render_merchant_detail(
                transactions,
                inactive,
                selected,
                categories=subscription_categories,
            )


def main() -> None:
    """Streamlit entry point for the subscriptions page."""
    st.set_page_config(
        page_title="Subscriptions",
        page_icon=":material/subscriptions:",
        layout="wide",
    )
    render_data_refresh_controls()
    configure_page(load_transactions_data())


if __name__ == "__main__":
    main()
