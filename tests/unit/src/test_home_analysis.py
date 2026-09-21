"""Tests for the Home page's pure analysis helpers."""

from typing import cast

import pandas as pd
import pytest

from src.analysis.home import (
    ACCOUNT_GROUP_DETAIL_COLUMNS,
    ACCOUNT_INVENTORY_COLUMNS,
    BALANCE_GROUP_COLUMNS,
    NET_WORTH_COLUMNS,
    build_account_group_details,
    build_account_inventory,
    build_balance_group_inventory,
    build_net_worth_history,
)
from tests._helpers import _balance_df


def test_net_worth_history_signs_and_carries_each_account_forward() -> None:
    balances = _balance_df(
        [
            {
                "Date": "2024-01-01",
                "Account": "Checking",
                "Account ID": "asset",
                "Balance": 100,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-10",
                "Account": "Checking",
                "Account ID": "asset",
                "Balance": 120,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-01",
                "Account": "Card",
                "Account ID": "debt",
                "Balance": 50,
                "Class": "Liability",
                "Group": "Credit",
            },
            {
                "Date": "2024-01-18",
                "Account": "Card",
                "Account ID": "debt",
                "Balance": 40,
                "Class": "Liability",
                "Group": "Credit",
            },
        ]
    )

    history = build_net_worth_history(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-22", tz="UTC"),
    )

    assert list(history.columns) == NET_WORTH_COLUMNS
    assert history["Date"].tolist() == list(
        pd.to_datetime(
            [
                "2024-01-01",
                "2024-01-07",
                "2024-01-14",
                "2024-01-21",
                "2024-01-22",
            ],
            utc=True,
        )
    )
    assert history["Assets"].tolist() == pytest.approx([100, 100, 120, 120, 120])
    assert history["Liabilities"].tolist() == pytest.approx([-50, -50, -50, -40, -40])
    assert history["Net_Worth"].tolist() == pytest.approx([50, 50, 70, 80, 80])


def test_net_worth_history_does_not_backfill_a_new_account() -> None:
    balances = _balance_df(
        [
            {
                "Date": "2024-01-01",
                "Account": "Checking",
                "Account ID": "existing",
                "Balance": 100,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-16",
                "Account": "Savings",
                "Account ID": "new",
                "Balance": 25,
                "Class": "Asset",
                "Group": "Cash",
            },
        ]
    )

    history = build_net_worth_history(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-22", tz="UTC"),
    )

    assert history["Assets"].tolist() == pytest.approx([100, 100, 100, 125, 125])


def test_net_worth_history_clips_a_pre_history_start() -> None:
    balances = _balance_df(
        [
            {
                "Date": "2024-01-10",
                "Account": "Checking",
                "Account ID": "asset",
                "Balance": 100,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-20",
                "Account": "Checking",
                "Account ID": "asset",
                "Balance": 120,
                "Class": "Asset",
                "Group": "Cash",
            },
        ]
    )

    history = build_net_worth_history(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-22", tz="UTC"),
    )

    assert history["Date"].tolist() == list(
        pd.to_datetime(
            [
                "2024-01-10",
                "2024-01-14",
                "2024-01-21",
                "2024-01-22",
            ],
            utc=True,
        )
    )
    assert history["Assets"].tolist() == pytest.approx([100, 100, 120, 120])
    assert (history["Net_Worth"] != 0).all()


