"""Pure calculations and chart data for spending analysis."""

import pandas as pd

from src.custom_types import DistributionStats, SpendingFilters, SpendingSummary
from src.filters import apply_transaction_filters
from src.spreadsheet import TransactionsSpreadsheet


def process_spending_data(
    transactions_spreadsheet: TransactionsSpreadsheet,
    filters: SpendingFilters,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return filtered expense rows and spending totals by category."""
    transactions = apply_transaction_filters(
        transactions_spreadsheet.scrubbed_df.copy(),
        filters,
    )
    period = transactions[
        (transactions["Date"] >= start_date)
        & (transactions["Date"] <= end_date)
        & (transactions["Type"] == "Expense")
    ].copy()
    by_category = period.groupby("Category")["Amount"].sum().abs().reset_index()
    by_category = by_category.sort_values("Amount", ascending=False)
    total_spending = by_category["Amount"].sum()
    by_category["Percentage"] = (
        (by_category["Amount"] / total_spending * 100).round(1)
        if total_spending > 0
        else 0
    )
    return period, by_category


def calculate_spending_summary(by_category: pd.DataFrame) -> SpendingSummary:
    """Return headline spending metrics from a category breakdown."""
    if by_category.empty:
        return SpendingSummary(
            total_spending=0.0,
            top_category="",
            top_category_amount=0.0,
            num_categories=0,
        )
    return SpendingSummary(
        total_spending=float(by_category["Amount"].sum()),
        top_category=str(by_category.iloc[0]["Category"]),
        top_category_amount=float(by_category.iloc[0]["Amount"]),
        num_categories=len(by_category),
    )


def prepare_spending_trend(
    period: pd.DataFrame,
    categories: list[str],
) -> pd.DataFrame:
    """Return monthly absolute spending for the selected categories."""
    monthly = period[period["Category"].isin(categories)].copy()
    monthly["Amount"] = monthly["Amount"].abs()
    return monthly.groupby(["Month", "Category"])["Amount"].sum().reset_index()


def prepare_amount_histogram(period: pd.DataFrame) -> pd.DataFrame:
    """Return transaction counts in the page's display amount buckets."""
    bins = [0, 10, 25, 50, 100, 250, 500, 1000, 5000, float("inf")]
    labels = [
        "$0-10",
        "$10-25",
        "$25-50",
        "$50-100",
        "$100-250",
        "$250-500",
        "$500-1K",
        "$1K-5K",
        "$5K+",
    ]
    amounts = period["Amount"].abs()
    ranges = pd.cut(amounts, bins=bins, labels=labels, include_lowest=True)
    return (
        pd.DataFrame({"Amount_Range": ranges})
        .groupby("Amount_Range", observed=True)
        .size()
        .reset_index(name="Count")
    )


def prepare_category_boxplot(period: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Return absolute transaction amounts for the largest categories."""
    categories = (
        period.groupby("Category")["Amount"].sum().abs().nlargest(limit).index
    )
    boxplot = period[period["Category"].isin(categories)].copy()
    boxplot["Amount_Abs"] = boxplot["Amount"].abs()
    return boxplot


def calculate_distribution_stats(period: pd.DataFrame) -> DistributionStats:
    """Return percentiles, bucket shares, and Pareto concentration metrics."""
    amounts = period["Amount"].abs()
    count = len(amounts)
    total_spending = float(amounts.sum())
    small = amounts < 25
    medium = (amounts >= 25) & (amounts < 250)
    large = amounts >= 250
    small_count = int(small.sum())
    medium_count = int(medium.sum())
    large_count = int(large.sum())

    sorted_amounts = amounts.sort_values(ascending=False)
    threshold = total_spending * 0.8
    transactions_for_80 = (
        int(sorted_amounts.cumsum().searchsorted(threshold, side="left")) + 1
        if total_spending > 0
        else 0
    )

    def spending_share(mask: pd.Series) -> float:
        return float(amounts[mask].sum() / total_spending * 100) if total_spending else 0.0

    def count_share(bucket_count: int) -> float:
        return bucket_count / count * 100 if count else 0.0

    return DistributionStats(
        median=float(amounts.quantile(0.50)) if count else 0.0,
        mean=float(amounts.mean()) if count else 0.0,
        p25=float(amounts.quantile(0.25)) if count else 0.0,
        p75=float(amounts.quantile(0.75)) if count else 0.0,
        p80=float(amounts.quantile(0.80)) if count else 0.0,
        p90=float(amounts.quantile(0.90)) if count else 0.0,
        small_count=small_count,
        medium_count=medium_count,
        large_count=large_count,
        small_pct=spending_share(small),
        medium_pct=spending_share(medium),
        large_pct=spending_share(large),
        small_count_pct=count_share(small_count),
        medium_count_pct=count_share(medium_count),
        large_count_pct=count_share(large_count),
        pareto_pct=count_share(transactions_for_80),
    )
