"""Generate local anonymized, raw-shape CSV fixtures from a Tiller export.

Reads ``example_data/tillder_data_v2.0.xlsx`` (gitignored, local-only) and
emits four CSVs under ``.local/test-fixtures/`` plus a ``REFERENCE_DATE.txt``
and ``INJECTED_ROWS.md`` manifest. The output preserves financial patterns
and must never be committed. The repository's test fixtures are fully
synthetic and are maintained separately under ``demo/data/``.

The CSVs preserve the *raw* (pre-scrub) column shapes so the test suite can
drive the real ``Spreadsheet.scrub()`` pipeline end-to-end.

The mapping is deterministic across runs (sha256-seeded shuffles) so re-running
the generator on the same input produces byte-identical CSVs.

Run from the repo root with::

    .venv/Scripts/python scripts/generate_test_fixtures.py

The generator fails fast with a clear message if the source xlsx is missing
or if cross-sheet joins break post-anonymization.
"""

import hashlib
import random
import re
import string
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, TypeIs, TypedDict, cast

import pandas as pd

# ---------------------------------------------------------------------------
# Paths & configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_XLSX = REPO_ROOT / "example_data" / "tillder_data_v2.0.xlsx"
FIXTURES_DIR = REPO_ROOT / ".local" / "test-fixtures"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Sampling caps -- keeps local output small while preserving patterns.
SAMPLE_MONTHS = 24
MAX_TRANSACTIONS_PER_CATEGORY = 60
MAX_TRANSACTIONS_TOTAL = 1500
MAX_BALANCE_ROWS_PER_ACCOUNT = 60

# Pattern minimums (must match Phase 0.4 of the plan). The generator MUST
# satisfy these post-injection or it errors out.
PATTERN_MIN = {
    "duplicate_pairs": 3,
    "recurring_merchants": 2,
    "top_n_ties": 2,
    "cross_year_categories": 1,
    "over_budget_categories": 1,
    "under_budget_categories": 1,
    "single_account_groups": 1,
    "zero_total_groups": 1,
    "all_liability_groups": 1,
}

# Categories that recurring-charge discovery filters out. Recurring
# merchant injections MUST avoid these or they never surface in tests.
SUBSCRIPTION_EXCLUDED_CATEGORIES = frozenset(
    {
        "Mortgage Payment",
        "Auto Loan Payment",
        "Student Loan Payment",
        "Personal Loan Payment",
        "Car Payment",
        "Rent",
        "Investment",
        "Stock Purchase",
        "401k",
        "HSA",
        "RSU",
        "ESPP",
    }
)
SUBSCRIPTION_EXCLUDED_REGEX = re.compile(r"Mortgage|Loan|Investment|401k|HSA|RSU|ESPP", re.IGNORECASE)

MIN_DUPLICATE_AMOUNT = 10.0  # Mirrors config/defaults.toml.
SYNTHETIC_SUBSCRIPTION_CATEGORY = "Misc Subscription"


class AccountSourceInfo(TypedDict):
    """Source account fields used to build anonymization metadata."""

    Account: object
    Class: object
    Institution: object


class SourceAccountConfig(TypedDict):
    """Group and visibility values from the source Accounts sheet."""

    Group: object
    Hide: object


class AccountMetadata(TypedDict):
    """Source composite key and class for one account ID."""

    src_composite: str
    Class: object


TransactionRawRow = TypedDict(
    "TransactionRawRow",
    {
        "Unnamed: 0": None,
        "Date": str,
        "Category": str,
        "Amount": str,
        "Account": str,
        "Month": str,
        "Full Description": str,
        "Institution": str,
        "Account #": str,
        "Week": str,
        "Date Added": str,
        "Categorized Date": str,
    },
)

BalanceHistoryRawRow = TypedDict(
    "BalanceHistoryRawRow",
    {
        "Unnamed: 0": None,
        "Date": str,
        "Time": str,
        "Account": str,
        "Account #": str,
        "Account ID": str,
        "Balance ID": str,
        "Institution": str,
        "Balance": str,
        "Month": str,
        "Week": str,
        "Type": str,
        "Class": str,
        "Account Status": str,
        "Date Added": str,
    },
)


class InjectionRecord[RowT](TypedDict):
    """Manifest entry for a generated fixture row."""

    pattern: str
    row: RowT


# ---------------------------------------------------------------------------
# Word pools (deterministic, embedded so the generator has no external deps)
# ---------------------------------------------------------------------------

ADJECTIVES = [
    "alpha",
    "bravo",
    "calm",
    "deep",
    "eager",
    "fancy",
    "glad",
    "happy",
    "icy",
    "jolly",
    "keen",
    "lucky",
    "merry",
    "nimble",
    "odd",
    "proud",
    "quick",
    "rough",
    "shy",
    "tame",
    "ugly",
    "vivid",
    "wise",
    "young",
    "zesty",
    "amber",
    "bold",
    "crisp",
    "dusty",
    "earnest",
    "feisty",
    "gentle",
    "hardy",
    "ivory",
    "jade",
    "kindly",
    "lemon",
    "modest",
    "noble",
    "olive",
    "plain",
    "quiet",
    "rare",
    "snug",
    "tidy",
    "upbeat",
    "vague",
    "warm",
    "xeric",
    "yummy",
    "zealous",
    "bright",
    "clever",
    "dapper",
    "elated",
    "frosty",
    "gleamy",
    "humble",
    "inert",
    "jaunty",
    "kempt",
    "lithe",
    "mellow",
    "noisy",
    "opaque",
    "plump",
    "quaint",
    "rosy",
    "sleek",
    "thrifty",
    "unique",
    "vast",
    "witty",
    "zany",
]

NOUNS = [
    "acorn",
    "bear",
    "cloud",
    "dragon",
    "eagle",
    "ferret",
    "goose",
    "hawk",
    "iris",
    "jaguar",
    "koala",
    "lemur",
    "moose",
    "nebula",
    "otter",
    "panda",
    "quail",
    "robin",
    "swan",
    "tiger",
    "uniform",
    "viper",
    "walrus",
    "xenon",
    "yacht",
    "zebra",
    "anvil",
    "barrel",
    "candle",
    "drum",
    "ember",
    "fork",
    "globe",
    "harp",
    "ingot",
    "jar",
    "kettle",
    "lamp",
    "magnet",
    "needle",
    "orb",
    "puzzle",
    "quilt",
    "ribbon",
    "shield",
    "torch",
    "umbrella",
    "vault",
    "wagon",
    "yarn",
    "anchor",
    "bridge",
    "crown",
    "dagger",
    "engine",
    "flag",
    "gate",
    "helmet",
    "island",
    "jewel",
    "key",
    "lantern",
    "mirror",
    "nest",
    "oasis",
    "pillar",
    "quiver",
    "raft",
    "saddle",
    "tower",
    "vessel",
    "wheel",
    "yard",
    "zinc",
]

INSTITUTION_NAMES = [
    "Aurora",
    "Brightway",
    "Coastline",
    "Delta",
    "Evergreen",
    "Frontier",
    "Granite",
    "Harbor",
    "Ironwood",
    "Juniper",
    "Keystone",
    "Liberty",
    "Meridian",
    "Northern",
    "Omni",
    "Pacific",
    "Quantum",
    "Riverside",
    "Summit",
    "Trident",
    "Union",
    "Vanguard",
    "Westbridge",
    "Yonder",
]