def test_balance_group_inventory_signs_changes_and_mixed_groups() -> None:
    balances = _balance_df(
        [
            {
                "Date": "2024-01-01",
                "Account": "Checking",
                "Account ID": "cash",
                "Balance": 100,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-20",
                "Account": "Checking",
                "Account ID": "cash",
                "Balance": 150,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-01",
                "Account": "Card",
                "Account ID": "card",
                "Balance": 200,
                "Class": "Liability",
                "Group": "Credit",
            },
            {
                "Date": "2024-01-20",
                "Account": "Card",
                "Account ID": "card",
                "Balance": 150,
                "Class": "Liability",
                "Group": "Credit",
            },
            {
                "Date": "2024-01-01",
                "Account": "Brokerage",
                "Account ID": "brokerage",
                "Balance": 500,
                "Class": "Asset",
                "Group": "Investing",
            },
            {
                "Date": "2024-01-20",
                "Account": "Brokerage",
                "Account ID": "brokerage",
                "Balance": 600,
                "Class": "Asset",
                "Group": "Investing",
            },
            {
                "Date": "2024-01-01",
                "Account": "Margin",
                "Account ID": "margin",
                "Balance": 200,
                "Class": "Liability",
                "Group": "Investing",
            },
            {
                "Date": "2024-01-20",
                "Account": "Margin",
                "Account ID": "margin",
                "Balance": 250,
                "Class": "Liability",
                "Group": "Investing",
            },
            {
                "Date": "2024-01-20",
                "Account": "New",
                "Account ID": "new",
                "Balance": 75,
                "Class": "Asset",
                "Group": "New assets",
            },
            {
                "Date": "2024-01-20",
                "Account": "Ignored",
                "Account ID": "blank",
                "Balance": 1,
                "Class": "Asset",
                "Group": "",
            },
        ]
    )

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
    assert inventory.loc["Credit", "Trend"] == pytest.approx([200, 200, 200, 150, 150, 150])
    assert inventory.loc["Investing", "Type"] == "Mixed"
    assert inventory.loc["Investing", "Balance"] == pytest.approx(350)
    assert inventory.loc["Investing", "Net_Contribution"] == pytest.approx(350)
    assert inventory.loc["Investing", "Period_Change"] == pytest.approx(50)
    trend = inventory.loc["Investing", "Trend"]
    assert isinstance(trend, list)
    assert trend[-1] == pytest.approx(350)
    assert inventory.loc["New assets", "Period_Change"] == pytest.approx(75)
    assert pd.isna(inventory.loc["New assets", "Period_Change_Pct"])


def test_group_inventory_uses_first_observation_as_pre_history_baseline() -> None:
    balances = _balance_df(
        [
            {
                "Date": "2024-01-10",
                "Account": "Checking",
                "Account ID": "existing",
                "Balance": 100,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-20",
                "Account": "Checking",
                "Account ID": "existing",
                "Balance": 120,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-20",
                "Account": "Savings",
                "Account ID": "new",
                "Balance": 25,
                "Class": "Asset",
                "Group": "Cash",
            },
        ]
    )

    inventory = build_balance_group_inventory(
        balances,
        pd.Timestamp("2023-01-01", tz="UTC"),
        pd.Timestamp("2024-01-31", tz="UTC"),
    ).set_index("Group")

    assert inventory.loc["Cash", "Net_Contribution"] == pytest.approx(145)
    assert inventory.loc["Cash", "Period_Change"] == pytest.approx(45)
    assert inventory.loc["Cash", "Period_Change_Pct"] == pytest.approx(45)


def test_group_inventory_uses_current_group_for_opening_balance_and_trend() -> None:
    balances = _balance_df(
        [
            {
                "Date": "2024-01-01",
                "Account": "Brokerage",
                "Account ID": "brokerage",
                "Balance": 100,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-20",
                "Account": "Brokerage",
                "Account ID": "brokerage",
                "Balance": 120,
                "Class": "Asset",
                "Group": "Investments",
            },
        ]
    )

    groups = build_balance_group_inventory(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-31", tz="UTC"),
    ).set_index("Group")
    accounts = build_account_inventory(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-31", tz="UTC"),
    )

    assert list(groups.index) == ["Investments"]
    assert groups.loc["Investments", "Period_Change"] == pytest.approx(20)
    assert accounts["Period_Change"].sum() == pytest.approx(groups.loc["Investments", "Period_Change"])
    trend = cast(list[float], groups.loc["Investments", "Trend"])
    assert trend[0] == pytest.approx(100)
    assert trend[-1] == pytest.approx(120)


def test_balance_analysis_preserves_credit_and_overdraft_signs() -> None:
    balances = _balance_df(
        [
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
        ]
    )

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
    assert list(build_account_group_details(empty, "Cash", is_liability=False).columns) == ACCOUNT_GROUP_DETAIL_COLUMNS
    assert build_net_worth_history(empty, start, end).empty
    assert build_balance_group_inventory(empty, start, end).empty
    assert build_account_inventory(empty, start, end).empty


