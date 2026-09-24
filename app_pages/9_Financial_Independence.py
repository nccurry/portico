"""Interactive financial-independence scenario sandbox."""

from typing import cast

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from src.analysis.financial_independence import (
    IncomeStream,
    build_income_projection,
    build_runway_sensitivity,
    build_spending_coverage,
    calculate_avg_monthly_income,
    calculate_avg_monthly_spending,
    calculate_fi_metrics,
    get_accounts_in_groups,
    project_portfolio,
    summarize_spending_coverage,
)
from src.config import get_settings
from src.constants import (
    COLOR_ADDITIONAL_SPENDING,
    COLOR_ASSET,
    COLOR_EXPENSE,
    COLOR_INCOME,
    COLOR_NET_WORTH,
    COLOR_PLACEHOLDER,
    COLOR_RETIREMENT,
    COLOR_SAVINGS,
)
from src.custom_types import FIFilters, FIScenario, FISummary, IncomeChange, SpendingChange, TransactionFilterOptions
from src.filters import render_fi_filters
from src.page_helpers import currency_input, render_data_refresh_controls
from src.reporting_periods import latest_data_timestamp, rolling_month_window
from src.spreadsheet import (
    BalanceHistorySpreadsheet,
    TransactionsSpreadsheet,
    get_all_accounts,
    get_portfolio_value,
    load_balance_history_data,
    load_transactions_data,
)
from src.transaction_filters import apply_transaction_filters
from src.value_visibility import (
    MASKED_VALUE,
    mask_value,
    value_safe_altair_chart,
    value_safe_dataframe,
    values_hidden,
)

SCENARIO_KEYS = {
    "investments": "fi_scenario_investments",
    "real_estate": "fi_scenario_real_estate",
    "real_estate_monthly_cash_flow": "fi_scenario_real_estate_monthly_cash_flow",
    "real_estate_appreciation_rate": "fi_scenario_real_estate_appreciation_rate",
    "spending": "fi_scenario_spending",
    "income": "fi_scenario_income",
    "social_security": "fi_scenario_social_security",
    "social_security_start_year": "fi_scenario_social_security_start_year",
    "pension": "fi_scenario_pension",
    "pension_start_year": "fi_scenario_pension_start_year",
    "return_rate": "fi_scenario_return_rate",
    "withdrawal_rate": "fi_scenario_withdrawal_rate",
    "years": "fi_scenario_years",
}
SOURCE_KEYS = {
    "investments": "fi_source_investments",
    "real_estate": "fi_source_real_estate",
    "real_estate_monthly_cash_flow": "fi_source_real_estate_monthly_cash_flow",
    "real_estate_appreciation_rate": "fi_source_real_estate_appreciation_rate",
    "spending": "fi_source_spending",
    "income": "fi_source_income",
    "social_security": "fi_source_social_security",
    "social_security_start_year": "fi_source_social_security_start_year",
    "pension": "fi_source_pension",
    "pension_start_year": "fi_source_pension_start_year",
}
ACTIVE_STREAMS_KEY = "fi_active_streams"
VARIABLE_SPENDING_KEY = "fi_variable_spending"
SPENDING_ROWS_KEY = "fi_spending_rows"
NEXT_SPENDING_ROW_KEY = "fi_next_spending_row"
VARIABLE_INCOME_KEY = "fi_variable_income"
INCOME_ROWS_KEY = "fi_income_rows"
NEXT_INCOME_ROW_KEY = "fi_next_income_row"
STREAM_OPTIONS = ("Earned income", "Investments", "Real estate", "Social Security", "Pension")


