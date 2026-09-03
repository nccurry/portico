"""Tests for subscription inventory and recurring-charge discovery."""

from collections.abc import Iterable, Sequence
from importlib import import_module
from typing import Literal, Protocol, cast

import altair as alt
import pandas as pd
import pytest

from src.analysis.subscriptions import (
    build_subscription_history,
    build_subscription_inventory,
    build_subscription_lifecycles,
    find_subscription_candidates,
    get_subscription_transactions,
    summarize_subscriptions,
)

SUBSCRIPTION_CATEGORY = "Misc Subscription"


class _SubscriptionsPage(Protocol):
    def prepare_lifecycle_timeline(
        self,
        lifecycles: pd.DataFrame,
        *,
        range_start: pd.Timestamp,
        range_end: pd.Timestamp,
        scope: Literal["Active and recent", "All merchants"],
    ) -> pd.DataFrame: ...

    def create_lifecycle_timeline_chart(
        self,
        timeline: pd.DataFrame,
        *,
        range_start: pd.Timestamp,
        range_end: pd.Timestamp,
    ) -> alt.LayerChart: ...

    def filter_subscription_history(
        self,
        history: pd.DataFrame,
        lookback: str,
    ) -> pd.DataFrame: ...

    def prepare_active_inventory(
        self,
        inventory: pd.DataFrame,
        lifecycles: pd.DataFrame,
    ) -> pd.DataFrame: ...


subscriptions_page = cast(
    _SubscriptionsPage,
    import_module("app_pages.5_Subscriptions"),
)


def _merchant_rows(
    merchant: str,
    dates: Iterable[str | pd.Timestamp],
    amounts: Sequence[float],
    *,
    category: str = SUBSCRIPTION_CATEGORY,
    group: str = "Entertainment",
) -> pd.DataFrame:
    """Build scrubbed transaction rows for one merchant."""
    timestamps = pd.to_datetime(pd.Index(list(dates)), utc=True)
    return pd.DataFrame(
        {
            "Date": timestamps,
            "Amount": list(amounts),
            "Type": ["Expense"] * len(timestamps),
            "Category": [category] * len(timestamps),
            "Group": [group] * len(timestamps),
            "Account": ["Checking"] * len(timestamps),
            "Month": timestamps.strftime("%Y-%m"),
            "Full Description": [merchant] * len(timestamps),
            "Institution": ["Bank"] * len(timestamps),
            "Account #": ["1234"] * len(timestamps),
        }
    )


def _with_latest_date(transactions: pd.DataFrame, latest: str) -> pd.DataFrame:
    """Add an unrelated row that anchors status calculations to a data date."""
    anchor = _merchant_rows(
        "PAYROLL",
        [latest],
        [1_000.0],
        category="Salary",
        group="Income",
    )
    anchor["Type"] = "Income"
    return pd.concat([transactions, anchor], ignore_index=True)


def test_categorized_subscription_appears_after_one_charge() -> None:
    transactions = _merchant_rows("NEW SERVICE", ["2026-04-15"], [-14.99])

    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    assert len(inventory) == 1
    assert inventory.iloc[0]["Status"] == "Active"
    assert inventory.iloc[0]["Cadence"] == "Pending"
    assert pd.isna(inventory.iloc[0]["Monthly_Run_Rate"])


def test_merchant_aliases_reconcile_subscription_inventory_and_details() -> None:
    transactions = pd.concat(
        [
            _merchant_rows("AMAZON MKTPL*1234", ["2026-01-01"], [-12.00]),
            _merchant_rows("AMAZON COM", ["2026-02-01"], [-14.00]),
        ],
        ignore_index=True,
    )
    aliases = {"AMAZON MKTPL": "AMAZON", "AMAZON COM": "AMAZON"}

    inventory = build_subscription_inventory(
        transactions,
        [SUBSCRIPTION_CATEGORY],
        aliases=aliases,
    )
    details = get_subscription_transactions(
        transactions,
        "Amazon",
        categories=[SUBSCRIPTION_CATEGORY],
        aliases=aliases,
    )

    assert inventory[["Merchant", "Charge_Count"]].to_dict("records") == [
        {"Merchant": "AMAZON", "Charge_Count": 2},
    ]
    assert len(details) == 2


@pytest.mark.parametrize(
    ("dates", "expected_cadence", "expected_monthly"),
    [
        (["2026-01-10", "2026-02-10", "2026-03-10"], "Monthly", 120.0),
        (["2025-07-10", "2025-10-10", "2026-01-10"], "Quarterly", 40.0),
        (["2024-01-10", "2025-01-10", "2026-01-10"], "Annual", 10.0),
    ],
)
def test_regular_cadences_are_monthly_normalized(
    dates: list[str],
    expected_cadence: str,
    expected_monthly: float,
) -> None:
    transactions = _merchant_rows("REGULAR SERVICE", dates, [-120.0] * 3)

    row = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY]).iloc[0]

    assert row["Cadence"] == expected_cadence
    assert row["Monthly_Run_Rate"] == pytest.approx(expected_monthly)
    assert row["Bundle_Type"] == "Single stream"


