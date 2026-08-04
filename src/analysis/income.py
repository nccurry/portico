"""Pure calculations for the income and savings page."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.custom_types import FilteredTransactionSummary, SavingsSummary
from src.filters import apply_transaction_filters
from src.spreadsheet import TransactionsSpreadsheet


def process_income_expense_data(
    transactions_spreadsheet: TransactionsSpreadsheet,
    filters: Mapping[str, Any],
) -> pd.DataFrame:
    """Apply filters and return one income, expense, and savings row per month."""
    transactions = apply_transaction_filters(
        transactions_spreadsheet.scrubbed_df.copy(),
        filters,
    )
    monthly_income = (
        transactions[transactions["Type"] == "Income"]
        .groupby("Month")["Amount"]
        .sum()
    )
    monthly_expense = (
        transactions[transactions["Type"] == "Expense"]
        .groupby("Month")["Amount"]
        .sum()
    )
    monthly = pd.concat(
        [monthly_income.rename("Income"), monthly_expense.rename("Expense")],
        axis=1,
    ).fillna(0).reset_index()
    monthly["Savings"] = monthly["Income"] + monthly["Expense"]
    monthly["Net"] = monthly["Savings"]
    monthly["Income_Display"] = monthly["Income"].abs()
    monthly["Expense_Display"] = monthly["Expense"].abs()
    monthly["Savings_Rate"] = monthly.apply(
        lambda row: (
            row["Savings"] / row["Income_Display"] * 100
            if row["Income_Display"] > 0.01
            else 0
        ),
        axis=1,
    )
    return monthly.sort_values("Month")


def calculate_savings_summary(monthly: pd.DataFrame) -> SavingsSummary:
    """Return aggregate savings metrics from monthly income and expense rows."""
    if monthly.empty:
        return SavingsSummary(
            avg_monthly_rate=0.0,
            overall_rate=0.0,
            avg_monthly_amount=0.0,
            total_saved=0.0,
            num_months=0,
        )

    total_income = float(monthly["Income_Display"].sum())
    total_saved = float(monthly["Savings"].sum())
    return SavingsSummary(
        avg_monthly_rate=float(monthly["Savings_Rate"].mean()),
        overall_rate=(total_saved / total_income * 100) if total_income > 0 else 0.0,
        avg_monthly_amount=float(monthly["Savings"].mean()),
        total_saved=total_saved,
        num_months=len(monthly),
    )


def summarize_filtered_transactions(
    transactions: pd.DataFrame,
) -> FilteredTransactionSummary:
    """Summarize transactions removed by the large-amount filters."""
    income = transactions.loc[transactions["Type"] == "Income", "Amount"].sum()
    expenses = transactions.loc[transactions["Type"] == "Expense", "Amount"].sum()
    income_amount = float(abs(income))
    expense_amount = float(abs(expenses))
    return FilteredTransactionSummary(
        count=len(transactions),
        total_amount=income_amount + expense_amount,
        income_amount=income_amount,
        expense_amount=expense_amount,
    )
