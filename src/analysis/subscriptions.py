"""Subscription inventory and recurring-charge discovery."""

from itertools import pairwise
from typing import Final, cast

import pandas as pd

from src.analysis.merchants import _mode_or_first, normalize_merchant_name
from src.constants import (
    SUBSCRIPTION_EXCLUDED_CATEGORIES,
    SUBSCRIPTION_EXCLUDED_CATEGORY_PATTERN,
)
from src.custom_types import SubscriptionSummary

CADENCE_DAYS: Final[dict[str, int]] = {
    "Monthly": 30,
    "Quarterly": 91,
    "Annual": 365,
}
CADENCE_MONTHS: Final[dict[str, int]] = {
    "Monthly": 1,
    "Quarterly": 3,
    "Annual": 12,
}
CADENCE_WINDOWS: Final[dict[str, tuple[int, int]]] = {
    "Monthly": (20, 40),
    "Quarterly": (75, 105),
    "Annual": (330, 400),
}
INVENTORY_COLUMNS: Final[list[str]] = [
    "Merchant",
    "Source",
    "Status",
    "Cadence",
    "Confidence",
    "First_Date",
    "Last_Date",
    "Next_Expected_Date",
    "Monthly_Run_Rate",
    "Trailing_12_Month_Spend",
    "Price_Change",
    "Price_Change_Date",
    "Category",
    "Account",
    "Charge_Count",
    "Bundle_Type",
]
CANDIDATE_COLUMNS: Final[list[str]] = [*INVENTORY_COLUMNS, "Evidence"]
LIFECYCLE_COLUMNS: Final[list[str]] = [
    "Merchant",
    "Episode",
    "Episode_Start",
    "Observed_End",
    "Active_Until",
    "Inactive_After",
    "Display_End",
    "Status",
    "Is_Current",
    "Cadence",
    "Category",
    "Account",
    "Charge_Count",
    "Latest_Charge_Amount",
    "Monthly_Run_Rate",
    "Next_Expected_Date",
    "Price_Change",
    "Price_Change_Date",
    "Observed_Duration_Days",
    "Lifecycle_Duration_Days",
]


