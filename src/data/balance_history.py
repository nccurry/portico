from datetime import datetime
from typing import Tuple, List
import pandas as pd


def get_latest_balance_by_group(
        scrubbed_data_frame: pd.DataFrame,
        group: str
) -> Tuple[pd.DataFrame, float]:
    """Summarize balance information by balance_history group"""
    df = scrubbed_data_frame.copy()
    df = df.sort_values(by='Date')
    df = df.drop_duplicates('Account ID', keep='last')
    df = df[df["Group"] == group]
    df = df.filter(["Account", "Balance"])
    total = float(df["Balance"].sum())

    return df, total


def get_balance_history_by_group(
        scrubbed_data_frame: pd.DataFrame,
        group: str,
) -> pd.DataFrame:
    """Get the balance history for all accounts under a single group"""
    df = scrubbed_data_frame.copy()
    df = df[df["Group"] == group]
    account_ids = df["Account ID"].unique()

    columns = ["Date", "Account", "Account ID", "Institution", "Group", "Balance"]
    agg_df = pd.DataFrame(columns=columns)
    for account_id in account_ids:
        account_df = get_balance_history_by_account_id(
            scrubbed_data_frame=scrubbed_data_frame,
            account_id=account_id,
            min_date=df["Date"].min(),
            max_date=df["Date"].max(),
            columns=columns
        )
        agg_df = pd.concat([agg_df, account_df])

    return agg_df.groupby(agg_df["Date"])["Balance"].sum()


def get_balance_history_by_account_id(
        scrubbed_data_frame: pd.DataFrame,
        account_id: str,
        min_date: datetime,
        max_date: datetime,
        columns: List[str] = ["Date", "Account", "Account ID", "Institution", "Group", "Balance"]
) -> pd.DataFrame:
    """Get the balance history for a balance_history group"""

    # Filter and sort
    df = scrubbed_data_frame.copy()
    df = df[df["Account ID"] == account_id]
    df = df.filter(columns)
    df = df.sort_values("Date")

    # Fill in missing dates
    df = df.drop_duplicates(["Date"], keep="last")
    idx = pd.date_range(min_date, max_date)
    df.index = pd.DatetimeIndex(df["Date"])
    df = df.reindex(idx)
    df["Date"] = df.index
    df = df.fillna(method="ffill")

    return df
