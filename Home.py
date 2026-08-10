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
from src.analysis.home import (
    build_account_inventory,
    build_balance_group_inventory,
    build_net_worth_history,
)
from src.constants import (
    COLOR_ASSET,
    COLOR_LIABILITY,
    COLOR_NET_WORTH,
    SPARKLINE_LOOKBACK_DEFAULT,
    SPARKLINE_LOOKBACK_OPTIONS,
)
from src.page_helpers import render_data_refresh_controls
from src.reporting_periods import latest_data_timestamp, reporting_anchor
from src.spreadsheet import (
    BalanceHistorySpreadsheet,
    load_balance_history_data,
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
    zero = (
        alt.Chart(pd.DataFrame({"Value": [0]}))
        .mark_rule(color="#64748B", opacity=0.55)
        .encode(y="Value:Q")
    )
    return cast(alt.LayerChart, alt.layer(areas, zero, net_worth).properties(height=330))


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
    stale_count = (
        len(find_stale_accounts(balances, as_of=balance_as_of))
        if balance_as_of is not None
        else 0
    )
    missing_mapping_count = len(find_missing_account_mappings(balances))

    with st.container(border=True):
        with st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
            gap="small",
        ):
            st.caption(f"Latest balance update {_format_date(balance_as_of)}")
            if stale_count:
                st.badge(
                    f"{stale_count} stale account{'s' if stale_count != 1 else ''}",
                    icon=":material/history:",
                    color="orange",
                )
            if missing_mapping_count:
                st.badge(
                    f"{missing_mapping_count} missing account "
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
                "pages/10_Data_Health.py",
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
    return f"{sign}${abs(value):,.0f}"


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
        st.altair_chart(create_financial_position_chart(history), width="stretch")


def _render_account_group(group_row: pd.Series, accounts: pd.DataFrame) -> None:
    """Render one balance group and its current accounts."""
    group = str(group_row["Group"])
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
            _format_currency(float(group_row["Net_Contribution"])),
            delta=_format_currency(float(group_row["Period_Change"]), show_plus=True),
            delta_description="Balance change across the selected time frame",
            chart_data=group_row["Trend"],
            chart_type="line",
            width="stretch",
        )

        account_count = len(selected_accounts)
        with st.expander(
            f"Account details ({account_count})",
            icon=":material/account_balance:",
        ):
            details = selected_accounts[
                [
                    "Account",
                    "Institution",
                    "Net_Contribution",
                    "Period_Change",
                    "Last_Updated",
                ]
            ].rename(
                columns={
                    "Net_Contribution": "Balance",
                    "Period_Change": "Change",
                }
            )
            st.dataframe(
                details,
                width="stretch",
                hide_index=True,
                column_config={
                    "Account": st.column_config.TextColumn("Account", pinned=True),
                    "Institution": "Institution",
                    "Balance": st.column_config.NumberColumn("Balance", format="$%+,.2f"),
                    "Change": st.column_config.NumberColumn("Change", format="$%+,.2f"),
                    "Last_Updated": st.column_config.DatetimeColumn(
                        "Updated",
                        format="MMM D, YYYY",
                    ),
                },
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
    lookback: str,
) -> None:
    """Render the accounts and net-worth overview from loaded Tiller sheets."""
    balances = balance_history_spreadsheet.scrubbed_df.copy()
    balance_as_of = latest_data_timestamp(balances)

    if balances.empty:
        _render_global_status(balance_as_of, balances)
        st.info(
            "No balance history is available yet. Refresh after Tiller has populated account balances.",
            icon=":material/info:",
        )
        return

    end_date = reporting_anchor(balances, anchor_to_data=True)
    lookback_days = SPARKLINE_LOOKBACK_OPTIONS[lookback]
    start_date = (
        pd.Timestamp(balances["Date"].min())
        if lookback_days is None
        else end_date - timedelta(days=lookback_days)
    )
    history, groups, accounts = _analyze_balances(balances, start_date, end_date)
    if history.empty:
        st.info("No balance history is available for this time frame.", icon=":material/info:")
        return

    _render_financial_position(history, start_date, lookback)
    _render_account_groups(groups, accounts)
    _render_global_status(balance_as_of, balances)


def main() -> None:
    """Run the grouped multipage navigation shell."""
    st.set_page_config(
        page_title="Tiller dashboard",
        page_icon=":material/account_balance:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    def home_page() -> None:
        render_data_refresh_controls()
        st.title("Accounts and net worth")
        lookback = st.segmented_control(
            "Time frame",
            options=list(SPARKLINE_LOOKBACK_OPTIONS),
            default=SPARKLINE_LOOKBACK_DEFAULT,
            key="home_balance_lookback",
            help="Controls every balance, movement, and trend shown on this page.",
            width="stretch",
        )
        selected_lookback = (
            str(lookback)
            if lookback in SPARKLINE_LOOKBACK_OPTIONS
            else SPARKLINE_LOOKBACK_DEFAULT
        )
        loading = st.empty()
        loading.skeleton(height=300)
        try:
            balance_history = load_balance_history_data()
        finally:
            loading.empty()
        configure_page(balance_history, selected_lookback)

    page = st.navigation(
        {
            "": [
                st.Page(home_page, title="Home", icon=":material/home:", default=True),
            ],
            "Analyze": [
                st.Page(
                    "pages/1_Income_and_Savings.py",
                    title="Income and savings",
                    icon=":material/savings:",
                ),
                st.Page(
                    "pages/2_Spending_by_Category.py",
                    title="Spending by category",
                    icon=":material/category:",
                ),
                st.Page(
                    "pages/3_Year_over_Year.py",
                    title="Year over year",
                    icon=":material/compare_arrows:",
                ),
                st.Page(
                    "pages/5_Subscriptions.py",
                    title="Subscriptions",
                    icon=":material/subscriptions:",
                ),
                st.Page(
                    "pages/6_Merchant_Analysis.py",
                    title="Merchant analysis",
                    icon=":material/storefront:",
                ),
                st.Page(
                    "pages/8_Top_Transactions.py",
                    title="Top transactions",
                    icon=":material/receipt_long:",
                ),
            ],
            "Plan": [
                st.Page(
                    "pages/7_Budget.py",
                    title="Budget",
                    icon=":material/account_balance_wallet:",
                ),
                st.Page(
                    "pages/9_Financial_Independence.py",
                    title="Financial independence",
                    icon=":material/monitoring:",
                ),
            ],
            "Maintain": [
                st.Page(
                    "pages/10_Data_Health.py",
                    title="Data health",
                    icon=":material/health_and_safety:",
                ),
            ],
        },
        position="sidebar",
        expanded=True,
    )
    page.run()


if __name__ == "__main__":
    main()