def build_subscription_inventory(
    transactions: pd.DataFrame,
    subscription_categories: list[str],
) -> pd.DataFrame:
    """Build a merchant-level inventory from Tiller subscription categories."""
    if transactions.empty or not subscription_categories:
        return pd.DataFrame(columns=INVENTORY_COLUMNS)

    expenses = _prepare_expenses(transactions)
    known = expenses[expenses["Category"].isin(subscription_categories)].copy()
    if known.empty:
        return pd.DataFrame(columns=INVENTORY_COLUMNS)

    latest_data_date = _latest_date(transactions)
    rows = [
        _build_inventory_row(merchant_df, latest_data_date, source="Categorized")
        for _, merchant_df in known.groupby("Merchant", sort=False)
    ]
    inventory = pd.DataFrame(rows, columns=INVENTORY_COLUMNS)
    return inventory.sort_values(
        ["Status", "First_Date", "Merchant"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def find_subscription_candidates(
    transactions: pd.DataFrame,
    subscription_categories: list[str],
    *,
    excluded_categories: list[str] | None = None,
    min_confidence: int = 80,
) -> pd.DataFrame:
    """Find strong recurring non-bill charges outside subscription categories."""
    if transactions.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)

    expenses = _prepare_expenses(transactions)
    eligible = _eligible_candidate_expenses(
        expenses,
        [*subscription_categories, *(excluded_categories or [])],
    )
    if eligible.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)

    latest_data_date = _latest_date(transactions)
    candidates: list[dict[str, object]] = []
    for _, merchant_df in eligible.groupby("Merchant", sort=False):
        charge_count = len(merchant_df)
        unique_months = int(merchant_df["Month_Key"].nunique())
        if charge_count < 3 or unique_months < 3:
            continue

        # Frequent merchants are purchases, not one recurring payment stream.
        if charge_count > unique_months * 1.25:
            continue

        cadence, regularity = _infer_cadence(merchant_df["Date"])
        if cadence not in CADENCE_DAYS or regularity < 0.70:
            continue

        amounts = merchant_df["Amount_Abs"]
        median_amount = float(amounts.median())
        amount_cv = float(amounts.std(ddof=0) / median_amount) if median_amount else 1.0
        confidence = round(
            regularity * 50
            + min(charge_count / 6, 1.0) * 15
            + min(unique_months / 6, 1.0) * 15
            + max(0.0, 1.0 - amount_cv / 0.5) * 20
        )
        if confidence < min_confidence:
            continue

        row = _build_inventory_row(merchant_df, latest_data_date, source="Detected")
        if row["Status"] == "Inactive":
            continue
        row["Cadence"] = cadence
        row["Confidence"] = confidence
        row["Bundle_Type"] = "Single stream"
        row["Evidence"] = (
            f"{charge_count} charges across {unique_months} months; "
            f"{regularity:.0%} of intervals match a {cadence.lower()} cadence"
        )
        candidates.append(row)

    result = pd.DataFrame(candidates, columns=CANDIDATE_COLUMNS)
    if result.empty:
        return result
    return result.sort_values(
        ["Status", "Last_Date", "Confidence"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def build_subscription_history(
    transactions: pd.DataFrame,
    inventory: pd.DataFrame,
    subscription_categories: list[str],
    *,
    lifecycles: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return monthly actual spend, rolling average, and active merchant count."""
    columns = ["Month", "Actual_Spend", "Rolling_Average", "Active_Merchants"]
    if transactions.empty or not subscription_categories:
        return pd.DataFrame(columns=columns)

    known = _prepare_expenses(transactions)
    known = known[known["Category"].isin(subscription_categories)].copy()
    if known.empty:
        return pd.DataFrame(columns=columns)

    start_month = _month_start(known["Date"].min())
    latest_data_date = _latest_date(transactions)
    end_month = _month_start(latest_data_date)
    months = pd.date_range(start_month, end_month, freq="MS", tz="UTC")
    history = pd.DataFrame({"Month": months})

    actual = known.assign(Month_Date=known["Date"].map(_month_start)).groupby("Month_Date")["Amount_Abs"].sum()
    history["Actual_Spend"] = history["Month"].map(actual).fillna(0.0)
    history["Rolling_Average"] = history["Actual_Spend"].rolling(3, min_periods=1).mean()

    if lifecycles is None:
        lifecycles = build_subscription_lifecycles(
            transactions,
            inventory,
            subscription_categories,
        )
    active_by_month: dict[pd.Timestamp, set[str]] = {month: set() for month in months}
    for lifecycle in lifecycles.itertuples(index=False):
        active_until = cast(pd.Timestamp, lifecycle.Active_Until)
        episode_start = cast(pd.Timestamp, lifecycle.Episode_Start)
        coverage_end = min(active_until, latest_data_date)
        if coverage_end < episode_start:
            continue
        covered_months = pd.date_range(
            _month_start(episode_start),
            _month_start(coverage_end),
            freq="MS",
            tz="UTC",
        )
        for month in covered_months:
            if month in active_by_month:
                active_by_month[month].add(str(lifecycle.Merchant))
    history["Active_Merchants"] = (
        history["Month"]
        .map({month: len(merchants) for month, merchants in active_by_month.items()})
        .fillna(0)
        .astype(int)
    )
    return history[columns]


def build_subscription_lifecycles(
    transactions: pd.DataFrame,
    inventory: pd.DataFrame,
    subscription_categories: list[str],
) -> pd.DataFrame:
    """Build observed and inferred lifecycle episodes for known subscriptions."""
    if transactions.empty or not subscription_categories:
        return pd.DataFrame(columns=LIFECYCLE_COLUMNS)

    known = _prepare_expenses(transactions)
    known = known[known["Category"].isin(subscription_categories)].copy()
    if known.empty:
        return pd.DataFrame(columns=LIFECYCLE_COLUMNS)

    latest_data_date = _latest_date(transactions)
    inventory_by_merchant = (
        inventory.drop_duplicates("Merchant", keep="first").set_index("Merchant")
        if not inventory.empty
        else pd.DataFrame()
    )
    rows: list[dict[str, object]] = []
    for merchant, merchant_df in known.groupby("Merchant", sort=False):
        inventory_row = (
            inventory_by_merchant.loc[merchant]
            if not inventory_by_merchant.empty and merchant in inventory_by_merchant.index
            else pd.Series(
                _build_inventory_row(
                    merchant_df,
                    latest_data_date,
                    source="Categorized",
                )
            )
        )
        cadence = str(inventory_row["Cadence"])
        episodes = _split_merchant_episodes(merchant_df, cadence)
        for episode_number, episode_df in enumerate(episodes, start=1):
            is_current = episode_number == len(episodes)
            episode_start = pd.Timestamp(episode_df["Date"].min())
            observed_end = pd.Timestamp(episode_df["Date"].max())
            next_expected, active_until, inactive_after = _subscription_boundaries(
                observed_end,
                cadence,
            )
            display_end = min(inactive_after, latest_data_date)
            status = str(inventory_row["Status"]) if is_current else "Inactive"
            price_change, price_change_date = _latest_price_change(episode_df, cadence)
            monthly_run_rate = (
                inventory_row["Monthly_Run_Rate"]
                if is_current
                else _monthly_run_rate(episode_df, cadence, observed_end)
            )
            rows.append(
                {
                    "Merchant": str(merchant),
                    "Episode": episode_number,
                    "Episode_Start": episode_start,
                    "Observed_End": observed_end,
                    "Active_Until": active_until,
                    "Inactive_After": inactive_after,
                    "Display_End": display_end,
                    "Status": status,
                    "Is_Current": is_current,
                    "Cadence": cadence,
                    "Category": str(_mode_or_first(episode_df["Category"])),
                    "Account": str(_mode_or_first(episode_df["Account"])),
                    "Charge_Count": len(episode_df),
                    "Latest_Charge_Amount": float(episode_df.iloc[-1]["Amount_Abs"]),
                    "Monthly_Run_Rate": monthly_run_rate,
                    "Next_Expected_Date": next_expected,
                    "Price_Change": price_change,
                    "Price_Change_Date": price_change_date,
                    "Observed_Duration_Days": (observed_end - episode_start).days,
                    "Lifecycle_Duration_Days": (display_end - episode_start).days,
                }
            )

    lifecycles = pd.DataFrame(rows, columns=LIFECYCLE_COLUMNS)
    if lifecycles.empty:
        return lifecycles

    status_rank = lifecycles["Status"].map({"Active": 0, "Inactive": 1})
    sort_date = lifecycles["Episode_Start"].where(
        lifecycles["Status"] != "Inactive",
        lifecycles["Display_End"],
    )
    return (
        lifecycles.assign(_Status_Rank=status_rank, _Sort_Date=sort_date)
        .sort_values(
            [
                "_Status_Rank",
                "_Sort_Date",
                "Lifecycle_Duration_Days",
                "Merchant",
                "Episode",
            ],
            ascending=[True, False, True, True, False],
        )
        .drop(columns=["_Status_Rank", "_Sort_Date"])
        .reset_index(drop=True)
    )


def summarize_subscriptions(
    inventory: pd.DataFrame,
    transactions: pd.DataFrame,
    subscription_categories: list[str],
) -> SubscriptionSummary:
    """Return active inventory and actual trailing-year subscription metrics."""
    latest_data_date = _latest_date(transactions) if not transactions.empty else pd.Timestamp.now(tz="UTC")
    known = _prepare_expenses(transactions) if not transactions.empty else pd.DataFrame()
    if not known.empty:
        known = known[known["Category"].isin(subscription_categories)]
        trailing_start = latest_data_date - pd.DateOffset(years=1)
        prior_start = latest_data_date - pd.DateOffset(years=2)
        trailing_spend = float(known.loc[known["Date"] > trailing_start, "Amount_Abs"].sum())
        prior_spend = float(
            known.loc[
                (known["Date"] > prior_start) & (known["Date"] <= trailing_start),
                "Amount_Abs",
            ].sum()
        )
    else:
        trailing_spend = 0.0
        prior_spend = 0.0

    active = inventory[inventory["Status"] == "Active"] if not inventory.empty else inventory
    run_rates = active["Monthly_Run_Rate"].dropna() if not active.empty else pd.Series(dtype=float)
    annual_change = (trailing_spend - prior_spend) / prior_spend * 100 if prior_spend else None
    return SubscriptionSummary(
        active_count=len(active),
        monthly_run_rate=float(run_rates.sum()),
        trailing_12_month_spend=trailing_spend,
        prior_12_month_spend=prior_spend,
        annual_change_pct=annual_change,
        pending_estimate_count=int(active["Monthly_Run_Rate"].isna().sum()) if not active.empty else 0,
    )


def get_subscription_transactions(
    transactions: pd.DataFrame,
    merchant: str,
    *,
    categories: list[str] | None = None,
    excluded_categories: list[str] | None = None,
) -> pd.DataFrame:
    """Return transactions matching one normalized merchant."""
    expenses = _prepare_expenses(transactions)
    if categories is not None:
        expenses = expenses[expenses["Category"].isin(categories)]
    elif excluded_categories is not None:
        expenses = _eligible_candidate_expenses(expenses, excluded_categories)
    target = normalize_merchant_name(merchant, method="first_three")
    return expenses[expenses["Merchant"] == target].sort_values("Date", ascending=False)


def _prepare_expenses(transactions: pd.DataFrame) -> pd.DataFrame:
    """Normalize expense transactions for subscription analysis."""
    expenses = transactions[transactions["Type"] == "Expense"].copy()
    expenses["Date"] = pd.to_datetime(expenses["Date"], utc=True)
    expenses["Amount_Abs"] = expenses["Amount"].abs()
    expenses["Merchant"] = expenses["Full Description"].map(
        lambda value: normalize_merchant_name(value, method="first_three")
    )
    expenses["Month_Key"] = expenses["Date"].dt.strftime("%Y-%m")
    return expenses


def _eligible_candidate_expenses(
    expenses: pd.DataFrame,
    excluded_categories: list[str],
) -> pd.DataFrame:
    """Keep non-bill expenses that are eligible for subscription discovery."""
    category_text = expenses["Category"].fillna("").astype(str)
    return expenses[
        (~expenses["Category"].isin(excluded_categories))
        & (~expenses["Category"].isin(SUBSCRIPTION_EXCLUDED_CATEGORIES))
        & (
            ~category_text.str.contains(
                SUBSCRIPTION_EXCLUDED_CATEGORY_PATTERN,
                case=False,
                na=False,
                regex=True,
            )
        )
        & (~category_text.str.upper().str.endswith("BILL"))
        & (~expenses["Group"].fillna("").str.contains("Bill|Transfer", case=False, regex=True))
    ].copy()


def _latest_date(transactions: pd.DataFrame) -> pd.Timestamp:
    """Return the latest UTC transaction date."""
    return pd.Timestamp(pd.to_datetime(transactions["Date"], utc=True).max())


def _build_inventory_row(
    merchant_df: pd.DataFrame,
    latest_data_date: pd.Timestamp,
    *,
    source: str,
) -> dict[str, object]:
    """Summarize one normalized merchant into an inventory row."""
    merchant_df = merchant_df.sort_values("Date")
    dates = merchant_df["Date"]
    charge_count = len(merchant_df)
    unique_months = int(merchant_df["Month_Key"].nunique())
    has_multiple_monthly_charges = charge_count > unique_months * 1.25

    cadence, regularity = _infer_cadence(dates)
    if has_multiple_monthly_charges or cadence == "Multiple":
        cadence = "Multiple"
        bundle_type = "Merchant bundle"
    elif cadence == "Pending":
        bundle_type = "Pending"
    else:
        bundle_type = "Single stream"

    first_date = pd.Timestamp(dates.min())
    last_date = pd.Timestamp(dates.max())
    next_expected, _, _ = _subscription_boundaries(last_date, cadence)
    status = _subscription_status(last_date, cadence, latest_data_date)
    monthly_run_rate = _monthly_run_rate(merchant_df, cadence, latest_data_date)
    trailing_start = latest_data_date - pd.DateOffset(years=1)
    trailing_spend = float(merchant_df.loc[merchant_df["Date"] > trailing_start, "Amount_Abs"].sum())
    latest_episode = _split_merchant_episodes(merchant_df, cadence)[-1]
    price_change, price_change_date = _latest_price_change(latest_episode, cadence)

    if cadence == "Pending":
        confidence = 40 if charge_count == 1 else 60
    elif cadence == "Multiple":
        confidence = min(85, 55 + unique_months * 3)
    else:
        confidence = round(min(100.0, regularity * 70 + min(charge_count / 6, 1.0) * 30))

    return {
        "Merchant": str(merchant_df["Merchant"].iloc[0]),
        "Source": source,
        "Status": status,
        "Cadence": cadence,
        "Confidence": confidence,
        "First_Date": first_date,
        "Last_Date": last_date,
        "Next_Expected_Date": next_expected,
        "Monthly_Run_Rate": monthly_run_rate,
        "Trailing_12_Month_Spend": trailing_spend,
        "Price_Change": price_change,
        "Price_Change_Date": price_change_date,
        "Category": str(_mode_or_first(merchant_df["Category"])),
        "Account": str(_mode_or_first(merchant_df["Account"])),
        "Charge_Count": charge_count,
        "Bundle_Type": bundle_type,
    }


def _split_merchant_episodes(
    merchant_df: pd.DataFrame,
    cadence: str,
) -> list[pd.DataFrame]:
    """Split a merchant when a later charge exceeds the inactive boundary."""
    ordered = merchant_df.sort_values("Date")
    starts = [0]
    dates = ordered["Date"].tolist()
    for index, (previous_date, current_date) in enumerate(
        pairwise(dates),
        start=1,
    ):
        _, _, inactive_after = _subscription_boundaries(
            pd.Timestamp(previous_date),
            cadence,
        )
        if pd.Timestamp(current_date) > inactive_after:
            starts.append(index)

    boundaries = [*starts, len(ordered)]
    return [ordered.iloc[start:end].copy() for start, end in pairwise(boundaries)]


def _subscription_boundaries(
    last_date: pd.Timestamp,
    cadence: str,
) -> tuple[pd.Timestamp | None, pd.Timestamp, pd.Timestamp]:
    """Return the expected, active, and inactive boundaries for a charge."""
    if cadence not in CADENCE_DAYS:
        inactive_after = last_date + pd.Timedelta(days=90)
        return None, inactive_after, inactive_after

    cadence_days = CADENCE_DAYS[cadence]
    next_expected = last_date + pd.Timedelta(days=cadence_days)
    review_grace = min(cadence_days, 90)
    inactive_after = next_expected + pd.Timedelta(days=review_grace)
    return next_expected, inactive_after, inactive_after


def _infer_cadence(dates: pd.Series) -> tuple[str, float]:
    """Infer cadence and interval regularity from merchant-level charge dates."""
    unique_dates = pd.Series(pd.to_datetime(dates, utc=True).drop_duplicates().sort_values())
    if len(unique_dates) < 3:
        return "Pending", 0.0

    gaps = unique_dates.diff().dt.days.dropna()
    scores = {
        cadence: float(gaps.between(min_days, max_days).mean())
        for cadence, (min_days, max_days) in CADENCE_WINDOWS.items()
    }
    cadence = max(scores, key=scores.__getitem__)
    regularity = scores[cadence]
    return (cadence, regularity) if regularity >= 0.70 else ("Multiple", regularity)


def _monthly_run_rate(
    merchant_df: pd.DataFrame,
    cadence: str,
    latest_data_date: pd.Timestamp,
) -> float:
    """Estimate current monthly cost for a regular stream or merchant bundle."""
    if cadence in CADENCE_MONTHS:
        latest_amount = float(merchant_df.sort_values("Date").iloc[-1]["Amount_Abs"])
        return latest_amount / CADENCE_MONTHS[cadence]
    if cadence == "Pending":
        return float("nan")

    first_month = _month_period(merchant_df["Date"].min())
    latest_month = _month_period(latest_data_date)
    start_month = max(first_month, latest_month - 11)
    months_observed = (latest_month.year - start_month.year) * 12 + latest_month.month - start_month.month + 1
    window_start = start_month.to_timestamp().tz_localize("UTC")
    spend = float(merchant_df.loc[merchant_df["Date"] >= window_start, "Amount_Abs"].sum())
    return spend / months_observed


def _month_period(value: pd.Timestamp) -> pd.Period:
    """Return a calendar-month period without emitting timezone conversion warnings."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.to_period("M")


def _month_start(value: pd.Timestamp) -> pd.Timestamp:
    """Return the UTC timestamp at the start of a value's calendar month."""
    return _month_period(value).to_timestamp().tz_localize("UTC")


def _subscription_status(
    last_date: pd.Timestamp,
    cadence: str,
    latest_data_date: pd.Timestamp,
) -> str:
    """Classify an inferred subscription lifecycle without claiming cancellation."""
    _, _, inactive_after = _subscription_boundaries(last_date, cadence)
    return "Active" if latest_data_date <= inactive_after else "Inactive"


def _latest_price_change(
    merchant_df: pd.DataFrame,
    cadence: str,
) -> tuple[float, pd.Timestamp | None]:
    """Return the latest meaningful consecutive price change for a regular stream."""
    if cadence not in CADENCE_DAYS:
        return 0.0, None

    ordered = merchant_df.sort_values("Date")
    amounts = ordered["Amount_Abs"].tolist()
    dates = ordered["Date"].tolist()
    latest_change = 0.0
    latest_date: pd.Timestamp | None = None
    for previous, current, change_date in zip(amounts[:-1], amounts[1:], dates[1:], strict=True):
        difference = float(current) - float(previous)
        percent = abs(difference) / float(previous) if previous else 0.0
        if abs(difference) >= 0.50 and percent >= 0.05:
            latest_change = difference
            latest_date = pd.Timestamp(change_date)
    return latest_change, latest_date
