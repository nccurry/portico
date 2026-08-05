"""Tiller-backed group budget dashboard."""

import calendar
from collections.abc import Sequence
from typing import cast

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis.budget import (
    build_group_budget_table,
    filter_budget_transactions,
    get_budget_vs_actual,
    get_group_budget_vs_actual,
    get_trailing_group_guidance,
    get_ytd_group_budget_vs_actual,
    summarize_budget,
)
from src.constants import (
    COLOR_BUDGET,
    COLOR_OVER_BUDGET,
    COLOR_UNDER_BUDGET,
    DEFAULT_BUDGET_GROUPS,
    DEFAULT_EXPENSE_THRESHOLD,
)
from src.custom_types import BudgetFilters
from src.filters import render_budget_filters
from src.page_helpers import render_data_refresh_controls
from src.spreadsheet import load_categories_data, load_transactions_data


def create_budget_group_chart(df: pd.DataFrame, title: str) -> alt.Chart:
    """Build a horizontal group-spending chart with budget target ticks."""
    if df.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(text=alt.value("No budget data"))  # type: ignore[no-any-return]

    chart_df = df[["Group", "Budget", "Spent"]].copy()
    chart_df["Over"] = chart_df["Spent"] > chart_df["Budget"]
    group_order = chart_df.sort_values("Spent", ascending=False)["Group"].tolist()

    bars = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            y=alt.Y("Group:N", sort=group_order, title=None),
            x=alt.X("Spent:Q", title="Amount ($)"),
            color=alt.condition(
                alt.datum.Over,
                alt.value(COLOR_OVER_BUDGET),
                alt.value(COLOR_UNDER_BUDGET),
            ),
            tooltip=[
                alt.Tooltip("Group:N"),
                alt.Tooltip("Spent:Q", format="$,.2f", title="Spent"),
                alt.Tooltip("Budget:Q", format="$,.2f", title="Budget"),
            ],
        )
    )
    targets = (
        alt.Chart(chart_df)
        .mark_tick(color=COLOR_BUDGET, thickness=3, size=24)
        .encode(
            y=alt.Y("Group:N", sort=group_order),
            x=alt.X("Budget:Q"),
            tooltip=[alt.Tooltip("Budget:Q", format="$,.2f", title="Budget")],
        )
    )
    return (bars + targets).properties(height=max(240, len(chart_df) * 55), title=title)  # type: ignore[no-any-return]


def _categories_sheet_url() -> str | None:
    """Return the configured Categories sheet URL without exposing credentials."""
    try:
        config = st.secrets["connections"]["categories"]
        url = str(config.get("spreadsheet", ""))
    except KeyError, TypeError:
        return None
    return url or None


def _passthrough_filters() -> BudgetFilters:
    """Return filters for the always-visible gross view."""
    return {
        "exclude_groups": [],
        "exclude_categories": [],
        "filter_large_expenses": False,
        "expense_threshold": DEFAULT_EXPENSE_THRESHOLD,
        "show_zero_budget": True,
    }


def _has_adjustments(filters: BudgetFilters) -> bool:
    """Return whether any one-off adjustment is active."""
    return bool(filters["exclude_groups"] or filters["exclude_categories"] or filters["filter_large_expenses"])


def _render_summary(label: str, comparison: pd.DataFrame) -> None:
    """Render one responsive row of budget metrics."""
    summary = summarize_budget(comparison)
    with st.container(horizontal=True):
        st.metric(f"{label} budget", f"${summary['budget']:,.2f}", border=True)
        st.metric(f"{label} spent", f"${summary['spent']:,.2f}", border=True)
        st.metric(
            f"{label} remaining",
            f"${summary['remaining']:,.2f}",
            delta_color="inverse" if summary["remaining"] >= 0 else "normal",
            border=True,
        )
        st.metric(f"{label} used", f"{summary['pct_used']:.1f}%", border=True)


def _guidance_table(
    gross: pd.DataFrame,
    adjusted: pd.DataFrame,
    *,
    show_adjusted: bool,
) -> pd.DataFrame:
    """Combine gross and adjusted trailing-average guidance."""
    result = gross.rename(columns={"Monthly_Average": "Gross_Monthly_Average"})
    result = result[["Group", "Monthly_Target", "Gross_Monthly_Average", "Monthly_Reduction", "Annualized_Reduction"]]
    if not show_adjusted:
        return result

    adjusted_values = adjusted[["Group", "Monthly_Average"]].rename(
        columns={"Monthly_Average": "Adjusted_Monthly_Average"}
    )
    result = result.merge(adjusted_values, on="Group", how="left")
    result["Adjusted_Monthly_Reduction"] = result["Adjusted_Monthly_Average"] - result["Monthly_Target"]
    result["Adjusted_Annualized_Reduction"] = result["Adjusted_Monthly_Reduction"] * 12
    return result


