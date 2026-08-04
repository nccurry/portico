"""Recurring-charge detection for the Subscription Tracker page."""

from typing import Final

import pandas as pd

from src.analysis.merchants import _mode_or_first, normalize_merchant_name
from src.custom_types import SubscriptionSummary
from src.constants import (
    SUBSCRIPTION_EXCLUDED_CATEGORIES,
    SUBSCRIPTION_EXCLUDED_CATEGORY_PATTERN,
)

CADENCE_DAYS: Final[dict[str, int]] = {
    "Monthly": 30,
    "Quarterly": 91,
    "Annual": 365,
}
CADENCE_WINDOWS: Final[dict[str, tuple[int, int]]] = {
    "Monthly": (20, 40),
    "Quarterly": (75, 105),
    "Annual": (330, 400),
}
SUBSCRIPTION_COLUMNS: Final[list[str]] = [
    "Merchant",
    "Amount_Rounded",
    "Count",
    "First_Date",
    "Last_Date",
    "Unique_Months",
    "Avg_Amount",
    "Category",
    "Account",
    "Days_Between",
    "Cadence",
    "Confidence",
    "Amount_Variability",
    "Monthly_Cost",
    "Annual_Cost",
    "Next_Expected_Date",
    "Status",
]


def detect_recurring_transactions(
    df: pd.DataFrame,
    min_occurrences: int = 3,
    min_months: int = 3,
    *,
    allowed_cadences: list[str] | None = None,
    amount_tolerance_pct: float = 0.10,
    amount_tolerance_abs: float = 0.50,
) -> pd.DataFrame:
    """Detect potential subscriptions using merchant, amount, and cadence patterns."""
    if df.empty:
        return pd.DataFrame(columns=SUBSCRIPTION_COLUMNS)

    allowed = set(["Monthly"] if allowed_cadences is None else allowed_cadences)
    df_expenses = df[
        (df["Type"] == "Expense") &
        (~df["Category"].isin(SUBSCRIPTION_EXCLUDED_CATEGORIES)) &
        (~df["Category"].str.contains(SUBSCRIPTION_EXCLUDED_CATEGORY_PATTERN, case=False, na=False, regex=True))
    ].copy()

    if df_expenses.empty:
        return pd.DataFrame(columns=SUBSCRIPTION_COLUMNS)

    df_expenses["Merchant"] = df_expenses["Full Description"].apply(
        lambda x: normalize_merchant_name(x, method="first_three")
    )
    df_expenses["Amount_Abs"] = df_expenses["Amount"].abs()
    df_expenses["Amount_Cluster"] = _assign_amount_clusters(
        df_expenses,
        amount_tolerance_pct=amount_tolerance_pct,
        amount_tolerance_abs=amount_tolerance_abs,
    )

    grouped = df_expenses.groupby(["Merchant", "Amount_Cluster"]).agg(
        Count=("Date", "count"),
        First_Date=("Date", "min"),
        Last_Date=("Date", "max"),
        Unique_Months=("Month", "nunique"),
        Avg_Amount=("Amount", "mean"),
        Median_Amount=("Amount_Abs", "median"),
        Min_Amount=("Amount_Abs", "min"),
        Max_Amount=("Amount_Abs", "max"),
        Category=("Category", _mode_or_first),
        Account=("Account", _mode_or_first),
    ).reset_index()

    count_minus_1 = (grouped["Count"] - 1).replace(0, 1)
    grouped["Days_Between"] = (grouped["Last_Date"] - grouped["First_Date"]).dt.days / count_minus_1
    grouped.loc[grouped["Count"] == 1, "Days_Between"] = 0
    grouped["Cadence"] = grouped["Days_Between"].apply(_classify_cadence)

    grouped = grouped[
        (grouped["Count"] >= min_occurrences) &
        (grouped["Unique_Months"] >= min_months) &
        (grouped["Cadence"].isin(allowed))
    ].copy()

    if grouped.empty:
        return pd.DataFrame(columns=SUBSCRIPTION_COLUMNS)

    grouped["Amount_Rounded"] = grouped["Median_Amount"].round(2)
    grouped["Amount_Variability"] = _amount_variability(grouped)
    grouped["Monthly_Cost"] = grouped.apply(_monthly_cost, axis=1)
    grouped["Annual_Cost"] = grouped["Monthly_Cost"] * 12
    grouped["Confidence"] = grouped.apply(_confidence_score, axis=1).round(0).astype(int)
    grouped["Next_Expected_Date"] = grouped.apply(_next_expected_date, axis=1)

    latest_data_date = pd.to_datetime(df_expenses["Date"], utc=True).max()
    grouped["Status"] = grouped.apply(lambda row: _subscription_status(row, latest_data_date), axis=1)

    grouped = grouped.sort_values(["Monthly_Cost", "Confidence"], ascending=[False, False])
    return grouped[SUBSCRIPTION_COLUMNS].reset_index(drop=True)


def summarize_subscriptions(subscriptions: pd.DataFrame) -> SubscriptionSummary:
    """Return aggregate monthly and annual subscription costs."""
    count = len(subscriptions)
    monthly_cost = (
        float(subscriptions["Monthly_Cost"].sum()) if count else 0.0
    )
    annual_cost = monthly_cost * 12
    return SubscriptionSummary(
        count=count,
        monthly_cost=monthly_cost,
        annual_cost=annual_cost,
        average_monthly_cost=monthly_cost / count if count else 0.0,
    )


