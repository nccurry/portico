"""Common filter UI components used across multiple pages."""
import streamlit as st

import pandas as pd
from src.reporting_periods import calculate_date_range as _calculate_date_range

from src.constants import (
    DEFAULT_EXCLUDE_CATEGORIES_INCOME_SAVINGS,
    DEFAULT_EXCLUDE_CATEGORIES_SPENDING,
    DEFAULT_EXCLUDE_GROUPS_INCOME_SAVINGS,
    DEFAULT_EXCLUDE_GROUPS_SPENDING,
    DEFAULT_EXPENSE_THRESHOLD,
    DEFAULT_EXPECTED_RETURN_RATE,
    DEFAULT_FI_INCLUDED_ACCOUNTS,
    DEFAULT_FI_PROJECTION_YEARS,
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
) -> SpendingFilters:
    """Render filter controls for Spending by Category page.

    Args:
        all_categories: List of all available categories for inclusion filter

    Returns:
        dictionary containing all filter selections
    """
    with st.expander("Filter Settings", expanded=False):
        col_filter1, col_filter2 = st.columns(2)

        with col_filter1:
            include_groups = st.multiselect(
                "Include Only These Groups",
                options=all_groups,
                default=[],
                help="If set, ONLY show these groups (ignores all exclude filters)"
            )

            include_categories = st.multiselect(
                "Include Only These Categories",
                options=all_categories,
                default=[],
                help="If set, ONLY show these categories (ignores all filters)"
            )

            st.divider()

            exclude_groups = st.multiselect(
                "Exclude Groups",
                options=all_groups,
                default=[g for g in DEFAULT_EXCLUDE_GROUPS_SPENDING if g in all_groups],
                help="Exclude entire transaction groups (Transfer always excluded)"
            )

            exclude_categories = st.multiselect(
                "Exclude Categories",
                options=all_categories,
                default=[
                    category
                    for category in DEFAULT_EXCLUDE_CATEGORIES_SPENDING
                    if category in all_categories
                ],
                help="Exclude specific one-time or non-recurring transaction categories"
            )

        with col_filter2:
            filter_large_expenses = st.checkbox(
                "Filter Large Expenses",
                value=False,
                help="Exclude individual large expense transactions above a threshold"
            )

            expense_threshold = DEFAULT_EXPENSE_THRESHOLD
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Expense Threshold ($)",
                    min_value=1000,
                    max_value=100000,
                    value=DEFAULT_EXPENSE_THRESHOLD,
                    step=500,
                    help="Exclude individual expense transactions larger than this amount"
                )

    return {
        'include_groups': include_groups,
        'include_categories': include_categories,
        'exclude_groups': exclude_groups,
        'exclude_categories': exclude_categories,
        'filter_large_expenses': filter_large_expenses,
        'expense_threshold': expense_threshold
    }


