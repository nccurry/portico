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


def calculate_avg_monthly_spending(
    transactions: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> tuple[float, pd.DataFrame]:
    """Return positive average and monthly expense totals inside the window."""
    columns = ["Month", "Spending"]
    periods = pd.period_range(start=start_month, end=end_month, freq="M")
    if periods.empty:
        return 0.0, pd.DataFrame(columns=columns)
    expenses = transactions[
        (transactions["Type"] == "Expense")
        & (transactions["Month"] >= start_month)
        & (transactions["Month"] <= end_month)
    ]
    totals = -expenses.groupby("Month")["Amount"].sum()
    totals = totals.reindex(periods.astype(str), fill_value=0.0).astype(float)
    monthly = totals.rename("Spending").rename_axis("Month").reset_index()
    return float(monthly["Spending"].mean()), monthly


def calculate_fi_metrics(
    portfolio_value: float,
    annual_spending: float,
    rate_pct: float,
    annual_income: float = 0.0,
    withdrawal_rate_pct: float = 4.0,
) -> FISummary:
    """Return annual funding, FI target, and portfolio runway."""
    rate = rate_pct / 100.0
    annual_return = portfolio_value * rate
    total_inflow = annual_return + annual_income
    annual_surplus = total_inflow - annual_spending
    net_withdrawal = annual_spending - annual_income
    net_annual_spending = max(net_withdrawal, 0.0)
    withdrawal_rate = withdrawal_rate_pct / 100.0
    sustainable_spending = portfolio_value * withdrawal_rate
    if net_annual_spending <= 0:
        fi_target = 0.0
    elif withdrawal_rate <= 0:
        fi_target = float("inf")
    else:
        fi_target = net_annual_spending / withdrawal_rate
    fi_gap = portfolio_value - fi_target

    if annual_spending <= 0:
        runway: float | None = None
    else:
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
        annual_return=annual_return,
        annual_income=annual_income,
        total_spending=annual_spending,
        annual_surplus=annual_surplus,
        runway_years=runway,
        net_annual_spending=net_annual_spending,
        sustainable_spending=sustainable_spending,
        fi_target=fi_target,
        fi_gap=fi_gap,
    )


def project_portfolio(
    portfolio_value: float,
    annual_spending: float,
    rate_pct: float,
    years: int,
    annual_income: float = 0.0,
) -> pd.DataFrame:
    """Apply the yearly return-and-withdrawal recurrence for ``years``."""
    rate = rate_pct / 100.0
    rows = [
        {
            "Year": 0,
            "Starting_Balance": portfolio_value,
            "Investment_Return": 0.0,
            "Income": 0.0,
            "Spending": 0.0,
            "Net_Cash_Flow": 0.0,
            "Balance": portfolio_value,
        }
    ]
    balance = portfolio_value
    for year in range(1, years + 1):
        starting_balance = balance
        investment_return = starting_balance * rate
        net_cash_flow = annual_income - annual_spending
        balance = max(starting_balance + investment_return + net_cash_flow, 0.0)
        rows.append(
            {
                "Year": year,
                "Starting_Balance": starting_balance,
                "Investment_Return": investment_return,
                "Income": annual_income,
                "Spending": annual_spending,
                "Net_Cash_Flow": net_cash_flow,
                "Balance": balance,
            }
        )
    return pd.DataFrame(rows)


def build_runway_sensitivity(
    portfolio_value: float,
    annual_spending: float,
    annual_income: float,
    *,
    baseline_return_rate: float = 5.0,
    spending_changes: tuple[int, ...] = (-20, -10, 0, 10, 20),
    return_rates: tuple[float, ...] | None = None,
) -> pd.DataFrame:
    """Return runway outcomes across nearby spending and return assumptions."""
    if return_rates is None:
        return_rates = tuple(
            sorted(
                {
                    max(0.0, baseline_return_rate + change)
                    for change in (-4.0, -2.0, 0.0, 2.0, 4.0)
                }
            )
        )
    rows: list[dict[str, float | str | bool]] = []
    for spending_change in spending_changes:
        scenario_spending = annual_spending * (1 + spending_change / 100)
        for return_rate in return_rates:
            runway = calculate_fi_metrics(
                portfolio_value,
                scenario_spending,
                return_rate,
                annual_income,
            )["runway_years"]
            rows.append(
                {
                    "Spending_Change": (
                        "Baseline"
                        if spending_change == 0
                        else f"{spending_change:+d}%"
                    ),
                    "Annual_Spending": scenario_spending,
                    "Return_Rate": return_rate,
                    "Is_Baseline_Return": return_rate == baseline_return_rate,
                    "Runway_Years": 100.0 if runway is None else min(runway, 100.0),
                    "Runway_Label": "Sustainable" if runway is None else f"{runway:.1f} years",
                }
            )
    return pd.DataFrame(rows)
