import pandas as pd
import math
from typing import List
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
    group: str,
    data_frame: pd.DataFrame
) -> List[str]:
    """Return all categories from a given group"""
    df = data_frame.copy()
    df = df[df["Group"] == group]

    return df["Category"].unique()