ACCOUNT_TYPE_LABELS = {
    "Checking": "Checking",
    "Savings": "Savings",
    "Credit": "Credit",
    "Investment": "Investment",
    "Loan": "Loan",
    "Mortgage": "Mortgage",
    "Real Estate": "Property",
}

# ---------------------------------------------------------------------------
# Pure anonymization helpers (each one is independently testable)
# ---------------------------------------------------------------------------


def _seeded_shuffle(items: list[str], seed_str: str) -> list[str]:
    """Return a copy of ``items`` shuffled deterministically by ``seed_str``."""
    digest = hashlib.sha256(seed_str.encode()).hexdigest()
    rng = random.Random(int(digest, 16))
    out = list(items)
    rng.shuffle(out)
    return out


def _normalize_token(token: str) -> str:
    """Lowercase, strip punctuation. Used as the canonical mapping key."""
    return re.sub(r"[^\w]+", "", token.lower())


def build_token_mapping(source_tokens: list[str]) -> dict[str, str]:
    """Build an injective source-token -> anonymized-token mapping.

    Pure-numeric tokens are remapped to deterministic 5-digit numerics (also
    injective). Word tokens use deterministic shuffles of an adjective/noun
    pool; if the source vocabulary exceeds the pool size, an integer suffix
    is appended (``-2``, ``-3``...) to keep the mapping one-to-one.

    Returns a dict keyed by ``_normalize_token(source_token)``.
    """
    mapping: dict[str, str] = {}
    used_words: set[str] = set()
    used_numerics: set[str] = set()

    word_pool = ADJECTIVES + NOUNS

    for token in source_tokens:
        key = _normalize_token(token)
        if not key or key in mapping:
            continue

        if key.isdigit():
            # Pure numeric token: injective 5-digit map seeded by the source.
            digest = int(hashlib.sha256(("num:" + key).encode()).hexdigest(), 16)
            candidate = f"{digest % 100000:05d}"
            attempt = 0
            while candidate in used_numerics:
                attempt += 1
                digest = int(hashlib.sha256(f"num:{key}:{attempt}".encode()).hexdigest(), 16)
                candidate = f"{digest % 100000:05d}"
            used_numerics.add(candidate)
            mapping[key] = candidate
            continue

        # Word token: deterministic shuffle picks a candidate; suffix on collide.
        shuffled = _seeded_shuffle(word_pool, "word:" + key)
        chosen: str | None = None
        for candidate in shuffled:
            if candidate not in used_words:
                chosen = candidate
                break

        if chosen is None:
            # Pool exhausted: pick the seeded-first word and append a suffix.
            base = shuffled[0]
            suffix = 2
            while True:
                candidate = f"{base}-{suffix}"
                if candidate not in used_words:
                    chosen = candidate
                    break
                suffix += 1

        used_words.add(chosen)
        mapping[key] = chosen

    return mapping


def anonymize_description(desc: object, token_mapping: dict[str, str]) -> str:
    """Replace each whitespace-delimited token via ``token_mapping``.

    Empty/NaN inputs become "Unknown Merchant" so ``extract_merchant_name``
    still gets a 2-token string.
    """
    if desc is None or (isinstance(desc, float) and pd.isna(desc)):
        return "Unknown Merchant"
    text = str(desc).strip()
    if not text:
        return "Unknown Merchant"
    out_tokens: list[str] = []
    for tok in text.split():
        key = _normalize_token(tok)
        out_tokens.append(token_mapping.get(key, tok if not key else key))
    return " ".join(out_tokens)


@dataclass(frozen=True)
class AccountAnonymization:
    """Anonymized identity for one source ``Account ID``."""

    account: str  # "Checking-A"
    account_num: str  # "xxxx1111"
    account_id: str  # 24-char alphanumeric, stable last-4
    institution: str  # "Aurora Bank"
    composite_key: str  # "checking-a - xxxx1111 (ab01)"  (lower)


def _classify_account_type(name: object, klass: object) -> str:
    """Pick a stable type label from messy source Account names."""
    text = "" if name is None else str(name).lower()
    if "credit" in text or "card" in text:
        return "Credit"
    if "mortgage" in text:
        return "Mortgage"
    if "loan" in text:
        return "Loan"
    if "saving" in text:
        return "Savings"
    if "check" in text:
        return "Checking"
    if "invest" in text or "401" in text or "ira" in text or "broker" in text:
        return "Investment"
    if isinstance(klass, str) and klass.lower() == "liability":
        return "Loan"
    if "estate" in text or "property" in text or "home" in text:
        return "Property"
    return "Checking"


def build_account_mapping(
    balance_history: pd.DataFrame,
) -> dict[str, AccountAnonymization]:
    """Map every source ``Account ID`` -> an anonymized identity.

    The composite key is rebuilt here so accounts.csv can be derived directly
    from this mapping (matches ``BalanceHistorySpreadsheet.scrub`` formula).
    """
    by_id: dict[str, AccountAnonymization] = {}
    type_counters: Counter[str] = Counter()
    institution_index: dict[str, str] = {}

    # Sort by Account ID so letter assignments are deterministic regardless
    # of source row order.
    seen: dict[str, AccountSourceInfo] = {}
    for _, row in balance_history.iterrows():
        aid = str(row.get("Account ID", "")).strip()
        if not aid or aid in seen:
            continue
        seen[aid] = {
            "Account": row.get("Account"),
            "Class": row.get("Class"),
            "Institution": row.get("Institution"),
        }

    for aid in sorted(seen.keys()):
        info = seen[aid]
        type_label = _classify_account_type(info["Account"], info["Class"])
        type_counters[type_label] += 1
        letter_idx = type_counters[type_label] - 1
        letter = _index_to_letters(letter_idx)
        anon_account = f"{type_label}-{letter}"

        # 4-digit account # tied to the ID for stability.
        digest = hashlib.sha256(("acctnum:" + aid).encode()).hexdigest()
        anon_account_num = "xxxx" + digest[:4].translate(str.maketrans("abcdef", "012345"))

        # 24-char alphanumeric ID. Last-4 derived from a separate digest so it
        # stays distinguishable across accounts.
        last4_digest = hashlib.sha256(("last4:" + aid).encode()).hexdigest()
        last4 = (last4_digest[:4]).upper()
        prefix_digest = hashlib.sha256(("prefix:" + aid).encode()).hexdigest()
        prefix = prefix_digest[:20]
        anon_account_id = (prefix + last4).lower()[:20] + last4

        # Institution: stable assignment per source institution.
        src_inst = "" if info["Institution"] is None else str(info["Institution"])
        if src_inst not in institution_index:
            inst_letter_idx = len(institution_index)
            inst_letter = _index_to_letters(inst_letter_idx)
            inst_name = INSTITUTION_NAMES[inst_letter_idx % len(INSTITUTION_NAMES)]
            institution_index[src_inst] = (
                f"{inst_name} Bank {inst_letter}" if inst_letter_idx >= len(INSTITUTION_NAMES) else f"{inst_name} Bank"
            )
        anon_institution = institution_index[src_inst]

        composite = (f"{anon_account} - {anon_account_num} ({anon_account_id[-4:].upper()})").lower()

        by_id[aid] = AccountAnonymization(
            account=anon_account,
            account_num=anon_account_num,
            account_id=anon_account_id,
            institution=anon_institution,
            composite_key=composite,
        )

    return by_id