def test_account_group_details_use_an_empty_schema_for_a_missing_group() -> None:
    accounts = pd.DataFrame(
        {
            "Group": ["Cash"],
            "Account": ["Checking"],
            "Balance": [500.0],
            "Net_Contribution": [500.0],
            "Period_Change": [25.0],
        }
    )

    details = build_account_group_details(accounts, "Investments", is_liability=False)

    assert list(details.columns) == ACCOUNT_GROUP_DETAIL_COLUMNS
    assert details.empty


def test_account_inventory_calculates_asset_liability_and_new_account_changes() -> None:
    balances = _balance_df(
        [
            {
                "Date": "2024-01-01",
                "Time": "2024-01-01 09:00",
                "Account": "Checking",
                "Account ID": "cash",
                "Institution": "Bank",
                "Type": "Depository",
                "Balance": 100,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-20",
                "Time": "2024-01-20 08:00",
                "Account": "Checking",
                "Account ID": "cash",
                "Institution": "Bank",
                "Type": "Depository",
                "Balance": 100,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-20",
                "Time": "2024-01-20 09:00",
                "Account": "Checking",
                "Account ID": "cash",
                "Institution": "Bank",
                "Type": "Depository",
                "Balance": 125,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-01",
                "Time": "2024-01-01 09:00",
                "Account": "Card",
                "Account ID": "card",
                "Institution": "Issuer",
                "Type": "Credit",
                "Balance": 100,
                "Class": "Liability",
                "Group": "Credit",
            },
            {
                "Date": "2024-01-19",
                "Time": "2024-01-19 09:00",
                "Account": "Card",
                "Account ID": "card",
                "Institution": "Issuer",
                "Type": "Credit",
                "Balance": 80,
                "Class": "Liability",
                "Group": "Credit",
            },
            {
                "Date": "2024-01-15",
                "Time": "2024-01-15 09:00",
                "Account": "New savings",
                "Account ID": "new",
                "Institution": "Bank",
                "Type": "Depository",
                "Balance": 50,
                "Class": "Asset",
                "Group": "Cash",
            },
            {
                "Date": "2024-01-19",
                "Time": "2024-01-19 09:00",
                "Account": "Ignored",
                "Account ID": "blank",
                "Institution": "Bank",
                "Type": "Depository",
                "Balance": 10,
                "Class": "Asset",
                "Group": "",
            },
        ]
    )

    inventory = build_account_inventory(
        balances,
        pd.Timestamp("2024-01-01", tz="UTC"),
        pd.Timestamp("2024-01-20", tz="UTC"),
    ).set_index("Account")

    assert set(inventory.index) == {"Checking", "Card", "New savings"}
    assert inventory.loc["Checking", "Balance"] == pytest.approx(125)
    assert inventory.loc["Checking", "Net_Contribution"] == pytest.approx(125)
    assert inventory.loc["Checking", "Period_Change"] == pytest.approx(25)
    assert inventory.loc["Card", "Balance"] == pytest.approx(80)
    assert inventory.loc["Card", "Net_Contribution"] == pytest.approx(-80)
    assert inventory.loc["Card", "Period_Change"] == pytest.approx(20)
    assert inventory.loc["New savings", "Period_Change"] == pytest.approx(50)


def test_account_group_details_show_balance_change_and_net_worth_impact() -> None:
    accounts = pd.DataFrame(
        {
            "Group": ["Investments", "Debt", "Debt"],
            "Account": ["Brokerage", "Home loan", "Credit card"],
            "Balance": [500.0, 200_000.0, 2_000.0],
            "Net_Contribution": [500.0, -200_000.0, -2_000.0],
            "Period_Change": [50.0, 1_000.0, -100.0],
        }
    )

    investment_details = build_account_group_details(accounts, "Investments", is_liability=False)
    debt_details = build_account_group_details(accounts, "Debt", is_liability=True)

    assert list(investment_details.columns) == ACCOUNT_GROUP_DETAIL_COLUMNS
    assert investment_details.to_dict("records") == [
        {
            "Account": "Brokerage",
            "Balance": 500.0,
            "Change": 50.0,
            "Net_Worth_Impact": 50.0,
        }
    ]
    assert debt_details.to_dict("records") == [
        {
            "Account": "Home loan",
            "Balance": 200_000.0,
            "Change": -1_000.0,
            "Net_Worth_Impact": 1_000.0,
        },
        {
            "Account": "Credit card",
            "Balance": 2_000.0,
            "Change": 100.0,
            "Net_Worth_Impact": -100.0,
        },
    ]