def test_multiple_charges_are_one_merchant_bundle() -> None:
    transactions = _merchant_rows(
        "APPLE COM BILL",
        [
            "2026-01-05",
            "2026-01-20",
            "2026-02-05",
            "2026-02-20",
            "2026-03-05",
            "2026-03-20",
        ],
        [-5.0, -15.0] * 3,
    )

    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])
    row = inventory.iloc[0]

    assert len(inventory) == 1
    assert row["Merchant"] == "APPLE COM BILL"
    assert row["Cadence"] == "Multiple"
    assert row["Bundle_Type"] == "Merchant bundle"
    assert row["Monthly_Run_Rate"] == pytest.approx(20.0)


def test_bundle_run_rate_includes_zero_spend_calendar_months() -> None:
    bundle = _merchant_rows(
        "APPLE COM BILL",
        ["2026-01-05", "2026-01-20", "2026-03-05", "2026-03-20"],
        [-5.0, -15.0, -5.0, -15.0],
    )

    row = build_subscription_inventory(
        _with_latest_date(bundle, "2026-04-30"),
        [SUBSCRIPTION_CATEGORY],
    ).iloc[0]

    assert row["Cadence"] == "Multiple"
    assert row["Monthly_Run_Rate"] == pytest.approx(10.0)


def test_price_change_stays_in_one_merchant_lifecycle() -> None:
    transactions = _merchant_rows(
        "STREAMING SERVICE",
        pd.date_range("2026-01-01", periods=6, freq="MS", tz="UTC"),
        [-10.0, -10.0, -10.0, -12.0, -12.0, -12.0],
    )

    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])
    row = inventory.iloc[0]

    assert len(inventory) == 1
    assert row["Monthly_Run_Rate"] == pytest.approx(12.0)
    assert row["Price_Change"] == pytest.approx(2.0)
    assert row["Price_Change_Date"] == pd.Timestamp("2026-04-01", tz="UTC")

    lifecycle = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    ).iloc[0]
    assert lifecycle["Price_Change"] == pytest.approx(2.0)
    assert lifecycle["Price_Change_Date"] == pd.Timestamp("2026-04-01", tz="UTC")


@pytest.mark.parametrize(
    ("amounts", "expected_change"),
    [
        ([-10.0, -10.0, -10.5], 0.5),
        ([-10.0, -10.0, -9.5], -0.5),
        ([-20.0, -20.0, -20.5], 0.0),
        ([-5.0, -5.0, -5.3], 0.0),
    ],
)
def test_price_change_requires_both_amount_and_percent_thresholds(
    amounts: list[float],
    expected_change: float,
) -> None:
    transactions = _merchant_rows(
        "STREAMING SERVICE",
        ["2026-01-01", "2026-02-01", "2026-03-01"],
        amounts,
    )

    row = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY]).iloc[0]

    assert row["Price_Change"] == pytest.approx(expected_change)
    if expected_change:
        assert row["Price_Change_Date"] == pd.Timestamp("2026-03-01", tz="UTC")
    else:
        assert pd.isna(row["Price_Change_Date"])


@pytest.mark.parametrize(
    ("latest", "expected_status"),
    [
        ("2026-04-05", "Active"),
        ("2026-04-20", "Active"),
        ("2026-04-30", "Active"),
        ("2026-05-01", "Inactive"),
    ],
)
def test_regular_status_boundaries(latest: str, expected_status: str) -> None:
    recurring = _merchant_rows(
        "MONTHLY SERVICE",
        ["2026-01-01", "2026-02-01", "2026-03-01"],
        [-10.0] * 3,
    )

    row = build_subscription_inventory(
        _with_latest_date(recurring, latest),
        [SUBSCRIPTION_CATEGORY],
    ).iloc[0]

    assert row["Status"] == expected_status


@pytest.mark.parametrize(
    ("latest", "expected_status"),
    [
        ("2026-02-10", "Active"),
        ("2026-03-05", "Active"),
        ("2026-04-01", "Active"),
        ("2026-04-02", "Inactive"),
    ],
)
def test_pending_status_uses_full_90_day_boundary(
    latest: str,
    expected_status: str,
) -> None:
    new_subscription = _merchant_rows("NEW SERVICE", ["2026-01-01"], [-9.99])

    row = build_subscription_inventory(
        _with_latest_date(new_subscription, latest),
        [SUBSCRIPTION_CATEGORY],
    ).iloc[0]

    assert row["Status"] == expected_status


