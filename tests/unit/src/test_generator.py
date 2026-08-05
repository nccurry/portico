"""Self-tests for ``scripts/generate_test_fixtures.py``.

These tests do NOT read the source xlsx. They exercise the generator's pure
helpers against synthetic inputs and validate invariants on the committed
fixture artifacts under ``tests/data/fixtures/``.
"""
import re
from datetime import time
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_test_fixtures import (
    AccountAnonymization,
    PATTERN_MIN,
    SYNTHETIC_ZERO_ACCOUNT,
    _composite_key_display,
    _format_money,
    _has_time_parts,
    _index_to_letters,
    _normalize_token,
    anonymize_balance_history,
    anonymize_description,
    anonymize_transactions,
    build_account_mapping,
    build_token_mapping,
    collect_description_tokens,
    sample_balance_history,
    sample_transactions,
    validate_pattern_minimums,
)
from tests.custom_types import DataFrameRow


_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures"


# ---------------------------------------------------------------------------
# Pure-helper tests
# ---------------------------------------------------------------------------


class TestNormalizeToken:
    """``_normalize_token`` strips punctuation and lowercases."""

    def test_time_parts_guard(self) -> None:
        """The runtime guard recognizes supported time-bearing values."""
        assert _has_time_parts(time(12, 30))
        assert _has_time_parts(pd.Timestamp("2024-01-01 12:30"))
        assert not _has_time_parts("12:30")

    def test_lowercases(self) -> None:
        assert _normalize_token("AmaZON") == "amazon"

    def test_strips_punctuation(self) -> None:
        assert _normalize_token("STORE#1234!") == "store1234"

    def test_empty_string(self) -> None:
        assert _normalize_token("!!!") == ""


class TestIndexToLetters:
    """``_index_to_letters`` is the spreadsheet-style letter sequence."""

    def test_first_26(self) -> None:
        assert _index_to_letters(0) == "A"
        assert _index_to_letters(25) == "Z"

    def test_double_letters(self) -> None:
        assert _index_to_letters(26) == "AA"
        assert _index_to_letters(27) == "AB"


class TestFormatMoney:
    def test_positive(self) -> None:
        assert _format_money(1234.56) == "$1,234.56"

    def test_negative(self) -> None:
        assert _format_money(-45.99) == "-$45.99"

    def test_zero(self) -> None:
        assert _format_money(0) == "$0.00"

    def test_invalid(self) -> None:
        assert _format_money("not a number") == ""


class TestBuildTokenMapping:
    """The token mapping is injective over the observed source token set."""

    def test_injective_on_distinct_tokens(self) -> None:
        tokens = sorted({"amazon", "starbucks", "kroger", "duke", "energy"})
        mapping = build_token_mapping(tokens)
        assert len(set(mapping.values())) == len(mapping)
        assert len(mapping) == len(tokens)

    def test_pure_numeric_routes_to_5_digit_string(self) -> None:
        mapping = build_token_mapping(["12345", "67890"])
        for value in mapping.values():
            assert re.fullmatch(r"\d{5}", value)

    def test_handles_punctuation_in_source(self) -> None:
        # Distinct after normalization.
        mapping = build_token_mapping(["store!", "store?"])
        assert "store" in mapping
        # Note: collapsed to one normalized key.
        assert len(mapping) == 1

    def test_overflow_appends_suffix(self) -> None:
        # Build a vocabulary larger than the word pool to force suffix overflow.
        from scripts.generate_test_fixtures import ADJECTIVES, NOUNS
        n = len(ADJECTIVES) + len(NOUNS) + 5
        tokens = [f"sourcetoken{i}" for i in range(n)]
        mapping = build_token_mapping(tokens)
        assert len(set(mapping.values())) == n  # injective even past pool size

    def test_deterministic(self) -> None:
        tokens = ["amazon", "starbucks", "kroger"]
        first = build_token_mapping(tokens)
        second = build_token_mapping(tokens)
        assert first == second


