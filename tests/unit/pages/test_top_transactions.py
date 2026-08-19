"""Tests for transaction exploration analysis."""

import pandas as pd
import pytest

from src.analysis.top_transactions import (
    build_transaction_breakdown,
    build_transaction_inventory,
    filter_transaction_focus,
    summarize_transaction_inventory,
)


def _explorer_transactions(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults = {
        "Date": "2024-01-01",
        "Amount": -100.0,
        "Type": "Expense",
        "Category": "Shopping",
        "Group": "Shopping",
        "Account": "Checking",
        "Month": "2024-01",
        "Full Description": "Example merchant",
        "Institution": "Bank",
        "Account #": "1234",
    }
    frame = pd.DataFrame([{**defaults, **row} for row in rows])
    frame["Date"] = pd.to_datetime(frame["Date"], utc=True)
    return frame


class TestTransactionExplorer:

    def test_inventory_applies_dimensions_search_and_amount_range(self) -> None:
        transactions = _explorer_transactions([
            {
                "Date": "2024-02-01",
                "Amount": -125.0,
                "Category": "Groceries",
                "Group": "Food",
                "Full Description": "Market Basket groceries",
            },
            {
                "Date": "2024-02-02",
                "Amount": -75.0,
                "Category": "Restaurants",
                "Group": "Food",
                "Full Description": "Corner Cafe dinner",
            },
            {"Date": "2024-02-03", "Amount": 3_000.0, "Type": "Income"},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
            transaction_types=["Expense"],
            groups=["Food"],
            categories=["Groceries"],
            accounts=["Checking"],
            search="market basket",
            minimum_magnitude=100.0,
            maximum_magnitude=200.0,
        )

        assert result["Full Description"].tolist() == ["Market Basket groceries"]
        assert result["Magnitude"].tolist() == [125.0]

    def test_aliases_keep_description_variants_from_looking_like_one_offs(self) -> None:
        transactions = _explorer_transactions([
            {"Full Description": "AMZN MKTPLACE order 1234"},
            {"Full Description": "AMAZON.COM purchase 5678", "Amount": -50.0},
            {"Full Description": "Local bookstore", "Amount": -30.0},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
            aliases={"AMZN MKTPLACE": "AMAZON", "AMAZON COM": "AMAZON"},
        )

        amazon = result[result["Merchant"].eq("AMAZON")]
        assert amazon["Occurrences"].tolist() == [2, 2]
        assert not amazon["Is_One_Off"].any()
        assert result.loc[result["Merchant"].eq("LOCAL BOOKSTORE"), "Is_One_Off"].item()

    def test_unusual_amounts_are_detected_within_repeat_merchants(self) -> None:
        transactions = _explorer_transactions([
            {"Full Description": "Utility power", "Amount": -100.0},
            {"Full Description": "Utility power", "Amount": -100.0},
            {"Full Description": "Utility power", "Amount": -500.0},
            {"Full Description": "One off", "Amount": -10_000.0},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
        )

        unusual = result[result["Is_Unusual"]]
        assert unusual["Amount"].tolist() == [-500.0]
        assert not result.loc[result["Merchant"].eq("ONE OFF"), "Is_Unusual"].item()

    def test_result_filters_do_not_reclassify_repeat_merchants(self) -> None:
        transactions = _explorer_transactions([
            {"Full Description": "Utility power company standard", "Amount": -100.0},
            {"Full Description": "Utility power company standard", "Amount": -100.0},
            {"Full Description": "Utility power company special", "Amount": -500.0},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
            search="special",
            minimum_magnitude=200.0,
        )

        assert result["Amount"].tolist() == [-500.0]
        assert result["Occurrences"].tolist() == [3]
        assert not result["Is_One_Off"].item()
        assert result["Is_Unusual"].item()

    def test_refunds_and_reversals_follow_type_and_amount_sign(self) -> None:
        transactions = _explorer_transactions([
            {"Amount": 25.0, "Type": "Expense", "Full Description": "Refund"},
            {"Amount": -50.0, "Type": "Income", "Full Description": "Income reversal"},
            {"Amount": 100.0, "Type": "Transfer", "Full Description": "Transfer"},
        ])

        result = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
        )

        assert result.set_index("Full Description")["Is_Reversal"].to_dict() == {
            "Transfer": False,
            "Income reversal": True,
            "Refund": True,
        }

    def test_focus_modes_filter_the_same_annotated_inventory(self) -> None:
        transactions = _explorer_transactions([
            {"Full Description": "Repeat", "Amount": -100.0},
            {"Full Description": "Repeat", "Amount": -100.0},
            {"Full Description": "Repeat", "Amount": -500.0},
            {"Full Description": "One off", "Amount": -200.0},
            {"Full Description": "Refund", "Amount": 25.0},
        ])
        inventory = build_transaction_inventory(
            transactions,
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-12-31", tz="UTC"),
        )

        assert filter_transaction_focus(inventory, "Largest", largest_count=2)[
            "Amount"
        ].tolist() == [-500.0, -200.0]
        assert set(
            filter_transaction_focus(inventory, "One-off merchants")["Merchant"]
        ) == {
            "ONE OFF",
            "REFUND",
        }
        assert filter_transaction_focus(inventory, "Unusual amounts")[
            "Amount"
        ].tolist() == [-500.0]
        assert filter_transaction_focus(inventory, "Refunds / reversals")[
            "Amount"
        ].tolist() == [25.0]
        with pytest.raises(ValueError, match="Unsupported transaction focus"):
            filter_transaction_focus(inventory, "Mystery")

    def test_summary_reconciles_raw_cash_directions(self) -> None:
        transactions = _explorer_transactions([
            {"Amount": -100.0},
            {"Amount": 20.0, "Type": "Expense"},
            {"Amount": 500.0, "Type": "Income"},
            {"Amount": -50.0, "Type": "Income"},
            {"Amount": -200.0, "Type": "Transfer"},
            {"Amount": 200.0, "Type": "Transfer"},
        ])

        summary = summarize_transaction_inventory(transactions)

        assert summary == {
            "transaction_count": 6,
            "inflow": pytest.approx(720.0),
            "outflow": pytest.approx(350.0),
            "net_amount": pytest.approx(370.0),
            "median_magnitude": pytest.approx(150.0),
        }

    def test_breakdown_summarizes_current_results(self) -> None:
        transactions = _explorer_transactions([
            {"Group": "Food", "Amount": -100.0},
            {"Group": "Food", "Amount": 25.0},
            {"Group": "Income", "Amount": 500.0, "Type": "Income"},
        ])

        result = build_transaction_breakdown(transactions, "Group")

        food = result.set_index("Entity").loc["Food"]
        assert food["Transactions"] == 2
        assert food["Outflow"] == pytest.approx(100.0)
        assert food["Inflow"] == pytest.approx(25.0)
        assert food["Net_Amount"] == pytest.approx(-75.0)
        assert result["Share"].sum() == pytest.approx(100.0)
        with pytest.raises(ValueError, match="Unsupported transaction breakdown"):
            build_transaction_breakdown(transactions, "Institution")