def _index_to_letters(idx: int) -> str:
    """0->A, 1->B, ..., 25->Z, 26->AA, 27->AB, ..."""
    letters: list[str] = []
    n = idx
    while True:
        letters.append(string.ascii_uppercase[n % 26])
        n //= 26
        if n == 0:
            break
        n -= 1
    return "".join(reversed(letters))


# ---------------------------------------------------------------------------
# Loading + sampling
# ---------------------------------------------------------------------------


def load_source_workbook() -> dict[str, pd.DataFrame]:
    """Read all four sheets we care about. Fail fast if the xlsx is missing."""
    if not SOURCE_XLSX.exists():
        sys.exit(
            f"\nERROR: source workbook not found at {SOURCE_XLSX}\n"
            f"Place a Tiller v2-schema xlsx export there and re-run.\n"
        )
    return {
        "transactions": pd.read_excel(SOURCE_XLSX, sheet_name="Transactions"),
        "balance_history": pd.read_excel(SOURCE_XLSX, sheet_name="Balance History"),
        "categories": pd.read_excel(SOURCE_XLSX, sheet_name="Categories"),
        "accounts": pd.read_excel(SOURCE_XLSX, sheet_name="Accounts"),
    }


def sample_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Take the most recent ``SAMPLE_MONTHS`` and cap rows per category.

    Within each category, rows are sorted newest-first so ``head()`` keeps
    the most recent data.  The global stride-downsample also preserves
    the last (newest) row so downstream date-range logic is accurate.
    """
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    cutoff = df["Date"].max() - pd.DateOffset(months=SAMPLE_MONTHS)
    df = df[df["Date"] >= cutoff]
    sampled: list[pd.DataFrame] = []
    for _, group in df.groupby("Category", dropna=False):
        group = group.sort_values("Date", ascending=False)
        if len(group) > MAX_TRANSACTIONS_PER_CATEGORY:
            sampled.append(group.head(MAX_TRANSACTIONS_PER_CATEGORY))
        else:
            sampled.append(group)
    out = pd.concat(sampled, ignore_index=True).sort_values("Date").reset_index(drop=True)
    if len(out) > MAX_TRANSACTIONS_TOTAL:
        stride = len(out) // MAX_TRANSACTIONS_TOTAL + 1
        strided = out.iloc[::stride]
        last_row = out.iloc[[-1]]
        if strided.index[-1] != last_row.index[0]:
            strided = pd.concat([strided, last_row])
        out = strided.reset_index(drop=True)
    return out


def sample_balance_history(df: pd.DataFrame) -> pd.DataFrame:
    """Cap rows per account to keep the fixture small.

    The latest row per account is always preserved so that downstream
    "latest balance" logic (which keeps the last row by Date/Time) sees
    the correct snapshot.
    """
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    cutoff = df["Date"].max() - pd.DateOffset(months=SAMPLE_MONTHS)
    df = df[df["Date"] >= cutoff]
    sampled: list[pd.DataFrame] = []
    sort_cols = ["Date", "Time"] if "Time" in df.columns else ["Date"]
    for _, group in df.groupby("Account ID", dropna=False):
        group = group.sort_values(sort_cols)
        if len(group) > MAX_BALANCE_ROWS_PER_ACCOUNT:
            stride = len(group) // MAX_BALANCE_ROWS_PER_ACCOUNT + 1
            strided = group.iloc[::stride]
            last_row = group.iloc[[-1]]
            if strided.index[-1] != last_row.index[0]:
                strided = pd.concat([strided, last_row])
            sampled.append(strided)
        else:
            sampled.append(group)
    return pd.concat(sampled, ignore_index=True).sort_values("Date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Anonymization application
# ---------------------------------------------------------------------------


def collect_description_tokens(*frames: pd.DataFrame) -> list[str]:
    """Walk every Full Description across the supplied frames and collect
    the unique normalized token set as an ordered list (sorted for determinism)."""
    tokens: set[str] = set()
    for df in frames:
        if "Full Description" not in df.columns:
            continue
        for desc in df["Full Description"].dropna():
            for tok in str(desc).split():
                key = _normalize_token(tok)
                if key:
                    tokens.add(key)
    return sorted(tokens)


def anonymize_transactions(
    df: pd.DataFrame,
    accounts: dict[str, AccountAnonymization],
    token_mapping: dict[str, str],
) -> pd.DataFrame:
    """Apply anonymization to a Transactions DataFrame. Returns RAW-shape df."""
    df = df.copy()
    df["Account ID"] = df["Account ID"].astype(str)
    # Build per-row anonymization from Account ID. Transactions without an
    # Account ID get the same anonymization as the source Account string maps to.
    fallback: dict[str, AccountAnonymization] = {info.account: info for info in accounts.values()}

    def lookup(row: pd.Series[Any]) -> AccountAnonymization | None:
        return accounts.get(str(row.get("Account ID", "")))

    def map_account(row: pd.Series[Any]) -> str:
        info = lookup(row)
        if info:
            return info.account
        # Fall back to a stable per-source-Account anonymization.
        src = str(row.get("Account", "")).strip()
        digest = int(hashlib.sha256(("orphan:" + src).encode()).hexdigest(), 16)
        keys = sorted(fallback.keys())
        if not keys:
            return "Checking-A"
        return keys[digest % len(keys)]

    def map_account_num(row: pd.Series[Any]) -> str:
        info = lookup(row)
        return info.account_num if info is not None else "xxxx0000"

    def map_institution(row: pd.Series[Any]) -> str:
        info = lookup(row)
        return info.institution if info is not None else "Aurora Bank"

    df["Account"] = df.apply(map_account, axis=1)
    df["Account #"] = df.apply(map_account_num, axis=1)
    df["Institution"] = df.apply(map_institution, axis=1)
    df["Full Description"] = df["Full Description"].apply(lambda d: anonymize_description(d, token_mapping))

    # Preserve the raw column shape that conftest expects.
    return _shape_transactions_raw(df)


def anonymize_balance_history(
    df: pd.DataFrame,
    accounts: dict[str, AccountAnonymization],
) -> pd.DataFrame:
    """Apply anonymization to a Balance History DataFrame. Returns RAW-shape df."""
    df = df.copy()
    df["Account ID"] = df["Account ID"].astype(str)
    df = df[df["Account ID"].isin(accounts)].copy()
    df["Account"] = df["Account ID"].map(lambda a: accounts[a].account)
    df["Account #"] = df["Account ID"].map(lambda a: accounts[a].account_num)
    df["Institution"] = df["Account ID"].map(lambda a: accounts[a].institution)
    # Re-anonymize Account ID itself.
    df["Account ID"] = df["Account ID"].map(lambda a: accounts[a].account_id)
    # Balance ID can be a stable derivative of the new Account ID + Date.
    df["Balance ID"] = df.apply(
        lambda r: hashlib.sha256((str(r["Account ID"]) + str(r["Date"])).encode()).hexdigest()[:24],
        axis=1,
    )
    return _shape_balance_history_raw(df)


def build_accounts_sheet(
    accounts: dict[str, AccountAnonymization],
    source_balance: pd.DataFrame,
    source_accounts: pd.DataFrame,
) -> pd.DataFrame:
    """Compose the 4-column accounts.csv from the anonymization mapping.

    Group is taken from the source Accounts sheet when available
    (joined on the source composite key), defaulting to a Class-derived group
    so the BalanceHistory join always lands.
    """
    src_lookup: dict[str, SourceAccountConfig] = {}
    if "Account" in source_accounts.columns:
        for _, row in source_accounts.iterrows():
            key = str(row.get("Account", "")).strip().lower()
            if key:
                src_lookup[key] = {
                    "Group": row.get("Group"),
                    "Hide": row.get("Hide"),
                }

    # Build per-Account-ID source composite + Class for fallback grouping.
    aid_meta: dict[str, AccountMetadata] = {}
    for _, row in source_balance.iterrows():
        aid = str(row.get("Account ID", "")).strip()
        if aid in accounts and aid not in aid_meta:
            acct_num = "" if pd.isna(row.get("Account #")) else str(row.get("Account #"))
            src_composite = (f"{row.get('Account')} - {acct_num} ({str(aid)[-4:].upper()})").lower()
            aid_meta[aid] = {
                "src_composite": src_composite,
                "Class": row.get("Class"),
            }

    rows: list[dict[str, object]] = []
    for aid in sorted(accounts.keys()):
        info = accounts[aid]
        meta = aid_meta.get(aid)
        src = src_lookup.get(meta["src_composite"]) if meta is not None else None
        group = src["Group"] if src is not None else None
        if group is None or (isinstance(group, float) and pd.isna(group)):
            klass = str(meta["Class"] if meta is not None else "").strip()
            group = "Liabilities" if klass.lower() == "liability" else "Assets"
        hide = src["Hide"] if src is not None else None
        hide_val = "" if hide is None or (isinstance(hide, float) and pd.isna(hide)) else str(hide)
        rows.append(
            {
                "Account": _composite_key_display(info),
                "Class Override": "",
                "Group": group,
                "Hide": hide_val,
            }
        )

    # Append the synthetic zero-total account so the join lands.
    rows.append(
        {
            "Account": _composite_key_display(SYNTHETIC_ZERO_ACCOUNT),
            "Class Override": "",
            "Group": SYNTHETIC_ZERO_GROUP_NAME,
            "Hide": "",
        }
    )
    return pd.DataFrame(rows, columns=["Account", "Class Override", "Group", "Hide"])


def _composite_key_display(info: AccountAnonymization) -> str:
    """Display form of the composite key (mixed case, matches Tiller's output)."""
    return f"{info.account} - {info.account_num} ({info.account_id[-4:].upper()})"


def anonymize_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Preserve non-blank Tiller categories."""
    df = df.copy()
    return df.dropna(subset=["Category"])


def _subscription_category_names(categories: pd.DataFrame) -> list[str]:
    """Return deterministic expense categories that can seed known subscriptions."""
    category_rows = categories.dropna(subset=["Category"])
    if "Type" in category_rows:
        category_rows = category_rows[category_rows["Type"].astype(str).str.casefold() == "expense"]
    return sorted(
        {
            category
            for category in category_rows["Category"].astype(str)
            if "subscription" in category.lower()
            and category not in SUBSCRIPTION_EXCLUDED_CATEGORIES
            and not SUBSCRIPTION_EXCLUDED_REGEX.search(category)
        }
    )


def _ensure_subscription_category(categories: pd.DataFrame) -> pd.DataFrame:
    """Add one deterministic subscription category when the source has none."""
    result = categories.copy()
    if _subscription_category_names(result):
        return result

    row: dict[object, object] = {column: 0.0 for column in result.columns}
    row.update(
        {
            "Category": SYNTHETIC_SUBSCRIPTION_CATEGORY,
            "Group": "Subscriptions",
            "Type": "Expense",
            "Hide From Reports": "",
        }
    )
    return pd.concat([result, pd.DataFrame([row], columns=result.columns)], ignore_index=True)


# ---------------------------------------------------------------------------
# Raw column shaping (must match conftest.TRANSACTIONS_RAW_COLUMNS etc.)
# ---------------------------------------------------------------------------

TRANSACTIONS_RAW_COLUMNS = [
    "Unnamed: 0",
    "Date",
    "Category",
    "Amount",
    "Account",
    "Month",
    "Full Description",
    "Institution",
    "Account #",
    "Week",
    "Date Added",
    "Categorized Date",
]

BALANCE_HISTORY_RAW_COLUMNS = [
    "Unnamed: 0",
    "Date",
    "Time",
    "Account",
    "Account #",
    "Account ID",
    "Balance ID",
    "Institution",
    "Balance",
    "Month",
    "Week",
    "Type",
    "Class",
    "Account Status",
    "Date Added",
]


def _format_money(val: object) -> str:
    """``1234.56`` -> ``$1,234.56``. Negatives -> ``-$5.00``."""
    try:
        f = float(str(val))
    except TypeError, ValueError:
        return ""
    sign = "-" if f < 0 else ""
    return f"{sign}${abs(f):,.2f}"


def _format_date_slash(val: object) -> str:
    """Format as ``MM/DD/YYYY``."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    ts = pd.to_datetime(cast(str | float | date | datetime, val), errors="coerce")
    if pd.isna(ts):
        return ""
    return str(ts.strftime("%m/%d/%Y"))


def _format_datetime_slash(val: object) -> str:
    """Format as ``MM/DD/YYYY HH:MM:SS``."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    ts = pd.to_datetime(cast(str | float | date | datetime, val), errors="coerce")
    if pd.isna(ts):
        return ""
    return str(ts.strftime("%m/%d/%Y %H:%M:%S"))


def _filled_column(df: pd.DataFrame, column: str, default: str) -> pd.Series[Any]:
    """Return a present column with missing cells replaced by ``default``."""
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="object")
    return df[column].fillna(default)


def _shape_transactions_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Format columns to match the live Google Sheets read shape."""
    out = pd.DataFrame()
    out["Unnamed: 0"] = [None] * len(df)
    out["Date"] = df["Date"].apply(_format_date_slash)
    out["Category"] = _filled_column(df, "Category", "")
    out["Amount"] = df["Amount"].apply(_format_money)
    out["Account"] = df["Account"]
    out["Month"] = df["Date"].apply(
        lambda d: pd.to_datetime(d).replace(day=1).strftime("%m/%d/%Y") if pd.notna(d) else ""
    )
    out["Full Description"] = df["Full Description"]
    out["Institution"] = df["Institution"]
    out["Account #"] = df["Account #"]
    out["Week"] = df["Date"].apply(_format_date_slash)
    out["Date Added"] = df["Date"].apply(_format_datetime_slash)
    out["Categorized Date"] = df["Date"].apply(_format_datetime_slash)
    return out[TRANSACTIONS_RAW_COLUMNS]


type TimeParts = datetime | time | pd.Timestamp


def _has_time_parts(value: object) -> TypeIs[TimeParts]:
    """Return whether a value exposes concrete hour, minute, and second fields."""
    return isinstance(value, (datetime, time, pd.Timestamp))


def _combine_date_time(date_val: object, time_val: object) -> str:
    """Combine a Date and a Time value into ``MM/DD/YYYY HH:MM:SS``.

    The Date supplies the calendar date; the Time supplies the time-of-day.
    Falls back to midnight when Time is missing or unparseable.
    """
    d = pd.to_datetime(
        cast(str | float | date | datetime, date_val),
        errors="coerce",
    )
    if pd.isna(d):
        return ""
    # time_val may be datetime.time, Timestamp, or string
    try:
        if _has_time_parts(time_val):
            h, m, s = time_val.hour, time_val.minute, time_val.second
        else:
            t = pd.to_datetime(
                cast(str | float | date | datetime, time_val),
                errors="coerce",
            )
            if pd.isna(t):
                h, m, s = 0, 0, 0
            else:
                h, m, s = t.hour, t.minute, t.second
    except Exception:
        h, m, s = 0, 0, 0
    combined = d.replace(hour=h, minute=m, second=s)
    return str(combined.strftime("%m/%d/%Y %H:%M:%S"))


def _shape_balance_history_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Format Balance History columns to match the live shape."""
    out = pd.DataFrame()
    out["Unnamed: 0"] = [None] * len(df)
    out["Date"] = df["Date"].apply(_format_date_slash)
    if "Time" in df.columns:
        out["Time"] = df.apply(
            lambda r: _combine_date_time(r["Date"], r["Time"]),
            axis=1,
        )
    else:
        out["Time"] = df["Date"].apply(_format_datetime_slash)
    out["Account"] = df["Account"]
    out["Account #"] = df["Account #"]
    out["Account ID"] = df["Account ID"]
    out["Balance ID"] = df["Balance ID"]
    out["Institution"] = df["Institution"]
    out["Balance"] = df["Balance"].apply(_format_money)
    out["Month"] = df["Date"].apply(
        lambda d: pd.to_datetime(d).replace(day=1).strftime("%m/%d/%Y") if pd.notna(d) else ""
    )
    out["Week"] = df["Date"].apply(_format_date_slash)
    out["Type"] = _filled_column(df, "Type", "")
    out["Class"] = _filled_column(df, "Class", "")
    out["Account Status"] = _filled_column(df, "Account Status", "Open")
    out["Date Added"] = df["Date"].apply(_format_datetime_slash)
    return out[BALANCE_HISTORY_RAW_COLUMNS]


# ---------------------------------------------------------------------------
# Pattern injection
# ---------------------------------------------------------------------------


@dataclass
class InjectionLog:
    """Tracks every synthetic row written to the fixtures."""

    transactions: list[InjectionRecord[TransactionRawRow]] = field(default_factory=list)
    balance_history: list[InjectionRecord[BalanceHistoryRawRow]] = field(default_factory=list)


def _pick_account(accounts: dict[str, AccountAnonymization], pattern: str) -> AccountAnonymization:
    """Pick a stable account for an injected pattern."""
    sorted_accounts = sorted(accounts.values(), key=lambda a: a.account_id)
    if not sorted_accounts:
        msg = "Cannot inject patterns with empty account map"
        raise RuntimeError(msg)
    candidates = [a for a in sorted_accounts if pattern.lower() in a.account.lower()]
    if candidates:
        return candidates[0]
    return sorted_accounts[0]


def _make_txn_row(
    *,
    date: str,
    category: str,
    amount: float,
    account: AccountAnonymization,
    description: str,
) -> TransactionRawRow:
    """Build a synthetic transactions row (raw shape)."""
    ts = pd.Timestamp(date)
    return {
        "Unnamed: 0": None,
        "Date": ts.strftime("%m/%d/%Y"),
        "Category": category,
        "Amount": _format_money(amount),
        "Account": account.account,
        "Month": ts.replace(day=1).strftime("%m/%d/%Y"),
        "Full Description": description,
        "Institution": account.institution,
        "Account #": account.account_num,
        "Week": ts.strftime("%m/%d/%Y"),
        "Date Added": ts.strftime("%m/%d/%Y 00:00:00"),
        "Categorized Date": ts.strftime("%m/%d/%Y 00:00:00"),
    }


def _make_bh_row(
    *,
    date: str,
    account: AccountAnonymization,
    balance: float,
    klass: str,
    type_: str = "Account",
) -> BalanceHistoryRawRow:
    """Build a synthetic balance history row (raw shape)."""
    ts = pd.Timestamp(date)
    return {
        "Unnamed: 0": None,
        "Date": ts.strftime("%m/%d/%Y"),
        "Time": ts.strftime("%m/%d/%Y 12:00:00"),
        "Account": account.account,
        "Account #": account.account_num,
        "Account ID": account.account_id,
        "Balance ID": hashlib.sha256((account.account_id + ts.isoformat()).encode()).hexdigest()[:24],
        "Institution": account.institution,
        "Balance": _format_money(balance),
        "Month": ts.replace(day=1).strftime("%m/%d/%Y"),
        "Week": ts.strftime("%m/%d/%Y"),
        "Type": type_,
        "Class": klass,
        "Account Status": "Open",
        "Date Added": ts.strftime("%m/%d/%Y 00:00:00"),
    }


def inject_patterns(
    transactions: pd.DataFrame,
    balance_history: pd.DataFrame,
    categories: pd.DataFrame,
    accounts: dict[str, AccountAnonymization],
    reference_date: pd.Timestamp,
    log: InjectionLog,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Append synthetic rows so phase0-pattern-preservation guarantees hold.

    The generator's caller asserts the resulting counts post-injection.
    """
    categories = _ensure_subscription_category(categories)
    new_txns: list[TransactionRawRow] = []
    new_bh: list[BalanceHistoryRawRow] = []

    valid_categories = set(categories["Category"].dropna().astype(str))

    # ---- Pattern 1: duplicate-pair seeds -------------------------------
    dup_account = _pick_account(accounts, "Checking")
    dup_dates = [
        reference_date - pd.DateOffset(months=2, days=10),
        reference_date - pd.DateOffset(months=4, days=5),
        reference_date - pd.DateOffset(months=6, days=12),
    ]
    dup_amounts = [-45.99, -125.50, -78.00]
    for i, (d, amt) in enumerate(zip(dup_dates, dup_amounts, strict=True)):
        cat = _safe_category(valid_categories, "Shopping")
        desc = f"duplicate pair seed {i + 1}"
        for _ in range(2):
            row = _make_txn_row(
                date=d.strftime("%Y-%m-%d"),
                category=cat,
                amount=amt,
                account=dup_account,
                description=desc,
            )
            new_txns.append(row)
            log.transactions.append(
                {
                    "pattern": f"Data Health duplicate-pair seed #{i + 1}",
                    "row": row,
                }
            )

    # ---- Pattern 2: recurring-merchant seeds ---------------------------
    rec_account = _pick_account(accounts, "Credit")
    known_subscription_categories = _subscription_category_names(categories)
    safe_recurring_cat = known_subscription_categories[0]
    recurring_seeds = [
        ("verum streamus", -15.99, 6),
        ("nimbus cloudus", -9.99, 5),
    ]
    for seed_idx, (merchant, amt, months) in enumerate(recurring_seeds):
        for m in range(months):
            d = reference_date - pd.DateOffset(months=months - m)
            row = _make_txn_row(
                date=d.strftime("%Y-%m-%d"),
                category=safe_recurring_cat,
                amount=amt,
                account=rec_account,
                description=f"{merchant} {m + 1:05d}",
            )
            new_txns.append(row)
            log.transactions.append(
                {
                    "pattern": f"Page 5 recurring monthly seed #{seed_idx + 1}",
                    "row": row,
                }
            )

    # ---- Pattern 3: top-N tie seeds ------------------------------------
    tie_account = _pick_account(accounts, "Credit")
    tie_dates = [
        reference_date - pd.DateOffset(months=1, days=1),
        reference_date - pd.DateOffset(months=1, days=8),
    ]
    tie_amount = -2500.00
    tie_cat = _safe_category(valid_categories, "Shopping")
    for i, d in enumerate(tie_dates):
        row = _make_txn_row(
            date=d.strftime("%Y-%m-%d"),
            category=tie_cat,
            amount=tie_amount,
            account=tie_account,
            description=f"magnum boxus {99000 + i}",
        )
        new_txns.append(row)
        log.transactions.append(
            {
                "pattern": "Page 8 top-N tie seed",
                "row": row,
            }
        )

    # ---- Pattern 4: cross-year category --------------------------------
    cross_year_cat = _safe_category(valid_categories, "Groceries")
    for year_offset in (1, 0):
        d = reference_date - pd.DateOffset(years=year_offset, months=1)
        row = _make_txn_row(
            date=d.strftime("%Y-%m-%d"),
            category=cross_year_cat,
            amount=-87.65,
            account=dup_account,
            description="cross year staple",
        )
        new_txns.append(row)
        log.transactions.append(
            {
                "pattern": "Page 3 cross-year seed",
                "row": row,
            }
        )

    # ---- Pattern 5/6: over-budget / under-budget categories ------------
    # We'll handle budget injection by ensuring categories has a budget row
    # (handled in inject_budget_patterns below).

    # ---- BalanceHistory injections -------------------------------------
    new_bh.extend(_inject_balance_patterns(accounts, reference_date, log))

    if new_txns:
        transactions = pd.concat(
            [transactions, pd.DataFrame(new_txns, columns=TRANSACTIONS_RAW_COLUMNS)],
            ignore_index=True,
        )
    if new_bh:
        balance_history = pd.concat(
            [balance_history, pd.DataFrame(new_bh, columns=BALANCE_HISTORY_RAW_COLUMNS)],
            ignore_index=True,
        )
    return transactions, balance_history, categories


def _safe_category(
    valid: set[str],
    preferred: str,
    *,
    avoid: frozenset[str] = frozenset(),
) -> str:
    """Pick a real category that is not in ``avoid`` and not regex-excluded."""
    if preferred in valid and preferred not in avoid and not SUBSCRIPTION_EXCLUDED_REGEX.search(preferred):
        return preferred
    for cat in sorted(valid):
        if cat in avoid:
            continue
        if SUBSCRIPTION_EXCLUDED_REGEX.search(cat):
            continue
        return cat
    return preferred  # Last-ditch fallback.


SYNTHETIC_ZERO_GROUP_NAME = "_SyntheticZeroGroup"
SYNTHETIC_ZERO_ACCOUNT = AccountAnonymization(
    account="ZeroSum-A",
    account_num="xxxx0001",
    account_id="zerosum0000000000000ZS01",
    institution="Synthetic Bank",
    composite_key="zerosum-a - xxxx0001 (zs01)",
)


def _inject_balance_patterns(
    accounts: dict[str, AccountAnonymization],
    reference_date: pd.Timestamp,
    log: InjectionLog,
) -> list[BalanceHistoryRawRow]:
    """Append synthetic BalanceHistory rows for required group shapes.

    Most pattern guarantees are satisfied by the natural shape of the source
    data (single-account groups appear when the source has only one account
    in a group; all-Liability groups appear via the existing Loan group).
    The one shape we always have to fabricate is the zero-total group --
    no realistic account holds exactly zero -- so we inject a fully synthetic
    account into its own group whose only balance row is zero.
    """
    out: list[BalanceHistoryRawRow] = []

    # Zero-total group: fully synthetic account with Balance 0 in a uniquely
    # named group so other accounts cannot mask the zero total.
    out.append(
        _make_bh_row(
            date=reference_date.strftime("%Y-%m-%d"),
            account=SYNTHETIC_ZERO_ACCOUNT,
            balance=0.0,
            klass="Asset",
        )
    )
    log.balance_history.append(
        {
            "pattern": "Home zero-total-group seed",
            "row": out[-1],
        }
    )
    return out


def inject_budget_patterns(
    categories: pd.DataFrame,
    transactions: pd.DataFrame,
    reference_date: pd.Timestamp,
    log: InjectionLog,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ensure at least one over-budget and one under-budget category exists
    in the latest budgeted month."""
    cat = categories.copy()
    txns = transactions.copy()
    month_col = pd.Timestamp(year=reference_date.year, month=reference_date.month, day=1)

    # Find a budget column for the reference month.
    budget_cols: list[pd.Timestamp] = [
        cast(pd.Timestamp, column) for column in cat.columns if isinstance(column, pd.Timestamp)
    ]
    if not budget_cols:
        return cat, txns

    nearest_col = min(budget_cols, key=lambda c: abs((c - month_col).days))

    over_cat = "Groceries" if "Groceries" in cat["Category"].values else cat["Category"].iloc[0]
    under_cat = "Restaurants" if "Restaurants" in cat["Category"].values else cat["Category"].iloc[1]

    cat.loc[cat["Category"] == over_cat, nearest_col] = 100.00
    cat.loc[cat["Category"] == under_cat, nearest_col] = 1000.00

    # Inject one over-budget transaction (300 spent against 100 budget).
    over_row = _make_txn_row(
        date=reference_date.strftime("%Y-%m-%d"),
        category=over_cat,
        amount=-300.00,
        account=_DUMMY_ACCOUNT,
        description="budget burn over",
    )
    log.transactions.append({"pattern": f"Page 7 over-budget seed ({over_cat})", "row": over_row})
    under_row = _make_txn_row(
        date=reference_date.strftime("%Y-%m-%d"),
        category=under_cat,
        amount=-50.00,
        account=_DUMMY_ACCOUNT,
        description="budget burn under",
    )
    log.transactions.append({"pattern": f"Page 7 under-budget seed ({under_cat})", "row": under_row})

    txns = pd.concat(
        [txns, pd.DataFrame([over_row, under_row], columns=TRANSACTIONS_RAW_COLUMNS)],
        ignore_index=True,
    )
    return cat, txns


# Placeholder used only by inject_budget_patterns -- replaced before write.
_DUMMY_ACCOUNT = AccountAnonymization(
    account="Checking-A",
    account_num="xxxx0000",
    account_id="0" * 20 + "AB01",
    institution="Aurora Bank",
    composite_key="checking-a - xxxx0000 (ab01)",
)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_csvs(
    transactions: pd.DataFrame,
    balance_history: pd.DataFrame,
    categories: pd.DataFrame,
    accounts_df: pd.DataFrame,
) -> None:
    """Write the four CSVs to the local output directory."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    transactions.to_csv(FIXTURES_DIR / "transactions.csv", index=False)
    balance_history.to_csv(FIXTURES_DIR / "balance_history.csv", index=False)
    categories.to_csv(FIXTURES_DIR / "categories.csv", index=False)
    accounts_df.to_csv(FIXTURES_DIR / "accounts.csv", index=False)


def write_reference_date(reference_date: pd.Timestamp) -> None:
    """Write REFERENCE_DATE.txt as ISO with explicit UTC offset."""
    ts = reference_date.tz_localize("UTC") if reference_date.tzinfo is None else reference_date
    (FIXTURES_DIR / "REFERENCE_DATE.txt").write_text(
        ts.isoformat() + "\n",
        encoding="utf-8",
    )


def write_injection_manifest(log: InjectionLog) -> None:
    """Write INJECTED_ROWS.md so humans can disambiguate synthetic vs source rows."""
    lines = [
        "# Synthetic rows injected into fixtures",
        "",
        "These rows were not present in the source xlsx with the required "
        "pattern shape; the generator added them deterministically.",
        "Identifying tuple = (Date | Amount | Description | Account).",
        "",
        "## transactions.csv",
        "",
    ]
    by_pattern: dict[str, list[TransactionRawRow]] = {}
    for transaction_entry in log.transactions:
        by_pattern.setdefault(transaction_entry["pattern"], []).append(transaction_entry["row"])
    for pattern, transaction_rows in by_pattern.items():
        lines.append(f"### {pattern}")
        for row in transaction_rows:
            lines.append(f"- {row['Date']} | {row['Amount']} | {row['Full Description']} | {row['Account']}")
        lines.append("")

    lines.append("## balance_history.csv")
    lines.append("")
    by_bh: dict[str, list[BalanceHistoryRawRow]] = {}
    for balance_entry in log.balance_history:
        by_bh.setdefault(balance_entry["pattern"], []).append(balance_entry["row"])
    for pattern, balance_rows in by_bh.items():
        lines.append(f"### {pattern}")
        for balance_row in balance_rows:
            lines.append(
                f"- {balance_row['Date']} | {balance_row['Balance']} | "
                f"{balance_row['Account']} | {balance_row['Class']}"
            )
        lines.append("")

    (FIXTURES_DIR / "INJECTED_ROWS.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Validation (cross-sheet join must survive)
# ---------------------------------------------------------------------------


def validate_pattern_minimums(
    transactions: pd.DataFrame,
    balance_history: pd.DataFrame,
    categories: pd.DataFrame,
    accounts_df: pd.DataFrame,
) -> None:
    """Fail fast if any PATTERN_MIN guarantee is not met post-injection."""
    errors: list[str] = []

    txn_dates = pd.to_datetime(transactions["Date"], format="mixed")
    txn_descs = transactions["Full Description"].astype(str)
    txn_amounts = transactions["Amount"].apply(
        lambda v: float(str(v).replace("$", "").replace(",", "")) if pd.notna(v) else 0.0
    )

    # duplicate_pairs: mirrors find_duplicates_efficient() with Data Health defaults —
    # same Account, same normalized description, amount >= $10, within 1 day.
    # Uses the actual self-join approach rather than exact-day keying.
    txn_accounts = transactions["Account"].astype(str)
    dup_df = pd.DataFrame(
        {
            "date": txn_dates,
            "amount": txn_amounts,
            "abs_amount": txn_amounts.abs(),
            "desc": txn_descs.str.lower().str.strip(),
            "account": txn_accounts,
        }
    ).reset_index(drop=True)
    dup_df = dup_df[dup_df["abs_amount"] >= 10.0]
    dup_df["_row_id"] = range(len(dup_df))
    pairs = dup_df.merge(dup_df, on="amount", suffixes=("_1", "_2"))
    pairs = pairs[pairs["_row_id_1"] < pairs["_row_id_2"]]
    pairs["days_apart"] = (pairs["date_2"] - pairs["date_1"]).dt.days.abs()
    pairs = pairs[pairs["days_apart"] <= 1]
    pairs = pairs[pairs["account_1"] == pairs["account_2"]]
    pairs = pairs[pairs["desc_1"] == pairs["desc_2"]]
    n_dup_pairs = len(pairs)
    if n_dup_pairs < PATTERN_MIN["duplicate_pairs"]:
        errors.append(f"duplicate_pairs: {n_dup_pairs} < {PATTERN_MIN['duplicate_pairs']}")

    # recurring_merchants: known Page 5 inventory is category-authoritative.
    # Merchants must have at least three authoritative categorized charges.
    from src.analysis.merchants import normalize_merchant_name

    subscription_categories = _subscription_category_names(categories)
    rec_df = transactions[transactions["Category"].isin(subscription_categories)].copy()
    rec_df["merchant"] = rec_df["Full Description"].map(
        lambda description: normalize_merchant_name(description, method="first_three")
    )
    recurring_charge_counts = rec_df.groupby("merchant").size()
    n_recurring = int((recurring_charge_counts >= 3).sum())
    if n_recurring < PATTERN_MIN["recurring_merchants"]:
        errors.append(f"recurring_merchants: {n_recurring} < {PATTERN_MIN['recurring_merchants']}")

    # top_n_ties: at least one pair of expense rows with the same absolute amount
    # that both land inside the top-50 expenses (the default N in Page 8), proving
    # the tie actually sits at a boundary that matters.
    expense_df = pd.DataFrame(
        {
            "abs_amount": txn_amounts[txn_amounts < 0].abs(),
        }
    ).reset_index(drop=True)
    top_50 = expense_df.nlargest(50, "abs_amount")
    tie_counts = top_50["abs_amount"].value_counts()
    n_ties = int((tie_counts >= 2).sum())
    if n_ties < PATTERN_MIN["top_n_ties"]:
        errors.append(f"top_n_ties: {n_ties} < {PATTERN_MIN['top_n_ties']}")

    # cross_year_categories: categories with transactions in ≥2 distinct years
    cat_years = pd.DataFrame(
        {
            "category": transactions["Category"].astype(str),
            "year": txn_dates.dt.year,
        }
    )
    cat_year_counts = cat_years.groupby("category")["year"].nunique()
    n_cross = int((cat_year_counts >= 2).sum())
    if n_cross < PATTERN_MIN["cross_year_categories"]:
        errors.append(f"cross_year_categories: {n_cross} < {PATTERN_MIN['cross_year_categories']}")

    # over/under_budget_categories: compare budget vs actual in latest month
    budget_cols: list[pd.Timestamp] = [
        cast(pd.Timestamp, column) for column in categories.columns if isinstance(column, pd.Timestamp)
    ]
    if budget_cols:
        latest_budget_col = max(budget_cols)
        budget_by_cat = categories.set_index("Category")[latest_budget_col].dropna()
        budget_by_cat = budget_by_cat[budget_by_cat > 0]
        ref_month = latest_budget_col.strftime("%m/%Y")
        txn_month = txn_dates.dt.strftime("%m/%Y")
        month_txns = transactions[txn_month == ref_month]
        actual_by_cat = month_txns.groupby("Category")["Amount"].apply(
            lambda s: s.apply(
                lambda v: abs(float(str(v).replace("$", "").replace(",", ""))) if pd.notna(v) else 0.0
            ).sum()
        )
        n_over = 0
        n_under = 0
        for cat_name in budget_by_cat.index:
            if cat_name in actual_by_cat.index:
                actual = actual_by_cat[cat_name]
                budget = budget_by_cat[cat_name]
                if actual > budget:
                    n_over += 1
                elif actual < budget:
                    n_under += 1
        if n_over < PATTERN_MIN["over_budget_categories"]:
            errors.append(f"over_budget_categories: {n_over} < {PATTERN_MIN['over_budget_categories']}")
        if n_under < PATTERN_MIN["under_budget_categories"]:
            errors.append(f"under_budget_categories: {n_under} < {PATTERN_MIN['under_budget_categories']}")

    # single_account_groups: groups with exactly 1 account
    acct_per_group = accounts_df.groupby("Group")["Account"].nunique()
    n_single = int((acct_per_group == 1).sum())
    if n_single < PATTERN_MIN["single_account_groups"]:
        errors.append(f"single_account_groups: {n_single} < {PATTERN_MIN['single_account_groups']}")

    # Build BH → group mapping via composite key (same join the scrub pipeline uses)
    bh_composite_keys = (
        balance_history["Account"].astype(str)
        + " - "
        + balance_history["Account #"].fillna("").astype(str)
        + " ("
        + balance_history["Account ID"].astype(str).str[-4:].str.upper()
        + ")"
    ).str.lower()
    acct_group_map = dict(zip(accounts_df["Account"].str.lower(), accounts_df["Group"]))
    bh_groups = bh_composite_keys.map(acct_group_map)

    # zero_total_groups: groups whose balance rows sum to 0
    bh_bal = balance_history["Balance"].apply(
        lambda v: float(str(v).replace("$", "").replace(",", "")) if pd.notna(v) else 0.0
    )
    group_totals = pd.DataFrame({"group": bh_groups, "bal": bh_bal}).groupby("group")["bal"].sum()
    n_zero = int((group_totals.abs() < 0.01).sum())
    if n_zero < PATTERN_MIN["zero_total_groups"]:
        errors.append(f"zero_total_groups: {n_zero} < {PATTERN_MIN['zero_total_groups']}")

    # all_liability_groups: groups where every row's Class is Liability
    bh_with_group = pd.DataFrame(
        {
            "group": bh_groups,
            "class": balance_history["Class"].fillna(""),
        }
    )
    bh_with_group = bh_with_group[bh_with_group["group"].notna()]
    if not bh_with_group.empty:
        group_classes = bh_with_group.groupby("group")["class"].apply(lambda s: set(s.dropna()) == {"Liability"})
        n_liability = int(group_classes.sum())
    else:
        n_liability = 0
    if n_liability < PATTERN_MIN["all_liability_groups"]:
        errors.append(f"all_liability_groups: {n_liability} < {PATTERN_MIN['all_liability_groups']}")

    if errors:
        sys.exit("ERROR: PATTERN_MIN guarantees not met:\n  " + "\n  ".join(errors))


def validate_balance_join(balance_history: pd.DataFrame, accounts_df: pd.DataFrame) -> None:
    """Fail fast if any BalanceHistory composite key has no matching Account."""
    bh = balance_history.copy()
    bh["_key"] = (
        bh["Account"].astype(str)
        + " - "
        + bh["Account #"].fillna("").astype(str)
        + " ("
        + bh["Account ID"].astype(str).str[-4:].str.upper()
        + ")"
    ).str.lower()
    accounts_keys = set(accounts_df["Account"].str.lower())
    missing = sorted(set(bh["_key"]) - accounts_keys)
    if missing:
        sys.exit("ERROR: BalanceHistory composite keys missing from Accounts:\n  " + "\n  ".join(missing[:5]))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main() -> None:  # pragma: no cover - thin orchestrator
    print(f"[fixture-gen] reading {SOURCE_XLSX}")
    raw = load_source_workbook()

    print("[fixture-gen] sampling source rows")
    transactions = sample_transactions(raw["transactions"])
    balance_history = sample_balance_history(raw["balance_history"])

    print("[fixture-gen] building anonymization mappings")
    accounts = build_account_mapping(raw["balance_history"])
    if not accounts:
        sys.exit("ERROR: no Account IDs found in source Balance History")

    tokens = collect_description_tokens(transactions)
    token_mapping = build_token_mapping(tokens)

    # Replace the dummy account placeholder with a real anonymized account
    # before injection so injected budget rows reference a valid identity.
    global _DUMMY_ACCOUNT
    _DUMMY_ACCOUNT = sorted(accounts.values(), key=lambda a: a.account_id)[0]

    print("[fixture-gen] applying anonymization")
    transactions = anonymize_transactions(transactions, accounts, token_mapping)
    balance_history = anonymize_balance_history(balance_history, accounts)

    categories = anonymize_categories(raw["categories"])

    reference_date = pd.Timestamp(pd.to_datetime(transactions["Date"], format="mixed").max().date())

    log = InjectionLog()
    print("[fixture-gen] injecting required patterns")
    transactions, balance_history, categories = inject_patterns(
        transactions,
        balance_history,
        categories,
        accounts,
        reference_date,
        log,
    )
    categories, transactions = inject_budget_patterns(
        categories,
        transactions,
        reference_date,
        log,
    )

    accounts_df = build_accounts_sheet(accounts, raw["balance_history"], raw["accounts"])

    # Make sure injected balance-history accounts are present in Accounts:
    # synthetic rows were added with real anonymized accounts, so the join
    # naturally lands -- but add a final check.
    print("[fixture-gen] validating cross-sheet join")
    validate_balance_join(balance_history, accounts_df)

    print("[fixture-gen] validating PATTERN_MIN guarantees")
    validate_pattern_minimums(transactions, balance_history, categories, accounts_df)

    print("[fixture-gen] writing CSVs to", FIXTURES_DIR)
    write_csvs(transactions, balance_history, categories, accounts_df)
    write_reference_date(reference_date)
    write_injection_manifest(log)

    print(
        f"[fixture-gen] done. injected: "
        f"{len([e for e in log.transactions if 'duplicate' in e['pattern'].lower()])} duplicates, "
        f"{len([e for e in log.transactions if 'recurring' in e['pattern'].lower()])} recurring, "
        f"{len([e for e in log.transactions if 'tie' in e['pattern'].lower()])} ties, "
        f"{len(log.balance_history)} balance shapes"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
