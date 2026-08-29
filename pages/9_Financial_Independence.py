"""Interactive financial-independence scenario sandbox."""

from typing import cast

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis.financial_independence import (
    build_runway_sensitivity,
    calculate_avg_monthly_spending,
    calculate_fi_metrics,
    get_savings_accounts as _get_savings_accounts,
    project_portfolio,
)
from src.constants import (
    COLOR_ASSET,
    COLOR_EXPENSE,
    COLOR_INCOME,
    COLOR_NET_WORTH,
    COLOR_PLACEHOLDER,
    COLOR_SAVINGS,
    DEFAULT_EXPECTED_RETURN_RATE,
    DEFAULT_FI_PROJECTION_YEARS,
    DEFAULT_WITHDRAWAL_RATE,
)
from src.custom_types import FIFilters, FISummary, TransactionFilterOptions
from src.filters import apply_transaction_filters, render_fi_filters
from src.page_helpers import render_data_refresh_controls
from src.reporting_periods import latest_data_timestamp, rolling_month_window
from src.spreadsheet import (
    BalanceHistorySpreadsheet,
    TransactionsSpreadsheet,
    get_all_accounts,
    get_portfolio_value,
    load_balance_history_data,
    load_transactions_data,
)
from src.value_visibility import (
    MASKED_VALUE,
    mask_value,
    value_safe_altair_chart,
    value_safe_dataframe,
    values_hidden,
)


SCENARIO_KEYS = {
    "assets": "fi_scenario_assets",
    "spending": "fi_scenario_spending",
    "income": "fi_scenario_income",
    "return_rate": "fi_scenario_return_rate",
    "withdrawal_rate": "fi_scenario_withdrawal_rate",
    "years": "fi_scenario_years",
}
SOURCE_ASSETS_KEY = "fi_source_assets"
SOURCE_SPENDING_KEY = "fi_source_spending"


