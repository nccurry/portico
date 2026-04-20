"""Financial Independence page: compares expected investment returns to average spending."""
import math

import altair as alt
import pandas as pd
import streamlit as st

from src.constants import (
    CHART_HEIGHT_STANDARD,
    COLOR_ASSET,
    COLOR_EXPENSE,
    COLOR_INCOME,
    COLOR_SAVINGS,
)
from src.custom_types import FIFilters, FISummary
from src.filters import apply_transaction_filters, render_fi_filters
from src.page_helpers import display_transactions_expander
from src.spreadsheet import (
    BalanceHistorySpreadsheet,
    TransactionsSpreadsheet,
    get_all_accounts,
    get_portfolio_value,
    load_balance_history_data,
    load_transactions_data,
)


def _get_savings_accounts(bal_df: pd.DataFrame) -> list[str]:
    """Return Account names whose Group is 'Savings' (case-insensitive)."""
    if "Group" not in bal_df.columns:
        return []
    df = bal_df
    if "Hide" in df.columns:
        df = df[df["Hide"] != "Hide"]
    mask = df["Group"].astype(str).str.lower() == "savings"
    return sorted(df[mask]["Account"].dropna().unique().tolist())


def calculate_avg_monthly_spending(
    df: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> tuple[float, pd.DataFrame]:
    """Return (avg_monthly_spend, monthly_totals_df) for Expense rows in window.

    Parameters
    ----------
    df:
        Already-filtered transactions. Expenses must have ``Type='Expense'`` and
        a negative ``Amount``; only expense rows contribute to the average.
    start_month, end_month:
        Inclusive ``YYYY-MM`` bounds on the ``Month`` column.

    Returns
    -------
    tuple[float, pd.DataFrame]
        ``(avg, totals)`` where ``avg`` is mean monthly spend as a positive
        float and ``totals`` has columns ``Month`` and ``Spending`` (positive).
        Returns ``(0.0, empty_df)`` when no expense rows are in range.
    """
    totals_cols = ["Month", "Spending"]
    if df.empty:
        return 0.0, pd.DataFrame(columns=totals_cols)

    expenses = df[df["Type"] == "Expense"].copy()
    expenses = expenses[
        (expenses["Month"] >= start_month) & (expenses["Month"] <= end_month)
    ]
    if expenses.empty:
        return 0.0, pd.DataFrame(columns=totals_cols)

    monthly = (
        expenses.groupby("Month")["Amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"Amount": "Spending"})
        .sort_values("Month")
        .reset_index(drop=True)
    )
    avg = float(monthly["Spending"].mean())
    return avg, monthly


def calculate_fi_metrics(
    portfolio_value: float,
    annual_spending: float,
    rate_pct: float,
) -> FISummary:
    """Derive FI metrics from portfolio size, spending, and expected return.

    ``rate_pct`` is a percentage (e.g. ``7.0`` for 7%). Runway uses the
    closed-form for ``B_{n+1} = B_n*(1+r) - S``; it is ``None`` when expected
    returns fully cover spending.
    """
    r = rate_pct / 100.0
    annual_return = portfolio_value * r

    if annual_spending <= 0:
        coverage = float("inf") if portfolio_value > 0 or annual_return > 0 else 0.0
        return FISummary(
            portfolio_value=portfolio_value,
            annual_return=annual_return,
            annual_spending=annual_spending,
            coverage_ratio=coverage,
            runway_years=None,
        )

    coverage = annual_return / annual_spending

    if portfolio_value <= 0:
        runway: float | None = 0.0
    elif r <= 0:
        runway = portfolio_value / annual_spending
    elif annual_return >= annual_spending:
        runway = None
    else:
        runway = math.log(
            annual_spending / (annual_spending - portfolio_value * r)
        ) / math.log(1.0 + r)

    return FISummary(
        portfolio_value=portfolio_value,
        annual_return=annual_return,
        annual_spending=annual_spending,
        coverage_ratio=coverage,
        runway_years=runway,
    )


def project_portfolio(
    portfolio_value: float,
    annual_spending: float,
    rate_pct: float,
    years: int,
) -> pd.DataFrame:
    """Simulate ``B_{n+1} = B_n*(1+r) - S`` for ``years`` years.

    Returns a DataFrame with columns ``Year`` (0..years) and ``Balance``.
    Balance is clamped at 0 once depleted so downstream charts do not plot
    negative values.
    """
    r = rate_pct / 100.0
    balances: list[float] = [portfolio_value]
    b = portfolio_value
    for _ in range(years):
        b = b * (1.0 + r) - annual_spending
        if b < 0:
            b = 0.0
        balances.append(b)
    return pd.DataFrame({"Year": list(range(years + 1)), "Balance": balances})


def _build_spending_filters(filters: FIFilters) -> dict[str, object]:
    """Project FIFilters onto the shape expected by apply_transaction_filters."""
    return {
        "exclude_groups": filters["exclude_groups"],
        "exclude_categories": filters["exclude_categories"],
        "filter_large_expenses": filters["filter_large_expenses"],
        "expense_threshold": filters["expense_threshold"],
    }


def _spending_window_months(lookback_months: int) -> tuple[str, str]:
    """Return (start_month, end_month) as YYYY-MM, excluding the current month."""
    now = pd.Timestamp.now(tz="UTC")
    end = (now - pd.DateOffset(months=1)).strftime("%Y-%m")
    start = (now - pd.DateOffset(months=lookback_months)).strftime("%Y-%m")
    return start, end


def _render_metric_row(summary: FISummary) -> None:
    """Top-row FI metrics: portfolio, return, spending, coverage, runway."""
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("Portfolio Value", f"${summary['portfolio_value']:,.0f}")
    with c2:
        st.metric(
            "Expected Annual Return",
            f"${summary['annual_return']:,.0f}",
            help="Portfolio value x expected return rate",
        )
    with c3:
        st.metric("Annual Spending", f"${summary['annual_spending']:,.0f}")
    with c4:
        cov = summary["coverage_ratio"]
        cov_str = "Infinite" if math.isinf(cov) else f"{cov * 100:.1f}%"
        delta = None if math.isinf(cov) else ("Covered" if cov >= 1 else "Not yet")
        st.metric(
            "Coverage",
            cov_str,
            delta=delta,
            help="Annual return / annual spending",
        )
    with c5:
        runway = summary["runway_years"]
        runway_str = "Infinite" if runway is None else f"{runway:.1f} yrs"
        st.metric(
            "Runway",
            runway_str,
            help="Years of spending the portfolio covers at the given return rate",
        )


def _create_comparison_chart(summary: FISummary) -> alt.LayerChart:
    """Two-bar chart comparing annual return to annual spending."""
    df = pd.DataFrame({
        "Metric": ["Annual Return", "Annual Spending"],
        "Amount": [summary["annual_return"], summary["annual_spending"]],
    })
    bars = alt.Chart(df).mark_bar().encode(
        x=alt.X("Metric:N", axis=alt.Axis(title=None, labelAngle=0)),
        y=alt.Y("Amount:Q", axis=alt.Axis(title="Amount ($)")),
        color=alt.Color(
            "Metric:N",
            scale=alt.Scale(
                domain=["Annual Return", "Annual Spending"],
                range=[COLOR_INCOME, COLOR_EXPENSE],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("Metric:N"),
            alt.Tooltip("Amount:Q", format="$,.0f"),
        ],
    )
    breakeven = alt.Chart(
        pd.DataFrame({"y": [summary["annual_spending"]]})
    ).mark_rule(color=COLOR_SAVINGS, strokeDash=[5, 5], strokeWidth=2).encode(y="y:Q")

    return (bars + breakeven).properties(  # type: ignore[no-any-return]
        height=CHART_HEIGHT_STANDARD,
        title="Annual Return vs Annual Spending",
        width="container",
    )


def _create_projection_chart(
    projection_df: pd.DataFrame,
    initial_value: float,
) -> alt.LayerChart:
    """Line chart of projected portfolio value with a baseline at the start value."""
    line = alt.Chart(projection_df).mark_line(
        color=COLOR_ASSET,
        strokeWidth=3,
        point=True,
    ).encode(
        x=alt.X("Year:Q", axis=alt.Axis(title="Year", format="d")),
        y=alt.Y("Balance:Q", axis=alt.Axis(title="Balance ($)", format="$,.0f")),
        tooltip=[
            alt.Tooltip("Year:Q"),
            alt.Tooltip("Balance:Q", format="$,.0f"),
        ],
    )
    baseline = alt.Chart(pd.DataFrame({"y": [initial_value]})).mark_rule(
        color=COLOR_SAVINGS, strokeDash=[5, 5], strokeWidth=2
    ).encode(y="y:Q")

    return (line + baseline).properties(  # type: ignore[no-any-return]
        height=CHART_HEIGHT_STANDARD,
        title="Portfolio Projection",
        width="container",
    )


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet,
) -> None:
    """Render the Financial Independence page."""
    st.header("Financial Independence")
    st.caption(
        "Compare expected investment returns to average spending and project "
        "portfolio runway over time."
    )

    bal_df = balance_history_spreadsheet.scrubbed_df
    all_accounts = get_all_accounts(bal_df)
    all_groups = transactions_spreadsheet.get_all_groups()
    savings_accounts = _get_savings_accounts(bal_df)

    filters = render_fi_filters(all_accounts, all_groups, savings_accounts)

    per_account_df, portfolio_value = get_portfolio_value(
        bal_df, filters["include_accounts"]
    )

    start_month, end_month = _spending_window_months(filters["spending_lookback_months"])
    tx_df = transactions_spreadsheet.scrubbed_df.copy()
    tx_df = apply_transaction_filters(tx_df, _build_spending_filters(filters))
    avg_monthly_spending, monthly_totals = calculate_avg_monthly_spending(
        tx_df, start_month, end_month
    )
    annual_spending = avg_monthly_spending * 12

    summary = calculate_fi_metrics(
        portfolio_value, annual_spending, filters["expected_return_rate"]
    )

    _render_metric_row(summary)

    st.divider()
    st.subheader("Return vs Spending")
    st.altair_chart(_create_comparison_chart(summary), width="stretch")

    st.divider()
    st.subheader("Portfolio Projection")
    projection_df = project_portfolio(
        portfolio_value,
        annual_spending,
        filters["expected_return_rate"],
        filters["projection_years"],
    )
    st.altair_chart(_create_projection_chart(projection_df, portfolio_value), width="stretch")

    with st.expander(f"Portfolio Accounts ({len(per_account_df)})"):
        if per_account_df.empty:
            st.info("No accounts selected")
        else:
            st.dataframe(
                per_account_df.sort_values("Balance", ascending=False),
                width="stretch",
                hide_index=True,
                column_config={
                    "Balance": st.column_config.NumberColumn("Balance", format="$%,.2f"),
                },
            )

    with st.expander(f"Monthly Spending ({start_month} to {end_month})"):
        if monthly_totals.empty:
            st.info("No spending in selected window")
        else:
            st.dataframe(
                monthly_totals,
                width="stretch",
                hide_index=True,
                column_config={
                    "Spending": st.column_config.NumberColumn("Spending", format="$%,.2f"),
                },
            )

    with st.expander("Projection Table"):
        st.dataframe(
            projection_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Balance": st.column_config.NumberColumn("Balance", format="$%,.2f"),
            },
        )

    tx_window = tx_df[(tx_df["Month"] >= start_month) & (tx_df["Month"] <= end_month)]
    display_transactions_expander(tx_window, "View Transactions Used for Spending Average")


def main() -> None:
    """Streamlit entry point for the Financial Independence page."""
    st.set_page_config(layout="wide")

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()
