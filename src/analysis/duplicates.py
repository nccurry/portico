"""Pure duplicate-transaction detection and summaries."""

import pandas as pd

from src.custom_types import DuplicateSummary


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
    candidates = df[df["Amount"].abs() >= min_amount].copy()
    if candidates.empty:
        return pd.DataFrame()

    candidates = candidates.sort_values(["Amount", "Date"]).reset_index(drop=True)
    candidates["_row_id"] = range(len(candidates))
    candidates["_norm_desc"] = candidates["Full Description"].apply(
        normalize_description
    )
    duplicates = candidates.merge(candidates, on="Amount", suffixes=("_1", "_2"))
    duplicates = duplicates[duplicates["_row_id_1"] < duplicates["_row_id_2"]]
    duplicates["Days_Apart"] = (
        duplicates["Date_2"] - duplicates["Date_1"]
    ).dt.days.abs()
    duplicates = duplicates[duplicates["Days_Apart"] <= days_threshold]

    if check_same_account:
        duplicates = duplicates[duplicates["Account_1"] == duplicates["Account_2"]]
    if check_same_category:
        duplicates = duplicates[duplicates["Category_1"] == duplicates["Category_2"]]
    if require_same_description:
        duplicates = duplicates[
            duplicates["_norm_desc_1"] == duplicates["_norm_desc_2"]
        ]

    return pd.DataFrame(
        {
            "Date1": duplicates["Date_1"],
            "Date2": duplicates["Date_2"],
            "Days_Apart": duplicates["Days_Apart"],
            "Amount": duplicates["Amount"],
            "Category": duplicates["Category_1"],
            "Account1": duplicates["Account_1"],
            "Account2": duplicates["Account_2"],
            "Description1": duplicates["Full Description_1"],
            "Description2": duplicates["Full Description_2"],
            "Month": duplicates["Month_1"],
        }
    )


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