def _render_group_drilldowns(
    groups: Sequence[str],
    month_str: str,
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    filters: BudgetFilters,
) -> None:
    """Render category and transaction details inside each group."""
    category_filters = dict(filters)
    category_filters["show_zero_budget"] = True
    category_comparison = get_budget_vs_actual(
        budget_df,
        transactions_df,
        month_str,
        cast(BudgetFilters, category_filters),
    )
    transactions = filter_budget_transactions(
        transactions_df,
        month_str,
        filters,
        groups=groups,
    )

    for group in groups:
        with st.expander(group):
            group_categories = category_comparison[category_comparison["Group"] == group]
            st.markdown("**Category breakdown**")
            st.dataframe(
                group_categories[["Category", "Budget", "Spent", "Remaining", "Pct_Used"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "Budget": st.column_config.NumberColumn("Budget", format="$%.2f"),
                    "Spent": st.column_config.NumberColumn("Spent", format="$%.2f"),
                    "Remaining": st.column_config.NumberColumn("Remaining", format="$%.2f"),
                    "Pct_Used": st.column_config.NumberColumn("Used", format="%.1f%%"),
                },
            )

            group_transactions = transactions[transactions["Group"] == group].sort_values(
                "Amount",
                key=lambda amounts: amounts.abs(),
                ascending=False,
            )
            st.markdown("**Transactions**")
            st.dataframe(
                group_transactions[["Date", "Category", "Full Description", "Amount"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                    "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                },
            )


def main() -> None:
    """Render the Tiller-backed group budget dashboard."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    st.header("Budget")
    st.caption(
        "Tiller is the source of truth. Streamlit rolls category budgets up into the groups that move the needle."
    )

    sheet_url = _categories_sheet_url()
    if sheet_url:
        st.link_button(
            "Edit budgets in Tiller",
            sheet_url,
            icon=":material/open_in_new:",
            type="primary",
        )

    transactions_spreadsheet = load_transactions_data()
    categories_spreadsheet = load_categories_data()
    transactions_df = transactions_spreadsheet.scrubbed_df
    budget_df = categories_spreadsheet.budget_df

    months = sorted(transactions_df["Month"].dropna().unique(), reverse=True)
    if not months:
        st.info("No transaction data available")
        st.stop()

    available_groups = transactions_spreadsheet.get_all_groups()
    default_groups = [group for group in DEFAULT_BUDGET_GROUPS if group in available_groups]
    selected_groups_value = st.pills(
        "Budget groups",
        available_groups,
        default=default_groups,
        selection_mode="multi",
        help="The dashboard defaults to the four discretionary groups that most affect cash flow.",
    )
    selected_groups = list(selected_groups_value or [])
    if not selected_groups:
        st.info("Select at least one budget group")
        st.stop()

    selected_month = st.selectbox("Month", months, index=0)
    adjusted_filters = render_budget_filters(
        transactions_spreadsheet.get_all_categories(),
        selected_groups,
    )
    gross_filters = _passthrough_filters()
    show_adjusted = _has_adjustments(adjusted_filters)

    gross_monthly = get_group_budget_vs_actual(
        budget_df,
        transactions_df,
        selected_month,
        gross_filters,
        selected_groups,
    )
    gross_ytd = get_ytd_group_budget_vs_actual(
        budget_df,
        transactions_df,
        selected_month,
        gross_filters,
        selected_groups,
    )
    adjusted_monthly = get_group_budget_vs_actual(
        budget_df,
        transactions_df,
        selected_month,
        adjusted_filters,
        selected_groups,
    )
    adjusted_ytd = get_ytd_group_budget_vs_actual(
        budget_df,
        transactions_df,
        selected_month,
        adjusted_filters,
        selected_groups,
    )

    st.subheader("Gross performance")
    _render_summary("Monthly", gross_monthly)
    _render_summary("YTD", gross_ytd)

    gross_monthly_transactions = filter_budget_transactions(
        transactions_df,
        selected_month,
        gross_filters,
        groups=selected_groups,
    )
    adjusted_monthly_transactions = filter_budget_transactions(
        transactions_df,
        selected_month,
        adjusted_filters,
        groups=selected_groups,
    )

    if show_adjusted:
        st.subheader("One-off-adjusted performance")
        _render_summary("Adjusted monthly", adjusted_monthly)
        _render_summary("Adjusted YTD", adjusted_ytd)
        excluded_indices = gross_monthly_transactions.index.difference(adjusted_monthly_transactions.index)
        excluded_transactions = gross_monthly_transactions.loc[excluded_indices]
        excluded_amount = float(excluded_transactions["Amount"].sum().abs())
        st.info(
            f"This adjusted view excludes {len(excluded_transactions):,} monthly transactions "
            f"totaling ${excluded_amount:,.2f}. Gross results above always include them."
        )

    st.subheader("Group performance")
    chart_data = gross_monthly
    chart_label = "Gross"
    if show_adjusted:
        chart_label = cast(
            str,
            st.segmented_control("Chart view", ["Gross", "Adjusted"], default="Adjusted"),
        )
        if chart_label == "Adjusted":
            chart_data = adjusted_monthly
    st.altair_chart(
        create_budget_group_chart(chart_data, f"{chart_label} budget vs actual — {selected_month}"),
        width="stretch",
    )

    now = pd.Timestamp.now(tz="UTC")
    if selected_month == now.strftime("%Y-%m"):
        summary = summarize_budget(chart_data)
        projected = summary["spent"] / now.day * calendar.monthrange(now.year, now.month)[1]
        days_remaining = calendar.monthrange(now.year, now.month)[1] - now.day
        color = "red" if projected > summary["budget"] else "green"
        st.markdown(
            f"**{days_remaining} days remaining** — on pace to spend "
            f":{color}[**${projected:,.0f}**] of the ${summary['budget']:,.0f} group budget."
        )

    group_table = build_group_budget_table(
        gross_monthly,
        adjusted_monthly,
        gross_ytd,
        adjusted_ytd,
    )
    display_columns = ["Group", "Monthly_Budget", "Monthly_Gross", "YTD_Budget", "YTD_Gross", "YTD_Pct"]
    if show_adjusted:
        display_columns = [
            "Group",
            "Monthly_Budget",
            "Monthly_Gross",
            "Monthly_Adjusted",
            "Monthly_Excluded",
            "YTD_Budget",
            "YTD_Gross",
            "YTD_Adjusted",
            "YTD_Excluded",
            "YTD_Pct",
        ]
    st.dataframe(
        group_table[display_columns],
        width="stretch",
        hide_index=True,
        column_config={
            column: st.column_config.NumberColumn(column.replace("_", " "), format="$%.2f")
            for column in display_columns
            if column not in {"Group", "YTD_Pct"}
        }
        | {"YTD_Pct": st.column_config.NumberColumn("YTD used", format="%.1f%%")},
    )

    st.subheader("Trailing 12-month guidance")
    st.caption(
        "Uses the 12 complete months before the selected month, so a partial current month does not distort the baseline."
    )
    gross_guidance = get_trailing_group_guidance(
        budget_df,
        transactions_df,
        selected_month,
        gross_filters,
        selected_groups,
    )
    adjusted_guidance = get_trailing_group_guidance(
        budget_df,
        transactions_df,
        selected_month,
        adjusted_filters,
        selected_groups,
    )
    guidance = _guidance_table(gross_guidance, adjusted_guidance, show_adjusted=show_adjusted)
    st.dataframe(
        guidance,
        width="stretch",
        hide_index=True,
        column_config={
            column: st.column_config.NumberColumn(column.replace("_", " "), format="$%.2f")
            for column in guidance.columns
            if column != "Group"
        },
    )

    major_transactions = gross_monthly_transactions[
        gross_monthly_transactions["Amount"].abs() > DEFAULT_EXPENSE_THRESHOLD
    ].sort_values("Amount", key=lambda amounts: amounts.abs(), ascending=False)
    st.subheader("Major spending drivers")
    if major_transactions.empty:
        st.caption(f"No individual transactions over ${DEFAULT_EXPENSE_THRESHOLD:,.0f} this month.")
    else:
        st.caption("These transactions remain included in gross budget performance.")
        st.dataframe(
            major_transactions[["Date", "Group", "Category", "Full Description", "Amount"]],
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            },
        )

    st.subheader("Drill-downs")
    _render_group_drilldowns(
        selected_groups,
        selected_month,
        budget_df,
        transactions_df,
        adjusted_filters if show_adjusted else gross_filters,
    )


if __name__ == "__main__":
    main()
