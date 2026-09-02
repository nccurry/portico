"""Load validated application settings from tracked and local TOML files."""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.constants import FI_SPENDING_LOOKBACK_OPTIONS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULTS_PATH = PROJECT_ROOT / "config" / "defaults.toml"


class ConfigError(ValueError):
    """A user-facing application configuration error."""


@dataclass(frozen=True)
class DataSettings:
    """Data source and demo-file settings."""

    mode: str
    demo_directory: Path
    demo_reference_date: datetime

    @property
    def is_demo(self) -> bool:
        """Return whether the app uses synthetic demo data."""
        return self.mode == "demo"


@dataclass(frozen=True)
class ReportingSettings:
    """Shared reporting-period choices."""

    lookback_months: tuple[int, ...]
    default_lookback_months: int


@dataclass(frozen=True)
class ThresholdSettings:
    """Transaction and duplicate-detection thresholds."""

    expense: int
    income: int
    duplicate_minimum: float
    duplicate_days: int


@dataclass(frozen=True)
class IncomeSavingsSettings:
    """Defaults for income and savings reports."""

    default_view: str
    target_rate: int
    exclude_categories: tuple[str, ...]
    exclude_groups: tuple[str, ...]


@dataclass(frozen=True)
class SpendingSettings:
    """Defaults for discretionary-spending reports."""

    default_view: str
    exclude_categories: tuple[str, ...]
    exclude_groups: tuple[str, ...]


@dataclass(frozen=True)
class SubscriptionSettings:
    """Defaults for subscription views and detection."""

    known_category_terms: tuple[str, ...]
    minimum_confidence: int
    stale_after_days: int
    default_exclude_categories: tuple[str, ...]
    detection_excluded_categories: tuple[str, ...]
    detection_excluded_pattern: str


@dataclass(frozen=True)
class YearOverYearSettings:
    """Defaults for the fixed year-over-year presets."""

    utility_group_terms: tuple[str, ...]
    utility_category_terms: tuple[str, ...]


@dataclass(frozen=True)
class BudgetSettings:
    """Defaults for budget history."""

    history_months: int


@dataclass(frozen=True)
class DataHealthSettings:
    """Defaults for adjustable data-health checks."""

    stale_account_days: int
    duplicate_require_same_account: bool
    duplicate_require_same_category: bool
    duplicate_require_same_description: bool


@dataclass(frozen=True)
class FinancialIndependenceSettings:
    """Defaults for financial-independence scenarios."""

    expected_return_rate: float
    withdrawal_rate: float
    target_amount: float
    spending_lookback_months: int
    projection_years: int
    included_account_patterns: tuple[str, ...]
    included_groups: tuple[str, ...]


@dataclass(frozen=True)
class FinancialSafetySettings:
    """Household policy for emergency-fund and debt progress."""

    emergency_fund_target_months: int
    emergency_fund_included_groups: tuple[str, ...]
    emergency_fund_included_account_patterns: tuple[str, ...]
    emergency_fund_spending_lookback_months: int
    emergency_fund_exclude_categories: tuple[str, ...]
    emergency_fund_exclude_groups: tuple[str, ...]
    debt_included_groups: tuple[str, ...]
    debt_included_account_patterns: tuple[str, ...]
    debt_baseline_date: date | None


@dataclass(frozen=True)
class WeeklySummarySettings:
    """Defaults for the scheduled Discord summary."""

    average_weeks: int
    rolling_weeks: int
    top_merchant_count: int


@dataclass(frozen=True)
class MerchantSettings:
    """Local merchant-description aliases."""

    aliases: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class Settings:
    """Validated application settings."""

    data: DataSettings
    reporting: ReportingSettings
    thresholds: ThresholdSettings
    income_savings: IncomeSavingsSettings
    spending: SpendingSettings
    subscriptions: SubscriptionSettings
    year_over_year: YearOverYearSettings
    budget: BudgetSettings
    data_health: DataHealthSettings
    financial_independence: FinancialIndependenceSettings
    financial_safety: FinancialSafetySettings
    weekly_summary: WeeklySummarySettings
    merchants: MerchantSettings