def _boundary_transactions(cadence: str, *, beyond_boundary: bool) -> pd.DataFrame:
    """Build charges whose final gap lands on or just after an inactive boundary."""
    if cadence == "Monthly":
        dates = list(pd.date_range("2026-01-01", periods=5, freq="MS", tz="UTC"))
        amounts = [-10.0] * 5
        boundary_days = 60
    elif cadence == "Quarterly":
        start = pd.Timestamp("2024-01-01", tz="UTC")
        dates = [start + pd.Timedelta(days=91 * index) for index in range(5)]
        amounts = [-120.0] * 5
        boundary_days = 181
    elif cadence == "Annual":
        start = pd.Timestamp("2020-01-01", tz="UTC")
        dates = [start + pd.Timedelta(days=365 * index) for index in range(5)]
        amounts = [-120.0] * 5
        boundary_days = 455
    elif cadence == "Pending":
        dates = [pd.Timestamp("2026-01-01", tz="UTC")]
        amounts = [-10.0]
        boundary_days = 90
    else:
        dates = list(
            pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-15",
                    "2026-02-01",
                    "2026-02-15",
                    "2026-03-01",
                    "2026-03-15",
                ],
                utc=True,
            )
        )
        amounts = [-5.0, -15.0] * 3
        boundary_days = 90

    final_date = dates[-1] + pd.Timedelta(days=boundary_days + int(beyond_boundary))
    return _merchant_rows("BOUNDARY SERVICE", [*dates, final_date], [*amounts, -10.0])


@pytest.mark.parametrize(
    ("cadence", "expected_cadence"),
    [
        ("Monthly", "Monthly"),
        ("Quarterly", "Quarterly"),
        ("Annual", "Annual"),
        ("Pending", "Pending"),
        ("Multiple", "Multiple"),
    ],
)
def test_charge_on_inactive_boundary_stays_in_same_episode(
    cadence: str,
    expected_cadence: str,
) -> None:
    transactions = _boundary_transactions(cadence, beyond_boundary=False)
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    assert inventory.iloc[0]["Cadence"] == expected_cadence
    assert len(lifecycles) == 1
    assert lifecycles.iloc[0]["Charge_Count"] == len(transactions)


@pytest.mark.parametrize("cadence", ["Monthly", "Quarterly", "Annual", "Pending", "Multiple"])
def test_charge_after_inactive_boundary_starts_new_episode(cadence: str) -> None:
    transactions = _boundary_transactions(cadence, beyond_boundary=True)
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    assert sorted(lifecycles["Episode"].tolist()) == [1, 2]
    assert lifecycles.loc[lifecycles["Episode"] == 2, "Charge_Count"].item() == 1


def test_lifecycle_schema_and_single_charge_inferred_tail_are_stable() -> None:
    subscription = _merchant_rows("NEW SERVICE", ["2026-01-01"], [-10.0])
    transactions = _with_latest_date(subscription, "2026-01-30")
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )
    row = lifecycles.iloc[0]

    assert lifecycles.columns.tolist() == [
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
    assert row["Episode_Start"] == pd.Timestamp("2026-01-01", tz="UTC")
    assert row["Observed_End"] == pd.Timestamp("2026-01-01", tz="UTC")
    assert row["Active_Until"] == pd.Timestamp("2026-04-01", tz="UTC")
    assert row["Inactive_After"] == pd.Timestamp("2026-04-01", tz="UTC")
    assert row["Display_End"] == pd.Timestamp("2026-01-30", tz="UTC")
    assert row["Display_End"] <= transactions["Date"].max()
    assert row["Observed_Duration_Days"] == 0
    assert row["Lifecycle_Duration_Days"] == 29


def test_restarted_merchant_has_inactive_history_and_active_current_episode() -> None:
    dates = [
        *pd.date_range("2026-01-01", periods=5, freq="MS", tz="UTC"),
        pd.Timestamp("2026-07-01", tz="UTC"),
        pd.Timestamp("2026-08-01", tz="UTC"),
        pd.Timestamp("2026-09-01", tz="UTC"),
    ]
    transactions = _merchant_rows("RESTARTED SERVICE", dates, [-10.0] * len(dates))
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    assert lifecycles["Episode"].tolist() == [2, 1]
    assert lifecycles["Status"].tolist() == ["Active", "Inactive"]
    assert lifecycles["Is_Current"].tolist() == [True, False]
    assert lifecycles.loc[lifecycles["Episode"] == 1, "Display_End"].item() == pd.Timestamp(
        "2026-06-30",
        tz="UTC",
    )


def test_restarted_merchant_uses_latest_current_price_and_run_rate() -> None:
    dates = [
        *pd.date_range("2026-01-01", periods=4, freq="MS", tz="UTC"),
        *pd.date_range("2026-07-01", periods=3, freq="MS", tz="UTC"),
    ]
    transactions = _merchant_rows(
        "RESTARTED SERVICE",
        dates,
        [-10.0] * 4 + [-20.0, -20.0, -25.0],
    )
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])
    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    inventory_row = inventory.iloc[0]
    current = lifecycles[lifecycles["Is_Current"]].iloc[0]
    assert inventory_row["Cadence"] == "Monthly"
    assert inventory_row["Monthly_Run_Rate"] == pytest.approx(25.0)
    assert inventory_row["Price_Change"] == pytest.approx(5.0)
    assert inventory_row["Price_Change_Date"] == pd.Timestamp("2026-09-01", tz="UTC")
    assert current["Episode_Start"] == pd.Timestamp("2026-07-01", tz="UTC")
    assert current["Latest_Charge_Amount"] == pytest.approx(25.0)
    assert current["Monthly_Run_Rate"] == pytest.approx(25.0)


