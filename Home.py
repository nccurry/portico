"""Application navigation shell and balance-sheet overview."""

from datetime import timedelta
from typing import cast

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis.data_health import (
    find_missing_account_mappings,
    find_stale_accounts,
)
from src.analysis.financial_safety import build_financial_safety_summary
from src.analysis.home import (
    build_account_inventory,
    build_balance_group_inventory,
    build_net_worth_history,
)
from src.config import ConfigError, get_settings
from src.constants import (
    CHART_HEIGHT_SPARKLINE,
    COLOR_ASSET,
    COLOR_LIABILITY,
    COLOR_NET_WORTH,
    SPARKLINE_LOOKBACK_DEFAULT,
    SPARKLINE_LOOKBACK_OPTIONS,
)
from src.custom_types import FinancialSafetySummary
from src.page_helpers import render_data_refresh_controls, render_demo_banner, render_time_frame_control
from src.reporting_periods import latest_data_timestamp, reporting_anchor
from src.spreadsheet import (
    BalanceHistorySpreadsheet,
    TransactionsSpreadsheet,
    load_balance_history_data,
    load_transactions_data,
)
from src.value_visibility import (
    mask_chart_values,
    mask_numeric_column_config,
    mask_value,
    render_value_visibility_control,
)

ANALYZE_PAGE_SPECS = (
    ("app_pages/1_Income_and_Savings.py", "Income and savings", ":material/savings:"),
    (
        "app_pages/6_Merchant_Analysis.py",
        "Spending by merchant",
        ":material/storefront:",
    ),
    (
        "app_pages/2_Spending_by_Category.py",
        "Spending by category",
        ":material/category:",
    ),
    ("app_pages/3_Year_over_Year.py", "Year over year", ":material/compare_arrows:"),
    ("app_pages/5_Subscriptions.py", "Subscriptions", ":material/subscriptions:"),
    ("app_pages/8_Top_Transactions.py", "Transactions", ":material/receipt_long:"),
)


def create_financial_position_chart(history: pd.DataFrame) -> alt.LayerChart:
    """Show signed assets and liabilities with net worth overlaid."""
    date_axis = alt.Axis(title=None, format="%b %Y", labelAngle=-35)
    value_axis = alt.Axis(title=None, format="$,.2s")
    color = alt.Color(
        "Series:N",
        title=None,
        scale=alt.Scale(
            domain=["Assets", "Liabilities"],
            range=[COLOR_ASSET, COLOR_LIABILITY],
        ),
        legend=alt.Legend(orient="top", direction="horizontal"),
    )
    areas = (
        alt.Chart(history)
        .transform_fold(["Assets", "Liabilities"], as_=["Series", "Value"])
        .mark_area(opacity=0.34, line={"strokeWidth": 1.5})
        .encode(
            x=alt.X("Date:T", axis=date_axis),
            y=alt.Y("Value:Q", axis=value_axis),
            color=color,
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("Series:N", title="Balance type"),
                alt.Tooltip("Value:Q", title="Balance", format="$,.0f"),
            ],
        )
    )
    net_worth = (
        alt.Chart(history)
        .mark_line(color=COLOR_NET_WORTH, strokeWidth=3)
        .encode(
            x=alt.X("Date:T", axis=date_axis),
            y=alt.Y("Net_Worth:Q", axis=value_axis),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("Net_Worth:Q", title="Net worth", format="$,.0f"),
            ],
        )
    )
    zero = alt.Chart(pd.DataFrame({"Value": [0]})).mark_rule(color="#64748B", opacity=0.55).encode(y="Value:Q")
    return cast(alt.LayerChart, alt.layer(areas, zero, net_worth).properties(height=330))


def create_account_group_sparkline(trend: list[float], *, color: str) -> alt.Chart:
    """Show an account-group trend with its semantic balance color."""
    history = pd.DataFrame({"Position": range(len(trend)), "Balance": trend})
    return cast(
        alt.Chart,
        (
            alt.Chart(history)
            .mark_line(color=color, strokeWidth=2)
            .encode(
                x=alt.X("Position:Q", axis=None),
                y=alt.Y("Balance:Q", axis=None),
            )
            .properties(height=CHART_HEIGHT_SPARKLINE)
            .configure_view(stroke=None)
        ),
    )


