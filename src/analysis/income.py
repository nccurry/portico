"""Pure calculations for the income and savings page."""

import pandas as pd

from src.custom_types import (
    FilteredTransactionSummary,
    IncomeExpenseFilters,
    SavingsSummary,
    TransactionFilterOptions,
)
from src.constants import DEFAULT_EXPENSE_THRESHOLD, DEFAULT_INCOME_THRESHOLD
from src.spreadsheet import TransactionsSpreadsheet


MONTHLY_CASH_FLOW_COLUMNS = [
    "Month",
    "Income",
    "Expense",
    "Net_Expenses",
    "Cash_Flow_Surplus",
    "Savings_Rate",
]


def _requested_months(start_month: str | None, end_month: str | None) -> pd.Index[str] | None:
    """Return the requested month index, where ``end_month`` is exclusive."""
    if (start_month is None) != (end_month is None):
        raise ValueError("start_month and end_month must be provided together")
    if start_month is None or end_month is None:
        return None

    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    if start >= end:
        return pd.Index([], dtype="object", name="Month")
    months = [str(month) for month in pd.period_range(start=start, end=end - 1, freq="M")]
    return pd.Index(months, dtype="object", name="Month")


def _append_reason(reasons: list[str], condition: bool, reason: str) -> None:
    if condition:
        reasons.append(reason)


def _row_exclusion_reasons(
    *,
    group: str,
    category: str,
    transaction_type: str,
    amount: float,
    filters: TransactionFilterOptions,
) -> str:
    """Describe every filter rule that excludes one transaction."""
    reasons: list[str] = []
    include_groups = set(filters.get("include_groups", ()))
    include_categories = set(filters.get("include_categories", ()))
    include_mode = bool(include_groups or include_categories)

    if transaction_type == "Income" and "exclude_income_categories" in filters:
        excluded_categories = set(filters["exclude_income_categories"])
    elif transaction_type == "Expense" and "exclude_expense_categories" in filters:
        excluded_categories = set(filters["exclude_expense_categories"])
    else:
        excluded_categories = set(filters.get("exclude_categories", ()))

    _append_reason(reasons, group == "Transfer", "Transfer group")
    if include_mode:
        _append_reason(
            reasons,
            group not in include_groups and category not in include_categories,
            "Outside included groups/categories",
        )
    else:
        _append_reason(
            reasons,
            group in filters.get("exclude_groups", ()),
            f"Excluded group: {group}",
        )
        _append_reason(
            reasons,
            category in excluded_categories,
            f"Excluded {transaction_type.lower()} category: {category}",
        )

    if transaction_type == "Income" and filters.get("filter_large_income"):
        threshold = float(filters.get("income_threshold", DEFAULT_INCOME_THRESHOLD))
        _append_reason(
            reasons,
            abs(amount) > threshold,
            f"Income over ${threshold:,.0f}",
        )
    if transaction_type == "Expense" and filters.get("filter_large_expenses"):
        threshold = float(filters.get("expense_threshold", DEFAULT_EXPENSE_THRESHOLD))
        _append_reason(
            reasons,
            abs(amount) > threshold,
            f"Expense over ${threshold:,.0f}",
        )

    return "; ".join(reasons)


def build_income_expense_ledger(
    transactions: pd.DataFrame,
    filters: TransactionFilterOptions,
    *,
    start_month: str | None = None,
    end_month: str | None = None,
) -> pd.DataFrame:
    """Annotate period income and expense rows with filter inclusion details.

    ``end_month`` is exclusive. Rows keep their original order and index so the
    ledger can support transaction-level drill-downs without rematching data.
    """
    requested_months = _requested_months(start_month, end_month)
    ledger = transactions[transactions["Type"].isin(("Income", "Expense"))].copy()
    if requested_months is not None:
        ledger = (
            ledger[(ledger["Month"] >= str(requested_months[0])) & (ledger["Month"] <= str(requested_months[-1]))]
            if not requested_months.empty
            else ledger.iloc[0:0].copy()
        )

    if ledger.empty:
        ledger["Included"] = pd.Series(dtype="bool")
        ledger["Exclusion_Reason"] = pd.Series(dtype="object")
        return ledger

    groups = ledger["Group"].astype(str).tolist()
    categories = ledger["Category"].astype(str).tolist()
    transaction_types = ledger["Type"].astype(str).tolist()
    amounts = ledger["Amount"].astype(float).tolist()
    exclusion_reasons = [
        _row_exclusion_reasons(
            group=group,
            category=category,
            transaction_type=transaction_type,
            amount=amount,
            filters=filters,
        )
        for group, category, transaction_type, amount in zip(
            groups,
            categories,
            transaction_types,
            amounts,
            strict=True,
        )
    ]
    ledger["Included"] = [not reason for reason in exclusion_reasons]
    ledger["Exclusion_Reason"] = exclusion_reasons
    return ledger


