"""Tests for the Home page's pure analysis helpers."""

import pandas as pd
import pytest

from src.analysis.home import (
    ACCOUNT_INVENTORY_COLUMNS,
    BALANCE_GROUP_COLUMNS,
    NET_WORTH_COLUMNS,
    build_account_inventory,
    build_balance_group_inventory,
    build_net_worth_history,
)
from tests._helpers import _balance_df


def test_net_worth_history_signs_and_carries_each_account_forward() -> None:
    balances = _balance_df([
        {"Date": "2024-01-01", "Account": "Checking", "Account ID": "asset", "Balance": 100, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-10", "Account": "Checking", "Account ID": "asset", "Balance": 120, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-01", "Account": "Card", "Account ID": "debt", "Balance": 50, "Class": "Liability", "Group": "Credit"},
        {"Date": "2024-01-18", "Account": "Card", "Account ID": "debt", "Balance": 40, "Class": "Liability", "Group": "Credit"},
    ])

    history = build_net_worth_history(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-22", tz="UTC"),
    )

    assert list(history.columns) == NET_WORTH_COLUMNS
    assert history["Date"].tolist() == list(pd.to_datetime([
        "2024-01-01", "2024-01-07", "2024-01-14", "2024-01-21", "2024-01-22",
    ], utc=True))
    assert history["Assets"].tolist() == pytest.approx([100, 100, 120, 120, 120])
    assert history["Liabilities"].tolist() == pytest.approx([-50, -50, -50, -40, -40])
    assert history["Net_Worth"].tolist() == pytest.approx([50, 50, 70, 80, 80])