def _currency(value: float, *, signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _build_spending_filters(filters: FIFilters) -> TransactionFilterOptions:
    return {
        "exclude_groups": filters["exclude_groups"],
        "exclude_categories": filters["exclude_categories"],
        "filter_large_expenses": filters["filter_large_expenses"],
        "expense_threshold": filters["expense_threshold"],
    }


def _set_scenario_defaults(portfolio_value: float, annual_spending: float) -> None:
    portfolio_value = float(round(portfolio_value))
    annual_spending = float(round(annual_spending))
    previous_assets = st.session_state.get(SOURCE_ASSETS_KEY)
    previous_spending = st.session_state.get(SOURCE_SPENDING_KEY)
    if SCENARIO_KEYS["assets"] not in st.session_state or st.session_state[SCENARIO_KEYS["assets"]] == previous_assets:
        st.session_state[SCENARIO_KEYS["assets"]] = portfolio_value
    if (
        SCENARIO_KEYS["spending"] not in st.session_state
        or st.session_state[SCENARIO_KEYS["spending"]] == previous_spending
    ):
        st.session_state[SCENARIO_KEYS["spending"]] = annual_spending
    st.session_state[SOURCE_ASSETS_KEY] = portfolio_value
    st.session_state[SOURCE_SPENDING_KEY] = annual_spending
    defaults = {
        SCENARIO_KEYS["income"]: 0.0,
        SCENARIO_KEYS["return_rate"]: float(DEFAULT_EXPECTED_RETURN_RATE),
        SCENARIO_KEYS["withdrawal_rate"]: float(DEFAULT_WITHDRAWAL_RATE),
        SCENARIO_KEYS["years"]: int(DEFAULT_FI_PROJECTION_YEARS),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _reset_scenario(portfolio_value: float, annual_spending: float) -> None:
    st.session_state[SCENARIO_KEYS["assets"]] = float(round(portfolio_value))
    st.session_state[SCENARIO_KEYS["spending"]] = float(round(annual_spending))
    st.session_state[SCENARIO_KEYS["income"]] = 0.0
    st.session_state[SCENARIO_KEYS["return_rate"]] = float(DEFAULT_EXPECTED_RETURN_RATE)
    st.session_state[SCENARIO_KEYS["withdrawal_rate"]] = float(DEFAULT_WITHDRAWAL_RATE)
    st.session_state[SCENARIO_KEYS["years"]] = int(DEFAULT_FI_PROJECTION_YEARS)


def _render_scenario_controls(
    portfolio_value: float,
    annual_spending: float,
) -> tuple[float, float, float, float, float, int]:
    _set_scenario_defaults(portfolio_value, annual_spending)
    if values_hidden():
        with st.container(border=True):
            st.subheader("Scenario")
            st.caption("Turn off Hide values to edit the scenario.")
        return (
            float(st.session_state[SCENARIO_KEYS["assets"]]),
            float(st.session_state[SCENARIO_KEYS["spending"]]),
            float(st.session_state[SCENARIO_KEYS["income"]]),
            float(st.session_state[SCENARIO_KEYS["return_rate"]]),
            float(st.session_state[SCENARIO_KEYS["withdrawal_rate"]]),
            int(st.session_state[SCENARIO_KEYS["years"]]),
        )

    with st.container(border=True):
        heading, reset = st.columns([4, 1], vertical_alignment="center")
        with heading:
            st.subheader("Scenario")
        with reset:
            st.button(
                "Reset to source data",
                icon=":material/restart_alt:",
                width="stretch",
                on_click=_reset_scenario,
                args=(portfolio_value, annual_spending),
            )

        first_row = st.columns(3)
        with first_row[0]:
            assets = st.number_input(
                "Investable assets",
                min_value=0.0,
                max_value=100_000_000.0,
                step=10_000.0,
                key=SCENARIO_KEYS["assets"],
                persist_state="session",
            )
        with first_row[1]:
            spending = st.number_input(
                "Annual spending",
                min_value=0.0,
                max_value=10_000_000.0,
                step=1_000.0,
                key=SCENARIO_KEYS["spending"],
                persist_state="session",
            )
        with first_row[2]:
            income = st.number_input(
                "Annual earned income",
                min_value=0.0,
                max_value=10_000_000.0,
                step=1_000.0,
                key=SCENARIO_KEYS["income"],
                persist_state="session",
            )

        second_row = st.columns(3)
        with second_row[0]:
            return_rate = st.number_input(
                "Expected real return (%)",
                min_value=0.0,
                max_value=20.0,
                step=0.5,
                format="%.1f",
                key=SCENARIO_KEYS["return_rate"],
                persist_state="session",
            )
        with second_row[1]:
            withdrawal_rate = st.number_input(
                "Withdrawal rate (%)",
                min_value=0.5,
                max_value=10.0,
                step=0.25,
                format="%.2f",
                key=SCENARIO_KEYS["withdrawal_rate"],
                persist_state="session",
            )
        with second_row[2]:
            years = st.number_input(
                "Projection horizon",
                min_value=1,
                max_value=100,
                step=5,
                key=SCENARIO_KEYS["years"],
                persist_state="session",
            )
    return (
        float(assets),
        float(spending),
        float(income),
        float(return_rate),
        float(withdrawal_rate),
        int(years),
    )


def _render_metrics(summary: FISummary) -> None:
    runway = summary["runway_years"]
    runway_value = "Sustainable" if runway is None else mask_value(f"{runway:.1f} years")
    runway_delta = (
        "Portfolio does not deplete"
        if runway is None
        else f"Until portfolio reaches {mask_value('$0')}"
    )
    gap = summary["annual_surplus"]
    gap_delta = "Annual surplus" if gap >= 0 else "Annual shortfall"
    fi_gap = summary["fi_gap"]
    fi_delta = f"{_currency(fi_gap)} above target" if fi_gap >= 0 else f"{_currency(-fi_gap)} still needed"
    with st.container(horizontal=True):
        st.metric(
            "Runway",
            runway_value,
            delta=runway_delta,
            delta_color="off",
            border=True,
        )
        st.metric(
            "Annual gap",
            _currency(gap, signed=True),
            delta=gap_delta,
            delta_color="normal",
            border=True,
        )
        st.metric(
            "Net portfolio spending",
            _currency(summary["net_annual_spending"]),
            delta=f"{_currency(summary['sustainable_spending'])} supported at withdrawal rate",
            delta_color="off",
            border=True,
        )
        st.metric(
            "FI target",
            _currency(summary["fi_target"]),
            delta=fi_delta,
            delta_color="normal",
            border=True,
        )


def _create_projection_chart(projection: pd.DataFrame) -> alt.LayerChart:
    base = alt.Chart(projection).encode(
        x=alt.X("Year:Q", title="Years from now", axis=alt.Axis(format="d")),
        y=alt.Y("Balance:Q", title="Portfolio balance", axis=alt.Axis(format="$,.2s")),
        tooltip=[
            alt.Tooltip("Year:Q", format="d"),
            alt.Tooltip("Starting_Balance:Q", title="Starting balance", format="$,.0f"),
            alt.Tooltip("Investment_Return:Q", title="Investment return", format="$,.0f"),
            alt.Tooltip("Income:Q", title="Earned income", format="$,.0f"),
            alt.Tooltip("Spending:Q", title="Spending", format="$,.0f"),
            alt.Tooltip("Balance:Q", title="Ending balance", format="$,.0f"),
        ],
    )
    area = base.mark_area(color=COLOR_NET_WORTH, opacity=0.2, line=False)
    line = base.mark_line(color=COLOR_NET_WORTH, strokeWidth=3)
    depletion = (
        alt.Chart(projection[projection["Balance"].le(0)].head(1))
        .mark_point(color=COLOR_EXPENSE, filled=True, size=120)
        .encode(
            x=alt.X("Year:Q"),
            y=alt.Y("Balance:Q"),
            tooltip=[alt.Tooltip("Year:Q", title="Depleted in year", format="d")],
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"Balance": [0.0]}))
        .mark_rule(color=COLOR_PLACEHOLDER, strokeDash=[4, 4])
        .encode(y="Balance:Q")
    )
    return cast(
        alt.LayerChart,
        (area + line + depletion + zero).properties(height=390),
    )


