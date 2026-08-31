from collections.abc import Mapping
from typing import Literal, cast

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from src.analysis.income import (
    build_income_expense_ledger,
    calculate_savings_summary,
    summarize_income_expense_ledger,
)
from src.constants import (
    COLOR_EXPENSE,
    COLOR_INCOME,
    COLOR_PLACEHOLDER,
    COLOR_SAVINGS,
)
from src.config import get_settings
from src.custom_types import SavingsSummary
from src.filters import render_income_expense_filters
from src.page_helpers import render_data_refresh_controls
from src.reporting_periods import month_lookback_options, rolling_month_window
from src.spreadsheet import TransactionsSpreadsheet, load_transactions_data
from src.value_visibility import mask_value, value_safe_altair_chart, value_safe_dataframe


CALCULATION_VIEWS = ["Regular", "Actual"]
CASH_FLOW_SELECTION = "cash_month_pick"
SAVINGS_RATE_SELECTION = "rate_month_pick"
MONTH_SELECTIONS = (CASH_FLOW_SELECTION, SAVINGS_RATE_SELECTION)
DETAIL_MONTH_KEY = "income_detail_month"
CHART_EPOCH_KEY = "income_chart_epoch"


def _format_currency(value: float) -> str:
    sign = "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _format_money_delta(value: float, comparison_months: int) -> str:
    sign = "+" if value > 0 else "-" if value < 0 else ""
    amount = mask_value(f"{sign}${abs(value):,.0f}")
    return f"{amount} vs previous {comparison_months} months"


def _format_rate(value: float | None) -> str:
    return "—" if value is None else mask_value(f"{value:.1f}%")


def _format_rate_delta(value: float | None, comparison_months: int) -> str | None:
    if value is None:
        return None
    sign = "+" if value > 0 else ""
    rate = mask_value(f"{sign}{value:.1f} pts")
    return f"{rate} vs previous {comparison_months} months"


def _render_summary_metrics(
    summary: SavingsSummary,
    previous: SavingsSummary | None,
    comparison_months: int,
) -> None:
    months = summary["num_months"]
    average_income = summary["total_income"] / months if months else 0.0
    average_expenses = summary["total_net_expenses"] / months if months else 0.0
    average_surplus = summary["average_monthly_surplus"]

    previous_income = None
    previous_expenses = None
    previous_surplus = None
    previous_rate = None
    if previous is not None:
        previous_months = previous["num_months"]
        previous_income = previous["total_income"] / previous_months if previous_months else 0.0
        previous_expenses = previous["total_net_expenses"] / previous_months if previous_months else 0.0
        previous_surplus = previous["average_monthly_surplus"]
        if summary["weighted_savings_rate"] is not None and previous["weighted_savings_rate"] is not None:
            previous_rate = summary["weighted_savings_rate"] - previous["weighted_savings_rate"]

    with st.container(horizontal=True):
        st.metric(
            "Avg monthly income",
            _format_currency(average_income),
            (
                _format_money_delta(
                    average_income - previous_income,
                    comparison_months,
                )
                if previous_income is not None
                else None
            ),
            border=True,
        )
        st.metric(
            "Avg monthly spending",
            _format_currency(average_expenses),
            (
                _format_money_delta(
                    average_expenses - previous_expenses,
                    comparison_months,
                )
                if previous_expenses is not None
                else None
            ),
            delta_color="inverse",
            border=True,
        )
        st.metric(
            "Avg monthly surplus",
            _format_currency(average_surplus),
            (
                _format_money_delta(
                    average_surplus - previous_surplus,
                    comparison_months,
                )
                if previous_surplus is not None
                else None
            ),
            border=True,
        )
        st.metric(
            "Savings rate",
            _format_rate(summary["weighted_savings_rate"]),
            _format_rate_delta(previous_rate, comparison_months),
            border=True,
        )


