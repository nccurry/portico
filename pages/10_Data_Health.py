"""Data Health page: prioritize cleanup work across imported Tiller data."""

from typing import TypedDict

import pandas as pd
import streamlit as st

from src.analysis.data_health import DataHealthReport, build_data_health_report
from src.analysis.duplicates import (
    find_duplicates_efficient,
    summarize_duplicates,
    summarize_duplicates_by_month,
)
from src.constants import DEFAULT_DUPLICATE_DAYS_THRESHOLD, MIN_DUPLICATE_AMOUNT
from src.custom_types import ColumnConfig
from src.page_helpers import get_transaction_column_config, render_data_refresh_controls
from src.spreadsheet import (
    BalanceHistorySpreadsheet,
    TransactionsSpreadsheet,
    load_balance_history_data,
    load_transactions_data,
)
from src.value_visibility import mask_value, value_safe_dataframe


class HealthCheck(TypedDict):
    """One row in the data-health issue queue."""

    key: str
    name: str
    status: str
    findings: int
    scope: str
    action: str
    data: pd.DataFrame


@st.cache_data(max_entries=10, show_spinner=False)
def _analyze_health(
    transactions: pd.DataFrame,
    balances: pd.DataFrame,
    stale_days: int,
    days_threshold: int,
    min_amount: float,
    check_same_account: bool,
    check_same_category: bool,
    require_same_description: bool,
) -> tuple[DataHealthReport, pd.DataFrame]:
    """Run all data-health checks for one settings combination."""
    report = build_data_health_report(
        transactions,
        balances,
        stale_days=stale_days,
    )
    duplicates = find_duplicates_efficient(
        transactions,
        days_threshold=days_threshold,
        min_amount=min_amount,
        check_same_account=check_same_account,
        check_same_category=check_same_category,
        require_same_description=require_same_description,
    )
    return report, duplicates


def _latest_timestamp(df: pd.DataFrame) -> pd.Timestamp | None:
    """Return the latest valid Date value in a frame."""
    if df.empty or "Date" not in df.columns:
        return None
    dates = pd.to_datetime(df["Date"], errors="coerce", utc=True).dropna()
    return pd.Timestamp(dates.max()) if not dates.empty else None


def _format_date(value: pd.Timestamp | None) -> str:
    """Format an optional timestamp for a metric value."""
    return value.strftime("%b %d, %Y") if value is not None else "No data"


def _age_label(value: pd.Timestamp | None) -> str:
    """Describe how old a source's latest row is."""
    if value is None:
        return "Source unavailable"
    today = pd.Timestamp.now(tz="UTC").normalize()
    age = max((today - value.normalize()).days, 0)
    if age == 0:
        return "Updated today"
    if age == 1:
        return f"Updated {mask_value('1')} day ago"
    return f"Updated {mask_value(str(age))} days ago"


def _amount_scope(df: pd.DataFrame, column: str = "Amount") -> str:
    """Format the gross financial scope of a set of findings."""
    if df.empty or column not in df.columns:
        return "—"
    amount = pd.to_numeric(df[column], errors="coerce").abs().sum()
    return mask_value(f"${amount:,.0f}")


def _build_health_checks(
    report: DataHealthReport,
    duplicates: pd.DataFrame,
) -> list[HealthCheck]:
    """Build the ordered issue queue shown on the page."""
    duplicate_summary = summarize_duplicates(duplicates)
    definitions: list[tuple[str, str, str, str, pd.DataFrame, str]] = [
        (
            "uncategorized",
            "Missing classifications",
            "Needs attention",
            "Assign a Tiller category with a valid group and type.",
            report["uncategorized_transactions"],
            _amount_scope(report["uncategorized_transactions"]),
        ),
        (
            "incomplete",
            "Missing transaction details",
            "Needs attention",
            "Fill the missing identifying fields in the Transactions sheet.",
            report["incomplete_transactions"],
            _amount_scope(report["incomplete_transactions"]),
        ),
        (
            "account_mapping",
            "Account mapping gaps",
            "Needs attention",
            "Map each account to an ID, group, and asset or liability class.",
            report["missing_account_mappings"],
            _amount_scope(report["missing_account_mappings"], "Balance"),
        ),
        (
            "stale_accounts",
            "Stale balance accounts",
            "Needs attention",
            "Refresh or reconnect accounts that stopped reporting balances.",
            report["stale_accounts"],
            _amount_scope(report["stale_accounts"], "Balance"),
        ),
        (
            "duplicates",
            "Potential duplicate transactions",
            "Review",
            "Confirm whether each pair represents the same underlying charge.",
            duplicates,
            mask_value(f"${duplicate_summary['total_amount']:,.0f}"),
        ),
        (
            "reversals",
            "Refunds and income reversals",
            "Review",
            "Confirm that refunds, clawbacks, and corrections are categorized as intended.",
            report["cash_flow_reversals"],
            _amount_scope(report["cash_flow_reversals"]),
        ),
    ]
    return [
        HealthCheck(
            key=key,
            name=name,
            status=status if not data.empty else "Passed",
            findings=len(data),
            scope=scope if not data.empty else "—",
            action=action,
            data=data,
        )
        for key, name, status, action, data, scope in definitions
    ]


