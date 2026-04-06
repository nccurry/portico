"""Common filter UI components used across multiple pages."""
import streamlit as st

import pandas as pd
from datetime import timedelta

from src.constants import (
    DEFAULT_EXCLUDE_CATEGORIES,
    DEFAULT_EXCLUDE_GROUPS_INCOME_SAVINGS,
    DEFAULT_EXCLUDE_GROUPS_SPENDING,
    DEFAULT_EXCLUDE_GROUPS_BUDGET,
    DEFAULT_EXPENSE_THRESHOLD,
    DEFAULT_INCOME_THRESHOLD,
    DEFAULT_SAVINGS_RATE_TARGET,
    MIN_SAVINGS_RATE,
    MAX_SAVINGS_RATE,
    SAVINGS_RATE_STEP,
)


def render_income_expense_filters(all_groups: list[str]) -> dict:
    """Render filter controls for Income & Savings page.
    
    Returns:
        dictionary containing all filter selections
    """
    with st.expander("⚙️ Filter Settings", expanded=False):
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            exclude_groups = st.multiselect(
                "Exclude Groups",
                options=all_groups,
                default=[g for g in DEFAULT_EXCLUDE_GROUPS_INCOME_SAVINGS if g in all_groups],
                help="Exclude entire transaction groups (Transfer always excluded)"
            )

            exclude_categories = st.multiselect(
                "Exclude Categories",
                options=DEFAULT_EXCLUDE_CATEGORIES,
                default=['Tax Return Payment', 'Given Gift', 'Christmas', '401k', 'HSA', 'Stock Purchase'],
                help="Exclude specific one-time or non-recurring transaction categories"
            )
        
        with col_filter2:
            filter_large_income = st.checkbox(
                "Filter Large Income",
                value=True,
                help="Exclude individual large income transactions above a threshold (bonuses, stock gains)"
            )
            
            income_threshold = DEFAULT_INCOME_THRESHOLD
            if filter_large_income:
                income_threshold = st.number_input(
                    "Income Threshold ($)",
                    min_value=5000,
                    max_value=100000,
                    value=DEFAULT_INCOME_THRESHOLD,
                    step=1000,
                    help="Exclude individual income transactions larger than this amount"
                )
            
            filter_large_expenses = st.checkbox(
                "Filter Large Expenses",
                value=True,
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
            
            target_rate = st.number_input(
                "Savings Rate Target (%)",
                min_value=MIN_SAVINGS_RATE,
                max_value=MAX_SAVINGS_RATE,
                value=DEFAULT_SAVINGS_RATE_TARGET,
                step=SAVINGS_RATE_STEP,
                help="Your goal savings rate - shown as gold dashed line on chart"
            )
    
    return {
        'exclude_groups': exclude_groups,
        'exclude_categories': exclude_categories,
        'filter_large_income': filter_large_income,
        'income_threshold': income_threshold,
        'filter_large_expenses': filter_large_expenses,
        'expense_threshold': expense_threshold,
        'target_rate': target_rate
    }


def render_spending_filters(all_categories: list[str], all_groups: list[str]) -> dict:
    """Render filter controls for Spending by Category page.
    
    Args:
        all_categories: List of all available categories for inclusion filter
        
    Returns:
        dictionary containing all filter selections
    """
    with st.expander("⚙️ Filter Settings", expanded=False):
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
                options=DEFAULT_EXCLUDE_CATEGORIES,
                default=DEFAULT_EXCLUDE_CATEGORIES,
                help="Exclude specific one-time or non-recurring transaction categories"
            )
        
        with col_filter2:
            filter_large_expenses = st.checkbox(
                "Filter Large Expenses",
                value=True,
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


def render_budget_filters(all_categories: list[str], all_groups: list[str]) -> dict:
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
                default=[g for g in DEFAULT_EXCLUDE_GROUPS_BUDGET if g in all_groups],
                help="Exclude entire transaction groups from budget comparison"
            )

            exclude_categories = st.multiselect(
                "Exclude Categories",
                options=all_categories,
                default=[c for c in DEFAULT_EXCLUDE_CATEGORIES if c in all_categories],
                help="Exclude specific categories from budget comparison"
            )

        with col_filter2:
            filter_large_expenses = st.checkbox(
                "Filter Large Expenses",
                value=True,
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

            show_zero_budget = st.checkbox(
                "Show categories without budget",
                value=False,
                help="Include categories that have no budget set"
            )

    return {
        'exclude_groups': exclude_groups,
        'exclude_categories': exclude_categories,
        'filter_large_expenses': filter_large_expenses,
        'expense_threshold': expense_threshold,
        'show_zero_budget': show_zero_budget,
    }


def calculate_date_range(period: str, df: pd.DataFrame = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calculate start and end dates for a given period string.
    
    Args:
        period: Time period name (e.g., "Last 3 Months", "Year to Date")
        df: Optional dataframe to get min date for "All Time" option
        
    Returns:
        Tuple of (start_date, end_date) as pandas Timestamps
    """
    now = pd.Timestamp.now(tz='UTC')
    
    if period == "This Month":
        return now.replace(day=1), now
    elif period == "Last Month":
        start = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        end = now.replace(day=1) - timedelta(days=1)
        return start, end
    elif period == "Last 3 Months":
        return now - timedelta(days=90), now
    elif period == "Last 6 Months":
        return now - timedelta(days=180), now
    elif period == "Last 12 Months":
        return now - timedelta(days=365), now
    elif period == "Year to Date":
        return now.replace(month=1, day=1), now
    elif period == "All Time":
        if df is not None:
            return df['Date'].min(), now
        return now - timedelta(days=365*5), now  # Default to 5 years
    else:
        # Default to last 3 months
        return now - timedelta(days=90), now


def apply_transaction_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
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