def _currency(value: float, *, signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _build_spending_filters(filters: FIFilters) -> TransactionFilterOptions:
    return {
        "exclude_groups": filters["exclude_groups"],
        "exclude_categories": filters["exclude_categories"],
        "include_transactions_like": filters.get("include_transactions_like", []),
        "exclude_transactions_like": filters.get("exclude_transactions_like", []),
        "filter_large_expenses": filters["filter_large_expenses"],
        "expense_threshold": filters["expense_threshold"],
    }


def _default_active_streams() -> list[str]:
    """Return the configured streams for a fresh scenario."""
    return [
        "Earned income" if stream == "Income" else stream
        for stream in get_settings().financial_independence.default_active_streams
    ]


def _set_source_default(name: str, source_value: float) -> None:
    """Refresh one scenario value only when it still follows source data."""
    scenario_key = SCENARIO_KEYS[name]
    source_key = SOURCE_KEYS[name]
    previous_source = st.session_state.get(source_key)
    if scenario_key not in st.session_state or st.session_state[scenario_key] == previous_source:
        st.session_state[scenario_key] = source_value
    st.session_state[source_key] = source_value


def _set_scenario_defaults(source_values: dict[str, float]) -> None:
    defaults_config = get_settings().financial_independence
    for name, source_value in source_values.items():
        _set_source_default(name, source_value)
    defaults = {
        SCENARIO_KEYS["return_rate"]: defaults_config.expected_return_rate,
        SCENARIO_KEYS["withdrawal_rate"]: defaults_config.withdrawal_rate,
        SCENARIO_KEYS["years"]: defaults_config.projection_years,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault(ACTIVE_STREAMS_KEY, _default_active_streams())
    st.session_state.setdefault(VARIABLE_SPENDING_KEY, False)
    st.session_state.setdefault(SPENDING_ROWS_KEY, [])
    st.session_state.setdefault(NEXT_SPENDING_ROW_KEY, 0)
    st.session_state.setdefault(VARIABLE_INCOME_KEY, False)
    st.session_state.setdefault(INCOME_ROWS_KEY, [])
    st.session_state.setdefault(NEXT_INCOME_ROW_KEY, 0)


def _spending_row_keys(row_id: int) -> tuple[str, str]:
    return f"fi_spending_start_{row_id}", f"fi_spending_amount_{row_id}"


def _clear_spending_row(row_id: int) -> None:
    start_key, amount_key = _spending_row_keys(row_id)
    for key in (start_key, amount_key, f"{amount_key}_currency", f"{amount_key}_currency_synced"):
        st.session_state.pop(key, None)


def _remove_spending_change(row_id: int) -> None:
    st.session_state[SPENDING_ROWS_KEY] = [
        current for current in st.session_state[SPENDING_ROWS_KEY] if current != row_id
    ]
    _clear_spending_row(row_id)


def _add_spending_change() -> None:
    rows = st.session_state[SPENDING_ROWS_KEY]
    row_id = st.session_state[NEXT_SPENDING_ROW_KEY] + 1
    st.session_state[NEXT_SPENDING_ROW_KEY] = row_id
    previous_year = max((st.session_state[_spending_row_keys(current)[0]] for current in rows), default=1)
    previous_amount = (
        st.session_state[_spending_row_keys(rows[-1])[1]] if rows else st.session_state[SCENARIO_KEYS["spending"]]
    )
    start_key, amount_key = _spending_row_keys(row_id)
    st.session_state[start_key] = min(previous_year + 5, 100)
    st.session_state[amount_key] = previous_amount
    st.session_state[SPENDING_ROWS_KEY] = [*rows, row_id]


def _income_row_keys(row_id: int) -> tuple[str, str]:
    return f"fi_income_start_{row_id}", f"fi_income_amount_{row_id}"


def _clear_income_row(row_id: int) -> None:
    start_key, amount_key = _income_row_keys(row_id)
    for key in (start_key, amount_key, f"{amount_key}_currency", f"{amount_key}_currency_synced"):
        st.session_state.pop(key, None)


def _remove_income_change(row_id: int) -> None:
    st.session_state[INCOME_ROWS_KEY] = [current for current in st.session_state[INCOME_ROWS_KEY] if current != row_id]
    _clear_income_row(row_id)


def _add_income_change() -> None:
    rows = st.session_state[INCOME_ROWS_KEY]
    row_id = st.session_state[NEXT_INCOME_ROW_KEY] + 1
    st.session_state[NEXT_INCOME_ROW_KEY] = row_id
    previous_year = max((st.session_state[_income_row_keys(current)[0]] for current in rows), default=1)
    previous_amount = (
        st.session_state[_income_row_keys(rows[-1])[1]] if rows else st.session_state[SCENARIO_KEYS["income"]]
    )
    start_key, amount_key = _income_row_keys(row_id)
    st.session_state[start_key] = min(previous_year + 5, 100)
    st.session_state[amount_key] = previous_amount
    st.session_state[INCOME_ROWS_KEY] = [*rows, row_id]


def _reset_scenario(source_values: dict[str, float]) -> None:
    defaults_config = get_settings().financial_independence
    for name, source_value in source_values.items():
        st.session_state[SCENARIO_KEYS[name]] = source_value
        st.session_state[SOURCE_KEYS[name]] = source_value
    st.session_state[SCENARIO_KEYS["return_rate"]] = defaults_config.expected_return_rate
    st.session_state[SCENARIO_KEYS["withdrawal_rate"]] = defaults_config.withdrawal_rate
    st.session_state[SCENARIO_KEYS["years"]] = defaults_config.projection_years
    st.session_state[ACTIVE_STREAMS_KEY] = _default_active_streams()
    for row_id in st.session_state[SPENDING_ROWS_KEY]:
        _clear_spending_row(row_id)
    st.session_state[SPENDING_ROWS_KEY] = []
    st.session_state[VARIABLE_SPENDING_KEY] = False
    for row_id in st.session_state[INCOME_ROWS_KEY]:
        _clear_income_row(row_id)
    st.session_state[INCOME_ROWS_KEY] = []
    st.session_state[VARIABLE_INCOME_KEY] = False


def _scenario_from_state() -> FIScenario:
    """Return the current stream scenario from session state."""
    active_streams = tuple(cast(list[str], st.session_state[ACTIVE_STREAMS_KEY]))
    spending_schedule: tuple[SpendingChange, ...] = ()
    if st.session_state[VARIABLE_SPENDING_KEY]:
        changes = []
        for row_id in st.session_state[SPENDING_ROWS_KEY]:
            start_key, amount_key = _spending_row_keys(row_id)
            changes.append(SpendingChange(int(st.session_state[start_key]), float(st.session_state[amount_key])))
        spending_schedule = tuple(sorted(changes, key=lambda change: change.start_year))
        if any(change.start_year > 100 or change.annual_amount > 10_000_000 for change in spending_schedule):
            raise ValueError("Spending changes must stay within the shown year and expense limits.")
        if len({change.start_year for change in spending_schedule}) != len(spending_schedule):
            raise ValueError("Use a different start year for each spending change.")
    income_schedule: tuple[IncomeChange, ...] = ()
    if st.session_state[VARIABLE_INCOME_KEY] and "Earned income" in active_streams:
        income_changes = []
        for row_id in st.session_state[INCOME_ROWS_KEY]:
            start_key, amount_key = _income_row_keys(row_id)
            income_changes.append(IncomeChange(int(st.session_state[start_key]), float(st.session_state[amount_key])))
        income_schedule = tuple(sorted(income_changes, key=lambda change: change.start_year))
        if any(change.start_year > 100 or change.annual_amount > 10_000_000 for change in income_schedule):
            raise ValueError("Income changes must stay within the shown year and amount limits.")
        if len({change.start_year for change in income_schedule}) != len(income_schedule):
            raise ValueError("Use a different start year for each income change.")
    return FIScenario(
        investments=float(st.session_state[SCENARIO_KEYS["investments"]]),
        real_estate=float(st.session_state[SCENARIO_KEYS["real_estate"]]),
        real_estate_monthly_cash_flow=float(st.session_state[SCENARIO_KEYS["real_estate_monthly_cash_flow"]]),
        real_estate_appreciation_rate=float(st.session_state[SCENARIO_KEYS["real_estate_appreciation_rate"]]),
        annual_spending=float(st.session_state[SCENARIO_KEYS["spending"]]),
        annual_income=float(st.session_state[SCENARIO_KEYS["income"]]),
        social_security_annual_income=float(st.session_state[SCENARIO_KEYS["social_security"]]),
        social_security_start_year=int(st.session_state[SCENARIO_KEYS["social_security_start_year"]]),
        pension_annual_income=float(st.session_state[SCENARIO_KEYS["pension"]]),
        pension_start_year=int(st.session_state[SCENARIO_KEYS["pension_start_year"]]),
        return_rate=float(st.session_state[SCENARIO_KEYS["return_rate"]]),
        withdrawal_rate=float(st.session_state[SCENARIO_KEYS["withdrawal_rate"]]),
        years=int(st.session_state[SCENARIO_KEYS["years"]]),
        active_streams=active_streams,
        spending_schedule=spending_schedule,
        income_schedule=income_schedule,
    )


def _render_scenario_controls(
    investments: float,
    real_estate: float,
    annual_spending: float,
    annual_income: float,
    reset_column: DeltaGenerator,
) -> FIScenario | None:
    defaults_config = get_settings().financial_independence
    source_values: dict[str, float] = {
        "investments": float(round(investments)),
        "real_estate": float(round(real_estate)),
        "real_estate_monthly_cash_flow": defaults_config.real_estate_monthly_cash_flow,
        "real_estate_appreciation_rate": defaults_config.real_estate_appreciation_rate,
        "spending": float(round(annual_spending)),
        "income": float(round(annual_income)),
        "social_security": defaults_config.social_security_annual_income,
        "social_security_start_year": defaults_config.social_security_start_year,
        "pension": defaults_config.pension_annual_income,
        "pension_start_year": defaults_config.pension_start_year,
    }
    _set_scenario_defaults(source_values)
    if values_hidden():
        st.caption("Show values to edit your plan.")
        try:
            return _scenario_from_state()
        except ValueError as error:
            st.error(str(error))
            return None

    with st.container():
        with reset_column:
            st.button(
                ":material/restore:",
                key="fi_reset_plan",
                help="Reset plan to defaults",
                width="content",
                on_click=_reset_scenario,
                args=(source_values,),
            )

        selected_streams = st.pills(
            "Include in plan",
            options=STREAM_OPTIONS,
            selection_mode="multi",
            help=(
                "Investments adds your current balance. Money left after expenses is invested at the configured "
                "growth rate, even when Investments is off."
            ),
            key=ACTIVE_STREAMS_KEY,
            format_func=lambda stream: "Income" if stream == "Earned income" else stream,
            persist_state="session",
            width="stretch",
        )
        active_streams = cast(list[str], selected_streams or [])

        if "Earned income" in active_streams:
            if st.session_state[VARIABLE_INCOME_KEY]:
                st.markdown("**Income over time**")
                first_income_columns = st.columns([1, 2, 1], vertical_alignment="bottom")
                with first_income_columns[0]:
                    st.number_input("Starts in year", value=1, disabled=True)
                with first_income_columns[1]:
                    currency_input(
                        "Income per year",
                        min_value=0.0,
                        max_value=10_000_000.0,
                        key=SCENARIO_KEYS["income"],
                        persist_state="session",
                    )
                for row_id in st.session_state[INCOME_ROWS_KEY]:
                    start_key, amount_key = _income_row_keys(row_id)
                    income_columns = st.columns([1, 2, 1], vertical_alignment="bottom")
                    with income_columns[0]:
                        st.number_input(
                            "Starts in year",
                            min_value=2,
                            max_value=100,
                            step=1,
                            key=start_key,
                            persist_state="session",
                        )
                    with income_columns[1]:
                        currency_input(
                            "Income per year",
                            min_value=0.0,
                            max_value=10_000_000.0,
                            key=amount_key,
                            persist_state="session",
                        )
                    with income_columns[2]:
                        st.button(
                            "Remove",
                            icon=":material/delete:",
                            key=f"fi_remove_income_{row_id}",
                            on_click=_remove_income_change,
                            args=(row_id,),
                            width="stretch",
                        )
                st.button(
                    "Add income period",
                    icon=":material/add:",
                    on_click=_add_income_change,
                    disabled=any(
                        st.session_state[_income_row_keys(row_id)[0]] == 100
                        for row_id in st.session_state[INCOME_ROWS_KEY]
                    ),
                )
            else:
                st.markdown("**Income**")
                currency_input(
                    "Income",
                    min_value=0.0,
                    max_value=10_000_000.0,
                    key=SCENARIO_KEYS["income"],
                    persist_state="session",
                )

        if st.session_state[VARIABLE_SPENDING_KEY]:
            st.markdown("**Expenses over time**")
            first_period_columns = st.columns([1, 2, 1], vertical_alignment="bottom")
            with first_period_columns[0]:
                st.number_input("Starts in year", value=1, disabled=True)
            with first_period_columns[1]:
                currency_input(
                    "Expenses per year",
                    min_value=0.0,
                    max_value=10_000_000.0,
                    key=SCENARIO_KEYS["spending"],
                    persist_state="session",
                )
            for row_id in st.session_state[SPENDING_ROWS_KEY]:
                start_key, amount_key = _spending_row_keys(row_id)
                period_columns = st.columns([1, 2, 1], vertical_alignment="bottom")
                with period_columns[0]:
                    st.number_input(
                        "Starts in year",
                        min_value=2,
                        max_value=100,
                        step=1,
                        key=start_key,
                        persist_state="session",
                    )
                with period_columns[1]:
                    currency_input(
                        "Expenses per year",
                        min_value=0.0,
                        max_value=10_000_000.0,
                        key=amount_key,
                        persist_state="session",
                    )
                with period_columns[2]:
                    st.button(
                        "Remove",
                        icon=":material/delete:",
                        key=f"fi_remove_spending_{row_id}",
                        on_click=_remove_spending_change,
                        args=(row_id,),
                        width="stretch",
                    )
            st.button(
                "Add expense period",
                icon=":material/add:",
                on_click=_add_spending_change,
                disabled=any(
                    st.session_state[_spending_row_keys(row_id)[0]] == 100
                    for row_id in st.session_state[SPENDING_ROWS_KEY]
                ),
            )
        else:
            st.markdown("**Expenses**")
            currency_input(
                "Expenses",
                min_value=0.0,
                max_value=10_000_000.0,
                key=SCENARIO_KEYS["spending"],
                persist_state="session",
            )

        active_assets = "Investments" in active_streams or "Real estate" in active_streams
        if active_assets:
            asset_columns = st.columns(int("Investments" in active_streams) + int("Real estate" in active_streams))
            column_index = 0
            if "Investments" in active_streams:
                with asset_columns[column_index]:
                    st.markdown("**Investments**")
                    currency_input(
                        "Investment balance",
                        min_value=-100_000_000.0,
                        max_value=100_000_000.0,
                        key=SCENARIO_KEYS["investments"],
                        persist_state="session",
                    )
                    st.number_input(
                        "Yearly investment growth (%)",
                        min_value=0.0,
                        max_value=20.0,
                        step=0.5,
                        format="%.1f",
                        help="Expected growth after inflation.",
                        key=SCENARIO_KEYS["return_rate"],
                        persist_state="session",
                    )
                column_index += 1
            if "Real estate" in active_streams:
                with asset_columns[column_index]:
                    st.markdown("**Real estate**")
                    currency_input(
                        "Property value",
                        min_value=-100_000_000.0,
                        max_value=100_000_000.0,
                        key=SCENARIO_KEYS["real_estate"],
                        persist_state="session",
                    )
                    currency_input(
                        "Monthly property cash flow",
                        min_value=-1_000_000.0,
                        max_value=1_000_000.0,
                        help="Money left after property costs. It can be negative.",
                        key=SCENARIO_KEYS["real_estate_monthly_cash_flow"],
                        persist_state="session",
                    )
                    st.number_input(
                        "Yearly property growth (%)",
                        min_value=-20.0,
                        max_value=20.0,
                        step=0.5,
                        format="%.1f",
                        help="Expected growth after inflation.",
                        key=SCENARIO_KEYS["real_estate_appreciation_rate"],
                        persist_state="session",
                    )

        active_retirement = "Social Security" in active_streams or "Pension" in active_streams
        if active_retirement:
            st.markdown("**Retirement income**")
            retirement_columns = st.columns(int("Social Security" in active_streams) + int("Pension" in active_streams))
            column_index = 0
            if "Social Security" in active_streams:
                with retirement_columns[column_index]:
                    currency_input(
                        "Yearly Social Security",
                        min_value=0.0,
                        max_value=10_000_000.0,
                        key=SCENARIO_KEYS["social_security"],
                        persist_state="session",
                    )
                    st.number_input(
                        "Social Security starts in (years)",
                        min_value=1,
                        max_value=100,
                        step=1,
                        key=SCENARIO_KEYS["social_security_start_year"],
                        persist_state="session",
                    )
                column_index += 1
            if "Pension" in active_streams:
                with retirement_columns[column_index]:
                    currency_input(
                        "Yearly pension",
                        min_value=0.0,
                        max_value=10_000_000.0,
                        key=SCENARIO_KEYS["pension"],
                        persist_state="session",
                    )
                    st.number_input(
                        "Pension starts in (years)",
                        min_value=1,
                        max_value=100,
                        step=1,
                        key=SCENARIO_KEYS["pension_start_year"],
                        persist_state="session",
                    )

        st.markdown("**Plan settings**")
        assumption_columns = st.columns(2)
        with assumption_columns[0]:
            st.number_input(
                "Portfolio withdrawal rate (%)",
                min_value=0.5,
                max_value=10.0,
                step=0.25,
                format="%.2f",
                help="The share of your included assets you plan to use each year. It sets your target.",
                key=SCENARIO_KEYS["withdrawal_rate"],
                persist_state="session",
            )
        with assumption_columns[1]:
            st.number_input(
                "Years to project",
                min_value=1,
                max_value=100,
                step=5,
                key=SCENARIO_KEYS["years"],
                persist_state="session",
            )
    try:
        return _scenario_from_state()
    except ValueError as error:
        st.error(str(error))
        return None


def _render_metrics(
    summary: FISummary,
    *,
    years_to_project: int,
    all_years_covered: bool,
    has_spending_changes: bool = False,
) -> None:
    runway = summary["runway_years"]
    if runway is None:
        runway_value = "Sustainable"
        runway_delta = "Your plan remains funded"
    elif all_years_covered:
        runway_value = "Covered"
        runway_delta = f"All {mask_value(str(years_to_project))} projected years funded"
    else:
        runway_value = mask_value(f"{runway:.1f} years")
        runway_delta = f"Until portfolio reaches {mask_value('$0')}"
    gap = summary["annual_surplus"]
    gap_delta = "Yearly surplus" if gap >= 0 else "Yearly shortfall"
    fi_gap = summary["fi_gap"]
    fi_delta = f"{_currency(fi_gap)} above target" if fi_gap >= 0 else f"{_currency(-fi_gap)} still needed"
    with st.container(horizontal=True):
        st.metric(
            "Runway",
            runway_value,
            delta=runway_delta,
            delta_color="off",
            help="Covered means expenses are funded for every projected year. Sustainable means the model does not project depletion.",
            border=True,
        )
        st.metric(
            "Yearly gap",
            _currency(gap, signed=True),
            delta=gap_delta,
            delta_color="normal",
            help="Based on year 1 expenses. Runway uses every spending change." if has_spending_changes else None,
            border=True,
        )
        st.metric(
            "Needed from portfolio",
            _currency(summary["net_annual_spending"]),
            delta=f"{_currency(summary['sustainable_spending'])} is sustainable at this rate",
            delta_color="off",
            border=True,
        )
        st.metric(
            "Investment target",
            _currency(summary["fi_target"]),
            delta=fi_delta,
            delta_color="normal",
            help="Based on year 1 expenses. Runway uses every spending change." if has_spending_changes else None,
            border=True,
        )


def _create_projection_chart(projection: pd.DataFrame) -> alt.LayerChart:
    base = alt.Chart(projection).encode(
        x=alt.X("Year:Q", title="Years from now", axis=alt.Axis(format="d")),
        y=alt.Y("Balance:Q", title="Total asset value", axis=alt.Axis(format="$,.2s")),
        tooltip=[
            alt.Tooltip("Year:Q", format="d"),
            alt.Tooltip("Starting_Balance:Q", title="Starting balance", format="$,.0f"),
            alt.Tooltip("Investment_Return:Q", title="Investment growth", format="$,.0f"),
            alt.Tooltip("Property_Growth:Q", title="Property growth", format="$,.0f"),
            alt.Tooltip("Income:Q", title="Income", format="$,.0f"),
            alt.Tooltip("Spending:Q", title="Expenses", format="$,.0f"),
            alt.Tooltip("Investments:Q", title="Investments", format="$,.0f"),
            alt.Tooltip("Real_Estate:Q", title="Real estate", format="$,.0f"),
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


def _create_spending_coverage_chart(coverage: pd.DataFrame) -> alt.Chart:
    """Show one bar for each stretch with the same funding mix."""
    stream_colors = {
        "Income": COLOR_INCOME,
        "Real estate cash flow": COLOR_ASSET,
        "Social Security": COLOR_RETIREMENT,
        "Pension": COLOR_ADDITIONAL_SPENDING,
        "From assets": COLOR_NET_WORTH,
        "Not covered": COLOR_EXPENSE,
    }
    periods = summarize_spending_coverage(coverage)
    stream_order = [
        stream for stream in stream_colors if periods.loc[periods["Stream"].eq(stream), "Amount"].ne(0).any()
    ]
    period_order = periods["Years"].drop_duplicates().tolist()
    return cast(
        alt.Chart,
        alt.Chart(periods[periods["Amount"].ne(0)])
        .mark_bar(size=32, cornerRadiusEnd=3)
        .encode(
            x=alt.X("sum(Amount):Q", title="Amount per year", axis=alt.Axis(format="$,.2s")),
            y=alt.Y("Years:N", title=None, sort=period_order, axis=alt.Axis(labelLimit=160)),
            color=alt.Color(
                "Stream:N",
                title=None,
                sort=stream_order,
                scale=alt.Scale(domain=stream_order, range=[stream_colors[stream] for stream in stream_order]),
                legend=alt.Legend(orient="bottom", direction="vertical", columns=1, labelLimit=250),
            ),
            tooltip=[
                alt.Tooltip("Years:N", title="Years"),
                alt.Tooltip("Stream:N", title="Source"),
                alt.Tooltip("Amount:Q", title="Amount per year", format="$,.0f"),
                alt.Tooltip("Needed:Q", title="Total needed", format="$,.0f"),
            ],
        )
        .properties(height=alt.Step(58)),
    )


def _create_sensitivity_chart(sensitivity: pd.DataFrame) -> alt.LayerChart:
    order = ["+20%", "+10%", "Baseline", "-10%", "-20%"]
    hidden = values_hidden()
    return_axis = alt.Axis(labelExpr=f"'{MASKED_VALUE}'") if hidden else alt.Axis(labelExpr="datum.label + '%'")
    spending_axis = alt.Axis(labelExpr=f"'{MASKED_VALUE}'") if hidden else alt.Undefined
    tooltip = [
        alt.Tooltip("Annual_Spending:Q", title="Starting expenses", format="$,.0f"),
        alt.Tooltip("Return_Rate:Q", title="Investment growth", format=".1f"),
        alt.Tooltip("Runway_Label:N", title="Runway"),
    ]
    base = alt.Chart(sensitivity).encode(
        x=alt.X(
            "Return_Rate:O",
            title="Investment growth (%)",
            axis=return_axis,
        ),
        y=alt.Y(
            "Spending_Change:N",
            title="Expenses",
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
        accounts_tab, expenses_tab, transactions_tab = st.tabs(["Accounts", "Expenses", "Transactions"])
        with accounts_tab:
            if accounts.empty:
                st.info("No active asset streams are selected.")
            else:
                value_safe_dataframe(
                    accounts.sort_values(["Stream", "Balance"], ascending=[True, False]),
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Balance": st.column_config.NumberColumn(format="$%.2f"),
                    },
                )
        with expenses_tab:
            st.caption(f"{start_month} through {end_month}")
            spending_chart = (
                alt.Chart(monthly_spending)
                .mark_bar(color=COLOR_EXPENSE)
                .encode(
                    x=alt.X("Month:N", title="Month"),
                    y=alt.Y("Spending:Q", title="Expenses"),
                    tooltip=[
                        alt.Tooltip("Month:N", title="Month"),
                        alt.Tooltip("Spending:Q", title="Expenses", format="$,.0f"),
                    ],
                )
            )
            value_safe_altair_chart(spending_chart, width="stretch")
            category_spending = (
                transactions.groupby(["Group", "Category"], dropna=False)["Amount"]
                .sum()
                .mul(-1)
                .rename("Expenses")
                .reset_index()
                .sort_values("Expenses", ascending=False)
            )
            value_safe_dataframe(
                category_spending,
                width="stretch",
                hide_index=True,
                column_config={
                    "Expenses": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
        with transactions_tab:
            display = transactions[["Date", "Full Description", "Group", "Category", "Account", "Amount"]].copy()
            display = display.rename(columns={"Full Description": "Description"})
            display["Expenses"] = -display.pop("Amount")
            value_safe_dataframe(
                display.sort_values("Expenses", ascending=False),
                width="stretch",
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn(format="MMM D, YYYY"),
                    "Expenses": st.column_config.NumberColumn(format="$%.2f"),
                },
            )


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet,
) -> None:
    st.title("Financial independence")

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

    settings = get_settings()
    all_accounts = get_all_accounts(balances_df)
    with st.container(border=True):
        header_columns = st.columns([5, 1], vertical_alignment="center")
        with header_columns[0]:
            st.subheader("Your plan")
        with header_columns[1]:
            header_actions = st.container(horizontal=True, horizontal_alignment="right")
        with header_actions:
            filters = render_fi_filters(
                all_accounts,
                transactions_spreadsheet.get_all_categories(),
                transactions_spreadsheet.get_all_groups(),
                get_accounts_in_groups(
                    balances_df,
                    settings.financial_independence.included_groups,
                ),
                get_accounts_in_groups(
                    balances_df,
                    settings.financial_independence.real_estate_included_groups,
                ),
            )
        warning_slot = st.empty()
        plan_content = st.container()

    investment_accounts, calculated_investments = get_portfolio_value(
        balances_df,
        filters["include_investment_accounts"],
    )
    investment_account_names = set(filters["include_investment_accounts"])
    overlapping_accounts = investment_account_names.intersection(filters["include_real_estate_accounts"])
    real_estate_account_names = [
        account for account in filters["include_real_estate_accounts"] if account not in overlapping_accounts
    ]
    if overlapping_accounts:
        warning_slot.warning(
            "Accounts selected for both Investments and Real estate are counted only once as Investments: "
            + ", ".join(sorted(overlapping_accounts)),
            icon=":material/error_outline:",
        )
    real_estate_accounts, calculated_real_estate = get_portfolio_value(
        balances_df,
        real_estate_account_names,
    )
    start_month, end_month = rolling_month_window(filters["spending_lookback_months"], transactions_df)
    available_months = transactions_df["Month"].dropna().astype(str)
    if not available_months.empty:
        start_month = max(start_month, str(available_months.min()))
    filtered_transactions = apply_transaction_filters(
        transactions_df,
        _build_spending_filters(filters),
    )
    expenses = filtered_transactions[
        filtered_transactions["Type"].eq("Expense") & filtered_transactions["Month"].between(start_month, end_month)
    ].copy()
    monthly_spending_value, monthly_spending = calculate_avg_monthly_spending(
        expenses,
        start_month,
        end_month,
    )
    calculated_spending = monthly_spending_value * 12
    calculated_income = 0.0
    if filters["income_from_transactions"]:
        monthly_income_value, _ = calculate_avg_monthly_income(
            transactions_df[transactions_df["Group"].ne("Transfer")],
            start_month,
            end_month,
        )
        calculated_income = monthly_income_value * 12

    with plan_content:
        scenario = _render_scenario_controls(
            calculated_investments,
            calculated_real_estate,
            calculated_spending,
            calculated_income,
            header_actions,
        )
    if scenario is None:
        return
    active_streams = set(scenario.active_streams)
    investments = scenario.investments if "Investments" in active_streams else 0.0
    property_value = scenario.real_estate if "Real estate" in active_streams else 0.0
    source_account_frames: list[pd.DataFrame] = []
    if "Investments" in active_streams:
        source_account_frames.append(investment_accounts.assign(Stream="Investments"))
    if "Real estate" in active_streams:
        source_account_frames.append(real_estate_accounts.assign(Stream="Real estate"))
    income_streams: list[IncomeStream] = []
    if "Social Security" in active_streams:
        income_streams.append(
            IncomeStream(
                "Social Security",
                scenario.social_security_annual_income,
                scenario.social_security_start_year,
            )
        )
    if "Pension" in active_streams:
        income_streams.append(IncomeStream("Pension", scenario.pension_annual_income, scenario.pension_start_year))
    if "Real estate" in active_streams:
        income_streams.append(IncomeStream("Real estate cash flow", scenario.real_estate_monthly_cash_flow * 12))
    annual_earned_income = scenario.annual_income if "Earned income" in active_streams else 0.0
    income_schedule = scenario.income_schedule if "Earned income" in active_streams else ()
    property_growth_rate = scenario.real_estate_appreciation_rate if "Real estate" in active_streams else 0.0
    income_projection = build_income_projection(
        annual_earned_income,
        tuple(income_streams),
        scenario.years,
        income_schedule,
    )
    summary = calculate_fi_metrics(
        investments,
        scenario.annual_spending,
        scenario.return_rate,
        annual_income=annual_earned_income,
        withdrawal_rate_pct=scenario.withdrawal_rate,
        income_streams=tuple(income_streams),
        real_estate_value=property_value,
        real_estate_rate_pct=property_growth_rate,
        spending_schedule=scenario.spending_schedule,
        income_schedule=income_schedule,
    )
    projection = project_portfolio(
        investments,
        scenario.annual_spending,
        scenario.return_rate,
        scenario.years,
        annual_income=annual_earned_income,
        income_streams=tuple(income_streams),
        real_estate_value=property_value,
        real_estate_rate_pct=property_growth_rate,
        spending_schedule=scenario.spending_schedule,
        income_schedule=income_schedule,
    )
    coverage = build_spending_coverage(income_projection, projection)
    all_years_covered = not coverage.loc[coverage["Stream"].eq("Not covered"), "Amount"].gt(0).any()
    _render_metrics(
        summary,
        years_to_project=scenario.years,
        all_years_covered=all_years_covered,
        has_spending_changes=bool(scenario.spending_schedule),
    )

    with st.container(border=True):
        st.subheader("Portfolio runway")
        value_safe_altair_chart(_create_projection_chart(projection), width="stretch")

    supporting = st.columns([1, 2])
    with supporting[0], st.container(border=True, height="stretch"):
        st.subheader(
            "How expenses are covered",
            help="Each bar shows one year's need. A property loss adds to that need. Red shows any amount the plan cannot cover.",
        )
        if coverage["Needed"].eq(0).all():
            st.info("No expenses to cover.")
        else:
            value_safe_altair_chart(_create_spending_coverage_chart(coverage), width="stretch")
    with supporting[1], st.container(border=True, height="stretch"):
        st.subheader(
            "Runway sensitivity",
            help="Expense changes apply to every spending period." if scenario.spending_schedule else None,
        )
        sensitivity = build_runway_sensitivity(
            investments,
            scenario.annual_spending,
            annual_earned_income,
            baseline_return_rate=scenario.return_rate,
            income_streams=tuple(income_streams),
            real_estate_value=property_value,
            real_estate_rate_pct=property_growth_rate,
            spending_schedule=scenario.spending_schedule,
            income_schedule=income_schedule,
        )
        value_safe_altair_chart(
            _create_sensitivity_chart(sensitivity),
            width="stretch",
        )

    _render_source_details(
        (
            pd.concat(source_account_frames, ignore_index=True)
            if source_account_frames
            else pd.DataFrame(columns=["Account", "Balance", "Stream"])
        ),
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