def _render_settings() -> tuple[int, int, float, bool, bool, bool]:
    """Render compact controls for checks with adjustable thresholds."""
    with st.popover("Check settings", icon=":material/tune:", width="stretch"):
        stale_days = st.slider(
            "Stale account threshold",
            min_value=1,
            max_value=60,
            value=7,
            step=1,
            key="data_health_stale_days",
            persist_state="page",
        )
        st.markdown("**Duplicate detection**")
        days_threshold = st.number_input(
            "Maximum days apart",
            min_value=0,
            max_value=7,
            value=DEFAULT_DUPLICATE_DAYS_THRESHOLD,
            key="data_health_duplicate_days",
            persist_state="page",
        )
        min_amount = st.number_input(
            "Minimum amount",
            min_value=0.0,
            max_value=1000.0,
            value=MIN_DUPLICATE_AMOUNT,
            step=10.0,
            key="data_health_duplicate_minimum",
            persist_state="page",
        )
        check_same_account = st.toggle(
            "Require the same account",
            value=True,
            key="data_health_same_account",
            persist_state="page",
        )
        check_same_category = st.toggle(
            "Require the same category",
            value=False,
            key="data_health_same_category",
            persist_state="page",
        )
        require_same_description = st.toggle(
            "Require the same description",
            value=True,
            key="data_health_same_description",
            persist_state="page",
        )
    return (
        stale_days,
        days_threshold,
        min_amount,
        check_same_account,
        check_same_category,
        require_same_description,
    )


def _render_summary(
    checks: list[HealthCheck],
    transactions: pd.DataFrame,
    balances: pd.DataFrame,
) -> None:
    """Render headline issue counts and source freshness."""
    attention = sum(check["findings"] for check in checks if check["status"] == "Needs attention")
    review = sum(check["findings"] for check in checks if check["status"] == "Review")
    transaction_latest = _latest_timestamp(transactions)
    balance_latest = _latest_timestamp(balances)
    account_column = "Account ID" if "Account ID" in balances.columns else "Account"
    account_count = balances[account_column].nunique() if account_column in balances else 0

    with st.container(horizontal=True):
        st.metric("Needs attention", mask_value(f"{attention:,}"), border=True)
        st.metric("Review items", mask_value(f"{review:,}"), border=True)
        st.metric(
            "Transactions through",
            _format_date(transaction_latest),
            delta=(f"{mask_value(f'{len(transactions):,}')} rows · {_age_label(transaction_latest)}"),
            delta_color="off",
            border=True,
        )
        st.metric(
            "Balances through",
            _format_date(balance_latest),
            delta=(f"{mask_value(f'{account_count:,}')} accounts · {_age_label(balance_latest)}"),
            delta_color="off",
            border=True,
        )


def _render_queue(checks: list[HealthCheck]) -> None:
    """Render the complete ordered checklist."""
    queue = pd.DataFrame(
        {
            "Status": [check["status"] for check in checks],
            "Check": [check["name"] for check in checks],
            "Findings": [check["findings"] for check in checks],
            "Financial_Scope": [check["scope"] for check in checks],
            "Next_Step": [check["action"] for check in checks],
        }
    )
    with st.container(border=True):
        st.subheader("Health checks")
        value_safe_dataframe(
            queue,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn("Status", pinned=True),
                "Check": st.column_config.TextColumn("Check", pinned=True, width="medium"),
                "Findings": st.column_config.NumberColumn("Findings", format="%d"),
                "Financial_Scope": st.column_config.TextColumn("Financial scope"),
                "Next_Step": st.column_config.TextColumn("Next step", width="large"),
            },
        )


def _transaction_columns(extra: str | None = None) -> ColumnConfig:
    """Return the shared transaction configuration plus an optional detail field."""
    config = dict(get_transaction_column_config())
    if extra is not None:
        config[extra] = st.column_config.TextColumn(extra.replace("_", " "))
    return config


def _render_transaction_findings(check: HealthCheck, extra: str | None = None) -> None:
    """Render transaction-level findings newest first."""
    findings = check["data"].sort_values("Date", ascending=False)
    value_safe_dataframe(
        findings,
        hide_index=True,
        height=min(600, 42 + 35 * max(len(findings), 1)),
        column_config=_transaction_columns(extra),
    )


