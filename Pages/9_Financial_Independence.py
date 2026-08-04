"""Financial Independence page: compares expected investment returns to average spending."""
import math

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis.financial_independence import (
    calculate_avg_monthly_spending,
    calculate_fi_metrics,
    get_savings_accounts as _get_savings_accounts,
    project_portfolio,
    resolve_annual_spending,
    resolve_portfolio_value,
)
from src.constants import (
    CHART_HEIGHT_STANDARD,
    COLOR_ADDITIONAL_SPENDING,
    COLOR_ASSET,
    COLOR_EXPENSE,
    COLOR_INCOME,
    COLOR_SAVINGS,
)
from src.custom_types import FIFilters, FISummary
from src.filters import apply_transaction_filters, render_fi_filters
from src.page_helpers import display_transactions_expander, render_data_refresh_controls
from src.reporting_periods import completed_month_window
from src.spreadsheet import (
    BalanceHistorySpreadsheet,
    TransactionsSpreadsheet,
    get_all_accounts,
    get_portfolio_value,
    load_balance_history_data,
    load_transactions_data,
)


def _build_spending_filters(filters: FIFilters) -> dict[str, object]:
    """Project FIFilters onto the shape expected by apply_transaction_filters."""
    return {
        "exclude_groups": filters["exclude_groups"],
        "exclude_categories": filters["exclude_categories"],
        "filter_large_expenses": filters["filter_large_expenses"],
        "expense_threshold": filters["expense_threshold"],
    }


def _spending_window_months(
    lookback_months: int,
    transactions_df: pd.DataFrame | None = None,
) -> tuple[str, str]:
    """Return (start_month, end_month) as YYYY-MM, excluding the current month."""
    return completed_month_window(
        lookback_months,
        transactions_df,
        anchor_to_data=transactions_df is not None,
    )


def _render_metric_row(summary: FISummary) -> None:
    """FI metrics in three unlabeled rows: raw, adjustments, then calculated."""
    cov = summary["coverage_ratio"]
    cov_str = "Infinite" if math.isinf(cov) else f"{cov * 100:.1f}%"
    cov_delta = None if math.isinf(cov) else ("Covered" if cov >= 1 else "Not yet")

    runway = summary["runway_years"]
    runway_str = "Infinite" if runway is None else f"{runway:.1f} yrs"

    raw = st.columns(2)
    with raw[0]:
        st.metric("Portfolio Value", f"${summary['portfolio_value']:,.0f}")
    with raw[1]:
        st.metric("Annual Spending", f"${summary['annual_spending']:,.0f}")

    adj = st.columns(2)
    with adj[0]:
        st.metric(
            "Supplemental Income",
            f"${summary['supplemental_income']:,.0f}",
            help="Non-portfolio income offsetting annual withdrawals",
        )
    with adj[1]:
        st.metric(
            "Additional Spending",
            f"${summary['supplemental_spending']:,.0f}",
            help="Extra spending added on top of the data-derived baseline",
        )

    calc = st.columns(4)
    with calc[0]:
        st.metric(
            "Expected Annual Return",
            f"${summary['annual_return']:,.0f}",
            help="Portfolio value x expected return rate",
        )
    with calc[1]:
        st.metric(
            "Coverage",
            cov_str,
            delta=cov_delta,
            help="(Annual return + supplemental income) / total spending",
        )
    with calc[2]:
        st.metric(
            "Runway",
            runway_str,
            help="Years of total spending the portfolio covers at the given return + income",
        )
    with calc[3]:
        st.metric(
            "Total Spending",
            f"${summary['total_spending']:,.0f}",
            delta=f"${summary['cashflow_gap']:,.0f} vs inflow",
            delta_color="normal",
            help="Annual Spending + Additional Spending. Delta is total inflow minus total spending.",
        )


