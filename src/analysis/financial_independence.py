"""Pure calculations for financial-independence scenarios."""

import math

import pandas as pd

from src.custom_types import FISummary


def get_savings_accounts(balance_history: pd.DataFrame) -> list[str]:
    """Return visible accounts assigned to the Saving or Savings group."""
    if "Group" not in balance_history.columns:
        return []
    balances = balance_history
    if "Hide" in balances.columns:
        balances = balances[balances["Hide"] != "Hide"]
    savings = balances["Group"].astype(str).str.lower().isin({"saving", "savings"})
    return sorted(balances.loc[savings, "Account"].dropna().unique().tolist())


def resolve_annual_spending(
    average_monthly_spending: float,
    override_value: float | None,
) -> float:
    """Return an override or annualize the average monthly spending."""
    return (
        float(override_value)
        if override_value is not None
        else average_monthly_spending * 12
    )


def resolve_portfolio_value(
    calculated_value: float,
    override_value: float | None,
) -> float:
    """Return an override or the data-derived portfolio value."""
    return float(override_value) if override_value is not None else calculated_value


def calculate_avg_monthly_spending(
    transactions: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> tuple[float, pd.DataFrame]:
    """Return positive average and monthly expense totals inside the window."""
    columns = ["Month", "Spending"]
    if transactions.empty:
        return 0.0, pd.DataFrame(columns=columns)
    expenses = transactions[
        (transactions["Type"] == "Expense")
        & (transactions["Month"] >= start_month)
        & (transactions["Month"] <= end_month)
    ]
    if expenses.empty:
        return 0.0, pd.DataFrame(columns=columns)
    monthly = (
        expenses.groupby("Month")["Amount"]
        .sum()
        .abs()
        .reset_index()
        .rename(columns={"Amount": "Spending"})
        .sort_values("Month")
        .reset_index(drop=True)
    )
    return float(monthly["Spending"].mean()), monthly


def calculate_fi_metrics(
    portfolio_value: float,
    annual_spending: float,
    rate_pct: float,
    annual_income: float = 0.0,
    additional_annual_spending: float = 0.0,
) -> FISummary:
    """Return annual return, coverage, cash-flow gap, and portfolio runway."""
    rate = rate_pct / 100.0
    annual_return = portfolio_value * rate
    total_spending = annual_spending + additional_annual_spending
    total_inflow = annual_return + annual_income
    cashflow_gap = total_inflow - total_spending
    net_withdrawal = total_spending - annual_income

    if total_spending <= 0:
        coverage = (
            float("inf")
            if portfolio_value > 0 or annual_return > 0 or annual_income > 0
            else 0.0
        )
        runway: float | None = None
    else:
        coverage = total_inflow / total_spending
        if net_withdrawal <= 0:
            runway = None
        elif portfolio_value <= 0:
            runway = 0.0
        elif rate <= 0:
            runway = portfolio_value / net_withdrawal
        elif annual_return >= net_withdrawal:
            runway = None
        else:
            runway = math.log(
                net_withdrawal / (net_withdrawal - portfolio_value * rate)
            ) / math.log(1.0 + rate)

    return FISummary(
        portfolio_value=portfolio_value,
        annual_return=annual_return,
        annual_spending=annual_spending,
        supplemental_spending=additional_annual_spending,
        supplemental_income=annual_income,
        total_spending=total_spending,
        total_inflow=total_inflow,
        cashflow_gap=cashflow_gap,
        coverage_ratio=coverage,
        runway_years=runway,
    )


def project_portfolio(
    portfolio_value: float,
    annual_spending: float,
    rate_pct: float,
    years: int,
    annual_income: float = 0.0,
    additional_annual_spending: float = 0.0,
) -> pd.DataFrame:
    """Apply the yearly return-and-withdrawal recurrence for ``years``."""
    rate = rate_pct / 100.0
    withdrawal = annual_spending + additional_annual_spending - annual_income
    balances = [portfolio_value]
    balance = portfolio_value
    for _ in range(years):
        balance = max(balance * (1.0 + rate) - withdrawal, 0.0)
        balances.append(balance)
    return pd.DataFrame({"Year": range(years + 1), "Balance": balances})
