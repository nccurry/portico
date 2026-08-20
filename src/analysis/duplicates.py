"""Pure duplicate-transaction detection and summaries."""

import pandas as pd

from src.custom_types import DuplicateSummary

_DUPLICATE_COLUMNS = (
    "Date1",
    "Date2",
    "Days_Apart",
    "Amount",
    "Category",
    "Account1",
    "Account2",
    "Description1",
    "Description2",
    "Month",
)


def normalize_description(description: object) -> str:
    """Normalize a transaction description for comparison."""
    return description.strip().lower() if isinstance(description, str) else ""


def find_duplicates_efficient(
    df: pd.DataFrame,
    days_threshold: int,
    min_amount: float,
    check_same_account: bool,
    check_same_category: bool,
    require_same_description: bool,
) -> pd.DataFrame:
    """Return unique pairs of transactions that satisfy duplicate rules."""
    candidates = df[
        (df["Amount"].abs() >= min_amount) & df["Date"].notna()
    ].copy()
    if candidates.empty:
        return pd.DataFrame(columns=_DUPLICATE_COLUMNS)

    candidates = candidates.sort_values(["Amount", "Date"]).reset_index(drop=True)
    candidates["_norm_desc"] = candidates["Full Description"].apply(
        normalize_description
    )
    pairs: list[dict[str, object]] = []
    for amount, amount_group in candidates.groupby("Amount", sort=False):
        records = amount_group.to_dict("records")
        for left_position, left in enumerate(records):
            for right in records[left_position + 1 :]:
                days_apart = (right["Date"] - left["Date"]).days
                if days_apart > days_threshold:
                    break
                if check_same_account and left["Account"] != right["Account"]:
                    continue
                if check_same_category and left["Category"] != right["Category"]:
                    continue
                if (
                    require_same_description
                    and left["_norm_desc"] != right["_norm_desc"]
                ):
                    continue
                pairs.append(
                    {
                        "Date1": left["Date"],
                        "Date2": right["Date"],
                        "Days_Apart": days_apart,
                        "Amount": amount,
                        "Category": left["Category"],
                        "Account1": left["Account"],
                        "Account2": right["Account"],
                        "Description1": left["Full Description"],
                        "Description2": right["Full Description"],
                        "Month": left["Month"],
                    }
                )
    return pd.DataFrame(pairs, columns=_DUPLICATE_COLUMNS)


def summarize_duplicates(duplicates: pd.DataFrame) -> DuplicateSummary:
    """Return headline values for a set of potential duplicate pairs."""
    return DuplicateSummary(
        pair_count=len(duplicates),
        total_amount=float(duplicates["Amount"].abs().sum())
        if not duplicates.empty
        else 0.0,
        affected_months=int(duplicates["Month"].nunique())
        if not duplicates.empty
        else 0,
    )


def summarize_duplicates_by_month(duplicates: pd.DataFrame) -> pd.DataFrame:
    """Return pair counts and absolute amounts by month, newest first."""
    if duplicates.empty:
        return pd.DataFrame(columns=["Month", "Count", "Total_Amount"])
    monthly = duplicates.groupby("Month")["Amount"].agg(
        Count="count",
        Total_Amount=lambda amounts: amounts.abs().sum(),
    ).reset_index()
    return monthly.sort_values("Month", ascending=False)