def create_cash_flow_history_chart(
    monthly: pd.DataFrame,
    target_rate: int,
    selected_month: str,
) -> alt.VConcatChart:
    """Build the coordinated cash-flow and savings-rate history chart."""
    chart_data = monthly.copy()
    chart_data["Month_Key"] = chart_data["Month"].astype(str)
    chart_data["Month_Date"] = pd.to_datetime(chart_data["Month"] + "-01")
    chart_data["Spending_Chart"] = -chart_data["Net_Expenses"]
    month_ticks = chart_data["Month_Date"].dt.strftime("%Y-%m-%d").tolist()

    bar_data = chart_data[["Month_Key", "Month_Date", "Income", "Spending_Chart"]].melt(
        id_vars=["Month_Key", "Month_Date"],
        value_vars=["Income", "Spending_Chart"],
        var_name="Series",
        value_name="Amount",
    )
    bar_data["Series"] = bar_data["Series"].replace({"Spending_Chart": "Spending"})

    cash_month_pick = alt.selection_point(
        name=CASH_FLOW_SELECTION,
        fields=["Month_Key"],
        on="click",
        toggle=False,
        clear="dblclick",
    )
    rate_month_pick = alt.selection_point(
        name=SAVINGS_RATE_SELECTION,
        fields=["Month_Key"],
        on="click",
        toggle=False,
        clear="dblclick",
    )
    month_axis = alt.X(
        "Month_Date:T",
        title=None,
        axis=alt.Axis(
            format="%b %Y",
            labelAngle=-35,
            labelOverlap=True,
            values=month_ticks,
        ),
    )
    hidden_month_axis = alt.X(
        "Month_Date:T",
        title=None,
        axis=alt.Axis(labels=False, ticks=False),
    )

    bars = (
        alt.Chart(bar_data)
        .mark_bar(size=18)
        .encode(
            x=hidden_month_axis,
            y=alt.Y(
                "Amount:Q",
                title="Monthly cash flow ($)",
                axis=alt.Axis(format="$~s"),
            ),
            color=alt.Color(
                "Series:N",
                scale=alt.Scale(
                    domain=["Income", "Spending"],
                    range=[COLOR_INCOME, COLOR_EXPENSE],
                ),
                legend=alt.Legend(orient="top", title=None),
            ),
            opacity=alt.value(0.85),
            tooltip=[
                alt.Tooltip("Month_Key:N", title="Month"),
                alt.Tooltip("Series:N", title="Type"),
                alt.Tooltip("Amount:Q", title="Cash flow", format="$,.2f"),
            ],
        )
    )
    surplus = (
        alt.Chart(chart_data)
        .mark_line(color=COLOR_SAVINGS, strokeWidth=3, point=True)
        .encode(
            x=hidden_month_axis,
            y=alt.Y("Cash_Flow_Surplus:Q"),
            tooltip=[
                alt.Tooltip("Month_Key:N", title="Month"),
                alt.Tooltip("Income:Q", title="Income", format="$,.2f"),
                alt.Tooltip("Net_Expenses:Q", title="Spending", format="$,.2f"),
                alt.Tooltip(
                    "Cash_Flow_Surplus:Q",
                    title="Net cash flow",
                    format="$,.2f",
                ),
                alt.Tooltip(
                    "Savings_Rate:Q",
                    title="Savings rate",
                    format=".1f",
                ),
            ],
        )
    )
    cash_zero = (
        alt.Chart(pd.DataFrame({"Value": [0]})).mark_rule(color=COLOR_PLACEHOLDER, opacity=0.5).encode(y="Value:Q")
    )
    click_target = (
        alt.Chart(chart_data)
        .mark_point(opacity=0.001, size=1600)
        .encode(x=hidden_month_axis)
        .add_params(cash_month_pick)
    )
    selected_data = chart_data[chart_data["Month_Key"] == selected_month]
    selected_cash_month = (
        alt.Chart(selected_data)
        .mark_rule(color=COLOR_PLACEHOLDER, opacity=0.75, strokeWidth=2)
        .encode(x=hidden_month_axis)
    )
    cash_flow = alt.layer(bars, surplus, cash_zero, click_target, selected_cash_month).properties(height=300)

    rate = (
        alt.Chart(chart_data)
        .mark_line(color=COLOR_SAVINGS, strokeWidth=2.5, point=True)
        .encode(
            x=month_axis,
            y=alt.Y(
                "Savings_Rate:Q",
                title="Savings rate",
                axis=alt.Axis(format=".0f"),
                scale=alt.Scale(zero=True),
            ),
            tooltip=[
                alt.Tooltip("Month_Key:N", title="Month"),
                alt.Tooltip("Savings_Rate:Q", title="Savings rate", format=".1f"),
            ],
        )
    )
    target = (
        alt.Chart(pd.DataFrame({"Target": [target_rate]}))
        .mark_rule(color=COLOR_PLACEHOLDER, strokeDash=[5, 5], strokeWidth=2)
        .encode(
            y="Target:Q",
            tooltip=[alt.Tooltip("Target:Q", title="Target", format=".0f")],
        )
    )
    rate_zero = (
        alt.Chart(pd.DataFrame({"Value": [0]})).mark_rule(color=COLOR_PLACEHOLDER, opacity=0.35).encode(y="Value:Q")
    )
    rate_click_target = (
        alt.Chart(chart_data).mark_point(opacity=0.001, size=1600).encode(x=month_axis).add_params(rate_month_pick)
    )
    selected_rate_month = (
        alt.Chart(selected_data).mark_rule(color=COLOR_PLACEHOLDER, opacity=0.75, strokeWidth=2).encode(x=month_axis)
    )
    savings_rate = alt.layer(
        rate,
        target,
        rate_zero,
        rate_click_target,
        selected_rate_month,
    ).properties(height=135)

    return cast(
        alt.VConcatChart,
        alt.vconcat(cash_flow, savings_rate, spacing=8).resolve_scale(x="shared"),
    )


