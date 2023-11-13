from typing import Tuple
import pandas as pd


def summarize_balance_by_group(data_frame: pd.DataFrame, group: str) -> Tuple[pd.DataFrame, float]:
    """Summarize balance information by balance_history group"""
    df = data_frame.copy()
    df = df.sort_values(by='Date')
    df = df.drop_duplicates('Account ID', keep='last')
    df = df[df["Group"] == group]
    df = df.filter(["Account", "Balance"])
    total = float(df["Balance"].sum())

    return df, total