def test_active_inventory_uses_current_episode_start_for_ordering() -> None:
    restarted = _merchant_rows(
        "RESTARTED SERVICE",
        [
            *pd.date_range("2026-01-01", periods=4, freq="MS", tz="UTC"),
            *pd.date_range("2026-07-01", periods=3, freq="MS", tz="UTC"),
        ],
        [-10.0] * 7,
    )
    continuous = _merchant_rows(
        "CONTINUOUS SERVICE",
        pd.date_range("2026-04-01", periods=5, freq="MS", tz="UTC"),
        [-15.0] * 5,
    )
    transactions = pd.concat([restarted, continuous], ignore_index=True)
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])
    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    active = subscriptions_page.prepare_active_inventory(inventory, lifecycles)

    assert active["Merchant"].tolist() == ["RESTARTED SERVICE", "CONTINUOUS SERVICE"]
    assert active["First_Date"].tolist() == [
        pd.Timestamp("2026-07-01", tz="UTC"),
        pd.Timestamp("2026-04-01", tz="UTC"),
    ]


def test_price_changes_are_scoped_to_regular_episodes() -> None:
    dates = [
        *pd.date_range("2026-01-01", periods=5, freq="MS", tz="UTC"),
        pd.Timestamp("2026-07-01", tz="UTC"),
        pd.Timestamp("2026-08-01", tz="UTC"),
        pd.Timestamp("2026-09-01", tz="UTC"),
    ]
    transactions = _merchant_rows(
        "RESTARTED SERVICE",
        dates,
        [-10.0] * 5 + [-20.0] * 3,
    )
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    assert inventory.iloc[0]["Price_Change"] == 0.0
    assert lifecycles["Price_Change"].tolist() == [0.0, 0.0]
    assert lifecycles["Price_Change_Date"].isna().all()


def test_bundle_lifecycles_do_not_report_price_changes() -> None:
    transactions = _merchant_rows(
        "BUNDLE SERVICE",
        [
            "2026-01-01",
            "2026-01-15",
            "2026-02-01",
            "2026-02-15",
            "2026-03-01",
            "2026-03-15",
        ],
        [-5.0, -15.0, -7.0, -17.0, -9.0, -19.0],
    )
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    assert lifecycles.iloc[0]["Cadence"] == "Multiple"
    assert lifecycles.iloc[0]["Price_Change"] == 0.0
    assert pd.isna(lifecycles.iloc[0]["Price_Change_Date"])