def process_income_expense_data(
    transactions_spreadsheet: TransactionsSpreadsheet,
    filters: IncomeExpenseFilters,
    *,
    start_month: str | None = None,
    end_month: str | None = None,
) -> pd.DataFrame:
    """Return monthly cash flow after applying the selected baseline filters.

    When a period is supplied, ``start_month`` is inclusive and ``end_month``
    is exclusive. Every requested calendar month appears, including months with
    no included transactions.
    """
    ledger = build_income_expense_ledger(
        transactions_spreadsheet.scrubbed_df,
        filters,
        start_month=start_month,
        end_month=end_month,
    )
    return summarize_income_expense_ledger(
        ledger,
        start_month=start_month,
        end_month=end_month,
    )


def summarize_income_expense_ledger(
    ledger: pd.DataFrame,
    *,
    start_month: str | None = None,
    end_month: str | None = None,
) -> pd.DataFrame:
    """Aggregate an annotated transaction ledger into monthly cash flow."""
    requested_months = _requested_months(start_month, end_month)
    transactions = ledger[ledger["Included"]]
    if requested_months is not None:
        transactions = (
            transactions[
                (transactions["Month"] >= str(requested_months[0]))
                & (transactions["Month"] <= str(requested_months[-1]))
            ]
            if not requested_months.empty
            else transactions.iloc[0:0].copy()
        )
    monthly_income = transactions[transactions["Type"] == "Income"].groupby("Month")["Amount"].sum()
    monthly_expense = transactions[transactions["Type"] == "Expense"].groupby("Month")["Amount"].sum()
    monthly = pd.concat(
        [monthly_income.rename("Income"), monthly_expense.rename("Expense")],
        axis=1,
    )
    if requested_months is not None:
        monthly = monthly.reindex(requested_months)
    monthly = monthly.fillna(0.0).reset_index()
    if monthly.empty:
        return pd.DataFrame(columns=MONTHLY_CASH_FLOW_COLUMNS)
    monthly[["Income", "Expense"]] = monthly[["Income", "Expense"]].astype(float)

    monthly["Net_Expenses"] = -monthly["Expense"]
    monthly["Cash_Flow_Surplus"] = monthly["Income"] - monthly["Net_Expenses"]
    monthly["Savings_Rate"] = (
        monthly["Cash_Flow_Surplus"].div(monthly["Income"]).mul(100).where(monthly["Income"].gt(0))
    )
    return monthly[MONTHLY_CASH_FLOW_COLUMNS].sort_values("Month", ignore_index=True)


def calculate_savings_summary(monthly: pd.DataFrame) -> SavingsSummary:
    """Return income-weighted period cash-flow metrics."""
    if monthly.empty:
        return SavingsSummary(
            total_income=0.0,
            total_net_expenses=0.0,
            total_cash_flow_surplus=0.0,
            weighted_savings_rate=None,
            average_monthly_surplus=0.0,
            positive_surplus_months=0,
            num_months=0,
        )

    income = monthly["Income"]
    net_expenses = monthly["Net_Expenses"]
    surplus = monthly["Cash_Flow_Surplus"]
    total_income = float(income.sum())
    total_net_expenses = float(net_expenses.sum())
    total_surplus = float(surplus.sum())
    weighted_rate = total_surplus / total_income * 100 if total_income > 0 else None

    return SavingsSummary(
        total_income=total_income,
        total_net_expenses=total_net_expenses,
        total_cash_flow_surplus=total_surplus,
        weighted_savings_rate=weighted_rate,
        average_monthly_surplus=float(surplus.mean()),
        positive_surplus_months=int(surplus.gt(0).sum()),
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
