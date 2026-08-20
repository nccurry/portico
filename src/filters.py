"""Common filter UI components used across multiple pages."""
import pandas as pd
import streamlit as st

from src.reporting_periods import calculate_date_range as _calculate_date_range

from src.constants import (
    DEFAULT_EXCLUDE_CATEGORIES_INCOME_SAVINGS,
    DEFAULT_EXCLUDE_CATEGORIES_SPENDING,
    DEFAULT_EXCLUDE_GROUPS_INCOME_SAVINGS,
    DEFAULT_EXCLUDE_GROUPS_SPENDING,
    DEFAULT_EXPENSE_THRESHOLD,
    DEFAULT_FI_INCLUDED_ACCOUNTS,
    DEFAULT_FI_SPENDING_LOOKBACK_MONTHS,
    DEFAULT_INCOME_THRESHOLD,
    DEFAULT_SAVINGS_RATE_TARGET,
    FI_SPENDING_LOOKBACK_OPTIONS,
    MIN_SAVINGS_RATE,
    MAX_SAVINGS_RATE,
    SAVINGS_RATE_STEP,
)
from src.custom_types import (
    BudgetFilters,
    FIFilters,
    IncomeExpenseFilters,
    SpendingFilters,
    TransactionFilterOptions,
)


def _set_income_filter_state(
    prefix: str,
    income_categories: list[str],
    expense_categories: list[str],
    expense_groups: list[str],
) -> None:
    """Reset one editable Income & Savings preset."""
    st.session_state[f"{prefix}_exclude_income_categories"] = income_categories
    st.session_state[f"{prefix}_exclude_expense_categories"] = expense_categories
    st.session_state[f"{prefix}_exclude_expense_groups"] = expense_groups
    st.session_state[f"{prefix}_filter_large_income"] = False
    st.session_state[f"{prefix}_income_threshold"] = DEFAULT_INCOME_THRESHOLD
    st.session_state[f"{prefix}_filter_large_expenses"] = False
    st.session_state[f"{prefix}_expense_threshold"] = DEFAULT_EXPENSE_THRESHOLD


