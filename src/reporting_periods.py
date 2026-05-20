"""Shared reporting-period helpers."""

from datetime import timedelta

import pandas as pd


def latest_data_timestamp(df: pd.DataFrame | None, column: str = "Date") -> pd.Timestamp | None:
    """Return the latest non-null timestamp in ``df[column]``."""
    if df is None or column not in df.columns or df.empty:
        return None

    values = pd.to_datetime(df[column], errors="coerce", utc=True).dropna()
    if values.empty:
        return None
    latest = values.max()
    return pd.Timestamp(latest)


def earliest_data_timestamp(df: pd.DataFrame | None, column: str = "Date") -> pd.Timestamp | None:
    """Return the earliest non-null timestamp in ``df[column]``."""
    if df is None or column not in df.columns or df.empty:
        return None

    values = pd.to_datetime(df[column], errors="coerce", utc=True).dropna()
    if values.empty:
        return None
    earliest = values.min()
    return pd.Timestamp(earliest)


def reporting_anchor(
    df: pd.DataFrame | None = None,
    *,
    column: str = "Date",
    anchor_to_data: bool = False,
) -> pd.Timestamp:
    """Return the timestamp that relative reports should anchor to."""
    if anchor_to_data:
        latest = latest_data_timestamp(df, column=column)
        if latest is not None:
            return latest
    return pd.Timestamp.now(tz="UTC")


def calculate_date_range(
    period: str,
    df: pd.DataFrame | None = None,
    *,
    anchor_to_data: bool = False,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calculate start/end dates for a named reporting period."""
    end = reporting_anchor(df, anchor_to_data=anchor_to_data)

    if period == "This Month":
        return end.replace(day=1), end
    if period == "Last Month":
        start_of_this_month = end.replace(day=1)
        last_month_end = start_of_this_month - timedelta(days=1)
        return last_month_end.replace(day=1), last_month_end
    if period == "Last 3 Months":
        return end - pd.DateOffset(months=3), end
    if period == "Last 6 Months":
        return end - pd.DateOffset(months=6), end
    if period == "Last 12 Months":
        return end - pd.DateOffset(months=12), end
    if period == "Year to Date":
        return end.replace(month=1, day=1), end
    if period == "All Time":
        earliest = earliest_data_timestamp(df) if df is not None else None
        if earliest is not None:
            return earliest, end
        return end - pd.DateOffset(years=5), end

    return end - pd.DateOffset(months=3), end


def completed_month_window(
    lookback_months: int,
    df: pd.DataFrame | None = None,
    *,
    anchor_to_data: bool = False,
) -> tuple[str, str]:
    """Return inclusive YYYY-MM bounds ending at the previous complete month."""
    anchor = reporting_anchor(df, anchor_to_data=anchor_to_data)
    end = anchor - pd.DateOffset(months=1)
    start = anchor - pd.DateOffset(months=lookback_months)
    return start.strftime("%Y-%m"), end.strftime("%Y-%m")


def current_month_string(
    df: pd.DataFrame | None = None,
    *,
    anchor_to_data: bool = False,
) -> str:
    """Return the reporting anchor's month as ``YYYY-MM``."""
    return reporting_anchor(df, anchor_to_data=anchor_to_data).strftime("%Y-%m")