def test_lifecycle_timeline_orders_merchants_by_status_and_recency() -> None:
    lifecycles = pd.DataFrame(
        {
            "Merchant": [
                "INACTIVE OLD",
                "ACTIVE OLD",
                "ACTIVE SHORTEST",
                "INACTIVE RECENT",
                "ACTIVE NEW",
            ],
            "Episode": [1, 1, 1, 1, 1],
            "Episode_Start": pd.to_datetime(
                ["2026-01-01", "2026-01-01", "2026-08-01", "2026-05-01", "2026-07-01"],
                utc=True,
            ),
            "Observed_End": pd.to_datetime(
                ["2026-02-01", "2026-08-01", "2026-08-15", "2026-06-01", "2026-08-15"],
                utc=True,
            ),
            "Active_Until": pd.to_datetime(
                ["2026-03-01", "2026-10-01", "2026-09-15", "2026-07-01", "2026-10-01"],
                utc=True,
            ),
            "Inactive_After": pd.to_datetime(
                ["2026-03-01", "2026-10-01", "2026-09-15", "2026-07-01", "2026-10-01"],
                utc=True,
            ),
            "Display_End": pd.to_datetime(
                ["2026-03-01", "2026-09-01", "2026-09-01", "2026-07-01", "2026-09-01"],
                utc=True,
            ),
            "Status": ["Inactive", "Active", "Active", "Inactive", "Active"],
            "Is_Current": [True] * 5,
            "Next_Expected_Date": [pd.NaT] * 5,
            "Price_Change_Date": [pd.NaT] * 5,
            "Lifecycle_Duration_Days": [59, 243, 31, 61, 62],
        }
    )

    timeline = subscriptions_page.prepare_lifecycle_timeline(
        lifecycles,
        range_start=pd.Timestamp("2026-01-01", tz="UTC"),
        range_end=pd.Timestamp("2026-09-01", tz="UTC"),
        scope="All merchants",
    )

    assert timeline["Merchant"].drop_duplicates().tolist() == [
        "ACTIVE SHORTEST",
        "ACTIVE NEW",
        "ACTIVE OLD",
        "INACTIVE RECENT",
        "INACTIVE OLD",
    ]


def test_lifecycle_timeline_scope_excludes_inferred_tail_only_by_default() -> None:
    lifecycles = pd.DataFrame(
        {
            "Merchant": ["TAIL ONLY"],
            "Episode": [1],
            "Episode_Start": pd.to_datetime(["2026-01-01"], utc=True),
            "Observed_End": pd.to_datetime(["2026-01-15"], utc=True),
            "Active_Until": pd.to_datetime(["2026-04-15"], utc=True),
            "Inactive_After": pd.to_datetime(["2026-04-15"], utc=True),
            "Display_End": pd.to_datetime(["2026-04-15"], utc=True),
            "Status": ["Inactive"],
            "Is_Current": [True],
            "Next_Expected_Date": [pd.NaT],
            "Price_Change_Date": [pd.NaT],
            "Lifecycle_Duration_Days": [104],
        }
    )

    recent = subscriptions_page.prepare_lifecycle_timeline(
        lifecycles,
        range_start=pd.Timestamp("2026-03-01", tz="UTC"),
        range_end=pd.Timestamp("2026-03-31", tz="UTC"),
        scope="Active and recent",
    )
    all_merchants = subscriptions_page.prepare_lifecycle_timeline(
        lifecycles,
        range_start=pd.Timestamp("2026-03-01", tz="UTC"),
        range_end=pd.Timestamp("2026-03-31", tz="UTC"),
        scope="All merchants",
    )

    assert recent.empty
    assert all_merchants["Merchant"].tolist() == ["TAIL ONLY"]
    row = all_merchants.iloc[0]
    assert row["Observed_Clip_Start"] == pd.Timestamp("2026-03-01", tz="UTC")
    assert row["Observed_Clip_End"] == pd.Timestamp("2026-01-15", tz="UTC")
    assert row["Tail_Clip_Start"] == pd.Timestamp("2026-03-01", tz="UTC")
    assert row["Tail_Clip_End"] == pd.Timestamp("2026-03-31", tz="UTC")
    assert not row["Show_Endpoint"]


def test_lifecycle_chart_has_observed_tail_endpoint_and_latest_date_layers() -> None:
    subscription = _merchant_rows(
        "STREAMING SERVICE",
        ["2026-01-01", "2026-02-01", "2026-03-01"],
        [-10.0, -10.0, -12.0],
    )
    transactions = _with_latest_date(subscription, "2026-03-15")
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])
    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )
    timeline = subscriptions_page.prepare_lifecycle_timeline(
        lifecycles,
        range_start=pd.Timestamp("2026-01-01", tz="UTC"),
        range_end=pd.Timestamp("2026-03-15", tz="UTC"),
        scope="All merchants",
    )

    spec = subscriptions_page.create_lifecycle_timeline_chart(
        timeline,
        range_start=pd.Timestamp("2026-01-01", tz="UTC"),
        range_end=pd.Timestamp("2026-03-15", tz="UTC"),
    ).to_dict()

    layers = spec["layer"]
    assert spec["height"] == 260
    assert [layer["mark"]["type"] for layer in layers] == ["bar", "bar", "point", "rule"]
    assert layers[0]["mark"]["opacity"] == pytest.approx(0.28)
    assert layers[0]["encoding"]["x"]["field"] == "Tail_Clip_Start"
    assert layers[0]["encoding"]["x2"]["field"] == "Tail_Clip_End"
    assert layers[1]["encoding"]["x"]["field"] == "Observed_Clip_Start"
    assert layers[1]["encoding"]["x2"]["field"] == "Observed_Clip_End"
    assert "Show_Endpoint" in str(layers[2]["transform"])
    assert layers[3]["mark"]["strokeDash"] == [5, 5]
    assert layers[3]["encoding"]["x"]["field"] == "Latest_Data_Date"
    assert layers[0]["encoding"]["color"]["scale"]["domain"] == ["Active", "Inactive"]
    tooltip_fields = {tooltip["field"] for tooltip in layers[0]["encoding"]["tooltip"]}
    assert {
        "Merchant",
        "Status",
        "Episode_Start",
        "Observed_End",
        "Display_End",
        "Cadence",
        "Charge_Count",
        "Latest_Charge_Amount",
        "Monthly_Run_Rate",
        "Next_Expected_Date",
        "Price_Change",
    } <= tooltip_fields