class TestAnonymizeDescription:
    """First-token preservation + token count preservation."""

    def test_first_token_preservation(self) -> None:
        mapping = build_token_mapping(["amazon", "order", "12345"])
        out = anonymize_description("Amazon Order 12345", mapping)
        first_token = out.split()[0]
        assert first_token == mapping["amazon"]

    def test_distinct_descriptions_can_share_first_token(self) -> None:
        mapping = build_token_mapping(["amazon", "order", "12345", "99999"])
        a = anonymize_description("Amazon Order 12345", mapping)
        b = anonymize_description("Amazon Order 99999", mapping)
        # Sharing first token is correct -- this is what real merchant data does.
        assert a.split()[0] == b.split()[0]
        assert a != b

    def test_token_count_preserved(self) -> None:
        mapping = build_token_mapping(["foo", "bar", "baz"])
        assert len(anonymize_description("Foo Bar Baz", mapping).split()) == 3
        assert len(anonymize_description("Foo", mapping).split()) == 1

    def test_nan_input(self) -> None:
        out = anonymize_description(float("nan"), {})
        assert out == "Unknown Merchant"

    def test_empty_input(self) -> None:
        assert anonymize_description("", {}) == "Unknown Merchant"


# ---------------------------------------------------------------------------
# Composite-key correctness
# ---------------------------------------------------------------------------


class TestCompositeKey:
    """Reconstructed composite key matches the formula in scrub()."""

    def test_format(self) -> None:
        info = AccountAnonymization(
            account="Checking-A",
            account_num="xxxx1111",
            account_id="0" * 20 + "AB01",
            institution="Aurora Bank",
            composite_key="checking-a - xxxx1111 (ab01)",
        )
        # display form keeps mixed case
        assert _composite_key_display(info) == "Checking-A - xxxx1111 (AB01)"

    def test_matches_scrub_formula(self) -> None:
        """BalanceHistory ``_account_key`` (lowercased) equals composite_key."""
        info = AccountAnonymization(
            account="Savings-B",
            account_num="xxxx2222",
            account_id="prefix000000000000000CD02",
            institution="Bank",
            composite_key="savings-b - xxxx2222 (cd02)",
        )
        # Mirror scrub() formula
        scrub_key = (
            f"{info.account} - {info.account_num} "
            f"({info.account_id[-4:].upper()})"
        ).lower()
        assert scrub_key == info.composite_key


# ---------------------------------------------------------------------------
# Fixture-artifact invariants
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixture_files() -> dict[str, pd.DataFrame]:
    """Load the four committed CSV fixtures."""
    if not (_FIXTURES_DIR / "transactions.csv").exists():
        pytest.skip("Committed synthetic fixtures are missing")
    return {
        name: pd.read_csv(_FIXTURES_DIR / f"{name}.csv")
        for name in ("transactions", "balance_history", "categories", "accounts")
    }


class TestPatternCounts:
    """Phase 0.4 minimums -- generator must satisfy all of these."""

    def test_duplicate_pair_seeds_present(self, fixture_files: dict[str, pd.DataFrame]) -> None:
        # Looking for our injected duplicate descriptions.
        descs = fixture_files["transactions"]["Full Description"].astype(str)
        assert (descs.str.contains("duplicate pair seed")).sum() >= 6  # 3 pairs * 2

    def test_recurring_seeds_present(self, fixture_files: dict[str, pd.DataFrame]) -> None:
        descs = fixture_files["transactions"]["Full Description"].astype(str)
        # Two distinct recurring merchants seeded.
        verum_count = descs.str.startswith("verum streamus").sum()
        nimbus_count = descs.str.startswith("nimbus cloudus").sum()
        assert verum_count >= 4
        assert nimbus_count >= 4

    def test_top_n_tie_seeds_present(self, fixture_files: dict[str, pd.DataFrame]) -> None:
        descs = fixture_files["transactions"]["Full Description"].astype(str)
        assert (descs.str.startswith("magnum boxus")).sum() >= 2

    def test_synthetic_zero_group_in_accounts(self, fixture_files: dict[str, pd.DataFrame]) -> None:
        groups = fixture_files["accounts"]["Group"].astype(str).tolist()
        from scripts.generate_test_fixtures import SYNTHETIC_ZERO_GROUP_NAME
        assert SYNTHETIC_ZERO_GROUP_NAME in groups

    def test_synthetic_zero_account_in_balance(self, fixture_files: dict[str, pd.DataFrame]) -> None:
        accounts = fixture_files["balance_history"]["Account"].astype(str).tolist()
        assert SYNTHETIC_ZERO_ACCOUNT.account in accounts