_SECTION_KEYS = {
    "data": {"mode", "demo_directory", "demo_reference_date"},
    "reporting": {"lookback_months", "default_lookback_months"},
    "thresholds": {"expense", "income", "duplicate_minimum", "duplicate_days"},
    "income_savings": {"default_view", "target_rate", "exclude_categories", "exclude_groups"},
    "spending": {"default_view", "exclude_categories", "exclude_groups"},
    "subscriptions": {
        "known_category_terms",
        "minimum_confidence",
        "stale_after_days",
        "default_exclude_categories",
        "detection_excluded_categories",
        "detection_excluded_pattern",
    },
    "year_over_year": {"utility_group_terms", "utility_category_terms"},
    "budget": {"history_months"},
    "data_health": {
        "stale_account_days",
        "duplicate_require_same_account",
        "duplicate_require_same_category",
        "duplicate_require_same_description",
    },
    "financial_independence": {
        "expected_return_rate",
        "withdrawal_rate",
        "target_amount",
        "spending_lookback_months",
        "projection_years",
        "included_account_patterns",
        "included_groups",
    },
    "financial_safety": {
        "emergency_fund_target_months",
        "emergency_fund_included_groups",
        "emergency_fund_included_account_patterns",
        "emergency_fund_spending_lookback_months",
        "emergency_fund_exclude_categories",
        "emergency_fund_exclude_groups",
        "debt_included_groups",
        "debt_included_account_patterns",
        "debt_baseline_date",
    },
    "weekly_summary": {"average_weeks", "rolling_weeks", "top_merchant_count"},
    "merchants": {"aliases"},
}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError as error:
        raise ConfigError(f"Configuration file does not exist: {path.name}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Invalid TOML in {path.name}: {error}") from error
    except OSError as error:
        raise ConfigError(f"Could not read configuration file: {path.name}") from error


def _merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            merged[key] = _merge(current, value)
        else:
            merged[key] = value
    return merged


def _validate_keys(document: Mapping[str, Any]) -> None:
    unknown_sections = set(document) - set(_SECTION_KEYS)
    if unknown_sections:
        names = ", ".join(sorted(unknown_sections))
        raise ConfigError(f"Unknown configuration section(s): {names}")

    for section_name, allowed_keys in _SECTION_KEYS.items():
        section = document.get(section_name)
        if not isinstance(section, Mapping):
            raise ConfigError(f"Configuration section [{section_name}] must be a table")
        unknown_keys = set(section) - allowed_keys
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            raise ConfigError(f"Unknown key(s) in [{section_name}]: {names}")

    aliases = document["merchants"].get("aliases")
    if not isinstance(aliases, Mapping):
        raise ConfigError("Configuration section [merchants.aliases] must be a table")


def _integer(section: Mapping[str, Any], key: str, minimum: int, maximum: int) -> int:
    value = section.get(key)
    if type(value) is not int:
        raise ConfigError(f"{key} must be an integer")
    if not minimum <= value <= maximum:
        raise ConfigError(f"{key} must be between {minimum} and {maximum}")
    return value


def _number(section: Mapping[str, Any], key: str, minimum: float, maximum: float) -> float:
    value = section.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{key} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise ConfigError(f"{key} must be between {minimum:g} and {maximum:g}")
    return result


def _boolean(section: Mapping[str, Any], key: str) -> bool:
    value = section.get(key)
    if type(value) is not bool:
        raise ConfigError(f"{key} must be true or false")
    return value


