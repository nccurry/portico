"""Behavior tests for spending exploration analysis."""

import pandas as pd
import pytest

from src.analysis.spending import (
    MERCHANT_COLUMNS,
    MONTHLY_COMPARISON_COLUMNS,
    OVERVIEW_COLUMNS,
    build_entity_monthly_comparison,
    build_merchant_breakdown,
    build_spending_ledger,
    build_spending_overview,
    summarize_spending,
)
from src.custom_types import SpendingFilters


def _filters(**overrides: object) -> SpendingFilters:
    filters: SpendingFilters = {
        "include_groups": [],
        "include_categories": [],
        "include_transactions_like": [],
        "exclude_groups": [],
        "exclude_categories": [],
        "exclude_transactions_like": [],
        "filter_large_expenses": False,
        "expense_threshold": 3_000,
    }
    filters.update(overrides)  # type: ignore[typeddict-item]
    return filters


def _transactions(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults: dict[str, object] = {
        "Date": pd.Timestamp("2024-01-15", tz="UTC"),
        "Month": "2024-01",
        "Amount": -100.0,
        "Type": "Expense",
        "Category": "Groceries",
        "Group": "Food",
        "Account": "Checking",
        "Full Description": "STORE PURCHASE",
    }
    return pd.DataFrame(
        [defaults | row for row in rows],
        columns=list(defaults),
    )


class TestBuildSpendingLedger:
    def test_keeps_only_expenses_inside_exclusive_month_window(self) -> None:
        transactions = _transactions(
            [
                {"Month": "2023-12"},
                {"Month": "2024-01"},
                {"Month": "2024-02", "Type": "Income"},
                {"Month": "2024-03"},
            ]
        )

        ledger = build_spending_ledger(
            transactions,
            _filters(),
            start_month="2024-01",
            end_month="2024-03",
        )

        assert ledger["Month"].tolist() == ["2024-01"]
        assert ledger["Included"].tolist() == [True]

    def test_refunds_reduce_spending(self) -> None:
        transactions = _transactions(
            [
                {"Amount": -200.0},
                {"Amount": 50.0, "Full Description": "STORE REFUND"},
            ]
        )

        ledger = build_spending_ledger(
            transactions,
            _filters(),
            start_month="2024-01",
            end_month="2024-02",
        )

        assert ledger["Net_Spend"].tolist() == pytest.approx([200.0, -50.0])
        assert ledger["Net_Spend"].sum() == pytest.approx(150.0)

    def test_records_every_matching_exclusion_reason(self) -> None:
        transactions = _transactions(
            [
                {
                    "Amount": -4_000.0,
                    "Group": "Travel",
                    "Category": "Flights",
                }
            ]
        )

        ledger = build_spending_ledger(
            transactions,
            _filters(
                exclude_groups=["Travel"],
                exclude_categories=["Flights"],
                filter_large_expenses=True,
            ),
            start_month="2024-01",
            end_month="2024-02",
        )

        assert not bool(ledger.iloc[0]["Included"])
        assert ledger.iloc[0]["Exclusion_Reason"].split("; ") == [
            "Excluded group: Travel",
            "Excluded category: Flights",
            "Expense over $3,000",
        ]

    def test_amount_equal_to_limit_remains_included(self) -> None:
        transactions = _transactions(
            [
                {"Amount": -3_000.0},
                {"Amount": -3_000.01},
            ]
        )

        ledger = build_spending_ledger(
            transactions,
            _filters(filter_large_expenses=True),
            start_month="2024-01",
            end_month="2024-02",
        )

        assert ledger["Included"].tolist() == [True, False]

    def test_include_filters_use_union_for_legacy_callers(self) -> None:
        transactions = _transactions(
            [
                {"Group": "Travel", "Category": "Flights"},
                {"Group": "Food", "Category": "Groceries"},
                {"Group": "Food", "Category": "Dining"},
            ]
        )

        ledger = build_spending_ledger(
            transactions,
            _filters(include_groups=["Travel"], include_categories=["Groceries"]),
            start_month="2024-01",
            end_month="2024-02",
        )

        assert ledger["Included"].tolist() == [True, True, False]

    def test_excludes_transaction_description_fragments(self) -> None:
        ledger = build_spending_ledger(
            _transactions(
                [
                    {"Full Description": "ACH IRS TAX PAYMENT", "Category": "Shopping"},
                    {"Full Description": "CHECK #1234", "Category": "Shopping"},
                    {"Full Description": "POS ASCEND FCU 123456789", "Category": "Shopping"},
                    {"Full Description": "HOME LOAN PAYMENT", "Category": "Shopping"},
                    {"Full Description": "AIRBNB 12345", "Category": "Shopping"},
                    {"Full Description": "COFFEE SHOP", "Category": "Shopping"},
                ]
            ),
            _filters(
                include_categories=["Shopping"],
                exclude_transactions_like=["IRS", "CHECK", "ASCEND FCU", "HOME LOAN", "AIRBNB"],
            ),
            start_month="2024-01",
            end_month="2024-02",
        )

        assert ledger["Included"].tolist() == [False, False, False, False, False, True]
        assert ledger["Exclusion_Reason"].tolist() == [
            "Excluded transaction like: IRS",
            "Excluded transaction like: CHECK",
            "Excluded transaction like: ASCEND FCU",
            "Excluded transaction like: HOME LOAN",
            "Excluded transaction like: AIRBNB",
            "",
        ]

    def test_empty_period_has_annotated_schema(self) -> None:
        ledger = build_spending_ledger(
            _transactions([]),
            _filters(),
            start_month="2025-01",
            end_month="2025-02",
        )

        assert ledger.empty
        assert {"Included", "Exclusion_Reason", "Net_Spend"}.issubset(ledger.columns)


class TestBuildSpendingOverview:
    def test_reconciles_group_totals_shares_changes_and_zero_months(self) -> None:
        current = build_spending_ledger(
            _transactions(
                [
                    {"Month": "2024-01", "Group": "Food", "Amount": -100.0},
                    {"Month": "2024-03", "Group": "Food", "Amount": -200.0},
                    {"Month": "2024-02", "Group": "Housing", "Amount": -500.0},
                ]
            ),
            _filters(),
            start_month="2024-01",
            end_month="2024-04",
        )
        comparison = build_spending_ledger(
            _transactions(
                [
                    {"Month": "2023-10", "Group": "Food", "Amount": -250.0},
                    {"Month": "2023-11", "Group": "Travel", "Amount": -300.0},
                ]
            ),
            _filters(),
            start_month="2023-10",
            end_month="2024-01",
        )

        overview = build_spending_overview(
            current,
            comparison,
            dimension="Group",
            months=["2024-01", "2024-02", "2024-03"],
        )

        assert overview.columns.tolist() == OVERVIEW_COLUMNS
        assert overview["Entity"].tolist() == ["Housing", "Food", "Travel"]
        food = overview[overview["Entity"] == "Food"].iloc[0]
        assert food["Spending"] == pytest.approx(300.0)
        assert food["Comparison_Spending"] == pytest.approx(250.0)
        assert food["Change"] == pytest.approx(50.0)
        assert food["Change_Pct"] == pytest.approx(20.0)
        assert food["Monthly_Trend"] == pytest.approx([100.0, 0.0, 200.0])
        assert overview["Spending"].sum() == pytest.approx(800.0)
        assert overview["Share"].sum() == pytest.approx(100.0)

    def test_category_overview_carries_authoritative_group(self) -> None:
        ledger = build_spending_ledger(
            _transactions(
                [
                    {"Category": "Groceries", "Group": "Food", "Amount": -100.0},
                    {"Category": "Rent", "Group": "Housing", "Amount": -500.0},
                ]
            ),
            _filters(),
            start_month="2024-01",
            end_month="2024-02",
        )

        overview = build_spending_overview(
            ledger,
            ledger.iloc[0:0],
            dimension="Category",
            months=["2024-01"],
        )

        assert dict(zip(overview["Entity"], overview["Group"], strict=True)) == {
            "Rent": "Housing",
            "Groceries": "Food",
        }

    def test_invalid_dimension_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsupported spending dimension"):
            build_spending_overview(
                pd.DataFrame(),
                pd.DataFrame(),
                dimension="Merchant",
                months=[],
            )

    def test_empty_ledgers_return_exact_schema(self) -> None:
        empty = pd.DataFrame(columns=["Included", "Group", "Net_Spend", "Month"])
        result = build_spending_overview(
            empty,
            empty,
            dimension="Group",
            months=["2024-01"],
        )
        assert result.empty
        assert result.columns.tolist() == OVERVIEW_COLUMNS


class TestSpendingDetailAnalysis:
    def test_summary_uses_net_spending_and_matched_month_count(self) -> None:
        current = build_spending_ledger(
            _transactions([{"Amount": -200.0}, {"Amount": 50.0}]),
            _filters(),
            start_month="2024-01",
            end_month="2024-02",
        )
        comparison = build_spending_ledger(
            _transactions([{"Amount": -100.0}]),
            _filters(),
            start_month="2024-01",
            end_month="2024-02",
        )

        summary = summarize_spending(current, comparison, num_months=3)

        assert summary == {
            "total_spending": 150.0,
            "average_monthly_spending": 50.0,
            "comparison_spending": 100.0,
            "change": 50.0,
            "change_pct": 50.0,
            "transaction_count": 2,
            "num_months": 3,
        }

    def test_summary_has_unavailable_pct_without_comparison_spending(self) -> None:
        current = build_spending_ledger(
            _transactions([{"Amount": -100.0}]),
            _filters(),
            start_month="2024-01",
            end_month="2024-02",
        )
        summary = summarize_spending(current, current.iloc[0:0], num_months=1)
        assert summary["change_pct"] is None

    def test_monthly_comparison_aligns_requested_months(self) -> None:
        current = build_spending_ledger(
            _transactions(
                [
                    {"Month": "2024-01", "Amount": -100.0},
                    {"Month": "2024-03", "Amount": -300.0},
                ]
            ),
            _filters(),
            start_month="2024-01",
            end_month="2024-04",
        )
        comparison = build_spending_ledger(
            _transactions([{"Month": "2023-12", "Amount": -50.0}]),
            _filters(),
            start_month="2023-10",
            end_month="2024-01",
        )

        result = build_entity_monthly_comparison(
            current,
            comparison,
            dimension="Category",
            entity="Groceries",
            current_months=["2024-01", "2024-02", "2024-03"],
            comparison_months=["2023-10", "2023-11", "2023-12"],
        )

        assert result.columns.tolist() == MONTHLY_COMPARISON_COLUMNS
        assert result["Current_Spend"].tolist() == pytest.approx([100, 0, 300])
        assert result["Comparison_Spend"].tolist() == pytest.approx([0, 0, 50])

    def test_merchant_breakdown_reconciles_refunds(self) -> None:
        ledger = build_spending_ledger(
            _transactions(
                [
                    {
                        "Amount": -200.0,
                        "Full Description": "POS PURCHASE KROGER #1234 STORE",
                    },
                    {
                        "Amount": 50.0,
                        "Full Description": "KROGER #1234 STORE REFUND",
                    },
                    {
                        "Amount": -25.0,
                        "Full Description": "COFFEE SHOP 4567",
                    },
                ]
            ),
            _filters(),
            start_month="2024-01",
            end_month="2024-02",
        )

        merchants = build_merchant_breakdown(ledger)

        assert merchants.columns.tolist() == MERCHANT_COLUMNS
        assert merchants["Spending"].sum() == pytest.approx(175.0)
        kroger = merchants[merchants["Merchant"].str.startswith("KROGER")].iloc[0]
        assert kroger["Spending"] == pytest.approx(150.0)
        assert kroger["Transactions"] == 2

    def test_merchant_breakdown_applies_configured_aliases(self) -> None:
        ledger = pd.DataFrame(
            {
                "Included": [True, True],
                "Net_Spend": [100.0, 50.0],
                "Full Description": [
                    "AMZN MKTPLACE order 123",
                    "AMAZON.COM order 456",
                ],
                "Date": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
            }
        )

        merchants = build_merchant_breakdown(
            ledger,
            aliases={"AMZN MKTPLACE": "AMAZON", "AMAZON COM": "AMAZON"},
        )

        assert merchants["Merchant"].tolist() == ["AMAZON"]
        assert merchants["Spending"].tolist() == pytest.approx([150.0])

    def test_merchant_breakdown_uses_the_shared_normalized_merchant_name(self) -> None:
        ledger = pd.DataFrame(
            {
                "Included": [True, True],
                "Net_Spend": [100.0, 50.0],
                "Full Description": [
                    "POS PURCHASE JUNIPER KITCHEN DINNER #1234",
                    "JUNIPER KITCHEN DINNER 5678",
                ],
                "Date": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
            }
        )

        merchants = build_merchant_breakdown(ledger)

        assert merchants["Merchant"].tolist() == ["JUNIPER KITCHEN DINNER"]
        assert merchants["Spending"].tolist() == pytest.approx([150.0])

    def test_empty_merchant_breakdown_has_exact_schema(self) -> None:
        result = build_merchant_breakdown(pd.DataFrame(columns=["Included", "Net_Spend", "Date"]))
        assert result.empty
        assert result.columns.tolist() == MERCHANT_COLUMNS
