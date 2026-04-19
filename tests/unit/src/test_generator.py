"""Self-tests for ``scripts/generate_test_fixtures.py``.

These tests do NOT read the source xlsx. They exercise the generator's pure
helpers against synthetic inputs and validate invariants on the committed
fixture artifacts under ``tests/data/fixtures/``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_test_fixtures import (
    AccountAnonymization,
    SYNTHETIC_ZERO_ACCOUNT,
    _composite_key_display,
    _format_money,
    _index_to_letters,
    _normalize_token,
    anonymize_balance_history,
    anonymize_description,
    anonymize_transactions,
    build_account_mapping,
    build_token_mapping,
    collect_description_tokens,
)


_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures"


# ---------------------------------------------------------------------------
# Pure-helper tests
# ---------------------------------------------------------------------------


class TestNormalizeToken:
    """``_normalize_token`` strips punctuation and lowercases."""

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
        pytest.skip("Fixtures not generated yet -- run scripts/generate_test_fixtures.py")
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
