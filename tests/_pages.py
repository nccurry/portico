"""Centralized loaders for ``Pages/N_Foo.py`` modules.

The Streamlit ``Pages/`` directory uses leading-digit module names that are
not legal Python identifiers, so we cannot ``import Pages.1_Income_and_Savings``
in the normal way. ``importlib.import_module`` works because it accepts the
module name as a string. This file centralizes the lookup so test files do
not each carry their own copy of the workaround.

Usage::

    from tests._pages import income_and_savings, top_transactions
    process = income_and_savings.process_income_expense_data
"""
from importlib import import_module
from types import ModuleType


def _load(name: str) -> ModuleType:
    return import_module(f"Pages.{name}")


income_and_savings: ModuleType = _load("1_Income_and_Savings")
spending_by_category: ModuleType = _load("2_Spending_by_Category")
year_over_year: ModuleType = _load("3_Year_over_Year")
duplicate_detection: ModuleType = _load("4_Duplicate_Detection")
subscriptions: ModuleType = _load("5_Subscriptions")
merchant_analysis: ModuleType = _load("6_Merchant_Analysis")
budget: ModuleType = _load("7_Budget")
top_transactions: ModuleType = _load("8_Top_Transactions")
financial_independence: ModuleType = _load("9_Financial_Independence")