def _render_duplicate_findings(duplicates: pd.DataFrame) -> None:
    """Render duplicate pairs and a compact monthly rollup."""
    value_safe_dataframe(
        duplicates.sort_values("Date1", ascending=False),
        hide_index=True,
        height=min(600, 42 + 35 * max(len(duplicates), 1)),
        column_config={
            "Date1": st.column_config.DateColumn("Date 1", format="MMM DD, YYYY"),
            "Date2": st.column_config.DateColumn("Date 2", format="MMM DD, YYYY"),
            "Days_Apart": st.column_config.NumberColumn("Days apart", format="%d"),
            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "Account1": st.column_config.TextColumn("Account 1"),
            "Account2": st.column_config.TextColumn("Account 2"),
            "Description1": st.column_config.TextColumn("Description 1", width="large"),
            "Description2": st.column_config.TextColumn("Description 2", width="large"),
        },
    )
    monthly = summarize_duplicates_by_month(duplicates)
    if len(monthly) > 1:
        st.markdown("**By month**")
        value_safe_dataframe(
            monthly,
            hide_index=True,
            column_config={
                "Count": st.column_config.NumberColumn("Pairs", format="%d"),
                "Total_Amount": st.column_config.NumberColumn("Flagged amount", format="$%.2f"),
            },
        )


def _render_account_findings(check: HealthCheck) -> None:
    """Render account-level mapping or freshness findings."""
    sort_column = "Days_Stale" if "Days_Stale" in check["data"].columns else "Account"
    ascending = sort_column != "Days_Stale"
    value_safe_dataframe(
        check["data"].sort_values(sort_column, ascending=ascending),
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Latest date", format="MMM DD, YYYY"),
            "Balance": st.column_config.NumberColumn("Balance", format="$%,.2f"),
            "Days_Stale": st.column_config.NumberColumn("Days stale", format="%d"),
            "Missing_Fields": st.column_config.TextColumn("Missing fields"),
        },
    )


def _render_detail(checks: list[HealthCheck]) -> None:
    """Render one user-selected check and its affected records."""
    check_by_key = {check["key"]: check for check in checks}
    default_key = next(
        (check["key"] for check in checks if check["findings"]),
        checks[0]["key"],
    )
    selected_key = st.selectbox(
        "Inspect check",
        options=list(check_by_key),
        index=list(check_by_key).index(default_key),
        format_func=lambda key: check_by_key[key]["name"],
        key="data_health_check",
        persist_state="page",
    )
    selected = check_by_key[selected_key]

    with st.container(border=True):
        with st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
        ):
            st.subheader(selected["name"])
            if selected["status"] == "Passed":
                st.badge("Passed", icon=":material/check_circle:", color="green")
            elif selected["status"] == "Review":
                st.badge(
                    f"{mask_value(str(selected['findings']))} to review",
                    icon=":material/visibility:",
                    color="orange",
                )
            else:
                st.badge(
                    f"{mask_value(str(selected['findings']))} need attention",
                    icon=":material/warning:",
                    color="red",
                )

        if selected["data"].empty:
            st.success("No findings for this check.", icon=":material/check_circle:")
            return

        st.caption(selected["action"])
        match selected_key:
            case "uncategorized":
                _render_transaction_findings(selected)
            case "incomplete":
                _render_transaction_findings(selected, "Missing_Fields")
            case "reversals":
                _render_transaction_findings(selected, "Review_Reason")
            case "duplicates":
                _render_duplicate_findings(selected["data"])
            case "account_mapping" | "stale_accounts":
                _render_account_findings(selected)


def configure_page(
    transactions_spreadsheet: TransactionsSpreadsheet,
    balance_history_spreadsheet: BalanceHistorySpreadsheet,
) -> None:
    """Render prioritized data-quality findings for imported Tiller sheets."""
    st.header("Data health")
    transactions = transactions_spreadsheet.scrubbed_df.copy()
    balances = balance_history_spreadsheet.scrubbed_df.copy()

    controls = st.columns([5, 1], vertical_alignment="bottom")
    with controls[0]:
        st.caption("Review source freshness, mapping gaps, and suspicious records.")
    with controls[1]:
        settings = _render_settings()

    if transactions.empty and balances.empty:
        st.info(
            "No transaction or balance data is available.",
            icon=":material/database_off:",
        )
        return

    report, duplicates = _analyze_health(transactions, balances, *settings)
    checks = _build_health_checks(report, duplicates)
    _render_summary(checks, transactions, balances)
    _render_queue(checks)
    _render_detail(checks)


def main() -> None:
    """Streamlit entry point for the Data Health page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    configure_page(load_transactions_data(), load_balance_history_data())


if __name__ == "__main__":
    main()