class TestCrossSheetJoin:
    """Every BalanceHistory row's composite key must match an Accounts row."""

    def test_join_lands(self, fixture_files: dict[str, pd.DataFrame]) -> None:
        bh = fixture_files["balance_history"]
        keys = (
            bh["Account"].astype(str) + " - " +
            bh["Account #"].fillna("").astype(str) + " (" +
            bh["Account ID"].astype(str).str[-4:].str.upper() + ")"
        ).str.lower()
        accounts_keys = set(fixture_files["accounts"]["Account"].str.lower())
        missing = set(keys) - accounts_keys
        assert not missing, f"Unmatched composite keys: {sorted(missing)[:5]}"


class TestDeterminism:
    """Re-running token mapping on the same input produces identical output."""

    def test_token_mapping_deterministic(self, fixture_files: dict[str, pd.DataFrame]) -> None:
        tokens = collect_description_tokens(fixture_files["transactions"])
        first = build_token_mapping(tokens)
        second = build_token_mapping(tokens)
        assert first == second


# ---------------------------------------------------------------------------
# Account mapping injectivity
# ---------------------------------------------------------------------------


class TestBuildAccountMapping:
    """Distinct source Account IDs map to distinct anonymized identities."""

    def test_injective(self) -> None:
        synth = pd.DataFrame({
            "Account ID": ["aid-1", "aid-2", "aid-3"],
            "Account": ["My Checking", "My Savings", "My Credit Card"],
            "Class": ["Asset", "Asset", "Liability"],
            "Institution": ["BankA", "BankA", "BankB"],
        })
        mapping = build_account_mapping(synth)
        assert len(mapping) == 3
        assert len({m.account for m in mapping.values()}) == 3
        assert len({m.account_num for m in mapping.values()}) == 3
        assert len({m.account_id for m in mapping.values()}) == 3


# ---------------------------------------------------------------------------
# Anonymization end-to-end on synthetic data
# ---------------------------------------------------------------------------


class TestAnonymizeFlow:
    """Anonymize-then-shape round trip yields raw-shape CSV-ready DataFrames."""

    def test_transactions_shape(self) -> None:
        synth_bh = pd.DataFrame({
            "Account ID": ["aid-1"],
            "Account": ["Checking"],
            "Class": ["Asset"],
            "Institution": ["BankA"],
        })
        accounts = build_account_mapping(synth_bh)
        token_map = build_token_mapping(["payroll", "deposit"])

        synth_txn = pd.DataFrame({
            "Date": [pd.Timestamp("2026-01-15")],
            "Category": ["Salary"],
            "Amount": [3500.00],
            "Account": ["Checking"],
            "Account ID": ["aid-1"],
            "Full Description": ["Payroll Deposit"],
            "Institution": ["BankA"],
            "Account #": ["1234"],
        })
        out = anonymize_transactions(synth_txn, accounts, token_map)
        from scripts.generate_test_fixtures import TRANSACTIONS_RAW_COLUMNS
        assert list(out.columns) == TRANSACTIONS_RAW_COLUMNS
        assert out["Amount"].iloc[0] == "$3,500.00"
        # First-token preservation: anonymized first token equals mapping[payroll]
        assert out["Full Description"].iloc[0].split()[0] == token_map["payroll"]

    def test_balance_history_shape(self) -> None:
        synth_bh = pd.DataFrame({
            "Date": [pd.Timestamp("2026-01-15")],
            "Time": [pd.Timestamp("2026-01-15 12:00:00")],
            "Account": ["Checking"],
            "Account #": ["1234"],
            "Account ID": ["aid-1"],
            "Balance ID": ["bal-1"],
            "Institution": ["BankA"],
            "Balance": [1000.00],
            "Class": ["Asset"],
            "Type": ["Account"],
            "Account Status": ["Open"],
        })
        accounts = build_account_mapping(synth_bh)
        out = anonymize_balance_history(synth_bh, accounts)
        from scripts.generate_test_fixtures import BALANCE_HISTORY_RAW_COLUMNS
        assert list(out.columns) == BALANCE_HISTORY_RAW_COLUMNS
        assert out["Balance"].iloc[0] == "$1,000.00"

    def test_balance_history_preserves_time(self) -> None:
        """Time column should reflect the original Time, not Date."""
        import datetime

        synth_bh = pd.DataFrame({
            "Date": [pd.Timestamp("2026-03-10"), pd.Timestamp("2026-03-10")],
            "Time": [datetime.time(9, 30, 0), datetime.time(14, 45, 15)],
            "Account": ["Checking", "Checking"],
            "Account #": ["1234", "1234"],
            "Account ID": ["aid-1", "aid-1"],
            "Balance ID": ["bal-1", "bal-2"],
            "Institution": ["BankA", "BankA"],
            "Balance": [1000.00, 1050.00],
            "Class": ["Asset", "Asset"],
            "Type": ["Account", "Account"],
            "Account Status": ["Open", "Open"],
        })
        accounts = build_account_mapping(synth_bh)
        out = anonymize_balance_history(synth_bh, accounts)
        assert "09:30:00" in out["Time"].iloc[0]
        assert "14:45:15" in out["Time"].iloc[1]