@pytest.mark.parametrize(
    ("lookback", "expected_rows"),
    [
        ("Last 3 months", 3),
        ("Last 6 months", 6),
        ("Last 12 months", 12),
        ("Last 24 months", 24),
        ("All history", 30),
    ],
)
def test_subscription_history_lookback_filters_only_trailing_rows(
    lookback: str,
    expected_rows: int,
) -> None:
    history = pd.DataFrame(
        {
            "Month": pd.date_range("2024-01-01", periods=30, freq="MS", tz="UTC"),
            "Actual_Spend": range(30),
        }
    )

    visible = subscriptions_page.filter_subscription_history(history, lookback)

    assert visible.index.tolist() == history.tail(expected_rows).index.tolist()


def test_discovery_surfaces_non_bill_and_respects_explicit_category_exclusions() -> None:
    dates = ["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15"]
    candidate = _merchant_rows(
        "SURPRISE SOFTWARE",
        dates,
        [-19.0] * 4,
        category="Software",
        group="Shopping",
    )
    utility = _merchant_rows(
        "UTILITY COMPANY",
        dates,
        [-120.0] * 4,
        category="Electric Bill",
        group="Bills",
    )

    candidates = find_subscription_candidates(
        pd.concat([candidate, utility], ignore_index=True),
        [SUBSCRIPTION_CATEGORY],
        excluded_categories=["Electric Bill"],
    )

    assert candidates["Merchant"].tolist() == ["SURPRISE SOFTWARE"]
    assert candidates.iloc[0]["Status"] == "Active"
    assert "4 charges across 4 months" in candidates.iloc[0]["Evidence"]


@pytest.mark.parametrize(
    ("category", "group"),
    [
        ("Electric", "Bills"),
        ("Rent", "Housing"),
        ("Personal Loan", "Debt"),
        ("Brokerage Investment", "Savings"),
        ("Coffee", "Transfer"),
        ("Software", "Shopping"),
    ],
)
def test_discovery_excludes_exact_user_selected_categories(
    category: str,
    group: str,
) -> None:
    transactions = _merchant_rows(
        "RECURRING MERCHANT",
        ["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15"],
        [-120.0] * 4,
        category=category,
        group=group,
    )

    candidates = find_subscription_candidates(
        transactions,
        [SUBSCRIPTION_CATEGORY],
        excluded_categories=[category],
    )

    assert candidates.empty


def test_discovery_does_not_interpret_category_text_as_a_hidden_regex_policy() -> None:
    transactions = _merchant_rows(
        "RECURRING MERCHANT",
        ["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15"],
        [-120.0] * 4,
        category="Personal Loan",
        group="Debt",
    )

    candidates = find_subscription_candidates(transactions, [SUBSCRIPTION_CATEGORY])

    assert candidates["Merchant"].tolist() == ["MERCHANT"]


def test_discovery_rejects_frequent_purchase_merchants() -> None:
    dates = pd.date_range("2026-01-01", periods=12, freq="10D", tz="UTC")
    transactions = _merchant_rows(
        "COFFEE SHOP",
        dates,
        [-5.0] * len(dates),
        category="Coffee",
        group="Food",
    )

    assert find_subscription_candidates(transactions, [SUBSCRIPTION_CATEGORY]).empty


@pytest.mark.parametrize(
    ("dates", "expected_cadence"),
    [
        (["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15"], "Monthly"),
        (["2025-07-15", "2025-10-15", "2026-01-15", "2026-04-15"], "Quarterly"),
        (["2023-01-15", "2024-01-15", "2025-01-15", "2026-01-15"], "Annual"),
    ],
)
def test_discovery_supports_regular_cadences(
    dates: list[str],
    expected_cadence: str,
) -> None:
    transactions = _merchant_rows(
        "SURPRISE SOFTWARE",
        dates,
        [-24.0] * len(dates),
        category="Software",
        group="Shopping",
    )

    row = find_subscription_candidates(transactions, [SUBSCRIPTION_CATEGORY]).iloc[0]

    assert row["Cadence"] == expected_cadence