def test_net_worth_history_does_not_backfill_a_new_account() -> None:
    balances = _balance_df([
        {"Date": "2024-01-01", "Account": "Checking", "Account ID": "existing", "Balance": 100, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-16", "Account": "Savings", "Account ID": "new", "Balance": 25, "Class": "Asset", "Group": "Cash"},
    ])

    history = build_net_worth_history(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-22", tz="UTC"),
    )

    assert history["Assets"].tolist() == pytest.approx([100, 100, 100, 125, 125])


def test_net_worth_history_clips_a_pre_history_start() -> None:
    balances = _balance_df([
        {"Date": "2024-01-10", "Account": "Checking", "Account ID": "asset", "Balance": 100, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-20", "Account": "Checking", "Account ID": "asset", "Balance": 120, "Class": "Asset", "Group": "Cash"},
    ])

    history = build_net_worth_history(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-22", tz="UTC"),
    )

    assert history["Date"].tolist() == list(pd.to_datetime([
        "2024-01-10", "2024-01-14", "2024-01-21", "2024-01-22",
    ], utc=True))
    assert history["Assets"].tolist() == pytest.approx([100, 100, 120, 120])
    assert (history["Net_Worth"] != 0).all()


def test_balance_group_inventory_signs_changes_and_mixed_groups() -> None:
    balances = _balance_df([
        {"Date": "2024-01-01", "Account": "Checking", "Account ID": "cash", "Balance": 100, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-20", "Account": "Checking", "Account ID": "cash", "Balance": 150, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-01", "Account": "Card", "Account ID": "card", "Balance": 200, "Class": "Liability", "Group": "Credit"},
        {"Date": "2024-01-20", "Account": "Card", "Account ID": "card", "Balance": 150, "Class": "Liability", "Group": "Credit"},
        {"Date": "2024-01-01", "Account": "Brokerage", "Account ID": "brokerage", "Balance": 500, "Class": "Asset", "Group": "Investing"},
        {"Date": "2024-01-20", "Account": "Brokerage", "Account ID": "brokerage", "Balance": 600, "Class": "Asset", "Group": "Investing"},
        {"Date": "2024-01-01", "Account": "Margin", "Account ID": "margin", "Balance": 200, "Class": "Liability", "Group": "Investing"},
        {"Date": "2024-01-20", "Account": "Margin", "Account ID": "margin", "Balance": 250, "Class": "Liability", "Group": "Investing"},
        {"Date": "2024-01-20", "Account": "New", "Account ID": "new", "Balance": 75, "Class": "Asset", "Group": "New assets"},
        {"Date": "2024-01-20", "Account": "Ignored", "Account ID": "blank", "Balance": 1, "Class": "Asset", "Group": ""},
    ])

    inventory = build_balance_group_inventory(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-31", tz="UTC"),
    ).set_index("Group")

    assert set(inventory.index) == {"Cash", "Credit", "Investing", "New assets"}
    assert inventory.loc["Cash", "Type"] == "Asset"
    assert inventory.loc["Cash", "Balance"] == pytest.approx(150)
    assert inventory.loc["Cash", "Net_Contribution"] == pytest.approx(150)
    assert inventory.loc["Cash", "Period_Change"] == pytest.approx(50)
    assert inventory.loc["Cash", "Period_Change_Pct"] == pytest.approx(50)
    assert inventory.loc["Credit", "Type"] == "Liability"
    assert inventory.loc["Credit", "Balance"] == pytest.approx(150)
    assert inventory.loc["Credit", "Net_Contribution"] == pytest.approx(-150)
    assert inventory.loc["Credit", "Period_Change"] == pytest.approx(50)
    assert inventory.loc["Credit", "Period_Change_Pct"] == pytest.approx(25)
    assert inventory.loc["Investing", "Type"] == "Mixed"
    assert inventory.loc["Investing", "Balance"] == pytest.approx(350)
    assert inventory.loc["Investing", "Net_Contribution"] == pytest.approx(350)
    assert inventory.loc["Investing", "Period_Change"] == pytest.approx(50)
    assert inventory.loc["Investing", "Account_Count"] == 2
    assert inventory.loc["Investing", "Last_Updated"] == pd.Timestamp("2024-01-20", tz="UTC")
    trend = inventory.loc["Investing", "Trend"]
    assert isinstance(trend, list)
    assert trend[-1] == pytest.approx(350)
    assert inventory.loc["New assets", "Period_Change"] == pytest.approx(75)
    assert pd.isna(inventory.loc["New assets", "Period_Change_Pct"])


def test_group_inventory_uses_first_observation_as_pre_history_baseline() -> None:
    balances = _balance_df([
        {"Date": "2024-01-10", "Account": "Checking", "Account ID": "existing", "Balance": 100, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-20", "Account": "Checking", "Account ID": "existing", "Balance": 120, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-20", "Account": "Savings", "Account ID": "new", "Balance": 25, "Class": "Asset", "Group": "Cash"},
    ])

    inventory = build_balance_group_inventory(
        balances,
        pd.Timestamp("2023-01-01", tz="UTC"),
        pd.Timestamp("2024-01-31", tz="UTC"),
    ).set_index("Group")

    assert inventory.loc["Cash", "Net_Contribution"] == pytest.approx(145)
    assert inventory.loc["Cash", "Period_Change"] == pytest.approx(45)
    assert inventory.loc["Cash", "Period_Change_Pct"] == pytest.approx(45)


def test_balance_analysis_preserves_credit_and_overdraft_signs() -> None:
    balances = _balance_df([
        {
            "Date": "2024-01-01",
            "Account": "Overdrawn checking",
            "Account ID": "overdraft",
            "Balance": -25,
            "Class": "Asset",
            "Group": "Cash",
        },
        {
            "Date": "2024-01-01",
            "Account": "Card credit",
            "Account ID": "credit",
            "Balance": -10,
            "Class": "Liability",
            "Group": "Credit",
        },
    ])

    history = build_net_worth_history(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-07", tz="UTC"),
    )
    inventory = build_balance_group_inventory(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-07", tz="UTC"),
    ).set_index("Group")

    assert history.iloc[-1]["Net_Worth"] == pytest.approx(-15)
    assert inventory.loc["Cash", "Balance"] == pytest.approx(25)
    assert inventory.loc["Cash", "Net_Contribution"] == pytest.approx(-25)
    assert inventory.loc["Credit", "Balance"] == pytest.approx(10)
    assert inventory.loc["Credit", "Net_Contribution"] == pytest.approx(10)


def test_balance_analysis_empty_inputs_have_stable_schemas() -> None:
    empty = pd.DataFrame()
    start = pd.Timestamp("2024-01-01", tz="UTC")
    end = pd.Timestamp("2024-01-31", tz="UTC")

    assert list(build_net_worth_history(empty, start, end).columns) == NET_WORTH_COLUMNS
    assert list(build_balance_group_inventory(empty, start, end).columns) == BALANCE_GROUP_COLUMNS
    assert "Period_Change" in ACCOUNT_INVENTORY_COLUMNS
    assert list(build_account_inventory(empty, start, end).columns) == ACCOUNT_INVENTORY_COLUMNS
    assert build_net_worth_history(empty, start, end).empty
    assert build_balance_group_inventory(empty, start, end).empty
    assert build_account_inventory(empty, start, end).empty


def test_account_inventory_calculates_asset_liability_and_new_account_changes() -> None:
    balances = _balance_df([
        {"Date": "2024-01-01", "Time": "2024-01-01 09:00", "Account": "Checking", "Account ID": "cash", "Institution": "Bank", "Type": "Depository", "Balance": 100, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-20", "Time": "2024-01-20 08:00", "Account": "Checking", "Account ID": "cash", "Institution": "Bank", "Type": "Depository", "Balance": 100, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-20", "Time": "2024-01-20 09:00", "Account": "Checking", "Account ID": "cash", "Institution": "Bank", "Type": "Depository", "Balance": 125, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-01", "Time": "2024-01-01 09:00", "Account": "Card", "Account ID": "card", "Institution": "Issuer", "Type": "Credit", "Balance": 100, "Class": "Liability", "Group": "Credit"},
        {"Date": "2024-01-19", "Time": "2024-01-19 09:00", "Account": "Card", "Account ID": "card", "Institution": "Issuer", "Type": "Credit", "Balance": 80, "Class": "Liability", "Group": "Credit"},
        {"Date": "2024-01-15", "Time": "2024-01-15 09:00", "Account": "New savings", "Account ID": "new", "Institution": "Bank", "Type": "Depository", "Balance": 50, "Class": "Asset", "Group": "Cash"},
        {"Date": "2024-01-19", "Time": "2024-01-19 09:00", "Account": "Ignored", "Account ID": "blank", "Institution": "Bank", "Type": "Depository", "Balance": 10, "Class": "Asset", "Group": ""},
    ])

    inventory = build_account_inventory(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-20", tz="UTC"),
    ).set_index("Account")

    assert set(inventory.index) == {"Checking", "Card", "New savings"}
    assert inventory.loc["Checking", "Balance"] == pytest.approx(125)
    assert inventory.loc["Checking", "Net_Contribution"] == pytest.approx(125)
    assert inventory.loc["Checking", "Period_Change"] == pytest.approx(25)
    assert inventory.loc["Checking", "Institution"] == "Bank"
    assert inventory.loc["Checking", "Type"] == "Depository"
    assert inventory.loc["Card", "Balance"] == pytest.approx(80)
    assert inventory.loc["Card", "Net_Contribution"] == pytest.approx(-80)
    assert inventory.loc["Card", "Period_Change"] == pytest.approx(20)
    assert inventory.loc["Card", "Class"] == "Liability"
    assert inventory.loc["New savings", "Period_Change"] == pytest.approx(50)
