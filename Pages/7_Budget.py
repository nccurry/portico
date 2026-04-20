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
from src.custom_types import BudgetFilters
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
    filters: BudgetFilters,
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
    filters: BudgetFilters,
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


def build_unified_budget_table(
    monthly_df: pd.DataFrame,
    ytd_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge monthly and YTD budget comparisons into a single table.

    Returns:
        DataFrame with Category, Group, Mo_Budget, Mo_Spent, Mo_Pct,
        YTD_Budget, YTD_Spent, YTD_Pct — sorted by Mo_Pct descending.
    """
    monthly = monthly_df[["Category", "Group", "Budget", "Spent", "Pct_Used"]].rename(
        columns={"Budget": "Mo_Budget", "Spent": "Mo_Spent", "Pct_Used": "Mo_Pct"}
    )
    ytd = ytd_df[["Category", "Budget", "Spent", "Pct_Used"]].rename(
        columns={"Budget": "YTD_Budget", "Spent": "YTD_Spent", "Pct_Used": "YTD_Pct"}
    )

    merged = monthly.merge(ytd, on="Category", how="outer")

    for col in ["Mo_Budget", "Mo_Spent", "Mo_Pct", "YTD_Budget", "YTD_Spent", "YTD_Pct"]:
        merged[col] = merged[col].fillna(0)
    merged["Group"] = merged["Group"].fillna("")

    return merged.sort_values("Mo_Pct", ascending=False).reset_index(drop=True)


def calculate_projected_spend(
    spent: float,
    days_elapsed: int,
    days_in_month: int,
) -> float:
    """Project end-of-month spend based on current pace."""
    if days_elapsed <= 0:
        return 0.0
    daily_rate = spent / days_elapsed
    return daily_rate * days_in_month


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

    # Monthly summary metrics
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
        st.metric(
            "Remaining",
            f"${total_remaining:,.2f}",
            delta_color="inverse" if total_remaining >= 0 else "normal",
        )
    with col4:
        st.metric("% Used", f"{pct_used:.1f}%")

    ytd_budget = ytd_actual["Budget"].sum()
    ytd_spent = ytd_actual["Spent"].sum()
    ytd_remaining = ytd_budget - ytd_spent
    ytd_pct = (ytd_spent / ytd_budget * 100) if ytd_budget > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("YTD Budget", f"${ytd_budget:,.2f}")
    with col2:
        st.metric("YTD Spent", f"${ytd_spent:,.2f}")
    with col3:
        st.metric(
            "YTD Remaining",
            f"${ytd_remaining:,.2f}",
            delta_color="inverse" if ytd_remaining >= 0 else "normal",
        )
    with col4:
        st.metric("YTD % Used", f"{ytd_pct:.1f}%")

    # Projection for current month
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
        # Bar chart for selected month
        st.altair_chart(
            create_budget_category_chart(budget_actual, f"Budget vs Actual — {selected_month}"),
            use_container_width=True,
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
            for _, row in budget_actual.iterrows():
                if row["Budget"] > 0:
                    proj = calculate_projected_spend(row["Spent"], days_elapsed, days_in_month)
                    color = "red" if proj > row["Budget"] else "green"
                    st.caption(
                        f"**{row['Category']}**: On pace: :{color}[${proj:,.0f}] "
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

    transactions_spreadsheet = load_transactions_data()
    categories_spreadsheet = load_categories_data()

    configure_page(transactions_spreadsheet, categories_spreadsheet)


if __name__ == "__main__":
    main()