def prepare_subscription_timeline(
    transactions: pd.DataFrame,
    subscriptions: pd.DataFrame,
) -> pd.DataFrame:
    """Return first/last matching charges and monthly cost per subscription."""
    timeline: list[dict[str, object]] = []
    for _, subscription in subscriptions.iterrows():
        merchant = str(subscription["Merchant"])
        matches = transactions[
            _subscription_match_mask(
                transactions,
                merchant,
                float(subscription["Amount_Rounded"]),
            )
        ]
        if matches.empty:
            continue
        timeline.append(
            {
                "Merchant": merchant[:30],
                "First_Date": matches["Date"].min(),
                "Last_Date": matches["Date"].max(),
                "Amount": float(subscription["Monthly_Cost"]),
            }
        )
    return pd.DataFrame(
        timeline,
        columns=["Merchant", "First_Date", "Last_Date", "Amount"],
    )


def _subscription_match_mask(
    df: pd.DataFrame,
    merchant: str,
    amount_rounded: float,
    *,
    amount_tolerance_pct: float = 0.10,
    amount_tolerance_abs: float = 0.50,
) -> pd.Series:
    """Return rows matching the same normalized merchant and amount band."""
    merchant_keys = df["Full Description"].apply(lambda x: normalize_merchant_name(x, method="first_three"))
    target = normalize_merchant_name(merchant, method="first_three")
    amounts = df["Amount"].abs()
    tolerance = max(amount_tolerance_abs, abs(amount_rounded) * amount_tolerance_pct)
    matches = (merchant_keys == target) & ((amounts - amount_rounded).abs() <= tolerance)
    if "Type" in df.columns:
        matches &= df["Type"] == "Expense"
    return matches


def _assign_amount_clusters(
    df: pd.DataFrame,
    *,
    amount_tolerance_pct: float,
    amount_tolerance_abs: float,
) -> pd.Series:
    """Cluster similar amounts per merchant."""
    cluster_ids = pd.Series(index=df.index, dtype="object")

    for merchant, merchant_df in df.sort_values("Amount_Abs").groupby("Merchant"):
        clusters: list[list[float]] = []
        for idx, amount in merchant_df["Amount_Abs"].items():
            assigned = False
            for cluster_idx, values in enumerate(clusters):
                median = float(pd.Series(values).median())
                tolerance = max(amount_tolerance_abs, median * amount_tolerance_pct)
                if abs(float(amount) - median) <= tolerance:
                    values.append(float(amount))
                    cluster_ids.at[idx] = f"{merchant}:{cluster_idx}"
                    assigned = True
                    break
            if not assigned:
                clusters.append([float(amount)])
                cluster_ids.at[idx] = f"{merchant}:{len(clusters) - 1}"

    return cluster_ids


def _classify_cadence(days_between: float) -> str:
    """Classify average days between charges into a supported cadence."""
    for cadence, (min_days, max_days) in CADENCE_WINDOWS.items():
        if min_days <= days_between <= max_days:
            return cadence
    return "Irregular"


def _amount_variability(grouped: pd.DataFrame) -> pd.Series:
    """Return max/min spread as a percentage of median amount."""
    median = grouped["Median_Amount"].replace(0, pd.NA)
    return ((grouped["Max_Amount"] - grouped["Min_Amount"]) / median * 100).fillna(0)


def _monthly_cost(row: pd.Series) -> float:
    """Estimate monthly subscription cost from cadence and median amount."""
    amount = float(row["Median_Amount"])
    cadence = str(row["Cadence"])
    if cadence == "Quarterly":
        return amount / 3
    if cadence == "Annual":
        return amount / 12
    return amount


def _confidence_score(row: pd.Series) -> float:
    """Score recurrence confidence from occurrence count, cadence, and amount stability."""
    occurrence_score = min(float(row["Count"]) / 6, 1.0) * 30
    month_score = min(float(row["Unique_Months"]) / 6, 1.0) * 25

    cadence = str(row["Cadence"])
    expected_days = CADENCE_DAYS.get(cadence, 30)
    cadence_delta = abs(float(row["Days_Between"]) - expected_days)
    cadence_score = max(0.0, 1.0 - cadence_delta / expected_days) * 25

    variability = float(row["Amount_Variability"])
    amount_score = max(0.0, 1.0 - variability / 20) * 20
    return occurrence_score + month_score + cadence_score + amount_score


def _next_expected_date(row: pd.Series) -> pd.Timestamp:
    """Estimate the next charge date from the last charge and cadence."""
    cadence = str(row["Cadence"])
    days = CADENCE_DAYS.get(cadence, 30)
    return pd.Timestamp(row["Last_Date"]) + pd.Timedelta(days=days)


def _subscription_status(row: pd.Series, latest_data_date: pd.Timestamp) -> str:
    """Classify whether a recurring charge still appears active in the data."""
    cadence = str(row["Cadence"])
    days = CADENCE_DAYS.get(cadence, 30)
    overdue_cutoff = pd.Timestamp(row["Last_Date"]) + pd.Timedelta(days=days * 1.5)
    return "Active" if overdue_cutoff >= latest_data_date else "Possibly Ended"