def _create_comparison_chart(summary: FISummary) -> alt.LayerChart:
    """Stacked-inflow vs spending chart.

    Left bar stacks Annual Return + Supplemental Income; right bar shows
    Annual Spending. A dashed rule at the spending level marks break-even.
    """
    rows = [
        {"Bar": "Inflow", "Component": "Annual Return", "Amount": summary["annual_return"]},
        {"Bar": "Inflow", "Component": "Supplemental Income", "Amount": summary["supplemental_income"]},
        {"Bar": "Spending", "Component": "Annual Spending", "Amount": summary["annual_spending"]},
        {"Bar": "Spending", "Component": "Additional Spending", "Amount": summary["supplemental_spending"]},
    ]
    df = pd.DataFrame(rows)
    bars = alt.Chart(df).mark_bar().encode(
        x=alt.X("Bar:N", axis=alt.Axis(title=None, labelAngle=0)),
        y=alt.Y("Amount:Q", axis=alt.Axis(title="Amount ($)"), stack="zero"),
        color=alt.Color(
            "Component:N",
            scale=alt.Scale(
                domain=[
                    "Annual Return", "Supplemental Income",
                    "Annual Spending", "Additional Spending",
                ],
                range=[
                    COLOR_INCOME, COLOR_SAVINGS,
                    COLOR_EXPENSE, COLOR_ADDITIONAL_SPENDING,
                ],
            ),
            legend=alt.Legend(title=None, orient="bottom"),
        ),
        tooltip=[
            alt.Tooltip("Component:N"),
            alt.Tooltip("Amount:Q", format="$,.0f"),
        ],
    )
    breakeven = alt.Chart(
        pd.DataFrame({"y": [summary["total_spending"]]})
    ).mark_rule(color=COLOR_SAVINGS, strokeDash=[5, 5], strokeWidth=2).encode(y="y:Q")

    return (bars + breakeven).properties(  # type: ignore[no-any-return]
        height=CHART_HEIGHT_STANDARD,
        title="Annual Inflow (Return + Income) vs Spending",
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

    per_account_df, calculated_portfolio_value = get_portfolio_value(
        bal_df, filters["include_accounts"]
    )
    portfolio_override = (
        filters["portfolio_value_override"]
        if filters["override_portfolio_value"]
        else None
    )
    portfolio_value = resolve_portfolio_value(
        calculated_portfolio_value, portfolio_override
    )

    tx_df = transactions_spreadsheet.scrubbed_df.copy()
    start_month, end_month = _spending_window_months(filters["spending_lookback_months"], tx_df)
    tx_df = apply_transaction_filters(tx_df, _build_spending_filters(filters))
    avg_monthly_spending, monthly_totals = calculate_avg_monthly_spending(
        tx_df, start_month, end_month
    )
    override_value = (
        filters["annual_spending_override"]
        if filters["override_annual_spending"]
        else None
    )
    annual_spending = resolve_annual_spending(avg_monthly_spending, override_value)

    summary = calculate_fi_metrics(
        portfolio_value,
        annual_spending,
        filters["expected_return_rate"],
        filters["supplemental_annual_income"],
        filters["supplemental_annual_spending"],
    )

    if filters["override_portfolio_value"]:
        st.caption(
            f"Portfolio Value overridden to ${portfolio_value:,.0f} "
            f"(calculated total: ${calculated_portfolio_value:,.0f})"
        )
    if filters["override_annual_spending"]:
        st.caption(
            f"Annual Spending overridden to ${annual_spending:,.0f} "
            f"(calculated baseline: ${avg_monthly_spending * 12:,.0f})"
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
        filters["supplemental_annual_income"],
        filters["supplemental_annual_spending"],
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
    render_data_refresh_controls()

    transactions_spreadsheet = load_transactions_data()
    balance_history_spreadsheet = load_balance_history_data()

    configure_page(transactions_spreadsheet, balance_history_spreadsheet)


if __name__ == "__main__":
    main()
