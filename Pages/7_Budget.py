import calendar

import streamlit as st
import pandas as pd
import altair as alt

from src.analysis.budget import (
    build_unified_budget_table,
    calculate_category_projections,
    calculate_projected_spend,
    get_budget_vs_actual,
    get_ytd_budget_vs_actual,
    summarize_budget,
)
from src.spreadsheet import (
    load_transactions_data,
    load_categories_data,
    TransactionsSpreadsheet,
    CategoriesSpreadsheet,
)
from src.filters import render_budget_filters, apply_transaction_filters
from src.page_helpers import display_transactions_expander, render_data_refresh_controls
from src.constants import (
    COLOR_BUDGET,
    COLOR_OVER_BUDGET,
    COLOR_UNDER_BUDGET,
)


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def create_budget_category_chart(
    df: pd.DataFrame,
    title: str = "Budget vs Actual by Category",
) -> alt.Chart:
    """Horizontal bar chart with spent amount and a tick mark at the budget level."""
    if df.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(text=alt.value("No budget data"))  # type: ignore[no-any-return]

    chart_df = df[["Category", "Budget", "Spent"]].copy()
    chart_df["Over"] = chart_df["Spent"] > chart_df["Budget"]

    bars = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            y=alt.Y("Category:N", sort=df["Category"].tolist(), title="Category",
                     axis=alt.Axis(labelLimit=200)),
            x=alt.X("Spent:Q", title="Amount ($)"),
            color=alt.condition(
                alt.datum.Over,
                alt.value(COLOR_OVER_BUDGET),
                alt.value(COLOR_UNDER_BUDGET),
            ),
            tooltip=[
                alt.Tooltip("Category:N"),
                alt.Tooltip("Spent:Q", format="$,.2f", title="Spent"),
                alt.Tooltip("Budget:Q", format="$,.2f", title="Budget"),
            ],
        )
    )

    budget_ticks = (
        alt.Chart(chart_df)
        .mark_tick(color=COLOR_BUDGET, thickness=3, size=20)
        .encode(
            y=alt.Y("Category:N", sort=df["Category"].tolist()),
            x=alt.X("Budget:Q"),
            tooltip=[
                alt.Tooltip("Category:N"),
                alt.Tooltip("Budget:Q", format="$,.2f", title="Budget"),
            ],
        )
    )

    return (bars + budget_ticks).properties(height=max(300, len(df) * 35), title=title)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    categories_spreadsheet: CategoriesSpreadsheet,
) -> None:
    """Render monthly and YTD budget-vs-actual comparisons with projected spend."""
    st.header("Budget")

    months = sorted(transactions_spreadsheet.scrubbed_df["Month"].dropna().unique(), reverse=True)
    if not months:
        st.info("No transaction data available")
        return

    all_categories = transactions_spreadsheet.get_all_categories()
    all_groups = transactions_spreadsheet.get_all_groups()
    filters = render_budget_filters(all_categories, all_groups)

    # Month selector
    selected_month = st.selectbox("Month", months, index=0)

    now = pd.Timestamp.now(tz="UTC")
    current_month_str = now.strftime("%Y-%m")

    # Monthly budget vs actual
    budget_actual = get_budget_vs_actual(
        categories_spreadsheet.budget_df,
        transactions_spreadsheet.scrubbed_df,
        selected_month,
        filters,
    )

    # YTD budget vs actual
    ytd_actual = get_ytd_budget_vs_actual(
        categories_spreadsheet.budget_df,
        transactions_spreadsheet.scrubbed_df,
        selected_month,
        filters,
    )

    monthly_summary = summarize_budget(budget_actual)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Monthly Budget", f"${monthly_summary['budget']:,.2f}")
    with col2:
        st.metric("Monthly Spent", f"${monthly_summary['spent']:,.2f}")
    with col3:
        st.metric(
            "Remaining",
            f"${monthly_summary['remaining']:,.2f}",
            delta_color="inverse" if monthly_summary["remaining"] >= 0 else "normal",
        )
    with col4:
        st.metric("% Used", f"{monthly_summary['pct_used']:.1f}%")

    ytd_summary = summarize_budget(ytd_actual)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("YTD Budget", f"${ytd_summary['budget']:,.2f}")
    with col2:
        st.metric("YTD Spent", f"${ytd_summary['spent']:,.2f}")
    with col3:
        st.metric(
            "YTD Remaining",
            f"${ytd_summary['remaining']:,.2f}",
            delta_color="inverse" if ytd_summary["remaining"] >= 0 else "normal",
        )
    with col4:
        st.metric("YTD % Used", f"{ytd_summary['pct_used']:.1f}%")

    # Projection for current month
    if selected_month == current_month_str and monthly_summary["budget"] > 0:
        days_elapsed = now.day
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        days_remaining = days_in_month - days_elapsed
        projected = calculate_projected_spend(
            monthly_summary["spent"], days_elapsed, days_in_month
        )

        proj_color = "red" if projected > monthly_summary["budget"] else "green"
        st.markdown(
            f"**{days_remaining} days remaining** in {now.strftime('%B')} "
            f"&mdash; On pace to spend: :{proj_color}[**${projected:,.2f}**] "
            f"of ${monthly_summary['budget']:,.2f} budget"
        )

    if budget_actual.empty:
        st.info("No budget data for the selected month and filters")
    else:
        # Bar chart for selected month
        st.altair_chart(
            create_budget_category_chart(budget_actual, f"Budget vs Actual — {selected_month}"),
            width="stretch",
        )

        # Unified budget table
        unified = build_unified_budget_table(budget_actual, ytd_actual)

        display_df = unified[
            ["Category", "Group", "Mo_Budget", "Mo_Spent", "Mo_Pct", "YTD_Budget", "YTD_Spent", "YTD_Pct"]
        ].copy()
        display_df["Mo_Pct"] = display_df["Mo_Pct"].apply(
            lambda x: f"{x:.1f}%" if x != float("inf") else "N/A"
        )
        display_df["YTD_Pct"] = display_df["YTD_Pct"].apply(
            lambda x: f"{x:.1f}%" if x != float("inf") else "N/A"
        )

        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Category": st.column_config.TextColumn("Category"),
                "Group": st.column_config.TextColumn("Group"),
                "Mo_Budget": st.column_config.NumberColumn("Mo Budget", format="$%.2f"),
                "Mo_Spent": st.column_config.NumberColumn("Mo Spent", format="$%.2f"),
                "Mo_Pct": st.column_config.TextColumn("Mo %"),
                "YTD_Budget": st.column_config.NumberColumn("YTD Budget", format="$%.2f"),
                "YTD_Spent": st.column_config.NumberColumn("YTD Spent", format="$%.2f"),
                "YTD_Pct": st.column_config.TextColumn("YTD %"),
            },
        )

        # Per-category projections for current month
        if selected_month == current_month_str:
            days_elapsed = now.day
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            projections = calculate_category_projections(
                budget_actual, days_elapsed, days_in_month
            )
            for _, row in projections.iterrows():
                color = "red" if row["Over_Budget"] else "green"
                st.caption(
                    f"**{row['Category']}**: On pace: :{color}[${row['Projected']:,.0f}] "
                    f"of ${row['Budget']:,.0f} budget"
                )

    # Transactions
    st.divider()
    txns = transactions_spreadsheet.scrubbed_df.copy()
    txns = txns[txns["Month"] == selected_month]
    included = apply_transaction_filters(txns.copy(), filters)
    included = included[included["Type"] == "Expense"]

    display_transactions_expander(included, "Included Transactions")

    excluded = txns[txns["Type"] == "Expense"]
    excluded = excluded[~excluded.index.isin(included.index)]
    if not excluded.empty:
        display_transactions_expander(excluded, "Excluded Transactions")


def main() -> None:
    """Streamlit entry point for the Budget page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()

    transactions_spreadsheet = load_transactions_data()
    categories_spreadsheet = load_categories_data()

    configure_page(transactions_spreadsheet, categories_spreadsheet)


if __name__ == "__main__":
    main()