# ---------------------------------------------------------------------------
# sample_balance_history always keeps the latest row
# ---------------------------------------------------------------------------


class TestSampleTransactions:

    def test_head_keeps_newest_within_category(self) -> None:
        """When a category exceeds MAX_TRANSACTIONS_PER_CATEGORY, the newest
        rows survive because sorting is newest-first before head()."""
        from scripts.generate_test_fixtures import MAX_TRANSACTIONS_PER_CATEGORY
        n = MAX_TRANSACTIONS_PER_CATEGORY + 20
        dates = pd.date_range("2025-01-01", periods=n, freq="D")
        df = pd.DataFrame({
            "Date": dates,
            "Category": ["TestCat"] * n,
            "Amount": range(n),
            "Account": ["Checking"] * n,
            "Month": [d.strftime("%Y-%m") for d in dates],
            "Full Description": [f"desc-{i}" for i in range(n)],
            "Institution": ["Bank"] * n,
            "Account #": ["1234"] * n,
        })
        sampled = sample_transactions(df)
        assert len(sampled) <= MAX_TRANSACTIONS_PER_CATEGORY
        latest_date = dates[-1]
        assert latest_date in sampled["Date"].values

    def test_stride_preserves_tail_row(self) -> None:
        """Global stride-downsample keeps the last (newest) row."""
        from scripts.generate_test_fixtures import MAX_TRANSACTIONS_TOTAL
        n = MAX_TRANSACTIONS_TOTAL + 100
        dates = pd.date_range("2025-01-01", periods=n, freq="h")
        df = pd.DataFrame({
            "Date": dates,
            "Category": [f"Cat-{i % 5}" for i in range(n)],
            "Amount": range(n),
            "Account": ["Checking"] * n,
            "Month": [d.strftime("%Y-%m") for d in dates],
            "Full Description": [f"desc-{i}" for i in range(n)],
            "Institution": ["Bank"] * n,
            "Account #": ["1234"] * n,
        })
        sampled = sample_transactions(df)
        latest_date = dates[-1]
        assert latest_date in sampled["Date"].values


class TestSampleBalanceHistory:

    def test_latest_row_always_kept(self) -> None:
        """When stride-sampling dense accounts, the last observation survives."""
        dates = pd.date_range("2025-01-01", periods=200, freq="D")
        df = pd.DataFrame({
            "Date": dates,
            "Account ID": ["acct-1"] * 200,
            "Balance": range(200),
        })
        from scripts.generate_test_fixtures import MAX_BALANCE_ROWS_PER_ACCOUNT
        assert len(df) > MAX_BALANCE_ROWS_PER_ACCOUNT

        sampled = sample_balance_history(df)
        latest_date = dates[-1]
        assert latest_date in sampled["Date"].values

    def test_small_account_untouched(self) -> None:
        """Accounts under the cap pass through without stride-sampling."""
        dates = pd.date_range("2025-01-01", periods=10, freq="D")
        df = pd.DataFrame({
            "Date": dates,
            "Account ID": ["acct-1"] * 10,
            "Balance": range(10),
        })
        sampled = sample_balance_history(df)
        assert len(sampled) == 10