def render_budget_filters(
    all_categories: list[str],
    all_groups: list[str],
) -> BudgetFilters:
    """Render filter controls for Budget page.

    Returns:
        dictionary containing all filter selections
    """
    with st.expander("Filter Settings", expanded=False):
        col_filter1, col_filter2 = st.columns(2)

        with col_filter1:
            exclude_groups = st.multiselect(
                "Exclude Groups",
                options=all_groups,
                default=[],
                help="Create an adjusted view without selected spending groups"
            )

            exclude_categories = st.multiselect(
                "Exclude Categories",
                options=all_categories,
                default=[],
                help="Create an adjusted view without selected one-off categories"
            )

        with col_filter2:
            filter_large_expenses = st.toggle(
                "Exclude large transactions",
                value=False,
                help="Create an adjusted view that excludes individual expenses above a threshold"
            )

            expense_threshold = DEFAULT_EXPENSE_THRESHOLD
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Expense Threshold ($)",
                    min_value=1000,
                    max_value=100000,
                    value=DEFAULT_EXPENSE_THRESHOLD,
                    step=500,
                    help="Exclude individual expense transactions larger than this amount"
                )

            show_zero_budget = st.toggle(
                "Show unbudgeted categories in drill-downs",
                value=True,
                help="Include spending categories that have no individual Tiller budget"
            )

    return {
        'exclude_groups': exclude_groups,
        'exclude_categories': exclude_categories,
        'filter_large_expenses': filter_large_expenses,
        'expense_threshold': expense_threshold,
        'show_zero_budget': show_zero_budget,
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
    """Render filter controls for the Financial Independence page.

    Mirrors ``render_income_expense_filters`` in layout and defaults. The
    ``include_accounts`` multiselect drives portfolio selection; the exclude /
    threshold controls drive the spending side (passed straight to
    ``apply_transaction_filters``).
    """
    default_accounts = default_fi_accounts(all_accounts, all_savings_accounts)

    with st.expander("Filter Settings", expanded=False):
        col_filters, col_controls = st.columns(2)

        # ---- LEFT COLUMN: Filters (what data goes in) ----
        with col_filters:
            st.markdown("##### Portfolio")
            include_accounts = st.multiselect(
                "Include Accounts",
                options=all_accounts,
                default=default_accounts,
                help="Accounts counted as part of the invested/savings portfolio",
            )

            st.markdown("---")
            st.markdown("##### Spending")
            exclude_groups = st.multiselect(
                "Exclude Groups",
                options=all_groups,
                default=[],
                help="Exclude entire transaction groups from the spending average",
            )

            exclude_categories = st.multiselect(
                "Exclude Categories",
                options=all_categories,
                default=[],
                help="Exclude non-recurring categories from the spending average",
            )

            filter_large_expenses = st.checkbox(
                "Filter Large Expenses",
                value=False,
                help="Exclude individual large expense transactions above a threshold",
            )

            expense_threshold = DEFAULT_EXPENSE_THRESHOLD
            if filter_large_expenses:
                expense_threshold = st.number_input(
                    "Expense Threshold ($)",
                    min_value=1000,
                    max_value=100000,
                    value=DEFAULT_EXPENSE_THRESHOLD,
                    step=500,
                )

        # ---- RIGHT COLUMN: Controls (knobs, scenarios, overrides) ----
        with col_controls:
            st.markdown("##### Returns & Horizon")
            expected_return_rate = st.number_input(
                "Expected Annual Return (%)",
                min_value=0.0,
                max_value=30.0,
                value=float(DEFAULT_EXPECTED_RETURN_RATE),
                step=0.5,
                help="Assumed nominal annual return on the portfolio",
            )

            spending_lookback_months = st.selectbox(
                "Spending Lookback",
                options=FI_SPENDING_LOOKBACK_OPTIONS,
                index=FI_SPENDING_LOOKBACK_OPTIONS.index(DEFAULT_FI_SPENDING_LOOKBACK_MONTHS),
                format_func=lambda n: f"Last {n} Months",
                help="How many months of spending to average",
            )

            projection_years = st.number_input(
                "Projection Horizon (Years)",
                min_value=1,
                max_value=80,
                value=DEFAULT_FI_PROJECTION_YEARS,
                step=5,
                help="How far out to project portfolio balance",
            )

            st.markdown("---")
            st.markdown("##### Scenario Adjustments")
            supplemental_annual_income = st.number_input(
                "Supplemental Annual Income ($)",
                min_value=0,
                max_value=1_000_000,
                value=0,
                step=1000,
                help=(
                    "Non-portfolio income (e.g. part-time work, rental, "
                    "Social Security). Reduces the net annual withdrawal."
                ),
            )

            supplemental_annual_spending = st.number_input(
                "Additional Annual Spending ($)",
                min_value=0,
                max_value=1_000_000,
                value=0,
                step=1000,
                help=(
                    "Extra spending on top of the data-derived baseline "
                    "(e.g. planned mortgage, healthcare, kids college). "
                    "Increases the net annual withdrawal."
                ),
            )

            st.markdown("---")
            st.markdown("##### Overrides")
            override_portfolio_value = st.checkbox(
                "Override Portfolio Value",
                value=False,
                help=(
                    "Replace the data-derived portfolio total with a fixed "
                    "value. Useful for spot-testing scenarios."
                ),
            )

            portfolio_value_override = 0.0
            if override_portfolio_value:
                portfolio_value_override = float(st.number_input(
                    "Portfolio Value Override ($)",
                    min_value=0,
                    max_value=100_000_000,
                    value=1_000_000,
                    step=10_000,
                    help="Used as the portfolio value instead of summing selected accounts",
                ))

            override_annual_spending = st.checkbox(
                "Override Annual Spending",
                value=False,
                help=(
                    "Replace the data-derived annual spending with a fixed "
                    "value. Additional Annual Spending still adds on top."
                ),
            )

            annual_spending_override = 0.0
            if override_annual_spending:
                annual_spending_override = float(st.number_input(
                    "Annual Spending Override ($)",
                    min_value=0,
                    max_value=10_000_000,
                    value=50_000,
                    step=1000,
                    help="Used as the baseline annual spending instead of the calculated average",
                ))

    return {
        "include_accounts": include_accounts,
        "exclude_groups": exclude_groups,
        "exclude_categories": exclude_categories,
        "filter_large_expenses": filter_large_expenses,
        "expense_threshold": expense_threshold,
        "expected_return_rate": expected_return_rate,
        "spending_lookback_months": int(spending_lookback_months),
        "projection_years": int(projection_years),
        "supplemental_annual_income": float(supplemental_annual_income),
        "supplemental_annual_spending": float(supplemental_annual_spending),
        "override_annual_spending": override_annual_spending,
        "annual_spending_override": annual_spending_override,
        "override_portfolio_value": override_portfolio_value,
        "portfolio_value_override": portfolio_value_override,
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