def _string(section: Mapping[str, Any], key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _choice(section: Mapping[str, Any], key: str, choices: set[str]) -> str:
    value = _string(section, key).casefold()
    if value not in choices:
        options = ", ".join(sorted(choices))
        raise ConfigError(f"{key} must be one of: {options}")
    return value


def _strings(section: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = section.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigError(f"{key} must be an array of non-empty strings")
    result = tuple(item.strip() for item in value)
    normalized = [item.casefold() for item in result]
    if len(normalized) != len(set(normalized)):
        raise ConfigError(f"{key} must not contain duplicates")
    return result


def _integers(section: Mapping[str, Any], key: str, minimum: int, maximum: int) -> tuple[int, ...]:
    value = section.get(key)
    if not isinstance(value, list) or not value or any(type(item) is not int for item in value):
        raise ConfigError(f"{key} must be a non-empty array of integers")
    result = tuple(value)
    if any(not minimum <= item <= maximum for item in result):
        raise ConfigError(f"{key} values must be between {minimum} and {maximum}")
    if len(result) != len(set(result)):
        raise ConfigError(f"{key} must not contain duplicates")
    if tuple(sorted(result)) != result:
        raise ConfigError(f"{key} must be in ascending order")
    return result


def _demo_directory(section: Mapping[str, Any], project_root: Path) -> Path:
    configured = Path(_string(section, "demo_directory"))
    if configured.is_absolute():
        raise ConfigError("demo_directory must be relative to the repository root")
    resolved = (project_root / configured).resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError as error:
        raise ConfigError("demo_directory must stay inside the repository") from error
    return resolved


def _utc_datetime(section: Mapping[str, Any], key: str) -> datetime:
    value = _string(section, key)
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ConfigError(f"{key} must be an ISO 8601 date and time") from error
    if timestamp.tzinfo is None:
        raise ConfigError(f"{key} must include a timezone")
    return timestamp.astimezone(UTC)


def _optional_date(section: Mapping[str, Any], key: str) -> date | None:
    value = section.get(key)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ConfigError(f"{key} must be an ISO 8601 date or an empty string")
    if not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ConfigError(f"{key} must be an ISO 8601 date or an empty string") from error


def _merchant_aliases(section: Mapping[str, Any]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    aliases = section["aliases"]
    assert isinstance(aliases, Mapping)
    normalized: list[tuple[str, tuple[str, ...]]] = []
    for merchant, fragments in aliases.items():
        if not isinstance(merchant, str) or not merchant.strip():
            raise ConfigError("Merchant alias names must be non-empty strings")
        values = _strings({"fragments": fragments}, "fragments")
        normalized.append((merchant.strip(), values))
    names = [merchant.casefold() for merchant, _ in normalized]
    if len(names) != len(set(names)):
        raise ConfigError("Merchant alias names must not contain duplicates")
    return tuple(normalized)


def _build_settings(document: Mapping[str, Any], project_root: Path) -> Settings:
    _validate_keys(document)
    data = document["data"]
    reporting = document["reporting"]
    thresholds = document["thresholds"]
    income_savings = document["income_savings"]
    spending = document["spending"]
    subscriptions = document["subscriptions"]
    year_over_year = document["year_over_year"]
    budget = document["budget"]
    data_health = document["data_health"]
    financial_independence = document["financial_independence"]
    financial_safety = document["financial_safety"]
    weekly_summary = document["weekly_summary"]
    merchants = document["merchants"]
    assert all(
        isinstance(section, Mapping)
        for section in (
            data,
            reporting,
            thresholds,
            income_savings,
            spending,
            subscriptions,
            year_over_year,
            budget,
            data_health,
            financial_independence,
            financial_safety,
            weekly_summary,
            merchants,
        )
    )

    mode = _string(data, "mode")
    if mode not in {"google_sheets", "demo"}:
        raise ConfigError("data.mode must be 'google_sheets' or 'demo'")
    pattern = _string(subscriptions, "detection_excluded_pattern")
    try:
        re.compile(pattern)
    except re.error as error:
        raise ConfigError(f"detection_excluded_pattern is not a valid regular expression: {error}") from error
    spending_lookback_months = _integer(financial_independence, "spending_lookback_months", 1, 120)
    if spending_lookback_months not in FI_SPENDING_LOOKBACK_OPTIONS:
        options = ", ".join(str(value) for value in FI_SPENDING_LOOKBACK_OPTIONS)
        raise ConfigError(f"spending_lookback_months must be one of: {options}")
    emergency_fund_spending_lookback_months = _integer(
        financial_safety,
        "emergency_fund_spending_lookback_months",
        1,
        120,
    )
    lookback_months = _integers(reporting, "lookback_months", 1, 120)
    if not 2 <= len(lookback_months) <= 5:
        raise ConfigError("lookback_months must contain between 2 and 5 values")
    default_lookback_months = _integer(reporting, "default_lookback_months", 1, 120)
    if default_lookback_months not in lookback_months:
        raise ConfigError("default_lookback_months must be included in lookback_months")

    return Settings(
        data=DataSettings(
            mode=mode,
            demo_directory=_demo_directory(data, project_root),
            demo_reference_date=_utc_datetime(data, "demo_reference_date"),
        ),
        reporting=ReportingSettings(
            lookback_months=lookback_months,
            default_lookback_months=default_lookback_months,
        ),
        thresholds=ThresholdSettings(
            expense=_integer(thresholds, "expense", 1_000, 100_000),
            income=_integer(thresholds, "income", 5_000, 100_000),
            duplicate_minimum=_number(thresholds, "duplicate_minimum", 0, 1_000),
            duplicate_days=_integer(thresholds, "duplicate_days", 0, 7),
        ),
        income_savings=IncomeSavingsSettings(
            default_view=_choice(income_savings, "default_view", {"regular", "actual"}),
            target_rate=_integer(income_savings, "target_rate", 0, 100),
            exclude_categories=_strings(income_savings, "exclude_categories"),
            exclude_groups=_strings(income_savings, "exclude_groups"),
        ),
        spending=SpendingSettings(
            default_view=_choice(spending, "default_view", {"all", "discretionary"}),
            exclude_categories=_strings(spending, "exclude_categories"),
            exclude_groups=_strings(spending, "exclude_groups"),
        ),
        subscriptions=SubscriptionSettings(
            known_category_terms=_strings(subscriptions, "known_category_terms"),
            minimum_confidence=_integer(subscriptions, "minimum_confidence", 70, 100),
            stale_after_days=_integer(subscriptions, "stale_after_days", 1, 365),
            default_exclude_categories=_strings(subscriptions, "default_exclude_categories"),
            detection_excluded_categories=_strings(subscriptions, "detection_excluded_categories"),
            detection_excluded_pattern=pattern,
        ),
        year_over_year=YearOverYearSettings(
            utility_group_terms=_strings(year_over_year, "utility_group_terms"),
            utility_category_terms=_strings(year_over_year, "utility_category_terms"),
        ),
        budget=BudgetSettings(history_months=_integer(budget, "history_months", 1, 120)),
        data_health=DataHealthSettings(
            stale_account_days=_integer(data_health, "stale_account_days", 1, 365),
            duplicate_require_same_account=_boolean(data_health, "duplicate_require_same_account"),
            duplicate_require_same_category=_boolean(data_health, "duplicate_require_same_category"),
            duplicate_require_same_description=_boolean(data_health, "duplicate_require_same_description"),
        ),
        financial_independence=FinancialIndependenceSettings(
            expected_return_rate=_number(financial_independence, "expected_return_rate", 0, 20),
            withdrawal_rate=_number(financial_independence, "withdrawal_rate", 0.5, 10),
            target_amount=_number(financial_independence, "target_amount", 1, 100_000_000),
            spending_lookback_months=spending_lookback_months,
            projection_years=_integer(financial_independence, "projection_years", 1, 100),
            included_account_patterns=_strings(financial_independence, "included_account_patterns"),
            included_groups=_strings(financial_independence, "included_groups"),
        ),
        financial_safety=FinancialSafetySettings(
            emergency_fund_target_months=_integer(financial_safety, "emergency_fund_target_months", 1, 24),
            emergency_fund_included_groups=_strings(financial_safety, "emergency_fund_included_groups"),
            emergency_fund_included_account_patterns=_strings(
                financial_safety,
                "emergency_fund_included_account_patterns",
            ),
            emergency_fund_spending_lookback_months=emergency_fund_spending_lookback_months,
            emergency_fund_exclude_categories=_strings(financial_safety, "emergency_fund_exclude_categories"),
            emergency_fund_exclude_groups=_strings(financial_safety, "emergency_fund_exclude_groups"),
            debt_included_groups=_strings(financial_safety, "debt_included_groups"),
            debt_included_account_patterns=_strings(financial_safety, "debt_included_account_patterns"),
            debt_baseline_date=_optional_date(financial_safety, "debt_baseline_date"),
        ),
        weekly_summary=WeeklySummarySettings(
            average_weeks=_integer(weekly_summary, "average_weeks", 1, 52),
            rolling_weeks=_integer(weekly_summary, "rolling_weeks", 1, 52),
            top_merchant_count=_integer(weekly_summary, "top_merchant_count", 1, 20),
        ),
        merchants=MerchantSettings(aliases=_merchant_aliases(merchants)),
    )


def load_settings(
    *,
    defaults_path: Path = DEFAULTS_PATH,
    local_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> Settings:
    """Load tracked defaults, an optional local file, and narrow environment overrides."""
    environment = os.environ if environ is None else environ
    document = _read_toml(defaults_path)

    configured_local = environment.get("PORTICO_CONFIG_PATH")
    configured_path = Path(configured_local) if configured_local else None
    if configured_path is not None and not configured_path.is_absolute():
        configured_path = project_root / configured_path
    selected_local = configured_path or local_path or project_root / "config" / "local.toml"
    if selected_local.exists():
        document = _merge(document, _read_toml(selected_local))
    elif configured_local:
        raise ConfigError("PORTICO_CONFIG_PATH does not exist")

    data_mode = environment.get("PORTICO_DATA_SOURCE")
    if data_mode:
        document = _merge(document, {"data": {"mode": data_mode}})
    return _build_settings(document, project_root)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return settings for the current process."""
    return load_settings()


def clear_settings_cache() -> None:
    """Clear the process settings cache for tests and explicit reloads."""
    get_settings.cache_clear()
