"""Pure calculations for emergency-fund, debt, and FI progress."""

from datetime import datetime

import pandas as pd

from src.config import FinancialIndependenceSettings, FinancialSafetySettings
from src.custom_types import FinancialSafetySummary
from src.spreadsheet import get_portfolio_value


def select_accounts(
    balance_history: pd.DataFrame,
    included_groups: tuple[str, ...],
    account_patterns: tuple[str, ...],
) -> list[str]:
    """Return visible accounts selected by group or case-insensitive name fragment."""
    required_columns = {"Account", "Group"}
    if balance_history.empty or not required_columns.issubset(balance_history.columns):
        return []

    balances = balance_history
    if "Hide" in balances.columns:
        balances = balances[balances["Hide"] != "Hide"]
    groups = {group.casefold() for group in included_groups}
    patterns = tuple(pattern.casefold() for pattern in account_patterns)
    group_match = balances["Group"].fillna("").astype(str).str.casefold().isin(groups)
    names = balances["Account"].fillna("").astype(str).str.casefold()
    pattern_match = names.map(lambda name: any(pattern in name for pattern in patterns))
    selected = balances.loc[group_match | pattern_match, "Account"].dropna().astype(str)
    return sorted(account for account in selected.unique() if account.strip())


def _average_monthly_expenses(
    transactions: pd.DataFrame,
    lookback_months: int,
    *,
    as_of: pd.Timestamp,
    excluded_categories: tuple[str, ...] = (),
    excluded_groups: tuple[str, ...] = (),
) -> float:
    """Return positive average expense spending over completed months before ``as_of``."""
    required_columns = {"Month", "Type", "Amount", "Category", "Group"}
    if transactions.empty or not required_columns.issubset(transactions.columns):
        return 0.0

    months = transactions["Month"].dropna().astype(str)
    if months.empty:
        return 0.0
    latest_month = pd.Period(months.max(), freq="M")
    current_month = pd.Period(pd.Timestamp(as_of).strftime("%Y-%m"), freq="M")
    latest_complete_month = min(latest_month, current_month - 1)
    period_range = pd.period_range(end=latest_complete_month, periods=lookback_months, freq="M")
    month_labels = period_range.astype(str)
    expenses = transactions[
        transactions["Type"].eq("Expense")
        & transactions["Month"].astype(str).isin(month_labels)
        & ~transactions["Category"].isin(excluded_categories)
        & ~transactions["Group"].isin(excluded_groups)
        & transactions["Group"].ne("Transfer")
    ]
    totals = -pd.to_numeric(expenses.groupby("Month")["Amount"].sum(), errors="coerce").fillna(0.0)
    totals = totals.reindex(month_labels, fill_value=0.0)
    return float(totals.mean())


def _signed_balance(
    balance_history: pd.DataFrame,
    accounts: list[str],
    *,
    as_of: datetime | None = None,
) -> float:
    """Return the latest signed balance for selected accounts."""
    _, balance = get_portfolio_value(balance_history, accounts, as_of=as_of)
    return balance


def build_financial_safety_summary(
    balance_history: pd.DataFrame,
    transactions: pd.DataFrame,
    financial_safety: FinancialSafetySettings,
    financial_independence: FinancialIndependenceSettings,
    *,
    as_of: pd.Timestamp,
) -> FinancialSafetySummary:
    """Summarize configurable emergency-fund, debt, and FI funding progress."""
    emergency_accounts = select_accounts(
        balance_history,
        financial_safety.emergency_fund_included_groups,
        financial_safety.emergency_fund_included_account_patterns,
    )
    emergency_balance = _signed_balance(balance_history, emergency_accounts)
    emergency_spending = _average_monthly_expenses(
        transactions,
        financial_safety.emergency_fund_spending_lookback_months,
        as_of=as_of,
        excluded_categories=financial_safety.emergency_fund_exclude_categories,
        excluded_groups=financial_safety.emergency_fund_exclude_groups,
    )
    emergency_target = emergency_spending * financial_safety.emergency_fund_target_months
    emergency_months = emergency_balance / emergency_spending if emergency_spending > 0 else None

    debt_accounts = select_accounts(
        balance_history,
        financial_safety.debt_included_groups,
        financial_safety.debt_included_account_patterns,
    )
    debt_balance = abs(_signed_balance(balance_history, debt_accounts))
    debt_rows = balance_history[balance_history["Account"].isin(debt_accounts)] if debt_accounts else pd.DataFrame()
    baseline_label: str | None = None
    baseline_balance = 0.0
    if not debt_rows.empty:
        if financial_safety.debt_baseline_date is None:
            baseline_timestamp = pd.Timestamp(debt_rows["Date"].min())
        else:
            baseline_timestamp = pd.Timestamp(financial_safety.debt_baseline_date, tz="UTC")
        baseline_balance = abs(
            _signed_balance(balance_history, debt_accounts, as_of=baseline_timestamp.to_pydatetime())
        )
        baseline_label = baseline_timestamp.strftime("%b %Y")
    debt_paid_down = baseline_balance - debt_balance
    debt_progress = debt_paid_down / baseline_balance * 100 if baseline_balance > 0 else None

    fi_accounts = select_accounts(
        balance_history,
        financial_independence.included_groups,
        financial_independence.included_account_patterns,
    )
    fi_portfolio = _signed_balance(balance_history, fi_accounts)
    fi_target = financial_independence.target_amount
    fi_progress = fi_portfolio / fi_target * 100 if fi_target > 0 else None

    return {
        "emergency_fund_balance": emergency_balance,
        "emergency_fund_average_monthly_spending": emergency_spending,
        "emergency_fund_target": emergency_target,
        "emergency_fund_months_covered": emergency_months,
        "emergency_fund_target_months": financial_safety.emergency_fund_target_months,
        "debt_balance": debt_balance,
        "debt_baseline_balance": baseline_balance,
        "debt_paid_down": debt_paid_down,
        "debt_progress_pct": debt_progress,
        "debt_baseline_label": baseline_label,
        "fi_portfolio_value": fi_portfolio,
        "fi_target": fi_target,
        "fi_progress_pct": fi_progress,
    }