def test_discovery_enforces_regularity_and_confidence_boundaries() -> None:
    def rows_from_gaps(gaps: list[int]) -> pd.DataFrame:
        dates = [pd.Timestamp("2026-01-01", tz="UTC")]
        for gap in gaps:
            dates.append(dates[-1] + pd.Timedelta(days=gap))
        return _merchant_rows(
            "SURPRISE SOFTWARE",
            dates,
            [-19.0] * len(dates),
            category="Software",
            group="Shopping",
        )

    exact_boundary = rows_from_gaps([30] * 7 + [50] * 3)
    below_boundary = rows_from_gaps([30] * 6 + [50] * 4)

    candidates = find_subscription_candidates(
        exact_boundary,
        [SUBSCRIPTION_CATEGORY],
        min_confidence=85,
    )

    assert candidates["Confidence"].tolist() == [85]
    assert "70% of intervals" in candidates.iloc[0]["Evidence"]
    assert find_subscription_candidates(
        exact_boundary,
        [SUBSCRIPTION_CATEGORY],
        min_confidence=86,
    ).empty
    assert find_subscription_candidates(
        below_boundary,
        [SUBSCRIPTION_CATEGORY],
        min_confidence=70,
    ).empty


def test_discovery_excludes_inactive_candidates() -> None:
    recurring = _merchant_rows(
        "OLD SOFTWARE",
        ["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15"],
        [-19.0] * 4,
        category="Software",
        group="Shopping",
    )

    candidates = find_subscription_candidates(
        _with_latest_date(recurring, "2026-07-01"),
        [SUBSCRIPTION_CATEGORY],
    )

    assert candidates.empty


def test_candidate_detail_uses_the_same_category_exclusions_as_discovery() -> None:
    eligible = _merchant_rows(
        "SHARED MERCHANT SERVICE SOFTWARE",
        ["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15"],
        [-19.0] * 4,
        category="Software",
        group="Shopping",
    )
    rent = _merchant_rows(
        "SHARED MERCHANT SERVICE RENT",
        ["2026-03-20"],
        [-1_200.0],
        category="Rent",
        group="Housing",
    )
    user_excluded = _merchant_rows(
        "SHARED MERCHANT SERVICE COURSE",
        ["2026-03-25"],
        [-99.0],
        category="Education",
        group="Shopping",
    )
    transactions = pd.concat([eligible, rent, user_excluded], ignore_index=True)
    exclusions = [SUBSCRIPTION_CATEGORY, "Education"]
    candidate = find_subscription_candidates(
        transactions,
        [SUBSCRIPTION_CATEGORY],
        excluded_categories=["Education"],
    ).iloc[0]

    matches = get_subscription_transactions(
        transactions,
        str(candidate["Merchant"]),
        excluded_categories=exclusions,
    )

    assert matches["Category"].unique().tolist() == ["Software"]
    assert len(matches) == 4


