"""Merchant name cleanup and merchant-level spending analysis."""

from collections.abc import Mapping, Sequence
import re

import pandas as pd

from src.custom_types import MerchantPeriodSummary


MERCHANT_OVERVIEW_COLUMNS = [
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
MERCHANT_MONTHLY_COLUMNS = [
    "Month_Index",
    "Current_Month",
    "Comparison_Month",
    "Month_Label",
    "Current_Spending",
    "Comparison_Spending",
    "Current_Transactions",
    "Comparison_Transactions",
]
MERCHANT_BREAKDOWN_COLUMNS = ["Entity", "Spending", "Share", "Transactions"]
DESCRIPTION_COLUMNS = ["Description", "Spending", "Transactions", "Last_Transaction"]

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
    return value is None or value is pd.NA or value is pd.NaT or (isinstance(value, float) and pd.isna(value))


def _clean_merchant_text(value: object) -> str:
    text = str(value).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9#*]+", " ", text)
    text = _MERCHANT_NOISE_RE.sub(" ", text)
    text = _TRAILING_ID_RE.sub(" ", text)
    text = _LONG_CODE_RE.sub(" ", text)
    text = text.replace("#", " ").replace("*", " ")
    return " ".join(text.split())


def build_merchant_aliases(config: Mapping[str, object]) -> dict[str, str]:
    """Convert canonical-vendor pattern lists into normalized alias rules."""
    aliases: dict[str, str] = {}
    for vendor, configured_patterns in config.items():
        canonical = str(vendor).strip().upper()
        if not canonical:
            raise ValueError("Merchant alias vendor names cannot be blank")
        if isinstance(configured_patterns, str):
            patterns: Sequence[object] = [configured_patterns]
        elif isinstance(configured_patterns, Sequence):
            patterns = configured_patterns
        else:
            raise ValueError(f"Merchant aliases for {canonical} must be a string or list")
        if not patterns:
            raise ValueError(f"Merchant aliases for {canonical} cannot be empty")

        for configured_pattern in patterns:
            if not isinstance(configured_pattern, str):
                raise ValueError(f"Merchant aliases for {canonical} must contain strings")
            pattern = _clean_merchant_text(configured_pattern)
            if not pattern:
                raise ValueError(f"Merchant aliases for {canonical} cannot be blank")
            existing = aliases.get(pattern)
            if existing is not None and existing != canonical:
                raise ValueError(f"Merchant alias {pattern!r} maps to both {existing} and {canonical}")
            aliases[pattern] = canonical
    return aliases


def extract_merchant_name(
    description: object,
    method: str = "first_word",
    *,
    aliases: Mapping[str, str] | None = None,
) -> str:
    """Extract a merchant token from a transaction description."""
    if _is_missing_description(description):
        return "Unknown"

    words = str(description).split()
    if not words:
        return "Unknown"

    if method == "normalized":
        return normalize_merchant_name(description, aliases=aliases)
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

    text = _clean_merchant_text(description)
    if not text:
        return "Unknown"

    aliases = aliases or {}
    normalized_aliases = sorted(
        ((_clean_merchant_text(pattern), str(replacement).strip().upper()) for pattern, replacement in aliases.items()),
        key=lambda item: (-len(item[0]), item[0]),
    )
    for pattern, replacement in normalized_aliases:
        if pattern and pattern in text:
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
    *,
    aliases: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Add a ``Merchant`` column derived from ``Full Description``."""
    enriched = df.copy()
    enriched["Merchant"] = enriched["Full Description"].apply(
        lambda x: extract_merchant_name(x, extraction_method, aliases=aliases)
    )
    return enriched


def _included(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return ledger.copy()
    if "Included" not in ledger:
        return ledger.copy()
    return ledger[ledger["Included"]].copy()


def build_merchant_overview(
    current_ledger: pd.DataFrame,
    comparison_ledger: pd.DataFrame,
    *,
    months: Sequence[str],
) -> pd.DataFrame:
    """Return current and comparison metrics for merchants in the current period."""
    current = _included(current_ledger)
    comparison = _included(comparison_ledger)
    if current.empty:
        return pd.DataFrame(columns=MERCHANT_OVERVIEW_COLUMNS)

    grouped = (
        current.groupby("Merchant", dropna=False)
        .agg(
            Spending=("Net_Spend", "sum"),
            Transactions=("Net_Spend", "size"),
            Primary_Category=("Category", _mode_or_first),
            Primary_Group=("Group", _mode_or_first),
            Primary_Account=("Account", _mode_or_first),
            First_Transaction=("Date", "min"),
            Last_Transaction=("Date", "max"),
        )
        .reset_index()
    )
    comparison_spending = comparison.groupby("Merchant")["Net_Spend"].sum()
    monthly = (
        current.groupby(["Merchant", "Month"])["Net_Spend"]
        .sum()
        .unstack(fill_value=0)
        .reindex(columns=list(months), fill_value=0.0)
        .astype(float)
    )
    monthly_trends: dict[object, list[float]] = {}
    for merchant in monthly.index:
        values = pd.to_numeric(monthly.loc[merchant], errors="coerce").fillna(0.0)
        monthly_trends[merchant] = values.astype(float).tolist()
    total_spending = float(grouped["Spending"].sum())
    month_count = len(months)
    grouped["Share"] = grouped["Spending"].div(total_spending).mul(100) if total_spending else 0.0
    grouped["Average_Monthly"] = grouped["Spending"].div(month_count) if month_count else 0.0
    grouped["Comparison_Spending"] = grouped["Merchant"].map(comparison_spending).fillna(0.0)
    grouped["Change"] = grouped["Spending"] - grouped["Comparison_Spending"]
    grouped["Change_Pct"] = grouped["Change"].div(grouped["Comparison_Spending"].abs().replace(0, pd.NA)).mul(100)
    grouped["Average_Transaction"] = grouped["Spending"].div(grouped["Transactions"])
    grouped["Monthly_Trend"] = grouped["Merchant"].map(monthly_trends)
    return grouped[MERCHANT_OVERVIEW_COLUMNS].sort_values(
        ["Spending", "Merchant"],
        ascending=[False, True],
        ignore_index=True,
    )


def summarize_merchant_period(
    overview: pd.DataFrame,
    *,
    num_months: int,
) -> MerchantPeriodSummary:
    """Return period-level totals from the merchant inventory."""
    if overview.empty:
        return MerchantPeriodSummary(
            total_spending=0.0,
            average_monthly_spending=0.0,
            merchant_count=0,
            repeat_spending_share=0.0,
        )
    total = float(overview["Spending"].sum())
    repeat_total = float(overview.loc[overview["Transactions"] >= 2, "Spending"].sum())
    return MerchantPeriodSummary(
        total_spending=total,
        average_monthly_spending=total / num_months if num_months else 0.0,
        merchant_count=len(overview),
        repeat_spending_share=repeat_total / total * 100 if total else 0.0,
    )


def build_merchant_monthly_comparison(
    current_ledger: pd.DataFrame,
    comparison_ledger: pd.DataFrame,
    *,
    merchant: str,
    current_months: Sequence[str],
    comparison_months: Sequence[str],
) -> pd.DataFrame:
    """Align one merchant's current monthly spending with comparison months."""
    current = _included(current_ledger)
    comparison = _included(comparison_ledger)
    current = current[current["Merchant"].astype(str) == merchant]
    comparison = comparison[comparison["Merchant"].astype(str) == merchant]
    current_spending = current.groupby("Month")["Net_Spend"].sum().reindex(list(current_months), fill_value=0.0)
    comparison_spending = (
        comparison.groupby("Month")["Net_Spend"].sum().reindex(list(comparison_months), fill_value=0.0)
    )
    current_counts = current.groupby("Month").size().reindex(list(current_months), fill_value=0)
    comparison_counts = comparison.groupby("Month").size().reindex(list(comparison_months), fill_value=0)
    rows = [
        {
            "Month_Index": index,
            "Current_Month": current_month,
            "Comparison_Month": comparison_month,
            "Month_Label": pd.Period(current_month, freq="M").strftime("%b %Y"),
            "Current_Spending": float(current_spending.loc[current_month]),
            "Comparison_Spending": float(comparison_spending.loc[comparison_month]),
            "Current_Transactions": int(current_counts.loc[current_month]),
            "Comparison_Transactions": int(comparison_counts.loc[comparison_month]),
        }
        for index, (current_month, comparison_month) in enumerate(zip(current_months, comparison_months, strict=True))
    ]
    return pd.DataFrame(rows, columns=MERCHANT_MONTHLY_COLUMNS)


def build_merchant_dimension_breakdown(
    ledger: pd.DataFrame,
    *,
    merchant: str,
    dimension: str,
) -> pd.DataFrame:
    """Return category, group, or account composition for one merchant."""
    if dimension not in {"Category", "Group", "Account"}:
        raise ValueError(f"Unsupported merchant breakdown: {dimension}")
    included = _included(ledger)
    included = included[included["Merchant"].astype(str) == merchant]
    if included.empty:
        return pd.DataFrame(columns=MERCHANT_BREAKDOWN_COLUMNS)
    grouped = (
        included.groupby(dimension, dropna=False)
        .agg(Spending=("Net_Spend", "sum"), Transactions=("Net_Spend", "size"))
        .reset_index()
        .rename(columns={dimension: "Entity"})
    )
    total = float(grouped["Spending"].sum())
    grouped["Share"] = grouped["Spending"].div(total).mul(100) if total else 0.0
    return grouped[MERCHANT_BREAKDOWN_COLUMNS].sort_values(
        ["Spending", "Entity"],
        ascending=[False, True],
        ignore_index=True,
    )


def build_merchant_description_breakdown(
    ledger: pd.DataFrame,
    *,
    merchant: str,
) -> pd.DataFrame:
    """Return raw transaction-description variants for one normalized merchant."""
    included = _included(ledger)
    included = included[included["Merchant"].astype(str) == merchant]
    if included.empty:
        return pd.DataFrame(columns=DESCRIPTION_COLUMNS)
    descriptions = included["Full Description"].fillna("Unknown").astype(str)
    included = included.assign(Description=descriptions)
    return (
        included.groupby("Description", dropna=False)
        .agg(
            Spending=("Net_Spend", "sum"),
            Transactions=("Net_Spend", "size"),
            Last_Transaction=("Date", "max"),
        )
        .reset_index()[DESCRIPTION_COLUMNS]
        .sort_values(
            ["Spending", "Description"],
            ascending=[False, True],
            ignore_index=True,
        )
    )


def _mode_or_first(values: pd.Series) -> object:
    """Return the mode for a series, falling back to its first value."""
    mode = values.mode()
    if not mode.empty:
        return mode.iloc[0]
    if not values.empty:
        return values.iloc[0]
    return "Unknown"