def _set_spending_filter_state(
    prefix: str,
    categories: list[str],
    groups: list[str],
) -> None:
    """Reset one editable spending preset."""
    st.session_state[f"{prefix}_exclude_categories"] = categories
    st.session_state[f"{prefix}_exclude_groups"] = groups
    st.session_state[f"{prefix}_filter_large_expenses"] = False
    st.session_state[f"{prefix}_expense_threshold"] = DEFAULT_EXPENSE_THRESHOLD


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
    regular_income_categories = [
        category
        for category in DEFAULT_EXCLUDE_CATEGORIES_INCOME_SAVINGS
        if category in income_categories
    ]
    regular_expense_categories = [
        category
        for category in DEFAULT_EXCLUDE_CATEGORIES_INCOME_SAVINGS
        if category in expense_categories
    ]
    regular_expense_groups = [
        group
        for group in DEFAULT_EXCLUDE_GROUPS_INCOME_SAVINGS
        if group in expense_groups
    ]

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
        f"{prefix}_filter_large_income": False,
        f"{prefix}_income_threshold": DEFAULT_INCOME_THRESHOLD,
        f"{prefix}_filter_large_expenses": False,
        f"{prefix}_expense_threshold": DEFAULT_EXPENSE_THRESHOLD,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    is_modified = (
        set(st.session_state[f"{prefix}_exclude_income_categories"])
        != set(default_income_categories)
        or set(st.session_state[f"{prefix}_exclude_expense_categories"])
        != set(default_expense_categories)
        or set(st.session_state[f"{prefix}_exclude_expense_groups"])
        != set(default_expense_groups)
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

        filter_large_income = st.toggle(
            "Exclude individual income over a limit",
            key=f"{prefix}_filter_large_income",
            persist_state="page",
        )
        income_threshold = int(st.session_state[f"{prefix}_income_threshold"])
        if filter_large_income:
            income_threshold = int(st.number_input(
                "Income limit",
                min_value=5000,
                max_value=100000,
                step=1000,
                key=f"{prefix}_income_threshold",
                persist_state="page",
            ))

        filter_large_expenses = st.toggle(
            "Exclude individual expenses over a limit",
            key=f"{prefix}_filter_large_expenses",
            persist_state="page",
        )
        expense_threshold = int(st.session_state[f"{prefix}_expense_threshold"])
        if filter_large_expenses:
            expense_threshold = int(st.number_input(
                "Expense limit",
                min_value=1000,
                max_value=100000,
                step=500,
                key=f"{prefix}_expense_threshold",
                persist_state="page",
            ))

        target_rate = int(st.number_input(
            "Savings rate target",
            min_value=MIN_SAVINGS_RATE,
            max_value=MAX_SAVINGS_RATE,
            value=DEFAULT_SAVINGS_RATE_TARGET,
            step=SAVINGS_RATE_STEP,
            key="income_savings_target_rate",
        ))

    return {
        'exclude_groups': exclude_groups,
        'exclude_income_categories': exclude_income_categories,
        'exclude_expense_categories': exclude_expense_categories,
        'filter_large_income': filter_large_income,
        'income_threshold': income_threshold,
        'filter_large_expenses': filter_large_expenses,
        'expense_threshold': expense_threshold,
        'target_rate': target_rate
    }


def render_spending_filters(
    all_categories: list[str],
    all_groups: list[str],
    *,
    view: str,
) -> SpendingFilters:
    """Render editable All spending and Discretionary presets."""
    discretionary_categories = [
        category
        for category in DEFAULT_EXCLUDE_CATEGORIES_SPENDING
        if category in all_categories
    ]
    discretionary_groups = [
        group
        for group in DEFAULT_EXCLUDE_GROUPS_SPENDING
        if group in all_groups
    ]
    if view == "All spending":
        default_categories: list[str] = []
        default_groups: list[str] = []
        prefix = "spending_all"
    elif view == "Discretionary":
        default_categories = discretionary_categories
        default_groups = discretionary_groups
        prefix = "spending_discretionary"
    else:
        raise ValueError(f"Unknown spending view: {view}")

    defaults = {
        f"{prefix}_exclude_categories": default_categories,
        f"{prefix}_exclude_groups": default_groups,
        f"{prefix}_filter_large_expenses": False,
        f"{prefix}_expense_threshold": DEFAULT_EXPENSE_THRESHOLD,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    is_modified = (
        set(st.session_state[f"{prefix}_exclude_categories"])
        != set(default_categories)
        or set(st.session_state[f"{prefix}_exclude_groups"]) != set(default_groups)
        or bool(st.session_state[f"{prefix}_filter_large_expenses"])
    )
    label = "Adjust view · modified" if is_modified else "Adjust view"
    with st.popover(label, icon=":material/tune:", width="stretch"):
        st.button(
            "Reset defaults",
            icon=":material/restart_alt:",
            on_click=_set_spending_filter_state,
            args=(prefix, default_categories, default_groups),
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
        filter_large_expenses = st.toggle(
            "Exclude individual expenses over a limit",
            key=f"{prefix}_filter_large_expenses",
            persist_state="page",
        )
        expense_threshold = int(st.session_state[f"{prefix}_expense_threshold"])
        if filter_large_expenses:
            expense_threshold = int(st.number_input(
                "Expense limit",
                min_value=1000,
                max_value=100000,
                step=500,
                key=f"{prefix}_expense_threshold",
                persist_state="page",
            ))

    return {
        "include_groups": [],
        "include_categories": [],
        "exclude_groups": exclude_groups,
        "exclude_categories": exclude_categories,
        "filter_large_expenses": filter_large_expenses,
        "expense_threshold": expense_threshold,
    }


def render_budget_filters(
    all_categories: list[str],
    all_groups: list[str],
) -> BudgetFilters:
    """Render compact controls for an optional adjusted budget view."""
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
        with columns[1]:
            filter_large_expenses = st.toggle(
                "Exclude large transactions",
                value=False,
                key="budget_filter_large_expenses",
                persist_state="page",
            )
            expense_threshold = DEFAULT_EXPENSE_THRESHOLD
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Maximum individual expense",
                    min_value=1000,
                    max_value=100000,
                    value=DEFAULT_EXPENSE_THRESHOLD,
                    step=500,
                    key="budget_expense_threshold",
                    persist_state="page",
                )

    return {
        "exclude_groups": exclude_groups,
        "exclude_categories": exclude_categories,
        "filter_large_expenses": filter_large_expenses,
        "expense_threshold": expense_threshold,
    }


def default_fi_accounts(all_accounts: list[str], all_savings_accounts: list[str]) -> list[str]:
    """Pick accounts pre-selected for the FI page.

    Returns accounts whose names contain any of ``DEFAULT_FI_INCLUDED_ACCOUNTS``
    (case-insensitive substring match), unioned with ``all_savings_accounts``.
    Preserves the sorted order of ``all_accounts``.
    """
    patterns = [p.lower() for p in DEFAULT_FI_INCLUDED_ACCOUNTS]
    savings = set(all_savings_accounts)
    selected: list[str] = []
    for acct in all_accounts:
        lower = acct.lower()
        if acct in savings or any(p in lower for p in patterns):
            selected.append(acct)
    return selected


def render_fi_filters(
    all_accounts: list[str],
    all_categories: list[str],
    all_groups: list[str],
    all_savings_accounts: list[str],
) -> FIFilters:
    """Render compact controls for the data behind the FI scenario."""
    default_accounts = default_fi_accounts(all_accounts, all_savings_accounts)
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
                index=FI_SPENDING_LOOKBACK_OPTIONS.index(
                    DEFAULT_FI_SPENDING_LOOKBACK_MONTHS
                ),
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
            filter_large_expenses = st.toggle(
                "Exclude large transactions",
                value=False,
                key="fi_filter_large_expenses",
                persist_state="page",
            )
            expense_threshold = DEFAULT_EXPENSE_THRESHOLD
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Maximum individual expense",
                    min_value=1000,
                    max_value=100000,
                    value=DEFAULT_EXPENSE_THRESHOLD,
                    step=500,
                    key="fi_expense_threshold",
                    persist_state="page",
                )

    return {
        "include_accounts": include_accounts,
        "exclude_groups": exclude_groups,
        "exclude_categories": exclude_categories,
        "filter_large_expenses": filter_large_expenses,
        "expense_threshold": expense_threshold,
        "spending_lookback_months": int(spending_lookback_months),
    }


def calculate_date_range(
    period: str,
    df: pd.DataFrame | None = None,
    *,
    anchor_to_data: bool = False,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calculate start and end dates for a given period string.

    Args:
        period: Time period name (e.g., "Last 3 Months", "Year to Date")
        df: Optional dataframe to get min date for "All Time" option

    Returns:
        Tuple of (start_date, end_date) as pandas Timestamps
    """
    return _calculate_date_range(period, df, anchor_to_data=anchor_to_data)


def apply_transaction_filters(
    df: pd.DataFrame,
    filters: TransactionFilterOptions,
) -> pd.DataFrame:
    """Apply standard filters to a transaction dataframe.

    Args:
        df: Transaction dataframe to filter
        filters: dictionary of filter settings from render_*_filters()

    Returns:
        Filtered dataframe
    """
    # Always exclude Transfer group
    df = df[df['Group'] != 'Transfer']

    # Apply include filters (union/OR when both set), or exclude filters
    if filters.get('include_groups') or filters.get('include_categories'):
        masks = []
        if filters.get('include_groups'):
            masks.append(df['Group'].isin(filters['include_groups']))
        if filters.get('include_categories'):
            masks.append(df['Category'].isin(filters['include_categories']))
        combined = masks[0]
        for m in masks[1:]:
            combined = combined | m
        df = df[combined]
    else:
        # No include filters — apply excludes
        if filters.get('exclude_groups'):
            df = df[~df['Group'].isin(filters['exclude_groups'])]
        if filters.get('exclude_categories'):
            df = df[~df['Category'].isin(filters['exclude_categories'])]

    # Filter large expenses
    if filters.get('filter_large_expenses'):
        threshold = filters.get('expense_threshold', DEFAULT_EXPENSE_THRESHOLD)
        df = df[(df['Type'] != 'Expense') | (df['Amount'].abs() <= threshold)]

    # Filter large income
    if filters.get('filter_large_income'):
        threshold = filters.get('income_threshold', DEFAULT_INCOME_THRESHOLD)
        df = df[(df['Type'] != 'Income') | (df['Amount'].abs() <= threshold)]

    return df
