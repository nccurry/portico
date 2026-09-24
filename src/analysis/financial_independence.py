"""Pure calculations for financial-independence scenarios."""

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import cast

import pandas as pd

from src.custom_types import FISummary, IncomeChange, SpendingChange


@dataclass(frozen=True)
class IncomeStream:
    """A recurring income source that begins during an FI projection."""

    name: str
    annual_amount: float
    start_year: int = 1


def get_accounts_in_groups(balance_history: pd.DataFrame, groups: tuple[str, ...]) -> list[str]:
    """Return visible accounts assigned to configured groups."""
    if "Group" not in balance_history.columns:
        return []
    balances = balance_history
    if "Hide" in balances.columns:
        balances = balances[balances["Hide"] != "Hide"]
    normalized_groups = {group.casefold() for group in groups}
    selected = balances["Group"].astype(str).str.casefold().isin(normalized_groups)
    return sorted(balances.loc[selected, "Account"].dropna().unique().tolist())


def calculate_avg_monthly_spending(
    transactions: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> tuple[float, pd.DataFrame]:
    """Return positive average and monthly expense totals inside the window."""
    return _calculate_avg_monthly_amount(
        transactions,
        start_month,
        end_month,
        transaction_type="Expense",
        amount_column="Spending",
        multiplier=-1.0,
    )


def calculate_avg_monthly_income(
    transactions: pd.DataFrame,
    start_month: str,
    end_month: str,
) -> tuple[float, pd.DataFrame]:
    """Return positive average and monthly income totals inside the window."""
    return _calculate_avg_monthly_amount(
        transactions,
        start_month,
        end_month,
        transaction_type="Income",
        amount_column="Income",
        multiplier=1.0,
    )


def _calculate_avg_monthly_amount(
    transactions: pd.DataFrame,
    start_month: str,
    end_month: str,
    *,
    transaction_type: str,
    amount_column: str,
    multiplier: float,
) -> tuple[float, pd.DataFrame]:
    """Return one transaction type's positive average and monthly totals."""
    columns = ["Month", amount_column]
    periods = pd.period_range(start=start_month, end=end_month, freq="M")
    if periods.empty:
        return 0.0, pd.DataFrame(columns=columns)
    matching = transactions[
        (transactions["Type"] == transaction_type)
        & (transactions["Month"] >= start_month)
        & (transactions["Month"] <= end_month)
    ]
    totals = matching.groupby("Month")["Amount"].sum() * multiplier
    totals = totals.reindex(periods.astype(str), fill_value=0.0).astype(float)
    monthly = totals.rename(amount_column).rename_axis("Month").reset_index()
    return float(monthly[amount_column].mean()), monthly


def build_income_projection(
    annual_earned_income: float,
    income_streams: tuple[IncomeStream, ...],
    years: int,
    income_schedule: tuple[IncomeChange, ...] = (),
) -> pd.DataFrame:
    """Return active income by stream for each projected year."""
    rows = []
    for year in range(1, years + 1):
        rows.append(
            {"Year": year, "Stream": "Income", "Income": income_for_year(annual_earned_income, income_schedule, year)}
        )
        rows.extend(
            {
                "Year": year,
                "Stream": stream.name,
                "Income": stream.annual_amount if year >= stream.start_year else 0.0,
            }
            for stream in income_streams
        )
    return pd.DataFrame(rows, columns=["Year", "Stream", "Income"])


def income_for_year(annual_income: float, income_schedule: tuple[IncomeChange, ...], year: int) -> float:
    """Return the earned-income amount active in a projected year."""
    change = max(
        (item for item in income_schedule if item.start_year <= year),
        key=lambda item: item.start_year,
        default=None,
    )
    return annual_income if change is None else change.annual_amount


def spending_for_year(annual_spending: float, spending_schedule: tuple[SpendingChange, ...], year: int) -> float:
    """Return the expense amount active in a projected year."""
    change = max(
        (item for item in spending_schedule if item.start_year <= year),
        key=lambda item: item.start_year,
        default=None,
    )
    return annual_spending if change is None else change.annual_amount


def build_spending_coverage(
    income_projection: pd.DataFrame,
    portfolio_projection: pd.DataFrame,
) -> pd.DataFrame:
    """Show what pays each year's expenses and what remains unfunded."""
    columns = ["Year", "Stream", "Amount", "Needed"]
    if income_projection.empty:
        return pd.DataFrame(columns=columns)

    available_assets = (
        portfolio_projection.set_index("Year")[["Starting_Balance", "Investment_Return", "Property_Growth"]]
        .sum(axis=1)
        .clip(lower=0.0)
    )
    yearly_spending = portfolio_projection.set_index("Year")["Spending"]
    rows: list[dict[str, int | str | float]] = []
    for year, yearly_income in income_projection.groupby("Year", sort=True):
        year = cast(int, year)
        needed = float(yearly_spending.loc[year]) - float(yearly_income["Income"].clip(upper=0.0).sum())
        remaining = needed
        for stream, income in yearly_income[["Stream", "Income"]].itertuples(index=False, name=None):
            amount = min(max(float(income), 0.0), remaining)
            remaining -= amount
            rows.append({"Year": year, "Stream": stream, "Amount": amount, "Needed": needed})

        from_assets = min(remaining, float(available_assets.loc[year]))
        rows.append({"Year": year, "Stream": "From assets", "Amount": from_assets, "Needed": needed})
        rows.append({"Year": year, "Stream": "Not covered", "Amount": remaining - from_assets, "Needed": needed})
    return pd.DataFrame(rows, columns=columns)


def summarize_spending_coverage(coverage: pd.DataFrame) -> pd.DataFrame:
    """Combine consecutive years with the same mix of income and withdrawals."""
    columns = ["Years", "Stream", "Amount", "Needed"]
    if coverage.empty:
        return pd.DataFrame(columns=columns)

    yearly = coverage.pivot_table(index="Year", columns="Stream", values="Amount", aggfunc="sum", fill_value=0.0)
    phase_by_year = yearly.ne(yearly.shift()).any(axis=1).cumsum()
    bounds = (
        pd.DataFrame({"Year": yearly.index, "Phase": phase_by_year.to_numpy()})
        .groupby("Phase")["Year"]
        .agg(["min", "max"])
    )
    labels = {
        phase: f"Year {start}" if start == end else f"Years {start}-{end}" for phase, start, end in bounds.itertuples()
    }
    periods = coverage.assign(Phase=coverage["Year"].map(phase_by_year))
    periods["Years"] = periods["Phase"].map(labels)
    return periods.drop_duplicates(["Phase", "Stream"])[columns].reset_index(drop=True)


def calculate_fi_metrics(
    portfolio_value: float,
    annual_spending: float,
    rate_pct: float,
    annual_income: float = 0.0,
    withdrawal_rate_pct: float = 4.0,
    income_streams: tuple[IncomeStream, ...] = (),
    *,
    real_estate_value: float = 0.0,
    real_estate_rate_pct: float = 0.0,
    spending_schedule: tuple[SpendingChange, ...] = (),
    income_schedule: tuple[IncomeChange, ...] = (),
) -> FISummary:
    """Return annual funding, FI target, and portfolio runway."""
    rate = rate_pct / 100.0
    real_estate_rate = real_estate_rate_pct / 100.0
    total_assets = portfolio_value + real_estate_value
    year_one_income = annual_income + sum(stream.annual_amount for stream in income_streams if stream.start_year <= 1)
    annual_return = portfolio_value * rate + real_estate_value * real_estate_rate
    total_inflow = annual_return + year_one_income
    annual_surplus = total_inflow - annual_spending
    net_withdrawal = annual_spending - year_one_income
    net_annual_spending = max(net_withdrawal, 0.0)
    withdrawal_rate = withdrawal_rate_pct / 100.0
    sustainable_spending = total_assets * withdrawal_rate
    if net_annual_spending <= 0:
        fi_target = 0.0
    elif withdrawal_rate <= 0:
        fi_target = float("inf")
    else:
        fi_target = net_annual_spending / withdrawal_rate
    fi_gap = total_assets - fi_target

    runway = _calculate_scheduled_runway(
        portfolio_value,
        annual_spending,
        rate,
        annual_income,
        income_streams,
        real_estate_value,
        real_estate_rate,
        spending_schedule,
        income_schedule,
    )

    return FISummary(
        annual_return=annual_return,
        annual_income=year_one_income,
        total_spending=annual_spending,
        annual_surplus=annual_surplus,
        runway_years=runway,
        net_annual_spending=net_annual_spending,
        sustainable_spending=sustainable_spending,
        fi_target=fi_target,
        fi_gap=fi_gap,
    )


def _calculate_scheduled_runway(
    portfolio_value: float,
    annual_spending: float,
    rate: float,
    annual_income: float,
    income_streams: tuple[IncomeStream, ...],
    real_estate_value: float,
    real_estate_rate: float,
    spending_schedule: tuple[SpendingChange, ...],
    income_schedule: tuple[IncomeChange, ...],
) -> float | None:
    """Calculate runway across changes in income or expenses."""
    phase_starts = sorted(
        {
            1,
            *(stream.start_year for stream in income_streams),
            *(change.start_year for change in spending_schedule),
            *(change.start_year for change in income_schedule),
        }
    )
    investments = portfolio_value
    property_value = real_estate_value
    for start_year, next_start_year in pairwise(phase_starts):
        income = income_for_year(annual_income, income_schedule, start_year) + sum(
            stream.annual_amount for stream in income_streams if stream.start_year <= start_year
        )
        spending = spending_for_year(annual_spending, spending_schedule, start_year)
        phase_runway = (
            _calculate_two_asset_runway(investments, property_value, spending, rate, real_estate_rate, income)
            if property_value
            else _calculate_constant_income_runway(investments, spending, rate, income)
        )
        if phase_runway is not None and phase_runway < next_start_year - start_year:
            return start_year - 1 + phase_runway
        for _ in range(start_year, next_start_year):
            investments, property_value, _, _ = _advance_balances(
                investments, property_value, rate, real_estate_rate, income - spending
            )

    final_start_year = phase_starts[-1]
    final_spending = spending_for_year(annual_spending, spending_schedule, final_start_year)
    final_income = income_for_year(annual_income, income_schedule, final_start_year) + sum(
        stream.annual_amount for stream in income_streams
    )
    if property_value:
        final_runway = _calculate_two_asset_runway(
            investments,
            property_value,
            final_spending,
            rate,
            real_estate_rate,
            final_income,
        )
    else:
        final_runway = _calculate_constant_income_runway(investments, final_spending, rate, final_income)
    return None if final_runway is None else final_start_year - 1 + final_runway


def _advance_balances(
    investments: float,
    property_value: float,
    investment_rate: float,
    real_estate_rate: float,
    net_cash_flow: float,
) -> tuple[float, float, float, float]:
    """Invest spare income and use property value only after investments run out."""
    investment_growth = investments * investment_rate
    property_growth = property_value * real_estate_rate
    investments += investment_growth + net_cash_flow
    property_value += property_growth
    if investments < 0:
        property_value += investments
        investments = 0.0
    if property_value < 0:
        investments = max(investments + property_value, 0.0)
        property_value = 0.0
    return investments, property_value, investment_growth, property_growth


def _calculate_two_asset_runway(
    investments: float,
    property_value: float,
    annual_spending: float,
    investment_rate: float,
    real_estate_rate: float,
    annual_income: float,
) -> float | None:
    """Calculate runway with investments spent before property value."""
    annual_withdrawal = annual_spending - annual_income
    if annual_withdrawal <= 0:
        return None
    if investments < 0 or property_value < 0:
        available = investments * (1.0 + investment_rate) + property_value * (1.0 + real_estate_rate)
        if available <= annual_withdrawal:
            return max(available / annual_withdrawal, 0.0)
        investments, property_value, _, _ = _advance_balances(
            investments, property_value, investment_rate, real_estate_rate, -annual_withdrawal
        )
        remaining_runway = _calculate_two_asset_runway(
            investments, property_value, annual_spending, investment_rate, real_estate_rate, annual_income
        )
        return None if remaining_runway is None else 1.0 + remaining_runway
    if investments <= 0:
        return _calculate_constant_income_runway(property_value, annual_spending, real_estate_rate, annual_income)

    investment_runway = _calculate_constant_income_runway(investments, annual_spending, investment_rate, annual_income)
    if investment_runway is None:
        return None
    if property_value <= 0:
        return investment_runway

    years_using_investments = math.ceil(investment_runway)
    years_before_sale = max(years_using_investments - 1, 0)
    if investment_rate == 0:
        investment_before_sale = investments - annual_withdrawal * years_before_sale
    elif investment_rate <= -1:
        investment_before_sale = investments
    else:
        growth = (1.0 + investment_rate) ** years_before_sale
        investment_before_sale = investments * growth - annual_withdrawal * (growth - 1.0) / investment_rate

    investment_available = max(investment_before_sale * (1.0 + investment_rate), 0.0)
    try:
        property_available = max(property_value * (1.0 + real_estate_rate) ** years_using_investments, 0.0)
    except OverflowError:
        return None
    remaining_property = property_available + investment_available - annual_withdrawal
    if remaining_property <= 0:
        return years_before_sale + (investment_available + property_available) / annual_withdrawal

    property_runway = _calculate_constant_income_runway(
        remaining_property, annual_spending, real_estate_rate, annual_income
    )
    return None if property_runway is None else years_using_investments + property_runway


def _calculate_constant_income_runway(
    portfolio_value: float,
    annual_spending: float,
    rate: float,
    annual_income: float,
) -> float | None:
    """Calculate runway after all recurring income streams have begun."""
    net_withdrawal = annual_spending - annual_income
    if net_withdrawal <= 0:
        return None
    if portfolio_value <= 0:
        return 0.0
    if rate == 0:
        return portfolio_value / net_withdrawal
    if rate <= -1:
        return 1.0
    annual_return = portfolio_value * rate
    if annual_return >= net_withdrawal:
        return None
    return math.log(net_withdrawal / (net_withdrawal - annual_return)) / math.log1p(rate)


def project_portfolio(
    portfolio_value: float,
    annual_spending: float,
    rate_pct: float,
    years: int,
    annual_income: float = 0.0,
    income_streams: tuple[IncomeStream, ...] = (),
    *,
    real_estate_value: float = 0.0,
    real_estate_rate_pct: float = 0.0,
    spending_schedule: tuple[SpendingChange, ...] = (),
    income_schedule: tuple[IncomeChange, ...] = (),
) -> pd.DataFrame:
    """Apply the yearly return-and-withdrawal recurrence for ``years``."""
    rate = rate_pct / 100.0
    real_estate_rate = real_estate_rate_pct / 100.0
    income_projection = build_income_projection(annual_income, income_streams, years, income_schedule)
    income_by_year = income_projection.groupby("Year")["Income"].sum()
    rows = [
        {
            "Year": 0,
            "Starting_Balance": portfolio_value + real_estate_value,
            "Investment_Return": 0.0,
            "Property_Growth": 0.0,
            "Income": 0.0,
            "Spending": 0.0,
            "Net_Cash_Flow": 0.0,
            "Investments": portfolio_value,
            "Real_Estate": real_estate_value,
            "Balance": portfolio_value + real_estate_value,
        }
    ]
    investments = portfolio_value
    property_value = real_estate_value
    for year in range(1, years + 1):
        starting_balance = investments + property_value
        income = float(income_by_year.get(year, 0.0))
        yearly_spending = spending_for_year(annual_spending, spending_schedule, year)
        net_cash_flow = income - yearly_spending
        investments, property_value, investment_return, property_growth = _advance_balances(
            investments, property_value, rate, real_estate_rate, net_cash_flow
        )
        rows.append(
            {
                "Year": year,
                "Starting_Balance": starting_balance,
                "Investment_Return": investment_return,
                "Property_Growth": property_growth,
                "Income": income,
                "Spending": yearly_spending,
                "Net_Cash_Flow": net_cash_flow,
                "Investments": investments,
                "Real_Estate": property_value,
                "Balance": investments + property_value,
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
    income_streams: tuple[IncomeStream, ...] = (),
    real_estate_value: float = 0.0,
    real_estate_rate_pct: float = 0.0,
    spending_schedule: tuple[SpendingChange, ...] = (),
    income_schedule: tuple[IncomeChange, ...] = (),
) -> pd.DataFrame:
    """Return runway outcomes across nearby spending and return assumptions."""
    if return_rates is None:
        minimum_return_rate = -20.0 if baseline_return_rate < 0 else 0.0
        return_rates = tuple(
            sorted({max(minimum_return_rate, baseline_return_rate + change) for change in (-4.0, -2.0, 0.0, 2.0, 4.0)})
        )
    rows: list[dict[str, float | str | bool]] = []
    for spending_change in spending_changes:
        spending_factor = 1 + spending_change / 100
        scenario_spending = annual_spending * spending_factor
        scenario_schedule = tuple(
            SpendingChange(change.start_year, change.annual_amount * spending_factor) for change in spending_schedule
        )
        for return_rate in return_rates:
            runway = calculate_fi_metrics(
                portfolio_value,
                scenario_spending,
                return_rate,
                annual_income,
                income_streams=income_streams,
                real_estate_value=real_estate_value,
                real_estate_rate_pct=real_estate_rate_pct,
                spending_schedule=scenario_schedule,
                income_schedule=income_schedule,
            )["runway_years"]
            rows.append(
                {
                    "Spending_Change": ("Baseline" if spending_change == 0 else f"{spending_change:+d}%"),
                    "Annual_Spending": scenario_spending,
                    "Return_Rate": return_rate,
                    "Is_Baseline_Return": return_rate == baseline_return_rate,
                    "Runway_Years": 100.0 if runway is None else min(runway, 100.0),
                    "Runway_Label": "Sustainable" if runway is None else f"{runway:.1f} years",
                }
            )
    return pd.DataFrame(rows)