def test_history_reconciles_to_categorized_transactions() -> None:
    first = _merchant_rows(
        "SERVICE ONE",
        ["2026-01-10", "2026-02-10", "2026-03-10"],
        [-10.0] * 3,
    )
    second = _merchant_rows(
        "SERVICE TWO",
        ["2026-02-20", "2026-03-20"],
        [-20.0] * 2,
    )
    unrelated = _merchant_rows(
        "GROCERY",
        ["2026-03-21"],
        [-200.0],
        category="Groceries",
        group="Food",
    )
    transactions = pd.concat([first, second, unrelated], ignore_index=True)
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])
    lifecycles = build_subscription_lifecycles(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    history = build_subscription_history(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )
    precomputed_history = build_subscription_history(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
        lifecycles=lifecycles,
    )

    pd.testing.assert_frame_equal(precomputed_history, history)
    assert history["Actual_Spend"].tolist() == pytest.approx([10.0, 30.0, 30.0])
    assert history["Rolling_Average"].tolist() == pytest.approx([10.0, 20.0, 70.0 / 3])
    assert history["Actual_Spend"].sum() == pytest.approx(70.0)
    assert history["Active_Merchants"].max() == 2


def test_history_counts_merchants_through_lifecycle_active_boundaries() -> None:
    monthly = _merchant_rows(
        "MONTHLY SERVICE",
        ["2026-01-01", "2026-02-01", "2026-03-01"],
        [-10.0] * 3,
    )
    pending = _merchant_rows("NEW SERVICE", ["2026-03-20"], [-20.0])
    transactions = _with_latest_date(
        pd.concat([monthly, pending], ignore_index=True),
        "2026-05-15",
    )
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    history = build_subscription_history(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    assert history["Actual_Spend"].tolist() == pytest.approx([10.0, 10.0, 30.0, 0.0, 0.0])
    assert history["Active_Merchants"].tolist() == [1, 1, 2, 2, 1]


def test_history_can_include_an_incomplete_month_after_latest_transaction() -> None:
    transactions = _merchant_rows(
        "MONTHLY SERVICE",
        ["2026-01-01", "2026-02-01", "2026-03-01"],
        [-10.0] * 3,
    )
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    history = build_subscription_history(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
        through_date=pd.Timestamp("2026-04-15", tz="UTC"),
    )

    assert history["Month"].tolist() == list(pd.date_range("2026-01-01", "2026-04-01", freq="MS", tz="UTC"))
    assert history["Actual_Spend"].tolist() == pytest.approx([10.0, 10.0, 10.0, 0.0])
    assert history["Active_Merchants"].tolist() == [1, 1, 1, 1]


def test_history_counts_pending_subscription_through_full_inactive_boundary() -> None:
    pending = _merchant_rows("NEW SERVICE", ["2026-01-01"], [-20.0])
    transactions = _with_latest_date(pending, "2026-04-02")
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    history = build_subscription_history(
        transactions,
        inventory,
        [SUBSCRIPTION_CATEGORY],
    )

    assert inventory.iloc[0]["Status"] == "Inactive"
    assert history["Active_Merchants"].tolist() == [1, 1, 1, 1]


def test_summary_uses_active_run_rate_and_actual_trailing_spend() -> None:
    dates = pd.date_range("2024-01-10", periods=24, freq="MS", tz="UTC")
    transactions = _merchant_rows("LONG SERVICE", dates, [-10.0] * 24)
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    summary = summarize_subscriptions(
        inventory,
        transactions,
        [SUBSCRIPTION_CATEGORY],
    )

    assert summary["active_count"] == 1
    assert summary["monthly_run_rate"] == pytest.approx(10.0)
    assert summary["trailing_12_month_spend"] == pytest.approx(120.0)
    assert summary["prior_12_month_spend"] == pytest.approx(120.0)
    assert summary["annual_change_pct"] == 0.0
    assert summary["pending_estimate_count"] == 0


def test_summary_counts_active_pending_estimates() -> None:
    transactions = _merchant_rows("NEW SERVICE", ["2026-04-15"], [-14.99])
    inventory = build_subscription_inventory(transactions, [SUBSCRIPTION_CATEGORY])

    summary = summarize_subscriptions(
        inventory,
        transactions,
        [SUBSCRIPTION_CATEGORY],
    )

    assert summary["active_count"] == 1
    assert summary["monthly_run_rate"] == 0.0
    assert summary["pending_estimate_count"] == 1


def test_merchant_detail_matching_uses_normalized_merchant_key() -> None:
    transactions = pd.concat(
        [
            _merchant_rows("APPLE MUSIC MONTHLY", ["2026-01-01"], [-9.99]),
            _merchant_rows("APPLE ICLOUD STORAGE", ["2026-01-01"], [-2.99]),
        ],
        ignore_index=True,
    )

    matches = get_subscription_transactions(
        transactions,
        "APPLE MUSIC MONTHLY",
        categories=[SUBSCRIPTION_CATEGORY],
    )

    assert matches["Full Description"].tolist() == ["APPLE MUSIC MONTHLY"]


def test_empty_inputs_return_stable_shapes() -> None:
    empty = pd.DataFrame(
        columns=[
            "Date",
            "Amount",
            "Type",
            "Category",
            "Group",
            "Account",
            "Month",
            "Full Description",
        ]
    )
    inventory_columns = [
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
    lifecycle_columns = [
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

    inventory = build_subscription_inventory(empty, [SUBSCRIPTION_CATEGORY])
    candidates = find_subscription_candidates(empty, [SUBSCRIPTION_CATEGORY])
    history = build_subscription_history(empty, pd.DataFrame(), [SUBSCRIPTION_CATEGORY])
    lifecycles = build_subscription_lifecycles(
        empty,
        pd.DataFrame(),
        [SUBSCRIPTION_CATEGORY],
    )

    assert inventory.empty and inventory.columns.tolist() == inventory_columns
    assert candidates.empty and candidates.columns.tolist() == [*inventory_columns, "Evidence"]
    assert history.empty and history.columns.tolist() == [
        "Month",
        "Actual_Spend",
        "Rolling_Average",
        "Active_Merchants",
    ]
    assert lifecycles.empty and lifecycles.columns.tolist() == lifecycle_columns
