"""Tests for merchant enrichment and analysis."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.merchants import (
    build_merchant_aliases,
    build_merchant_description_breakdown,
    build_merchant_dimension_breakdown,
    build_merchant_monthly_comparison,
    build_merchant_overview,
    enrich_with_merchant,
    normalize_merchant_name,
    summarize_merchant_period,
)
from src.page_helpers import extract_merchant_name
from tests._helpers import _make_merchant_df


class TestExtractMerchantName:
    def test_first_word(self) -> None:
        assert extract_merchant_name("KROGER #1234 STORE", "first_word") == "KROGER"

    def test_first_two(self) -> None:
        assert extract_merchant_name("KROGER #1234 STORE", "first_two") == "KROGER #1234"

    def test_first_three(self) -> None:
        assert extract_merchant_name("KROGER #1234 STORE", "first_three") == "KROGER #1234 STORE"

    def test_nan_returns_unknown(self) -> None:
        assert extract_merchant_name(np.nan, "first_word") == "Unknown"

    def test_empty_returns_unknown(self) -> None:
        assert extract_merchant_name("", "first_word") == "Unknown"

    def test_whitespace_only_returns_unknown(self) -> None:
        assert extract_merchant_name("   ", "first_word") == "Unknown"

    def test_unknown_method_falls_back_to_first_word(self) -> None:
        """Invalid method argument falls through to first_word extraction."""
        assert extract_merchant_name("ACME STORE", "gibberish_method") == "ACME"

    def test_single_word_first_two_returns_single(self) -> None:
        """first_two on a single-word description returns that single word."""
        assert extract_merchant_name("AMAZON", "first_two") == "AMAZON"

    def test_single_word_first_three_returns_single(self) -> None:
        """first_three on a single-word description returns that single word."""
        assert extract_merchant_name("AMAZON", "first_three") == "AMAZON"

    def test_none_returns_unknown(self) -> None:
        """None (not just NaN) is handled by the pd.isna check."""
        assert extract_merchant_name(None, "first_word") == "Unknown"

    def test_integer_input_coerced_to_string(self) -> None:
        """Non-string, non-NaN input (like an int) is coerced to string and split."""
        # str(12345) = "12345" → single "word" → returns "12345"
        assert extract_merchant_name(12345, "first_word") == "12345"

    def test_leading_trailing_whitespace_ignored(self) -> None:
        """split() ignores leading/trailing whitespace."""
        assert extract_merchant_name("   AMAZON   ORDER   ", "first_two") == "AMAZON ORDER"

    def test_multiple_internal_spaces_collapsed_by_split(self) -> None:
        """str.split() collapses runs of whitespace."""
        assert extract_merchant_name("UBER    *TRIP    NYC", "first_three") == "UBER *TRIP NYC"

    def test_normalized_removes_payment_noise_and_ids(self) -> None:
        assert normalize_merchant_name("POS PURCHASE KROGER #1234 STORE") == "KROGER STORE"


class TestEnrichWithMerchant:
    def test_adds_merchant_column(self) -> None:
        df = _make_merchant_df()
        enriched = enrich_with_merchant(df, "first_word")
        assert "Merchant" in enriched.columns
        assert "KROGER" in enriched["Merchant"].values

    def test_does_not_mutate_input(self) -> None:
        df = _make_merchant_df()
        _ = enrich_with_merchant(df, "first_word")
        assert "Merchant" not in df.columns

    def test_first_two_method(self) -> None:
        df = _make_merchant_df()
        enriched = enrich_with_merchant(df, "first_two")
        assert "KROGER #1234" in enriched["Merchant"].values

    def test_aliases_combine_description_variants(self) -> None:
        transactions = pd.DataFrame(
            {
                "Full Description": [
                    "AMZN MKTPLACE PMTS SEATTLE",
                    "AMAZON.COM ORDER 12345",
                    "ASCEND STORE 4421",
                ]
            }
        )
        aliases = build_merchant_aliases(
            {
                "Amazon": ["AMZN MKTPLACE", "AMAZON.COM"],
                "Ascend": ["ASCEND"],
            }
        )

        enriched = enrich_with_merchant(
            transactions,
            "normalized",
            aliases=aliases,
        )

        assert enriched["Merchant"].tolist() == ["AMAZON", "AMAZON", "ASCEND"]

    def test_normalized_method_removes_the_refund_marker(self) -> None:
        transactions = pd.DataFrame(
            {
                "Full Description": [
                    "POS PURCHASE KROGER #1234 STORE",
                    "KROGER #1234 STORE REFUND",
                ]
            }
        )

        enriched = enrich_with_merchant(
            transactions,
            "normalized",
        )

        assert enriched["Merchant"].tolist() == ["KROGER STORE", "KROGER STORE"]
        assert normalize_merchant_name("Refund") == "REFUND"


class TestMerchantAliases:
    def test_builds_normalized_rules_from_strings_and_lists(self) -> None:
        assert build_merchant_aliases(
            {
                "Amazon": ["AMZN MKTPLACE", "Amazon.com"],
                "Ascend": "ASCEND #1234",
            }
        ) == {
            "AMZN MKTPLACE": "AMAZON",
            "AMAZON COM": "AMAZON",
            "ASCEND": "ASCEND",
        }

    def test_more_specific_rule_wins_regardless_of_configuration_order(self) -> None:
        aliases = build_merchant_aliases(
            {
                "Amazon": ["AMAZON"],
                "Amazon Prime": ["AMAZON PRIME"],
            }
        )

        assert normalize_merchant_name("AMAZON PRIME MEMBERSHIP", aliases=aliases) == "AMAZON PRIME"

    def test_conflicting_patterns_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="maps to both AMAZON and AWS"):
            build_merchant_aliases(
                {
                    "Amazon": ["AMZN"],
                    "AWS": ["amzn"],
                }
            )

    @pytest.mark.parametrize(
        "config",
        [
            {"": ["AMAZON"]},
            {"Amazon": []},
            {"Amazon": [1]},
            {"Amazon": 1},
            {"Amazon": ["POS PURCHASE"]},
        ],
    )
    def test_invalid_alias_configuration_is_rejected(self, config: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            build_merchant_aliases(config)


def _merchant_ledger(*, comparison: bool = False) -> pd.DataFrame:
    if comparison:
        return pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-10-05", "2024-11-12"], utc=True),
                "Month": ["2024-10", "2024-11"],
                "Merchant": ["MARKET", "CAFE"],
                "Included": [True, True],
                "Net_Spend": [60.0, 100.0],
                "Category": ["Groceries", "Restaurants"],
                "Group": ["Food", "Food"],
                "Account": ["Card", "Card"],
                "Full Description": ["MARKET #1", "CAFE MAIN"],
            }
        )
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2025-01-05", "2025-03-08", "2025-02-12", "2025-02-20"],
                utc=True,
            ),
            "Month": ["2025-01", "2025-03", "2025-02", "2025-02"],
            "Merchant": ["MARKET", "MARKET", "CAFE", "EXCLUDED"],
            "Included": [True, True, True, False],
            "Net_Spend": [100.0, -20.0, 50.0, 999.0],
            "Category": ["Groceries", "Groceries", "Restaurants", "Travel"],
            "Group": ["Food", "Food", "Food", "Travel"],
            "Account": ["Card", "Card", "Checking", "Card"],
            "Full Description": [
                "MARKET #1",
                "MARKET REFUND",
                "CAFE MAIN",
                "EXCLUDED HOTEL",
            ],
        }
    )


class TestMerchantPeriodAnalysis:
    def test_overview_reconciles_refunds_exclusions_and_comparison(self) -> None:
        overview = build_merchant_overview(
            _merchant_ledger(),
            _merchant_ledger(comparison=True),
            months=["2025-01", "2025-02", "2025-03"],
        )

        assert overview["Merchant"].tolist() == ["MARKET", "CAFE"]
        market = overview.iloc[0]
        assert market["Spending"] == pytest.approx(80.0)
        assert market["Comparison_Spending"] == pytest.approx(60.0)
        assert market["Change"] == pytest.approx(20.0)
        assert market["Change_Pct"] == pytest.approx(100 / 3)
        assert market["Transactions"] == 2
        assert market["Monthly_Trend"] == [100.0, 0.0, -20.0]
        assert market["Primary_Category"] == "Groceries"
        assert market["Primary_Account"] == "Card"
        assert "EXCLUDED" not in overview["Merchant"].values
        assert overview["Spending"].sum() == pytest.approx(130.0)

    def test_summary_uses_period_months_and_repeat_spending(self) -> None:
        overview = build_merchant_overview(
            _merchant_ledger(),
            _merchant_ledger(comparison=True),
            months=["2025-01", "2025-02", "2025-03"],
        )

        summary = summarize_merchant_period(overview, num_months=3)

        assert summary["total_spending"] == pytest.approx(130.0)
        assert summary["average_monthly_spending"] == pytest.approx(130 / 3)
        assert summary["merchant_count"] == 2
        assert summary["repeat_spending_share"] == pytest.approx(80 / 130 * 100)

    def test_monthly_comparison_aligns_period_positions(self) -> None:
        result = build_merchant_monthly_comparison(
            _merchant_ledger(),
            _merchant_ledger(comparison=True),
            merchant="MARKET",
            current_months=["2025-01", "2025-02", "2025-03"],
            comparison_months=["2024-10", "2024-11", "2024-12"],
        )

        assert result["Current_Spending"].tolist() == [100.0, 0.0, -20.0]
        assert result["Comparison_Spending"].tolist() == [60.0, 0.0, 0.0]
        assert result["Current_Transactions"].tolist() == [1, 0, 1]
        assert result["Month_Label"].tolist() == ["Jan 2025", "Feb 2025", "Mar 2025"]

    def test_breakdowns_reconcile_to_selected_merchant(self) -> None:
        category = build_merchant_dimension_breakdown(_merchant_ledger(), merchant="MARKET", dimension="Category")
        account = build_merchant_dimension_breakdown(_merchant_ledger(), merchant="MARKET", dimension="Account")
        descriptions = build_merchant_description_breakdown(_merchant_ledger(), merchant="MARKET")

        assert category.to_dict("records") == [
            {
                "Entity": "Groceries",
                "Spending": 80.0,
                "Share": 100.0,
                "Transactions": 2,
            }
        ]
        assert account["Spending"].sum() == pytest.approx(80.0)
        assert descriptions["Spending"].sum() == pytest.approx(80.0)
        assert descriptions["Description"].tolist() == [
            "MARKET #1",
            "MARKET REFUND",
        ]

    def test_invalid_breakdown_dimension_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsupported merchant breakdown"):
            build_merchant_dimension_breakdown(_merchant_ledger(), merchant="MARKET", dimension="Institution")

    def test_empty_outputs_keep_stable_schemas(self) -> None:
        empty = _merchant_ledger().iloc[0:0]

        overview = build_merchant_overview(
            empty,
            empty,
            months=["2025-01"],
        )
        history = build_merchant_monthly_comparison(
            empty,
            empty,
            merchant="MARKET",
            current_months=["2025-01"],
            comparison_months=["2024-01"],
        )
        breakdown = build_merchant_dimension_breakdown(empty, merchant="MARKET", dimension="Category")
        descriptions = build_merchant_description_breakdown(empty, merchant="MARKET")

        assert overview.columns.tolist() == [
            "Merchant",
            "Spending",
            "Share",
            "Average_Monthly",
            "Comparison_Spending",
            "Change",
            "Change_Pct",
            "Transactions",
            "Average_Transaction",
            "Primary_Category",
            "Primary_Group",
            "Primary_Account",
            "First_Transaction",
            "Last_Transaction",
            "Monthly_Trend",
        ]
        assert history.shape == (1, 8)
        assert history["Current_Spending"].tolist() == [0.0]
        assert breakdown.columns.tolist() == [
            "Entity",
            "Spending",
            "Share",
            "Transactions",
        ]
        assert descriptions.columns.tolist() == [
            "Description",
            "Spending",
            "Transactions",
            "Last_Transaction",
        ]