def create_net_worth_attribution_chart(groups: pd.DataFrame) -> alt.Chart:
    """Show which account groups contributed to the selected net-worth movement."""
    order = groups.sort_values("Period_Change")["Group"].tolist()
    return cast(
        alt.Chart,
        (
            alt.Chart(groups)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("Period_Change:Q", title="Net-worth movement ($)", axis=alt.Axis(format="$,.2s")),
                y=alt.Y("Group:N", title=None, sort=order),
                color=alt.condition(
                    "datum.Period_Change >= 0",
                    alt.value(COLOR_ASSET),
                    alt.value(COLOR_LIABILITY),
                ),
                tooltip=[
                    alt.Tooltip("Group:N", title="Account group"),
                    alt.Tooltip("Period_Change:Q", title="Net-worth movement", format="$,.0f"),
                    alt.Tooltip("Net_Contribution:Q", title="Current contribution", format="$,.0f"),
                ],
            )
            .properties(height=max(180, len(groups) * 42))
        ),
    )


@st.cache_data(show_spinner=False)
def _analyze_balances(
    balances: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build balance history, group inventory, and current account inventory."""
    return (
        build_net_worth_history(balances, start_date, end_date),
        build_balance_group_inventory(balances, start_date, end_date),
        build_account_inventory(balances, start_date, end_date),
    )


def _format_date(value: pd.Timestamp | None) -> str:
    """Format an optional data timestamp for page copy."""
    return value.strftime("%b %d, %Y") if value is not None else "not available"


def _render_global_status(
    balance_as_of: pd.Timestamp | None,
    balances: pd.DataFrame,
) -> None:
    """Show compact balance freshness and account-mapping signals."""
    stale_count = len(find_stale_accounts(balances, as_of=balance_as_of)) if balance_as_of is not None else 0
    missing_mapping_count = len(find_missing_account_mappings(balances))

    with (
        st.container(border=True),
        st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
            gap="small",
        ),
    ):
        st.caption(f"Latest balance update {_format_date(balance_as_of)}")
        if stale_count:
            st.badge(
                f"{mask_value(str(stale_count))} stale account{'s' if stale_count != 1 else ''}",
                icon=":material/history:",
                color="orange",
            )
        if missing_mapping_count:
            st.badge(
                f"{mask_value(str(missing_mapping_count))} missing account "
                f"mapping{'s' if missing_mapping_count != 1 else ''}",
                icon=":material/account_tree:",
                color="orange",
            )
        if balance_as_of is not None and not stale_count and not missing_mapping_count:
            st.badge(
                "Account data looks current",
                icon=":material/check_circle:",
                color="green",
            )
        st.page_link(
            "app_pages/10_Data_Health.py",
            label="Data health",
            icon=":material/arrow_forward:",
        )


def _period_label(
    history: pd.DataFrame,
    requested_start: pd.Timestamp,
    lookback: str,
) -> str:
    """Describe the actual comparison window shown in a metric."""
    observed_start = pd.Timestamp(history["Date"].iloc[0])
    if lookback == "All" or observed_start > requested_start + pd.Timedelta(days=7):
        return f"since {observed_start:%b %Y}"
    return f"over {lookback}"


def _format_currency(value: float, *, show_plus: bool = False) -> str:
    """Format a dollar amount with an optional explicit positive sign."""
    sign = "-" if value < 0 else "+" if show_plus and value > 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _render_financial_position(
    history: pd.DataFrame,
    requested_start: pd.Timestamp,
    lookback: str,
) -> None:
    """Render the balance-sheet metrics and signed history in one section."""
    current = history.iloc[-1]
    opening = history.iloc[0]
    period = _period_label(history, requested_start, lookback)
    net_worth_change = float(current["Net_Worth"] - opening["Net_Worth"])
    asset_change = float(current["Assets"] - opening["Assets"])
    liability_change = abs(float(current["Liabilities"])) - abs(float(opening["Liabilities"]))

    with st.container(border=True):
        st.subheader("Net worth history")
        with st.container(horizontal=True, gap="small"):
            st.metric(
                "Net worth",
                _format_currency(float(current["Net_Worth"])),
                delta=f"{_format_currency(net_worth_change, show_plus=True)} {period}",
                delta_description="Change in net worth across the selected time frame",
                width="stretch",
            )
            st.metric(
                "Assets",
                _format_currency(float(current["Assets"])),
                delta=f"{_format_currency(asset_change, show_plus=True)} {period}",
                delta_description="Change in total asset balances",
                width="stretch",
            )
            st.metric(
                "Liabilities",
                _format_currency(abs(float(current["Liabilities"]))),
                delta=f"{_format_currency(liability_change, show_plus=True)} {period}",
                delta_color="inverse",
                delta_description="Change in total liability balances; lower is better",
                width="stretch",
            )
        st.altair_chart(
            mask_chart_values(create_financial_position_chart(history)),
            width="stretch",
        )


def _render_net_worth_attribution(groups: pd.DataFrame) -> None:
    """Render a group-level explanation of the selected net-worth movement."""
    if groups.empty:
        return
    with st.container(border=True):
        st.subheader(
            "What changed",
            help=(
                "Balance movement by account group across the selected time frame. "
                "Transfers can offset between groups; this is not an investment-return calculation."
            ),
        )
        st.altair_chart(mask_chart_values(create_net_worth_attribution_chart(groups)), width="stretch")


def _progress_bar(value: float | None) -> float:
    """Clamp a percentage for Streamlit's 0-to-1 progress indicator."""
    if value is None:
        return 0.0
    return min(max(value / 100, 0.0), 1.0)


def _render_financial_safety(summary: FinancialSafetySummary) -> None:
    """Render concise progress toward emergency, debt, and FI safety goals."""
    emergency_months = summary["emergency_fund_months_covered"]
    debt_progress = summary["debt_progress_pct"]
    fi_progress = summary["fi_progress_pct"]
    with st.container(border=True):
        st.subheader(
            "Financial safety",
            help=(
                "Emergency-fund and debt settings come from `[financial_safety]`. "
                "The FI funding target and account scope come from `[financial_independence]`."
            ),
        )
        columns = st.columns(3, gap="medium")
        with columns[0]:
            emergency_delta = (
                f"{mask_value(f'{emergency_months:.1f}')} of "
                f"{mask_value(str(summary['emergency_fund_target_months']))} months covered"
                if emergency_months is not None
                else "Need expense history to set a target"
            )
            st.metric(
                "Emergency fund",
                _format_currency(summary["emergency_fund_balance"]),
                delta=emergency_delta,
                delta_color="off",
            )
            st.progress(
                _progress_bar(
                    None
                    if emergency_months is None
                    else emergency_months / summary["emergency_fund_target_months"] * 100
                )
            )
            st.caption(f"Target {_format_currency(summary['emergency_fund_target'])}")
        with columns[1]:
            debt_label = summary["debt_baseline_label"]
            debt_delta = (
                f"{_format_currency(summary['debt_paid_down'], show_plus=True)} paid down since {debt_label}"
                if debt_label is not None
                else "Set debt groups to track payoff progress"
            )
            st.metric(
                "Debt balance",
                _format_currency(summary["debt_balance"]),
                delta=debt_delta,
            )
            st.progress(_progress_bar(debt_progress))
            if debt_progress is not None:
                st.caption(f"{mask_value(f'{debt_progress:.0f}%')} of starting balance paid down")
        with columns[2]:
            fi_delta = (
                f"{_format_currency(summary['fi_portfolio_value'] - summary['fi_target'], show_plus=True)} vs target"
                if fi_progress is not None
                else "Need expense history to calculate a target"
            )
            st.metric(
                "FI funding",
                mask_value(f"{fi_progress:.0f}%") if fi_progress is not None else "Not available",
                delta=fi_delta,
            )
            st.progress(_progress_bar(fi_progress))
            st.caption(f"Target {_format_currency(summary['fi_target'])}")
        st.page_link(
            "app_pages/9_Financial_Independence.py",
            label="Explore FI scenarios",
            icon=":material/arrow_forward:",
        )


def _render_account_group(group_row: pd.Series, accounts: pd.DataFrame) -> None:
    """Render one balance group and its current accounts."""
    group = str(group_row["Group"])
    is_liability = group_row["Type"] == "Liability"
    display_balance = float(group_row["Balance"] if is_liability else group_row["Net_Contribution"])
    display_change = float(-group_row["Period_Change"] if is_liability else group_row["Period_Change"])
    balance_label = "Debt" if is_liability else "Balance"
    change_description = (
        "Debt balance across the selected time frame; lower is better"
        if is_liability
        else "Balance change across the selected time frame"
    )
    selected_accounts = (
        accounts[accounts["Group"] == group]
        .sort_values(
            "Net_Contribution",
            key=lambda values: values.abs(),
            ascending=False,
        )
        .reset_index(drop=True)
    )

    with st.container(border=True):
        st.metric(
            group,
            _format_currency(display_balance),
            delta=_format_currency(display_change, show_plus=True),
            delta_color="inverse" if is_liability else "normal",
            delta_description=change_description,
            width="stretch",
        )
        trend = cast(list[float], group_row["Trend"])
        sparkline_color = COLOR_LIABILITY if is_liability else COLOR_ASSET
        st.altair_chart(
            mask_chart_values(create_account_group_sparkline(trend, color=sparkline_color)),
            width="stretch",
        )

        account_count = len(selected_accounts)
        with st.expander(
            f"Account details ({mask_value(str(account_count))})",
            icon=":material/account_balance:",
        ):
            balance_column = "Balance" if is_liability else "Net_Contribution"
            details = selected_accounts[
                [
                    "Account",
                    "Institution",
                    balance_column,
                    "Period_Change",
                    "Last_Updated",
                ]
            ].rename(
                columns={
                    balance_column: "Balance",
                    "Period_Change": "Change",
                }
            )
            if is_liability:
                details["Change"] = -details["Change"]
            st.dataframe(
                details,
                width="stretch",
                hide_index=True,
                column_config=mask_numeric_column_config(
                    details,
                    {
                        "Account": st.column_config.TextColumn("Account", pinned=True),
                        "Institution": "Institution",
                        "Balance": st.column_config.NumberColumn(balance_label, format="$%,.2f"),
                        "Change": st.column_config.NumberColumn("Change", format="$%+,.2f"),
                        "Last_Updated": st.column_config.DatetimeColumn(
                            "Updated",
                            format="MMM D, YYYY",
                        ),
                    },
                ),
                placeholder="No current accounts are available for this group.",
            )


def _render_account_groups(groups: pd.DataFrame, accounts: pd.DataFrame) -> None:
    """Render balance groups with responsive account summaries."""
    st.subheader("Account groups")
    if groups.empty:
        st.info("No mapped balance groups are available.", icon=":material/account_balance:")
        return

    display = groups.sort_values(
        "Net_Contribution",
        key=lambda values: values.abs(),
        ascending=False,
    ).reset_index(drop=True)
    for row_start in range(0, len(display), 2):
        columns = st.columns(2, gap="medium")
        rows = display.iloc[row_start : row_start + 2]
        for column, (_, group_row) in zip(columns, rows.iterrows(), strict=False):
            with column:
                _render_account_group(group_row, accounts)


def configure_page(
    balance_history_spreadsheet: BalanceHistorySpreadsheet,
    transactions_spreadsheet: TransactionsSpreadsheet,
    lookback: str,
) -> None:
    """Render the accounts and net-worth overview from loaded spreadsheet data."""
    balances = balance_history_spreadsheet.scrubbed_df.copy()
    balance_as_of = latest_data_timestamp(balances)

    if balances.empty:
        _render_global_status(balance_as_of, balances)
        st.info(
            "No balance history is available yet. Refresh after your spreadsheet has account balances.",
            icon=":material/info:",
        )
        return

    transactions = transactions_spreadsheet.scrubbed_df.copy()
    end_date = reporting_anchor(balances)
    lookback_days = SPARKLINE_LOOKBACK_OPTIONS[lookback]
    start_date = (
        pd.Timestamp(balances["Date"].min()) if lookback_days is None else end_date - timedelta(days=lookback_days)
    )
    history, groups, accounts = _analyze_balances(balances, start_date, end_date)
    if history.empty:
        st.info("No balance history is available for this time frame.", icon=":material/info:")
        return

    _render_financial_position(history, start_date, lookback)
    _render_net_worth_attribution(groups)
    _render_account_groups(groups, accounts)
    _render_financial_safety(
        build_financial_safety_summary(
            balances,
            transactions,
            get_settings().financial_safety,
            get_settings().financial_independence,
            as_of=reporting_anchor(transactions),
        )
    )
    _render_global_status(balance_as_of, balances)


def main() -> None:
    """Run the grouped multipage navigation shell."""
    st.set_page_config(
        page_title="Portico",
        page_icon=":material/account_balance:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    try:
        get_settings()
    except ConfigError as error:
        st.error(f"Configuration error: {error}")
        st.stop()
    render_demo_banner()

    def home_page() -> None:
        render_data_refresh_controls()
        st.title("Accounts and net worth")
        lookback = render_time_frame_control(
            list(SPARKLINE_LOOKBACK_OPTIONS),
            default=SPARKLINE_LOOKBACK_DEFAULT,
            key="home_balance_lookback",
        )
        selected_lookback = str(lookback) if lookback in SPARKLINE_LOOKBACK_OPTIONS else SPARKLINE_LOOKBACK_DEFAULT
        loading = st.empty()
        loading.skeleton(height=300)
        try:
            balance_history = load_balance_history_data()
            transactions = load_transactions_data()
        finally:
            loading.empty()
        configure_page(balance_history, transactions, selected_lookback)

    page = st.navigation(
        {
            "": [
                st.Page(home_page, title="Home", icon=":material/home:", default=True),
            ],
            "Analyze": [st.Page(path, title=title, icon=icon) for path, title, icon in ANALYZE_PAGE_SPECS],
            "Plan": [
                st.Page(
                    "app_pages/7_Budget.py",
                    title="Budget",
                    icon=":material/account_balance_wallet:",
                ),
                st.Page(
                    "app_pages/9_Financial_Independence.py",
                    title="Financial independence",
                    icon=":material/monitoring:",
                ),
            ],
            "Maintain": [
                st.Page(
                    "app_pages/10_Data_Health.py",
                    title="Data health",
                    icon=":material/health_and_safety:",
                ),
            ],
        },
        position="sidebar",
        expanded=True,
    )
    render_value_visibility_control()
    page.run()


if __name__ == "__main__":
    main()