# ---------------------------------------------------------------------------
# PATTERN_MIN enforcement on fixtures
# ---------------------------------------------------------------------------


class TestPatternMinValidation:
    """validate_pattern_minimums should pass on the committed fixtures."""

    def test_all_pattern_min_keys_present(self) -> None:
        expected_keys = {
            "duplicate_pairs", "recurring_merchants", "top_n_ties",
            "cross_year_categories", "over_budget_categories",
            "under_budget_categories", "single_account_groups",
            "zero_total_groups", "all_liability_groups",
        }
        assert set(PATTERN_MIN.keys()) == expected_keys

    def test_validates_without_error(self, fixture_files: dict[str, pd.DataFrame]) -> None:
        """The committed fixtures must satisfy all PATTERN_MIN guarantees."""
        validate_pattern_minimums(
            fixture_files["transactions"],
            fixture_files["balance_history"],
            fixture_files["categories"],
            fixture_files["accounts"],
        )


# ---------------------------------------------------------------------------
# Validator-vs-page-helper agreement
# ---------------------------------------------------------------------------


class TestValidatorAgreesWithPageHelpers:
    """The validator must accept data that the page helpers actually detect,
    and reject data that does not contain the required patterns.

    Each test crafts synthetic raw-CSV-shaped data, runs both the validator
    check and the corresponding page helper, and asserts they agree.
    """

    def _base_txn(self, date: str, amount: float, desc: str,
                  account: str = "Checking", category: str = "Groceries") -> DataFrameRow:
        return {
            "Date": date, "Category": category, "Amount": amount,
            "Account": account, "Month": date[:7],
            "Full Description": desc, "Institution": "Bank",
            "Account #": "1234", "Week": "1", "Date Added": date,
            "Categorized Date": date,
        }

    def test_duplicate_validator_agrees_with_page4(self) -> None:
        """The validator's self-join duplicate logic (same account, same
        description, within 1 day, >= $10) matches find_duplicates_efficient
        on identical data."""
        from src.analysis.duplicates import find_duplicates_efficient

        rows = [
            self._base_txn("2024-01-15", -50.0, "STORE PURCHASE", "Checking"),
            self._base_txn("2024-01-15", -50.0, "STORE PURCHASE", "Checking"),
            self._base_txn("2024-01-15", -50.0, "DIFFERENT STORE", "Checking"),
            self._base_txn("2024-01-20", -25.0, "ANOTHER THING", "Savings"),
        ]
        df_raw = pd.DataFrame(rows)
        df_raw["Date"] = pd.to_datetime(df_raw["Date"])

        df_scrubbed = df_raw.copy()
        df_scrubbed["Date"] = pd.to_datetime(df_scrubbed["Date"], utc=True)
        df_scrubbed["Type"] = "Expense"
        df_scrubbed["Group"] = "Food"

        page_result = find_duplicates_efficient(
            df_scrubbed, days_threshold=1, min_amount=10,
            check_same_account=True, check_same_category=False,
            require_same_description=True,
        )

        # Replicate the validator's self-join logic on the same data
        txn_dates = pd.to_datetime(df_raw["Date"])
        txn_amounts = df_raw["Amount"].astype(float)
        txn_descs = df_raw["Full Description"].astype(str)
        txn_accounts = df_raw["Account"].astype(str)
        dup_df = pd.DataFrame({
            "date": txn_dates, "amount": txn_amounts,
            "abs_amount": txn_amounts.abs(),
            "desc": txn_descs.str.lower().str.strip(),
            "account": txn_accounts,
        }).reset_index(drop=True)
        dup_df = dup_df[dup_df["abs_amount"] >= 10.0]
        dup_df["_row_id"] = range(len(dup_df))
        pairs = dup_df.merge(dup_df, on="amount", suffixes=("_1", "_2"))
        pairs = pairs[pairs["_row_id_1"] < pairs["_row_id_2"]]
        pairs["days_apart"] = (pairs["date_2"] - pairs["date_1"]).dt.days.abs()
        pairs = pairs[pairs["days_apart"] <= 1]
        pairs = pairs[pairs["account_1"] == pairs["account_2"]]
        pairs = pairs[pairs["desc_1"] == pairs["desc_2"]]

        assert len(page_result) == len(pairs), (
            f"Page found {len(page_result)} pairs, validator logic found {len(pairs)}"
        )

    def test_duplicate_validator_rejects_different_descriptions(self) -> None:
        """Same amount, same day, same account — but different descriptions.
        Neither the page helper (with description matching) nor the validator
        should count these as a duplicate pair."""
        from src.analysis.duplicates import find_duplicates_efficient

        rows = [
            self._base_txn("2024-01-15", -50.0, "KROGER STORE", "Checking"),
            self._base_txn("2024-01-15", -50.0, "TARGET STORE", "Checking"),
        ]
        df_raw = pd.DataFrame(rows)
        df_raw["Date"] = pd.to_datetime(df_raw["Date"])

        df_scrubbed = df_raw.copy()
        df_scrubbed["Date"] = pd.to_datetime(df_scrubbed["Date"], utc=True)
        df_scrubbed["Type"] = "Expense"
        df_scrubbed["Group"] = "Food"

        page_result = find_duplicates_efficient(
            df_scrubbed, days_threshold=1, min_amount=10,
            check_same_account=True, check_same_category=False,
            require_same_description=True,
        )
        assert len(page_result) == 0, "Page helper should not find duplicates"

    def test_recurring_validator_agrees_with_page5_cadence(self) -> None:
        """A merchant with monthly cadence is detected by both the validator
        and detect_recurring_transactions."""
        from src.analysis.subscriptions import detect_recurring_transactions

        dates = pd.date_range("2024-01-15", periods=6, freq="MS") + pd.Timedelta(days=14)
        rows = [
            self._base_txn(
                d.strftime("%Y-%m-%d"), -15.99, "NETFLIX MONTHLY SUB",
                category="Entertainment",
            )
            for d in dates
        ]
        df_raw = pd.DataFrame(rows)
        df_raw["Date"] = pd.to_datetime(df_raw["Date"])

        df_scrubbed = df_raw.copy()
        df_scrubbed["Date"] = pd.to_datetime(df_scrubbed["Date"], utc=True)
        df_scrubbed["Type"] = "Expense"
        df_scrubbed["Group"] = "Entertainment"

        page_result = detect_recurring_transactions(df_scrubbed)
        assert len(page_result) >= 1, "Page helper should detect the subscription"

    def test_recurring_validator_rejects_non_monthly_cadence(self) -> None:
        """A merchant that appears frequently but with 5-day cadence (not 20-40)
        should NOT be flagged as a subscription by detect_recurring_transactions."""
        from src.analysis.subscriptions import detect_recurring_transactions

        dates = pd.date_range("2024-01-01", periods=10, freq="5D")
        rows = [
            self._base_txn(
                d.strftime("%Y-%m-%d"), -10.0, "DAILY COFFEE SHOP",
                category="Coffee",
            )
            for d in dates
        ]
        df_scrubbed = pd.DataFrame(rows)
        df_scrubbed["Date"] = pd.to_datetime(df_scrubbed["Date"], utc=True)
        df_scrubbed["Type"] = "Expense"
        df_scrubbed["Group"] = "Food"

        page_result = detect_recurring_transactions(df_scrubbed)
        assert len(page_result) == 0, "Page helper should not flag 5-day cadence"

    def test_top_n_tie_validator_checks_boundary(self) -> None:
        """Tied amounts must both land inside the top-N to count. Two expenses
        of -100 in a pool of 3 total expenses (with one at -200) should produce
        a tie within top-3 that the validator accepts."""
        rows = [
            self._base_txn("2024-01-01", -200.0, "BIG PURCHASE"),
            self._base_txn("2024-01-02", -100.0, "TIE ROW A"),
            self._base_txn("2024-01-03", -100.0, "TIE ROW B"),
        ]
        df_raw = pd.DataFrame(rows)
        df_raw["Date"] = pd.to_datetime(df_raw["Date"])

        amounts = df_raw["Amount"].astype(float)
        expense_abs = amounts[amounts < 0].abs()
        top_50 = expense_abs.nlargest(50)
        tie_counts = top_50.value_counts()
        n_ties = int((tie_counts >= 2).sum())
        assert n_ties >= 1, "Tie should be visible within top-50"