def _create_funding_chart(summary: FISummary) -> alt.Chart:
    data = pd.DataFrame(
        [
            {
                "Side": "Annual funding",
                "Component": "Investment return",
                "Amount": summary["annual_return"],
            },
            {
                "Side": "Annual funding",
                "Component": "Earned income",
                "Amount": summary["annual_income"],
            },
            {
                "Side": "Annual spending",
                "Component": "Spending",
                "Amount": summary["total_spending"],
            },
        ]
    )
    return cast(
        alt.Chart,
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("sum(Amount):Q", title="Annual amount", axis=alt.Axis(format="$,.2s")),
            y=alt.Y("Side:N", title=None, sort=["Annual funding", "Annual spending"]),
            color=alt.Color(
                "Component:N",
                title=None,
                scale=alt.Scale(
                    domain=["Investment return", "Earned income", "Spending"],
                    range=[COLOR_ASSET, COLOR_INCOME, COLOR_EXPENSE],
                ),
            ),
            tooltip=[
                alt.Tooltip("Component:N"),
                alt.Tooltip("Amount:Q", format="$,.0f"),
            ],
        )
        .properties(height=220),
    )


def _create_sensitivity_chart(sensitivity: pd.DataFrame) -> alt.LayerChart:
    order = ["+20%", "+10%", "Baseline", "-10%", "-20%"]
    hidden = values_hidden()
    return_axis = (
        alt.Axis(labelExpr=f"'{MASKED_VALUE}'")
        if hidden
        else alt.Axis(labelExpr="datum.label + '%'")
    )
    spending_axis = (
        alt.Axis(labelExpr=f"'{MASKED_VALUE}'") if hidden else alt.Undefined
    )
    tooltip = [
        alt.Tooltip("Annual_Spending:Q", title="Annual spending", format="$,.0f"),
        alt.Tooltip("Return_Rate:Q", title="Real return", format=".1f"),
        alt.Tooltip("Runway_Label:N", title="Runway"),
    ]
    base = alt.Chart(sensitivity).encode(
        x=alt.X(
            "Return_Rate:O",
            title="Expected real return",
            axis=return_axis,
        ),
        y=alt.Y(
            "Spending_Change:N",
            title="Annual spending",
            sort=order,
            axis=spending_axis,
        ),
        tooltip=tooltip,
    )
    cells = base.mark_rect(cornerRadius=2).encode(
        color=alt.Color(
            "Runway_Years:Q",
            title="Runway (years)",
            scale=alt.Scale(
                domain=[0, 100],
                range=[COLOR_EXPENSE, COLOR_SAVINGS, COLOR_ASSET],
            ),
        ),
        stroke=alt.condition(
            "datum.Is_Baseline_Return",
            alt.value(COLOR_NET_WORTH),
            alt.value(None),
        ),
        strokeWidth=alt.condition(
            "datum.Is_Baseline_Return",
            alt.value(3),
            alt.value(0),
        ),
    )
    label_text = alt.value(MASKED_VALUE) if hidden else alt.Text("Runway_Label:N")
    labels = base.mark_text(fontSize=12).encode(
        text=label_text,
        color=alt.value("white"),
    )
    return cast(alt.LayerChart, (cells + labels).properties(height=220))


