"""Common filter UI components used across multiple pages."""

from collections.abc import Sequence

import pandas as pd
import streamlit as st

from src.config import TransactionSetSettings, get_settings
from src.constants import (
    FI_SPENDING_LOOKBACK_OPTIONS,
    MAX_SAVINGS_RATE,
    MIN_SAVINGS_RATE,
    SAVINGS_RATE_STEP,
)
from src.custom_types import (
    BudgetFilters,
    FIFilters,
    IncomeExpenseFilters,
    SpendingFilters,
)
from src.reporting_periods import calculate_date_range as _calculate_date_range


def _transaction_like_multiselect(
    label: str,
    *,
    default_terms: Sequence[str],
    key: str,
) -> list[str]:
    """Render a free-text transaction-description filter."""
    return list(
        st.multiselect(
            label,
            options=list(default_terms),
            key=key,
            placeholder="Type text and press Enter",
            help="Case-insensitive literal text matched against Full Description.",
            accept_new_options=True,
            persist_state="page",
        )
    )


def _set_income_filter_state(
    prefix: str,
    income_categories: list[str],
    expense_categories: list[str],
    expense_groups: list[str],
    include_transactions_like: list[str],
    exclude_transactions_like: list[str],
) -> None:
    """Reset one editable Income & Savings preset."""
    thresholds = get_settings().thresholds
    st.session_state[f"{prefix}_exclude_income_categories"] = income_categories
    st.session_state[f"{prefix}_exclude_expense_categories"] = expense_categories
    st.session_state[f"{prefix}_exclude_expense_groups"] = expense_groups
    st.session_state[f"{prefix}_include_transactions_like"] = include_transactions_like
    st.session_state[f"{prefix}_exclude_transactions_like"] = exclude_transactions_like
    st.session_state[f"{prefix}_filter_large_income"] = False
    st.session_state[f"{prefix}_income_threshold"] = thresholds.income
    st.session_state[f"{prefix}_filter_large_expenses"] = False
    st.session_state[f"{prefix}_expense_threshold"] = thresholds.expense


def _set_spending_filter_state(
    prefix: str,
    categories: list[str],
    groups: list[str],
    include_transactions_like: list[str],
    exclude_transactions_like: list[str],
) -> None:
    """Reset one editable spending preset."""
    expense_threshold = get_settings().thresholds.expense
    st.session_state[f"{prefix}_exclude_categories"] = categories
    st.session_state[f"{prefix}_exclude_groups"] = groups
    st.session_state[f"{prefix}_include_transactions_like"] = include_transactions_like
    st.session_state[f"{prefix}_exclude_transactions_like"] = exclude_transactions_like
    st.session_state[f"{prefix}_filter_large_expenses"] = False
    st.session_state[f"{prefix}_expense_threshold"] = expense_threshold


