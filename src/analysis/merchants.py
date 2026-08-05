"""Merchant name cleanup and merchant-level spending analysis."""

from collections.abc import Mapping
import re

import pandas as pd

from src.custom_types import MerchantSummary

_MERCHANT_NOISE_RE = re.compile(
    r"\b("
    r"POS|DEBIT|CARD|PURCHASE|AUTH|AUTHORIZATION|CHECKCARD|VISA|MC|SQ|TST|PAYPAL|"
    r"ONLINE|PAYMENT|RECURRING|PPD|CCD|ACH"
    r")\b",
    re.IGNORECASE,
)
_TRAILING_ID_RE = re.compile(r"[#*]?\s*\d{3,}\b")
_LONG_CODE_RE = re.compile(r"\b(?=[A-Z0-9]*\d)[A-Z0-9]{8,}\b")


def _is_missing_description(value: object) -> bool:
    """Return whether a scalar transaction description is missing."""
    return (
        value is None
        or value is pd.NA
        or value is pd.NaT
        or (isinstance(value, float) and pd.isna(value))
    )


def extract_merchant_name(description: object, method: str = "first_word") -> str:
    """Extract a merchant token from a transaction description."""
    if _is_missing_description(description):
        return "Unknown"

    words = str(description).split()
    if not words:
        return "Unknown"

    if method == "normalized":
        return normalize_merchant_name(description)
    if method == "first_word":
        return words[0]
    if method == "first_two":
        return " ".join(words[:2])
    if method == "first_three":
        return " ".join(words[:3])
    return words[0]


def normalize_merchant_name(
    description: object,
    *,
    aliases: Mapping[str, str] | None = None,
    method: str = "first_three",
) -> str:
    """Return a stable merchant key for analysis.

    The cleanup is intentionally deterministic: uppercase, strip common payment
    processor words, remove obvious numeric identifiers, and collapse spaces.
    """
    if _is_missing_description(description):
        return "Unknown"

    text = str(description).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9#*]+", " ", text)
    text = _MERCHANT_NOISE_RE.sub(" ", text)
    text = _TRAILING_ID_RE.sub(" ", text)
    text = _LONG_CODE_RE.sub(" ", text)
    text = text.replace("#", " ").replace("*", " ")
    text = " ".join(text.split())
    if not text:
        return "Unknown"

    aliases = aliases or {}
    for pattern, replacement in aliases.items():
        if pattern.upper() in text:
            return replacement

    words = text.split()
    if method == "first_word":
        return words[0]
    if method == "first_two":
        return " ".join(words[:2])
    return " ".join(words[:3])


def enrich_with_merchant(
    df: pd.DataFrame,
    extraction_method: str = "first_two",
) -> pd.DataFrame:
    """Add a ``Merchant`` column derived from ``Full Description``."""
    enriched = df.copy()
    enriched["Merchant"] = enriched["Full Description"].apply(
        lambda x: extract_merchant_name(x, extraction_method)
    )
    return enriched


def analyze_merchants(
    df: pd.DataFrame,
    min_transactions: int = 1,
) -> pd.DataFrame:
    """Aggregate spending statistics by merchant."""
    df_expenses = df[df["Type"] == "Expense"].copy()

    if df_expenses.empty:
        return pd.DataFrame()

    merchant_stats = df_expenses.groupby("Merchant").agg(
        Total_Spent=("Amount", "sum"),
        Avg_Transaction=("Amount", "mean"),
        Num_Transactions=("Amount", "count"),
        First_Transaction=("Date", "min"),
        Last_Transaction=("Date", "max"),
        Primary_Category=("Category", _mode_or_first),
        Primary_Account=("Account", _mode_or_first),
    ).reset_index()

    merchant_stats["Total_Spent"] = merchant_stats["Total_Spent"].abs()
    merchant_stats["Avg_Transaction"] = merchant_stats["Avg_Transaction"].abs()
    merchant_stats = merchant_stats[merchant_stats["Num_Transactions"] >= min_transactions]
    merchant_stats = merchant_stats.sort_values("Total_Spent", ascending=False)
    merchant_stats["Days_Active"] = (
        merchant_stats["Last_Transaction"] - merchant_stats["First_Transaction"]
    ).dt.days

    return merchant_stats


def summarize_merchants(merchant_stats: pd.DataFrame) -> MerchantSummary:
    """Return headline spending metrics for the included merchants."""
    if merchant_stats.empty:
        return MerchantSummary(
            count=0,
            total_spent=0.0,
            top_merchant="",
            top_merchant_spent=0.0,
            average_spent=0.0,
        )
    total_spent = float(merchant_stats["Total_Spent"].sum())
    return MerchantSummary(
        count=len(merchant_stats),
        total_spent=total_spent,
        top_merchant=str(merchant_stats.iloc[0]["Merchant"]),
        top_merchant_spent=float(merchant_stats.iloc[0]["Total_Spent"]),
        average_spent=total_spent / len(merchant_stats),
    )


def prepare_merchant_timeline(
    transactions: pd.DataFrame,
    merchant_stats: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """Return absolute monthly spending for the largest merchants."""
    merchants = merchant_stats.head(top_n)["Merchant"]
    top_transactions = transactions[
        transactions["Merchant"].isin(merchants)
        & (transactions["Type"] == "Expense")
    ].copy()
    if top_transactions.empty:
        return pd.DataFrame(columns=["Merchant", "Month", "Amount_Abs"])
    top_transactions["Amount_Abs"] = top_transactions["Amount"].abs()
    return (
        top_transactions.groupby(["Merchant", "Month"])["Amount_Abs"]
        .sum()
        .reset_index()
    )


def _mode_or_first(values: pd.Series) -> object:
    """Return the mode for a series, falling back to its first value."""
    mode = values.mode()
    if not mode.empty:
        return mode.iloc[0]
    if not values.empty:
        return values.iloc[0]
    return "Unknown"