def _selected_month_from_event(event: object) -> str | None:
    """Extract the selected month from a Streamlit Vega-Lite event."""
    if not isinstance(event, Mapping):
        return None
    selection = event.get("selection", {})
    if not isinstance(selection, Mapping):
        return None
    for selection_name in MONTH_SELECTIONS:
        selected = selection.get(selection_name)
        if isinstance(selected, list) and selected:
            record = selected[0]
            if isinstance(record, Mapping) and "Month_Key" in record:
                return str(record["Month_Key"])
        if isinstance(selected, Mapping):
            months = selected.get("Month_Key", [])
            if isinstance(months, list) and months:
                return str(months[0])
    return None


def _reset_chart_selection() -> None:
    st.session_state[CHART_EPOCH_KEY] = st.session_state.get(CHART_EPOCH_KEY, 0) + 1


def _month_label(month: str) -> str:
    return pd.Period(month, freq="M").strftime("%B %Y")


def _transaction_table(transactions: pd.DataFrame, *, show_reason: bool) -> None:
    columns = [
        "Date",
        "Full Description",
        "Type",
        "Category",
        "Group",
        "Account",
        "Amount",
    ]
    if show_reason:
        columns.append("Exclusion_Reason")
    available = [column for column in columns if column in transactions]
    display = (
        transactions.assign(
            _Sort_Amount=pd.to_numeric(transactions["Amount"], errors="coerce").abs(),
        )
        .sort_values(
            ["_Sort_Amount", "Date"],
            ascending=[False, False],
        )[available]
        .copy()
    )
    display = display.rename(
        columns={
            "Full Description": "Description",
            "Exclusion_Reason": "Exclusion reason",
        }
    )
    value_safe_dataframe(
        display,
        width="stretch",
        hide_index=True,
        height=min(500, 38 * (len(display) + 1) + 8),
        column_config={
            "Date": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
            "Description": st.column_config.TextColumn("Description", width="large"),
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "Exclusion reason": st.column_config.TextColumn(
                "Exclusion reason",
                width="large",
            ),
        },
    )


def _category_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame()
    summary = (
        transactions.groupby(["Type", "Group", "Category"], dropna=False)
        .agg(Transactions=("Amount", "size"), Amount=("Amount", "sum"))
        .reset_index()
    )
    summary["_Sort"] = summary["Amount"].abs()
    return summary.sort_values("_Sort", ascending=False).drop(columns="_Sort")


def _render_largest_transactions(transactions: pd.DataFrame) -> None:
    badges: list[tuple[str, Literal["green", "red"]]] = []
    drivers: list[tuple[str, str, Literal["green", "red"]]] = [
        ("Income", "Largest income", "green"),
        ("Expense", "Largest expense", "red"),
    ]
    for transaction_type, label, color in drivers:
        matching = transactions[transactions["Type"] == transaction_type]
        if matching.empty:
            continue
        row = matching.assign(_Magnitude=matching["Amount"].abs()).sort_values("_Magnitude", ascending=False).iloc[0]
        raw_description = row.get("Full Description", row.get("Description", "Transaction"))
        description = "Transaction" if pd.isna(raw_description) else str(raw_description)
        badges.append(
            (
                f"{label} · {_format_currency(abs(float(row['Amount'])))} · {description}",
                color,
            )
        )

    with st.container(horizontal=True):
        for label, color in badges:
            st.badge(label, color=color)