def _render_source_details(
    accounts: pd.DataFrame,
    monthly_spending: pd.DataFrame,
    transactions: pd.DataFrame,
    *,
    start_month: str,
    end_month: str,
) -> None:
    with st.expander("Source details", icon=":material/table_view:"):
        accounts_tab, spending_tab, transactions_tab = st.tabs(["Accounts", "Spending", "Transactions"])
        with accounts_tab:
            if accounts.empty:
                st.info("No portfolio accounts are selected.")
            else:
                value_safe_dataframe(
                    accounts.sort_values("Balance", ascending=False),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Balance": st.column_config.NumberColumn(format="$%.2f"),
                    },
                )
        with spending_tab:
            st.caption(f"{start_month} through {end_month}")
            spending_chart = (
                alt.Chart(monthly_spending)
                .mark_bar(color=COLOR_EXPENSE)
                .encode(
                    x=alt.X("Month:N", title="Month"),
                    y=alt.Y("Spending:Q", title="Spending"),
                    tooltip=[
                        alt.Tooltip("Month:N", title="Month"),
                        alt.Tooltip("Spending:Q", title="Spending", format="$,.0f"),
                    ],
                )
            )
            value_safe_altair_chart(spending_chart, width="stretch")
            category_spending = (
                transactions.groupby(["Group", "Category"], dropna=False)["Amount"]
                .sum()
                .mul(-1)
                .rename("Spending")
                .reset_index()
                .sort_values("Spending", ascending=False)
            )
            value_safe_dataframe(
                category_spending,
                width="stretch",
                hide_index=True,
                column_config={
                    "Spending": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
        with transactions_tab:
            display = transactions[["Date", "Full Description", "Group", "Category", "Account", "Amount"]].copy()
            display = display.rename(columns={"Full Description": "Description"})
            display["Spending"] = -display.pop("Amount")
            value_safe_dataframe(
                display.sort_values("Spending", ascending=False),
                width="stretch",
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn(format="MMM D, YYYY"),
                    "Spending": st.column_config.NumberColumn(format="$%.2f"),
                },
            )


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet,
) -> None:
    st.header("Financial independence")

    transactions_df = transactions_spreadsheet.scrubbed_df.copy()
    balances_df = balance_history_spreadsheet.scrubbed_df.copy()
    if transactions_df.empty or balances_df.empty:
        st.info("Transaction and balance history are required for this analysis.")
        return

    latest_transactions = latest_data_timestamp(transactions_df)
    latest_balances = latest_data_timestamp(balances_df)
    if latest_transactions is not None and latest_balances is not None:
        st.caption(
            "Transactions through "
            f"{latest_transactions.strftime('%B %d, %Y').replace(' 0', ' ')} · "
            "balances through "
            f"{latest_balances.strftime('%B %d, %Y').replace(' 0', ' ')}"
        )

    all_accounts = get_all_accounts(balances_df)
    source_controls, _ = st.columns([1.25, 4], vertical_alignment="bottom")
    with source_controls:
        filters = render_fi_filters(
            all_accounts,
            transactions_spreadsheet.get_all_categories(),
            transactions_spreadsheet.get_all_groups(),
            _get_savings_accounts(balances_df),
        )

    accounts, calculated_portfolio = get_portfolio_value(
        balances_df,
        filters["include_accounts"],
    )
    start_month, end_month = rolling_month_window(filters["spending_lookback_months"])
    available_months = transactions_df["Month"].dropna().astype(str)
    if not available_months.empty:
        start_month = max(start_month, str(available_months.min()))
    expenses = apply_transaction_filters(
        transactions_df,
        _build_spending_filters(filters),
    )
    expenses = expenses[expenses["Type"].eq("Expense") & expenses["Month"].between(start_month, end_month)].copy()
    monthly_spending_value, monthly_spending = calculate_avg_monthly_spending(
        expenses,
        start_month,
        end_month,
    )
    calculated_spending = monthly_spending_value * 12

    assets, spending, income, return_rate, withdrawal_rate, years = _render_scenario_controls(
        calculated_portfolio, calculated_spending
    )
    summary = calculate_fi_metrics(
        assets,
        spending,
        return_rate,
        annual_income=income,
        withdrawal_rate_pct=withdrawal_rate,
    )
    projection = project_portfolio(
        assets,
        spending,
        return_rate,
        years,
        annual_income=income,
    )
    _render_metrics(summary)

    with st.container(border=True):
        st.subheader("Portfolio runway")
        value_safe_altair_chart(_create_projection_chart(projection), width="stretch")

    supporting = st.columns([1, 2])
    with supporting[0]:
        with st.container(border=True, height="stretch"):
            st.subheader("Annual funding")
            value_safe_altair_chart(_create_funding_chart(summary), width="stretch")
    with supporting[1]:
        with st.container(border=True, height="stretch"):
            st.subheader("Runway sensitivity")
            sensitivity = build_runway_sensitivity(
                assets,
                spending,
                income,
                baseline_return_rate=return_rate,
            )
            value_safe_altair_chart(
                _create_sensitivity_chart(sensitivity),
                width="stretch",
            )

    _render_source_details(
        accounts,
        monthly_spending,
        expenses,
        start_month=start_month,
        end_month=end_month,
    )


def main() -> None:
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    configure_page(load_transactions_data(), load_balance_history_data())


if __name__ == "__main__":
    main()
