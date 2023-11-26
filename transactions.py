import datetime
import pandas as pd
import math
from typing import List, Optional
import numpy as np


def get_total_months(
    data_frame: pd.DataFrame
) -> int:
    """Given Tiller data, return the total amount of months in the data set"""
    oldest_date = data_frame["Date"].min()
    latest_date = data_frame["Date"].max()
    total_months = math.ceil((latest_date - oldest_date)/np.timedelta64(1, 'M'))

    return total_months


def get_group_categories(
    data_frame: pd.DataFrame,
    group: str
) -> List[str]:
    """Return all categories from a given group"""
    df = data_frame.copy()
    df = df[df["Group"] == group]

    return df["Category"].unique()


def get_category_stats_by_group(
        data_frame: pd.DataFrame,
        group: str
) -> pd.DataFrame:
    """Return a data frame summarizing the transaction amounts per group"""
    df = data_frame.copy()
    df = df[df["Group"] == group]
    df = df.groupby('Category').describe().unstack(1).reset_index().pivot(index='Category', values=0, columns='level_1')

    return df


def get_amounts_by_group(
        data_frame: pd.DataFrame,
        type: str = "Expense",
        start_date: Optional[datetime.datetime] = None,
        end_date: Optional[datetime.datetime] = None,
        ignore_groups: List[str] = []
) -> pd.DataFrame:
    """Get the total spending per group over a specified period"""
    df = data_frame.copy()
    df = df.filter(["Date", "Group", "Amount", "Type"])

    df = df.sort_values("Date")

    df = df[df["Type"] == type]

    if start_date is None:
        start_date = data_frame["Date"].min()
    if end_date is None:
        end_date = data_frame["Date"].max()

    df = df[df["Date"].between(start_date, end_date)]

    if ignore_groups:
        df = df[-df["Group"].isin(ignore_groups)]

    df = df.groupby("Group").sum()

    return df


def get_amounts_by_group_category(
        data_frame: pd.DataFrame,
        group: str,
        start_date: Optional[datetime.datetime] = None,
        end_date: Optional[datetime.datetime] = None,
        ignore_categories: List[str] = []
) -> pd.DataFrame:
    """Get the total spending per group categories over a specified period"""
    df = data_frame.copy()
    df = df.filter(["Date", "Group", "Category", "Amount", "Type"])

    df = df.sort_values("Date")

    df = df[df["Group"] == group]

    if start_date is None:
        start_date = data_frame["Date"].min()
    if end_date is None:
        end_date = data_frame["Date"].max()

    df = df[df["Date"].between(start_date, end_date)]

    if ignore_categories:
        df = df[-df["Category"].isin(ignore_categories)]

    df = df.groupby("Category").sum()

    return df