def _render_month_detail(
    ledger: pd.DataFrame,
    monthly: pd.DataFrame,
    chart_event: object,
) -> None:
    months = monthly["Month"].astype(str).tolist()
    selected_from_chart = _selected_month_from_event(chart_event)
    if selected_from_chart in months and selected_from_chart != st.session_state.get(DETAIL_MONTH_KEY):
        st.session_state[DETAIL_MONTH_KEY] = selected_from_chart
        st.rerun()
    if st.session_state.get(DETAIL_MONTH_KEY) not in months:
        st.session_state[DETAIL_MONTH_KEY] = months[-1]

    with st.container(border=True):
        selected_month = st.selectbox(
            "Month detail",
            options=list(reversed(months)),
            format_func=_month_label,
            key=DETAIL_MONTH_KEY,
            on_change=_reset_chart_selection,
            persist_state="page",
        )
        month_row = monthly[monthly["Month"] == selected_month].iloc[0]
        rate = month_row["Savings_Rate"]
        with st.container(horizontal=True):
            st.metric("Income", _format_currency(float(month_row["Income"])), border=True)
            st.metric(
                "Spending",
                _format_currency(float(month_row["Net_Expenses"])),
                border=True,
            )
            st.metric(
                "Net cash flow",
                _format_currency(float(month_row["Cash_Flow_Surplus"])),
                border=True,
            )
            st.metric(
                "Savings rate",
                _format_rate(None if pd.isna(rate) else float(rate)),
                border=True,
            )

        month_ledger = ledger[ledger["Month"] == selected_month]
        included = month_ledger[month_ledger["Included"]]
        excluded = month_ledger[~month_ledger["Included"]]
        included_tab, excluded_tab = st.tabs(
            [
                f"Included ({len(included)})",
                f"Excluded ({len(excluded)})",
            ]
        )
        with included_tab:
            if included.empty:
                st.info("No transactions are included for this month.")
            else:
                _render_largest_transactions(included)
                st.markdown("**By category**")
                value_safe_dataframe(
                    _category_summary(included),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Transactions": st.column_config.NumberColumn(
                            "Transactions",
                            format="%d",
                        ),
                        "Amount": st.column_config.NumberColumn(
                            "Cash flow",
                            format="$%.2f",
                        ),
                    },
                )
                st.markdown("**Transactions**")
                _transaction_table(included, show_reason=False)
        with excluded_tab:
            if excluded.empty:
                st.info("No transactions are excluded for this month.")
            else:
                _transaction_table(excluded, show_reason=True)


def _render_monthly_totals(monthly: pd.DataFrame) -> None:
    with st.expander("Monthly totals", icon=":material/table_chart:"):
        display = monthly[
            [
                "Month",
                "Income",
                "Net_Expenses",
                "Cash_Flow_Surplus",
                "Savings_Rate",
            ]
        ].copy()
        value_safe_dataframe(
            display,
            width="stretch",
            hide_index=True,
            column_config={
                "Month": st.column_config.TextColumn("Month"),
                "Income": st.column_config.NumberColumn("Income", format="$%.2f"),
                "Net_Expenses": st.column_config.NumberColumn(
                    "Spending",
                    format="$%.2f",
                ),
                "Cash_Flow_Surplus": st.column_config.NumberColumn(
                    "Net cash flow",
                    format="$%.2f",
                ),
                "Savings_Rate": st.column_config.NumberColumn(
                    "Savings rate",
                    format="%.1f%%",
                ),
            },
        )


def _transaction_options(
    transactions: pd.DataFrame,
) -> tuple[list[str], list[str], list[str]]:
    def values(transaction_type: str, column: str) -> list[str]:
        series = transactions.loc[transactions["Type"] == transaction_type, column]
        return sorted(series.dropna().astype(str).unique().tolist())

    return (
        values("Income", "Category"),
        values("Expense", "Category"),
        values("Expense", "Group"),
    )


def _previous_period(
    start_month: str,
    lookback_months: int,
) -> tuple[str, str]:
    start = pd.Period(start_month, freq="M") - lookback_months
    return str(start), start_month


