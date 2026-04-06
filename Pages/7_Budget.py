import calendar

import streamlit as st
import pandas as pd
import altair as alt

from src.spreadsheet import (
    load_transactions_data,
    load_categories_data,
    TransactionsSpreadsheet,
    CategoriesSpreadsheet,
)
from src.filters import render_budget_filters, apply_transaction_filters
from src.page_helpers import display_transactions_expander
from src.constants import (
    COLOR_BUDGET,
    COLOR_OVER_BUDGET,
    COLOR_UNDER_BUDGET,
)


# ---------------------------------------------------------------------------
# Pure helper functions (testable without Streamlit)
# ---------------------------------------------------------------------------

def get_budget_vs_actual(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: dict,
) -> pd.DataFrame:
    """Compare budgets to actual spending for a given month.

    Returns:
        DataFrame with Category, Group, Type, Budget, Spent, Remaining, Pct_Used
    """
    month_num = int(month_str.split("-")[1])

    budgets = budget_df[budget_df["Month_Num"] == month_num][
        ["Category", "Group", "Type", "Budget"]
    ].copy()

    txns = transactions_df[transactions_df["Month"] == month_str].copy()
    txns = apply_transaction_filters(txns, filters)
    txns = txns[txns["Type"] == "Expense"]

    actuals = (
        txns.groupby("Category")["Amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"Amount": "Spent"})
    )

    result = budgets.merge(actuals, on="Category", how="outer")
    result["Budget"] = pd.to_numeric(result["Budget"], errors="coerce").fillna(0)
    result["Spent"] = pd.to_numeric(result["Spent"], errors="coerce").fillna(0)

    if not txns.empty:
        txn_meta = txns[["Category", "Group", "Type"]].drop_duplicates("Category")
        missing = result["Group"].isna()
        if missing.any():
            filled = result.loc[missing, ["Category"]].merge(txn_meta, on="Category", how="left")
            result.loc[missing, "Group"] = filled["Group"].values
            result.loc[missing, "Type"] = filled["Type"].values

    if filters.get("exclude_groups"):
        result = result[~result["Group"].isin(filters["exclude_groups"])]
    if filters.get("exclude_categories"):
        result = result[~result["Category"].isin(filters["exclude_categories"])]

    result["Remaining"] = result["Budget"] - result["Spent"]
    result["Pct_Used"] = result.apply(
        lambda r: (r["Spent"] / r["Budget"] * 100) if r["Budget"] > 0 else (0 if r["Spent"] == 0 else float("inf")),
        axis=1,
    )

    if not filters.get("show_zero_budget", False):
        result = result[(result["Budget"] > 0) | (result["Spent"] > 0)]
        result = result[result["Budget"] > 0]

    return result.sort_values("Pct_Used", ascending=False).reset_index(drop=True)


def get_ytd_budget_vs_actual(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    month_str: str,
    filters: dict,
) -> pd.DataFrame:
    """Compare YTD cumulative budgets to actual spending through a given month.

    Returns:
        DataFrame with Category, Group, Type, Budget, Spent, Remaining, Pct_Used
    """
    year = month_str.split("-")[0]
    month_num = int(month_str.split("-")[1])

    budgets = budget_df[budget_df["Month_Num"].between(1, month_num)].copy()
    budgets = (
        budgets.groupby(["Category", "Group", "Type"])["Budget"]
        .sum()
        .reset_index()
    )

    ytd_months = [f"{year}-{m:02d}" for m in range(1, month_num + 1)]
    txns = transactions_df[transactions_df["Month"].isin(ytd_months)].copy()
    txns = apply_transaction_filters(txns, filters)
    txns = txns[txns["Type"] == "Expense"]

    actuals = (
        txns.groupby("Category")["Amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"Amount": "Spent"})
    )

    result = budgets.merge(actuals, on="Category", how="outer")
    result["Budget"] = pd.to_numeric(result["Budget"], errors="coerce").fillna(0)
    result["Spent"] = pd.to_numeric(result["Spent"], errors="coerce").fillna(0)

    if not txns.empty:
        txn_meta = txns[["Category", "Group", "Type"]].drop_duplicates("Category")
        missing = result["Group"].isna()
        if missing.any():
            filled = result.loc[missing, ["Category"]].merge(txn_meta, on="Category", how="left")
            result.loc[missing, "Group"] = filled["Group"].values
            result.loc[missing, "Type"] = filled["Type"].values

    if filters.get("exclude_groups"):
        result = result[~result["Group"].isin(filters["exclude_groups"])]
    if filters.get("exclude_categories"):
        result = result[~result["Category"].isin(filters["exclude_categories"])]

    result["Remaining"] = result["Budget"] - result["Spent"]
    result["Pct_Used"] = result.apply(
        lambda r: (r["Spent"] / r["Budget"] * 100) if r["Budget"] > 0 else (0 if r["Spent"] == 0 else float("inf")),
        axis=1,
    )

    if not filters.get("show_zero_budget", False):
        result = result[(result["Budget"] > 0) | (result["Spent"] > 0)]
        result = result[result["Budget"] > 0]

    return result.sort_values("Pct_Used", ascending=False).reset_index(drop=True)


def get_monthly_budget_comparison(
    budget_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    category: str,
    year: str,
    filters: dict,
    through_month: int = 12,
) -> pd.DataFrame:
    """Get cumulative budget vs actual for a category across a year.

    Args:
        through_month: Only include months 1 through this value (default 12)

    Returns:
        DataFrame with Month (1..through_month), Budget, Actual columns (cumulative)
    """
    rows = []
    cumulative_budget = 0
    cumulative_actual = 0

    for month_num in range(1, through_month + 1):
        month_str = f"{year}-{month_num:02d}"

        # Budget for this month
        budget_row = budget_df[
            (budget_df["Category"] == category) & (budget_df["Month_Num"] == month_num)
        ]
        cumulative_budget += budget_row["Budget"].iloc[0] if not budget_row.empty else 0

        # Actual spend for this month
        txns = transactions_df[transactions_df["Month"] == month_str].copy()
        txns = apply_transaction_filters(txns, filters)
        txns = txns[(txns["Type"] == "Expense") & (txns["Category"] == category)]
        cumulative_actual += txns["Amount"].sum() * -1 if not txns.empty else 0

        rows.append({"Month": month_num, "Budget": cumulative_budget, "Actual": cumulative_actual})

    return pd.DataFrame(rows)


def calculate_projected_spend(spent: float, days_elapsed: int, days_in_month: int) -> float:
    """Project end-of-month spend based on current pace."""
    if days_elapsed <= 0:
        return 0.0
    daily_rate = spent / days_elapsed
    return daily_rate * days_in_month


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def create_budget_vs_actual_chart(df: pd.DataFrame, title: str) -> alt.Chart:
    """Line chart comparing budget vs actual spending by month for a category."""
    if df.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(text=alt.value("No data"))

    # Trim trailing zero-actual months (future months)
    non_zero = df[df["Actual"] != 0]
    if not non_zero.empty:
        last_month = non_zero["Month"].max()
        df = df[df["Month"] <= last_month].copy()

    chart_df = df.melt(id_vars="Month", var_name="Type", value_name="Amount")

    color_scale = alt.Scale(
        domain=["Budget", "Actual"],
        range=[COLOR_BUDGET, COLOR_UNDER_BUDGET],
    )

    chart = (
        alt.Chart(chart_df)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("Month:O", axis=alt.Axis(title="Month", labelAngle=0)),
            y=alt.Y("Amount:Q", axis=alt.Axis(title="Amount ($)"), scale=alt.Scale(zero=True)),
            color=alt.Color("Type:N", scale=color_scale, title=""),
            tooltip=[
                alt.Tooltip("Month:O"),
                alt.Tooltip("Type:N"),
                alt.Tooltip("Amount:Q", format="$,.2f"),
            ],
        )
        .properties(height=300, title=title)
    )
    return chart


def create_budget_category_chart(df: pd.DataFrame, title: str = "Budget vs Actual by Category") -> alt.Chart:
    """Horizontal bar chart with spent amount and a tick mark at the budget level."""
    if df.empty:
        return alt.Chart(pd.DataFrame()).mark_text().encode(text=alt.value("No budget data"))

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

    # Budget reference tick per category
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

    return (bars + budget_ticks).properties(height=max(300, len(df) * 35), title=title)


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    categories_spreadsheet: CategoriesSpreadsheet,
) -> None:
    st.header("Budget")

    months = sorted(transactions_spreadsheet.scrubbed_df["Month"].dropna().unique(), reverse=True)
    if not months:
        st.info("No transaction data available")
        return

    # Filters
    all_categories = sorted(
        [str(c) for c in transactions_spreadsheet.scrubbed_df["Category"].unique()
         if pd.notna(c) and str(c).strip()]
    )
    all_groups = sorted(
        [str(g) for g in transactions_spreadsheet.scrubbed_df["Group"].unique()
         if pd.notna(g) and str(g).strip() and g != "Transfer"]
    )
    filters = render_budget_filters(all_categories, all_groups)

    # Determine current year from most recent month
    now = pd.Timestamp.now(tz="UTC")
    current_year = str(now.year)

    # Get budgeted categories (any category with a non-zero budget)
    budgeted_cats = (
        categories_spreadsheet.budget_df[categories_spreadsheet.budget_df["Budget"] > 0]["Category"]
        .unique()
        .tolist()
    )

    # --- YTD section: per-category budget vs actual across the year ---
    st.subheader("Year to Date")

    for category in sorted(budgeted_cats):
        comparison = get_monthly_budget_comparison(
            categories_spreadsheet.budget_df,
            transactions_spreadsheet.scrubbed_df,
            category,
            current_year,
            filters,
            through_month=now.month,
        )

        st.markdown(f"**{category}**")
        col1, col2 = st.columns([1, 4])

        # Pivot table on the left
        display = comparison[comparison["Actual"] > 0].copy()
        if display.empty:
            display = comparison[comparison["Month"] <= now.month].copy()
        display_table = display.set_index("Month")[["Budget", "Actual"]].copy()
        display_table.index = display_table.index.map(lambda m: calendar.month_abbr[m])
        col1.dataframe(
            display_table,
            column_config={
                "Budget": st.column_config.NumberColumn("Budget", format="$%.0f"),
                "Actual": st.column_config.NumberColumn("Actual", format="$%.0f"),
            },
        )

        # Line chart on the right
        chart = create_budget_vs_actual_chart(comparison, category)
        col2.altair_chart(chart, use_container_width=True)

    st.divider()

    # --- Monthly section ---
    st.subheader("Monthly Detail")

    selected_month = st.selectbox("Month", months, index=0)

    budget_actual = get_budget_vs_actual(
        categories_spreadsheet.budget_df,
        transactions_spreadsheet.scrubbed_df,
        selected_month,
        filters,
    )

    # Summary metrics
    total_budget = budget_actual["Budget"].sum()
    total_spent = budget_actual["Spent"].sum()
    total_remaining = total_budget - total_spent
    pct_used = (total_spent / total_budget * 100) if total_budget > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Monthly Budget", f"${total_budget:,.2f}")
    with col2:
        st.metric("Monthly Spent", f"${total_spent:,.2f}")
    with col3:
        delta_color = "inverse" if total_remaining >= 0 else "normal"
        st.metric("Remaining", f"${total_remaining:,.2f}", delta_color=delta_color)
    with col4:
        st.metric("% Used", f"{pct_used:.1f}%")

    # Days remaining context (current month only)
    current_month_str = now.strftime("%Y-%m")
    if selected_month == current_month_str and total_budget > 0:
        days_elapsed = now.day
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        days_remaining = days_in_month - days_elapsed
        projected = calculate_projected_spend(total_spent, days_elapsed, days_in_month)

        proj_color = "red" if projected > total_budget else "green"
        st.markdown(
            f"**{days_remaining} days remaining** in {now.strftime('%B')} "
            f"&mdash; On pace to spend: :{proj_color}[**${projected:,.2f}**] of ${total_budget:,.2f} budget"
        )

    if budget_actual.empty:
        st.info("No budget data for the selected month and filters")
    else:
        st.altair_chart(
            create_budget_category_chart(budget_actual, f"Budget vs Actual — {selected_month}"),
            use_container_width=True,
        )

        # Per-category projections for current month
        if selected_month == current_month_str:
            days_elapsed = now.day
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            for _, row in budget_actual.iterrows():
                if row["Budget"] > 0:
                    proj = calculate_projected_spend(row["Spent"], days_elapsed, days_in_month)
                    color = "red" if proj > row["Budget"] else "green"
                    st.caption(
                        f"**{row['Category']}**: On pace: :{color}[${proj:,.0f}] "
                        f"of ${row['Budget']:,.0f} budget"
                    )

        with st.expander("View All Categories"):
            display_df = budget_actual[
                ["Category", "Group", "Budget", "Spent", "Remaining", "Pct_Used"]
            ].copy()
            display_df["Pct_Used"] = display_df["Pct_Used"].apply(
                lambda x: f"{x:.1f}%" if x != float("inf") else "N/A"
            )
            st.dataframe(
                display_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Budget": st.column_config.NumberColumn("Budget", format="$%.2f"),
                    "Spent": st.column_config.NumberColumn("Spent", format="$%.2f"),
                    "Remaining": st.column_config.NumberColumn("Remaining", format="$%.2f"),
                    "Pct_Used": st.column_config.TextColumn("% Used"),
                },
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
    """Page entrypoint"""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    categories_spreadsheet = load_categories_data()

    configure_page(transactions_spreadsheet, categories_spreadsheet)


if __name__ == "__main__":
    main()
