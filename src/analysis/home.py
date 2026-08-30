"""Pure calculations for the Home page."""

import pandas as pd


NET_WORTH_COLUMNS = ["Date", "Assets", "Liabilities", "Net_Worth"]
BALANCE_GROUP_COLUMNS = [
    "Group",
    "Type",
    "Balance",
    "Net_Contribution",
    "Period_Change",
    "Period_Change_Pct",
    "Last_Updated",
    "Account_Count",
    "Trend",
]
ACCOUNT_INVENTORY_COLUMNS = [
    "Group",
    "Account",
    "Institution",
    "Type",
    "Class",
    "Balance",
    "Net_Contribution",
    "Period_Change",
    "Last_Updated",
]


def build_net_worth_history(
    balance_history_df: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Return weekly assets, liabilities, and net worth through ``end_date``."""
    start = _as_utc(start_date).normalize()
    end = _as_utc(end_date).normalize()
    if balance_history_df.empty or start > end:
        return _empty_net_worth_history()

    balances = _prepare_balances(balance_history_df)
    balances = balances[balances["Date"] <= end]
    if balances.empty:
        return _empty_net_worth_history()
    start = max(start, balances["Date"].min().normalize())

    dates = pd.date_range(start=start, end=end, freq="W-SUN")
    dates = dates.union(pd.DatetimeIndex([start, end])).sort_values()

    assets = pd.Series(0.0, index=dates)
    liabilities = pd.Series(0.0, index=dates)
    for _, account in balances.groupby("_Account_Key", sort=False):
        account = account.sort_values(["Date", "_Sequence"]).drop_duplicates("Date", keep="last")
        observations = account.set_index("Date")[["_Contribution", "_Class"]]
        sampled = observations.reindex(observations.index.union(dates)).sort_index().ffill().reindex(dates)
        asset_values = sampled["_Contribution"].where(sampled["_Class"] == "Asset", 0.0).fillna(0.0)
        liability_values = sampled["_Contribution"].where(sampled["_Class"] == "Liability", 0.0).fillna(0.0)
        assets = assets.add(asset_values, fill_value=0.0)
        liabilities = liabilities.add(liability_values, fill_value=0.0)

    history = pd.DataFrame(
        {
            "Date": dates,
            "Assets": assets.to_numpy(),
            "Liabilities": liabilities.to_numpy(),
        }
    )
    history["Net_Worth"] = history["Assets"] + history["Liabilities"]
    return history.reset_index(drop=True)


def build_balance_group_inventory(
    balance_history_df: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Summarize current balance groups and their net-worth contribution.

    ``Balance`` is a positive magnitude for pure groups. For a mixed group, it
    is the absolute value of the group's net contribution.
    """
    start = _as_utc(start_date)
    end = _as_utc(end_date)
    if balance_history_df.empty or start > end:
        return _empty_balance_group_inventory()

    balances = _prepare_balances(balance_history_df)
    available = balances[balances["Date"] <= end]
    if available.empty:
        return _empty_balance_group_inventory()
    start = max(start, available["Date"].min())
    current = _latest_accounts_as_of(balances, end)
    current = current[current["Group"].str.strip().ne("")]
    if current.empty:
        return _empty_balance_group_inventory()

    opening = _latest_accounts_as_of(balances, start).set_index("_Account_Key")
    opening_contributions = opening["_Contribution"]
    weekly_by_group = {}
    for group, group_rows in current.groupby("Group", sort=True):
        account_keys = set(group_rows["_Account_Key"])
        weekly_by_group[str(group)] = build_net_worth_history(
            balances[balances["_Account_Key"].isin(account_keys)],
            start,
            end,
        )["Net_Worth"].tolist()

    records: list[dict[str, object]] = []
    for group, group_rows in current.groupby("Group", sort=True):
        group_name = str(group)
        classes = set(group_rows["_Class"])
        group_type = classes.pop() if len(classes) == 1 else "Mixed"
        net_contribution = float(group_rows["_Contribution"].sum())
        opening_contribution = float(group_rows["_Account_Key"].map(opening_contributions).fillna(0.0).sum())
        period_change = net_contribution - opening_contribution
        period_change_pct = (
            period_change / abs(opening_contribution) * 100 if abs(opening_contribution) > 0.01 else float("nan")
        )
        balance = float(group_rows["_Magnitude"].sum()) if group_type != "Mixed" else abs(net_contribution)
        records.append(
            {
                "Group": group_name,
                "Type": group_type,
                "Balance": balance,
                "Net_Contribution": net_contribution,
                "Period_Change": period_change,
                "Period_Change_Pct": period_change_pct,
                "Last_Updated": group_rows["Date"].max(),
                "Account_Count": int(group_rows["_Account_Key"].nunique()),
                "Trend": weekly_by_group[group_name],
            }
        )

    return pd.DataFrame.from_records(records, columns=BALANCE_GROUP_COLUMNS)


def build_account_inventory(
    balance_history_df: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Return current accounts and their contribution change over the selected period."""
    start = _as_utc(start_date)
    end = _as_utc(end_date)
    if balance_history_df.empty or start > end:
        return _empty_account_inventory()

    balances = _prepare_balances(balance_history_df)
    available = balances[balances["Date"] <= end]
    if available.empty:
        return _empty_account_inventory()

    start = max(start, available["Date"].min())
    current = _latest_accounts_as_of(balances, end)
    current = current[current["Group"].str.strip().ne("")].copy()
    if current.empty:
        return _empty_account_inventory()

    opening = _latest_accounts_as_of(balances, start).set_index("_Account_Key")
    opening_contributions = opening["_Contribution"]
    for column in ("Account", "Institution", "Type"):
        if column not in current:
            current[column] = ""
    current["Class"] = current["_Class"]
    current["Balance"] = current["_Magnitude"]
    current["Net_Contribution"] = current["_Contribution"]
    current["Period_Change"] = current["_Contribution"] - current["_Account_Key"].map(opening_contributions).fillna(0.0)
    current["Last_Updated"] = current["Date"]
    return (
        current.filter(ACCOUNT_INVENTORY_COLUMNS)
        .sort_values(["Group", "Account"], kind="stable")
        .reset_index(drop=True)
    )


def _prepare_balances(balance_history_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize balance history for account-level as-of calculations."""
    balances = balance_history_df.copy()
    balances["Date"] = pd.to_datetime(balances["Date"], errors="coerce", utc=True)
    balances["Balance"] = pd.to_numeric(balances["Balance"], errors="coerce")
    balances = balances.dropna(subset=["Date", "Balance"])
    groups = balances["Group"] if "Group" in balances else pd.Series("", index=balances.index)
    classes = balances["Class"] if "Class" in balances else pd.Series("Asset", index=balances.index)
    balances["Group"] = groups.fillna("").astype(str).str.strip()
    balances["_Class"] = classes.fillna("Asset").astype(str)
    balances["_Class"] = balances["_Class"].where(balances["_Class"] == "Liability", "Asset")
    balances["_Magnitude"] = balances["Balance"].abs()
    balances["_Contribution"] = balances["Balance"].where(
        balances["_Class"] == "Asset",
        -balances["Balance"],
    )

    if "Account ID" in balances:
        account_ids = balances["Account ID"].astype("string").str.strip()
    else:
        account_ids = pd.Series(pd.NA, index=balances.index, dtype="string")
    if "Account" in balances:
        account_names = balances["Account"].astype("string").str.strip()
    else:
        account_names = balances.index.to_series().astype("string")
    balances["_Account_Key"] = account_ids.where(
        account_ids.notna() & account_ids.ne(""),
        account_names,
    )
    balances = balances[balances["_Account_Key"].notna() & balances["_Account_Key"].ne("")]

    if "Time" in balances:
        times = pd.to_datetime(balances["Time"], errors="coerce", utc=True)
        balances["_Sequence"] = times.fillna(balances["Date"])
    else:
        balances["_Sequence"] = balances["Date"]
    return balances.sort_values(["_Account_Key", "Date", "_Sequence"])


def _latest_accounts_as_of(
    balances: pd.DataFrame,
    boundary: pd.Timestamp,
) -> pd.DataFrame:
    """Return each account's latest observation on or before ``boundary``."""
    return (
        balances[balances["Date"] <= boundary]
        .sort_values(["_Account_Key", "Date", "_Sequence"])
        .drop_duplicates("_Account_Key", keep="last")
    )


def _as_utc(value: pd.Timestamp) -> pd.Timestamp:
    """Normalize a timestamp to UTC."""
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def _empty_net_worth_history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.Series(dtype="datetime64[ns, UTC]"),
            "Assets": pd.Series(dtype=float),
            "Liabilities": pd.Series(dtype=float),
            "Net_Worth": pd.Series(dtype=float),
        }
    )


def _empty_balance_group_inventory() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Group": pd.Series(dtype=str),
            "Type": pd.Series(dtype=str),
            "Balance": pd.Series(dtype=float),
            "Net_Contribution": pd.Series(dtype=float),
            "Period_Change": pd.Series(dtype=float),
            "Period_Change_Pct": pd.Series(dtype=float),
            "Last_Updated": pd.Series(dtype="datetime64[ns, UTC]"),
            "Account_Count": pd.Series(dtype=int),
            "Trend": pd.Series(dtype=object),
        }
    )


def _empty_account_inventory() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Group": pd.Series(dtype=str),
            "Account": pd.Series(dtype=str),
            "Institution": pd.Series(dtype=str),
            "Type": pd.Series(dtype=str),
            "Class": pd.Series(dtype=str),
            "Balance": pd.Series(dtype=float),
            "Net_Contribution": pd.Series(dtype=float),
            "Period_Change": pd.Series(dtype=float),
            "Last_Updated": pd.Series(dtype="datetime64[ns, UTC]"),
        }
    )