def _has_full_period_history(
    transactions: pd.DataFrame,
    start_month: str,
) -> bool:
    if "Date" not in transactions:
        return False
    dates = pd.to_datetime(
        transactions["Date"],
        errors="coerce",
        utc=True,
    ).dropna()
    if dates.empty:
        return False
    period_start = pd.Timestamp(f"{start_month}-01", tz="UTC")
    return bool(dates.min() <= period_start)


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    *,
    lookback: str,
    calculation_view: str,
    adjust_slot: DeltaGenerator,
) -> None:
    """Render the interactive income and savings calculation."""
    transactions = transactions_spreadsheet.scrubbed_df.copy()
    income_categories, expense_categories, expense_groups = _transaction_options(transactions)
    with adjust_slot:
        filters = render_income_expense_filters(
            income_categories,
            expense_categories,
            expense_groups,
            view=calculation_view,
        )

    lookback_months = month_lookback_options(get_settings().reporting.lookback_months)[lookback]
    start_month, current_month = rolling_month_window(lookback_months)
    end_month = str(pd.Period(current_month, freq="M") + 1)
    ledger = build_income_expense_ledger(
        transactions,
        filters,
        start_month=start_month,
        end_month=end_month,
    )
    monthly = summarize_income_expense_ledger(
        ledger,
        start_month=start_month,
        end_month=end_month,
    )

    if ledger.empty:
        st.info("No categorized income or expense transactions fall in this period.")
        return

    prior_start, prior_end = _previous_period(start_month, lookback_months)
    prior_ledger = build_income_expense_ledger(
        transactions,
        filters,
        start_month=prior_start,
        end_month=prior_end,
    )
    prior_monthly = summarize_income_expense_ledger(
        prior_ledger,
        start_month=prior_start,
        end_month=prior_end,
    )
    summary = calculate_savings_summary(monthly)
    previous_summary = (
        calculate_savings_summary(prior_monthly) if _has_full_period_history(transactions, prior_start) else None
    )
    _render_summary_metrics(summary, previous_summary, lookback_months)

    included_count = int(ledger["Included"].sum())
    excluded_count = len(ledger) - included_count
    excluded = ledger[~ledger["Included"]]
    excluded_income = float(excluded.loc[excluded["Type"] == "Income", "Amount"].sum())
    excluded_spending = float(-excluded.loc[excluded["Type"] == "Expense", "Amount"].sum())
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.subheader("Monthly cash flow")
            positive_color: Literal["green", "orange"] = (
                "green" if summary["positive_surplus_months"] >= summary["num_months"] / 2 else "orange"
            )
            st.badge(
                f"{mask_value(str(summary['positive_surplus_months']))} of "
                f"{mask_value(str(summary['num_months']))} positive months",
                color=positive_color,
            )
            if excluded_count:
                st.badge(
                    (
                        f"{mask_value(str(excluded_count))} excluded · "
                        f"{_format_currency(excluded_income)} income · "
                        f"{_format_currency(excluded_spending)} spending"
                    ),
                    color="gray",
                )

        chart_event: object
        if included_count:
            st.session_state.setdefault(CHART_EPOCH_KEY, 0)
            months = monthly["Month"].astype(str).tolist()
            if st.session_state.get(DETAIL_MONTH_KEY) not in months:
                st.session_state[DETAIL_MONTH_KEY] = months[-1]
            chart = create_cash_flow_history_chart(
                monthly,
                filters["target_rate"],
                str(st.session_state[DETAIL_MONTH_KEY]),
            )
            chart_event = value_safe_altair_chart(
                chart,
                width="stretch",
                key=f"income_history_{st.session_state[CHART_EPOCH_KEY]}",
                on_select="rerun",
                selection_mode=MONTH_SELECTIONS,
            )
        else:
            st.info("All transactions in this period are excluded from this calculation.")
            chart_event = {}

    _render_month_detail(ledger, monthly, chart_event)
    _render_monthly_totals(monthly)


def main() -> None:
    """Streamlit entry point for the Income & Savings page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    st.title("Income and savings")

    settings = get_settings()
    lookback_options = month_lookback_options(settings.reporting.lookback_months)
    default_lookback = next(
        label for label, months in lookback_options.items() if months == settings.reporting.default_lookback_months
    )
    with st.container(horizontal=True, vertical_alignment="bottom"):
        lookback = st.segmented_control(
            "Time frame",
            options=list(lookback_options),
            default=default_lookback,
            required=True,
            key="income_lookback",
            persist_state="page",
        )
        calculation_view = st.segmented_control(
            "Calculation",
            options=CALCULATION_VIEWS,
            default=settings.income_savings.default_view.title(),
            required=True,
            key="income_calculation_view",
            help=(
                "Regular starts with your usual one-off exclusions. Actual starts "
                "with everything included. You can adjust either view directly."
            ),
            persist_state="page",
        )
        adjust_slot = st.empty()

    transactions_spreadsheet = load_transactions_data()
    configure_page(
        transactions_spreadsheet,
        lookback=str(lookback),
        calculation_view=str(calculation_view),
        adjust_slot=adjust_slot,
    )


if __name__ == "__main__":
    main()