def render_income_expense_filters(
    income_categories: list[str],
    expense_categories: list[str],
    expense_groups: list[str],
    *,
    view: str,
) -> IncomeExpenseFilters:
    """Render the Income & Savings calculation controls.

    Returns:
        dictionary containing all filter selections
    """
    settings = get_settings()
    thresholds = settings.thresholds
    income_defaults = settings.income_savings
    regular_income_categories = [
        category for category in income_defaults.exclude_categories if category in income_categories
    ]
    regular_expense_categories = [
        category for category in income_defaults.exclude_categories if category in expense_categories
    ]
    regular_expense_groups = [group for group in income_defaults.exclude_groups if group in expense_groups]

    if view == "Regular":
        default_income_categories = regular_income_categories
        default_expense_categories = regular_expense_categories
        default_expense_groups = regular_expense_groups
    elif view == "Actual":
        default_income_categories = []
        default_expense_categories = []
        default_expense_groups = []
    else:
        raise ValueError(f"Unknown income calculation view: {view}")

    prefix = f"income_{view.lower()}"
    defaults = {
        f"{prefix}_exclude_income_categories": default_income_categories,
        f"{prefix}_exclude_expense_categories": default_expense_categories,
        f"{prefix}_exclude_expense_groups": default_expense_groups,
        f"{prefix}_include_transactions_like": [],
        f"{prefix}_exclude_transactions_like": [],
        f"{prefix}_filter_large_income": False,
        f"{prefix}_income_threshold": thresholds.income,
        f"{prefix}_filter_large_expenses": False,
        f"{prefix}_expense_threshold": thresholds.expense,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    is_modified = (
        set(st.session_state[f"{prefix}_exclude_income_categories"]) != set(default_income_categories)
        or set(st.session_state[f"{prefix}_exclude_expense_categories"]) != set(default_expense_categories)
        or set(st.session_state[f"{prefix}_exclude_expense_groups"]) != set(default_expense_groups)
        or bool(st.session_state[f"{prefix}_include_transactions_like"])
        or bool(st.session_state[f"{prefix}_exclude_transactions_like"])
        or bool(st.session_state[f"{prefix}_filter_large_income"])
        or bool(st.session_state[f"{prefix}_filter_large_expenses"])
    )
    popover_label = "Adjust calculation · modified" if is_modified else "Adjust calculation"
    with st.popover(
        popover_label,
        icon=":material/tune:",
        width="stretch",
    ):
        st.button(
            "Reset defaults",
            icon=":material/restart_alt:",
            on_click=_set_income_filter_state,
            args=(
                prefix,
                default_income_categories,
                default_expense_categories,
                default_expense_groups,
                [],
                [],
            ),
        )
        exclude_income_categories = st.multiselect(
            "Exclude income categories",
            options=income_categories,
            key=f"{prefix}_exclude_income_categories",
            persist_state="page",
        )
        exclude_groups = st.multiselect(
            "Exclude expense groups",
            options=expense_groups,
            key=f"{prefix}_exclude_expense_groups",
            persist_state="page",
        )
        exclude_expense_categories = st.multiselect(
            "Exclude expense categories",
            options=expense_categories,
            key=f"{prefix}_exclude_expense_categories",
            persist_state="page",
        )
        include_transactions_like = _transaction_like_multiselect(
            "Include transaction names containing",
            default_terms=[],
            key=f"{prefix}_include_transactions_like",
        )
        exclude_transactions_like = _transaction_like_multiselect(
            "Exclude transaction names containing",
            default_terms=[],
            key=f"{prefix}_exclude_transactions_like",
        )

        filter_large_income = st.toggle(
            "Exclude individual income over a limit",
            key=f"{prefix}_filter_large_income",
            persist_state="page",
        )
        income_threshold = int(st.session_state[f"{prefix}_income_threshold"])
        if filter_large_income:
            income_threshold = int(
                st.number_input(
                    "Income limit",
                    min_value=5000,
                    max_value=100000,
                    step=1000,
                    key=f"{prefix}_income_threshold",
                    persist_state="page",
                )
            )

        filter_large_expenses = st.toggle(
            "Exclude individual expenses over a limit",
            key=f"{prefix}_filter_large_expenses",
            persist_state="page",
        )
        expense_threshold = int(st.session_state[f"{prefix}_expense_threshold"])
        if filter_large_expenses:
            expense_threshold = int(
                st.number_input(
                    "Expense limit",
                    min_value=1000,
                    max_value=100000,
                    step=500,
                    key=f"{prefix}_expense_threshold",
                    persist_state="page",
                )
            )

        target_rate = int(
            st.number_input(
                "Savings rate target",
                min_value=MIN_SAVINGS_RATE,
                max_value=MAX_SAVINGS_RATE,
                value=income_defaults.target_rate,
                step=SAVINGS_RATE_STEP,
                key="income_savings_target_rate",
            )
        )

    return {
        "exclude_groups": exclude_groups,
        "exclude_income_categories": exclude_income_categories,
        "exclude_expense_categories": exclude_expense_categories,
        "include_transactions_like": include_transactions_like,
        "exclude_transactions_like": exclude_transactions_like,
        "filter_large_income": filter_large_income,
        "income_threshold": income_threshold,
        "filter_large_expenses": filter_large_expenses,
        "expense_threshold": expense_threshold,
        "target_rate": target_rate,
    }


def render_spending_filters(
    all_categories: list[str],
    all_groups: list[str],
    *,
    transaction_set: TransactionSetSettings,
) -> SpendingFilters:
    """Render page-local narrowing controls over one configured transaction set."""
    default_categories: list[str] = []
    default_groups: list[str] = []
    default_include_groups: list[str] = []
    default_include_categories: list[str] = []
    default_include_transactions_like: list[str] = []
    default_exclude_transactions_like: list[str] = []
    prefix = f"spending_{transaction_set.key}"

    defaults = {
        f"{prefix}_exclude_categories": default_categories,
        f"{prefix}_exclude_groups": default_groups,
        f"{prefix}_include_transactions_like": default_include_transactions_like,
        f"{prefix}_exclude_transactions_like": default_exclude_transactions_like,
        f"{prefix}_filter_large_expenses": False,
        f"{prefix}_expense_threshold": get_settings().thresholds.expense,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    is_modified = (
        set(st.session_state[f"{prefix}_exclude_categories"]) != set(default_categories)
        or set(st.session_state[f"{prefix}_exclude_groups"]) != set(default_groups)
        or set(st.session_state[f"{prefix}_include_transactions_like"]) != set(default_include_transactions_like)
        or set(st.session_state[f"{prefix}_exclude_transactions_like"]) != set(default_exclude_transactions_like)
        or bool(st.session_state[f"{prefix}_filter_large_expenses"])
    )
    label = "Adjust view · modified" if is_modified else "Adjust view"
    with st.popover(label, icon=":material/tune:", width="stretch"):
        st.button(
            "Reset defaults",
            icon=":material/restart_alt:",
            on_click=_set_spending_filter_state,
            args=(
                prefix,
                default_categories,
                default_groups,
                default_include_transactions_like,
                default_exclude_transactions_like,
            ),
        )
        exclude_groups = st.multiselect(
            "Exclude groups",
            options=all_groups,
            key=f"{prefix}_exclude_groups",
            persist_state="page",
        )
        exclude_categories = st.multiselect(
            "Exclude categories",
            options=all_categories,
            key=f"{prefix}_exclude_categories",
            persist_state="page",
        )
        include_transactions_like = _transaction_like_multiselect(
            "Include transaction names containing",
            default_terms=default_include_transactions_like,
            key=f"{prefix}_include_transactions_like",
        )
        exclude_transactions_like = _transaction_like_multiselect(
            "Exclude transaction names containing",
            default_terms=default_exclude_transactions_like,
            key=f"{prefix}_exclude_transactions_like",
        )
        filter_large_expenses = st.toggle(
            "Exclude individual expenses over a limit",
            key=f"{prefix}_filter_large_expenses",
            persist_state="page",
        )
        expense_threshold = int(st.session_state[f"{prefix}_expense_threshold"])
        if filter_large_expenses:
            expense_threshold = int(
                st.number_input(
                    "Expense limit",
                    min_value=1000,
                    max_value=100000,
                    step=500,
                    key=f"{prefix}_expense_threshold",
                    persist_state="page",
                )
            )

    return {
        "include_groups": default_include_groups,
        "include_categories": default_include_categories,
        "include_transactions_like": include_transactions_like,
        "exclude_groups": exclude_groups,
        "exclude_categories": exclude_categories,
        "exclude_transactions_like": exclude_transactions_like,
        "filter_large_expenses": filter_large_expenses,
        "expense_threshold": expense_threshold,
    }


def render_budget_filters(
    all_categories: list[str],
    all_groups: list[str],
) -> BudgetFilters:
    """Render compact controls for an optional adjusted budget view."""
    default_expense_threshold = get_settings().thresholds.expense
    with st.popover(
        "Adjust view",
        icon=":material/tune:",
        width="stretch",
    ):
        columns = st.columns(2)
        with columns[0]:
            exclude_groups = st.multiselect(
                "Exclude groups",
                options=all_groups,
                default=[],
                key="budget_exclude_groups",
                persist_state="page",
            )
            exclude_categories = st.multiselect(
                "Exclude categories",
                options=all_categories,
                default=[],
                key="budget_exclude_categories",
                persist_state="page",
            )
            include_transactions_like = _transaction_like_multiselect(
                "Include transaction names containing",
                default_terms=[],
                key="budget_include_transactions_like",
            )
            exclude_transactions_like = _transaction_like_multiselect(
                "Exclude transaction names containing",
                default_terms=[],
                key="budget_exclude_transactions_like",
            )
        with columns[1]:
            filter_large_expenses = st.toggle(
                "Exclude large transactions",
                value=False,
                key="budget_filter_large_expenses",
                persist_state="page",
            )
            expense_threshold = default_expense_threshold
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Maximum individual expense",
                    min_value=1000,
                    max_value=100000,
                    value=default_expense_threshold,
                    step=500,
                    key="budget_expense_threshold",
                    persist_state="page",
                )

    return {
        "exclude_groups": exclude_groups,
        "exclude_categories": exclude_categories,
        "include_transactions_like": include_transactions_like,
        "exclude_transactions_like": exclude_transactions_like,
        "filter_large_expenses": filter_large_expenses,
        "expense_threshold": expense_threshold,
    }


def default_fi_accounts(
    all_accounts: list[str],
    included_group_accounts: list[str],
    account_patterns: tuple[str, ...] | None = None,
) -> list[str]:
    """Pick accounts pre-selected for the FI page.

    Return accounts selected by configured patterns or configured account groups.
    """
    configured_patterns = (
        get_settings().financial_independence.included_account_patterns
        if account_patterns is None
        else account_patterns
    )
    patterns = [pattern.casefold() for pattern in configured_patterns]
    grouped = set(included_group_accounts)
    selected: list[str] = []
    for acct in all_accounts:
        normalized = acct.casefold()
        if acct in grouped or any(pattern in normalized for pattern in patterns):
            selected.append(acct)
    return selected


def render_fi_filters(
    all_accounts: list[str],
    all_categories: list[str],
    all_groups: list[str],
    included_group_accounts: list[str],
) -> FIFilters:
    """Render compact controls for the data behind the FI scenario."""
    settings = get_settings()
    fi_defaults = settings.financial_independence
    default_expense_threshold = settings.thresholds.expense
    default_accounts = default_fi_accounts(all_accounts, included_group_accounts)
    with st.popover(
        "Adjust source data",
        icon=":material/tune:",
        width="stretch",
    ):
        columns = st.columns(2)
        with columns[0]:
            st.markdown("**Portfolio**")
            include_accounts = st.multiselect(
                "Included accounts",
                options=all_accounts,
                default=default_accounts,
                key="fi_include_accounts",
                persist_state="page",
            )
            spending_lookback_months = st.selectbox(
                "Spending history",
                options=FI_SPENDING_LOOKBACK_OPTIONS,
                index=FI_SPENDING_LOOKBACK_OPTIONS.index(fi_defaults.spending_lookback_months),
                format_func=lambda n: f"Last {n} months",
                key="fi_spending_lookback",
                persist_state="page",
            )
        with columns[1]:
            st.markdown("**Spending baseline**")
            exclude_groups = st.multiselect(
                "Exclude groups",
                options=all_groups,
                default=[],
                key="fi_exclude_groups",
                persist_state="page",
            )
            exclude_categories = st.multiselect(
                "Exclude categories",
                options=all_categories,
                default=[],
                key="fi_exclude_categories",
                persist_state="page",
            )
            include_transactions_like = _transaction_like_multiselect(
                "Include transaction names containing",
                default_terms=[],
                key="fi_include_transactions_like",
            )
            exclude_transactions_like = _transaction_like_multiselect(
                "Exclude transaction names containing",
                default_terms=[],
                key="fi_exclude_transactions_like",
            )
            filter_large_expenses = st.toggle(
                "Exclude large transactions",
                value=False,
                key="fi_filter_large_expenses",
                persist_state="page",
            )
            expense_threshold = default_expense_threshold
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Maximum individual expense",
                    min_value=1000,
                    max_value=100000,
                    value=default_expense_threshold,
                    step=500,
                    key="fi_expense_threshold",
                    persist_state="page",
                )

    return {
        "include_accounts": include_accounts,
        "exclude_groups": exclude_groups,
        "exclude_categories": exclude_categories,
        "include_transactions_like": include_transactions_like,
        "exclude_transactions_like": exclude_transactions_like,
        "filter_large_expenses": filter_large_expenses,
        "expense_threshold": expense_threshold,
        "spending_lookback_months": int(spending_lookback_months),
    }


def calculate_date_range(
    period: str,
    df: pd.DataFrame | None = None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calculate start and end dates for a given period string.

    Args:
        period: Time period name (e.g., "Last 3 Months", "Year to Date")
        df: Optional dataframe to get min date for "All Time" option

    Returns:
        Tuple of (start_date, end_date) as pandas Timestamps
    """
    return _calculate_date_range(period, df)
